# P04 — Backend: Manajemen Dokumen, Storage TTL, Worker Pool, Inspeksi PDF

> **Milestone:** M1 · **Bergantung:** P01, P03 (dan G1 disetujui) · **Estimasi:** 1,5 hari
> **Referensi:** PRD FR-01, FR-19 (deteksi), FR-20, NFR-SEC-04/05/07, NFR-PERF-01, Lampiran A.2 (`DocumentMeta`), A.4 · PLAN D-07, D-08

## Peran

Anda adalah senior backend engineer Python yang fokus pada keamanan pemrosesan berkas dan ketahanan layanan.

## Konteks

Fondasi (config, error, audit, health) sudah ada. PKI & fixture tersedia. Keputusan G1 sudah dicatat di `docs/TODO.md` — ikuti keputusan engine (PyMuPDF atau alternatif) untuk inspeksi.

## Tujuan

Menyediakan endpoint dokumen yang aman dan cepat: upload tervalidasi, inspeksi di proses terisolasi, penyimpanan sementara dengan TTL, serta unduh dan hapus.

## Tugas

### 1. Worker pool (`app/services/worker_pool.py`)

1. `WorkerPool` membungkus `concurrent.futures.ProcessPoolExecutor` dengan `mp_context=multiprocessing.get_context("forkserver")`, `max_workers=TTE_PDF_WORKERS`.
2. `async run(fn, *args, timeout=TTE_JOB_TIMEOUT_SECONDS)`: `loop.run_in_executor` + `asyncio.wait_for`. Batas antrean (`max_workers * 4`); bila penuh → `AppError(BUSY)` dengan header `Retry-After: 2`.
3. Timeout → `AppError(JOB_TIMEOUT)` **dan** pool di-_recycle_ (hentikan proses worker yang macet, buat pool baru). `BrokenProcessPool` → recycle + `INTERNAL_ERROR`.
4. Fungsi job harus _top-level_ dan menerima/mengembalikan tipe yang dapat di-_pickle_ (bytes, dict). Worker mengatur batas memori (`resource.setrlimit(RLIMIT_AS)` bila tersedia; nilai dari `TTE_WORKER_MEMORY_MB`, default 768) pada inisialisasi.
5. Lifecycle via lifespan FastAPI; registrasi readiness check `worker_pool`.

### 2. Storage (`app/services/storage.py`)

1. Protokol `Storage` + implementasi `FileStorage(TTE_DATA_DIR)`: `put_document(bytes, meta) -> DocumentRecord`, `get_document(id, owner)`, `read_bytes(id, owner)`, `delete_document(id, owner, cascade=True)`, `put_asset(...)`, `get_asset(...)`, `list_expired(now)`.
2. Tata letak: `documents/<id>.pdf` + `documents/<id>.json`, `assets/<id>.png` + `.json`. Penulisan atomik (tulis ke `*.tmp` lalu `os.replace`), permission `0o600`.
3. Metadata: `id`, `parent_id`, `kind` (`original|stamped|signed`), `owner` (string; default `anonymous`, dipakai P12), `filename` (sanitasi: basename, hanya karakter aman, ≤ 120 karakter, ekstensi `.pdf`), `size_bytes`, `sha256`, `page_count`, `pages[]`, `pdf_version`, `has_signatures`, `signature_count`, `docmdp` (null atau level), `created_at`, `expires_at`, `children[]`, `asset_ids[]`.
4. Akses dengan `owner` berbeda atau dokumen kedaluwarsa → `DOCUMENT_NOT_FOUND` (respons seragam).
5. `delete_document(cascade=True)` menghapus turunan (`children`) secara rekursif; aset hanya dihapus bila tidak dipakai dokumen lain.

### 3. Janitor (`app/services/janitor.py`)

Task asyncio tiap 60 detik: hapus dokumen/aset kedaluwarsa, emit audit `document.expired`. Saat startup: hapus berkas `*.tmp` dan yang kedaluwarsa. Hentikan rapi saat shutdown.

### 4. Inspeksi PDF (`app/services/pdf_inspect.py`, dijalankan di worker)

1. `inspect_pdf(data: bytes, max_pages: int) -> dict`: validasi magic bytes `%PDF-` di 1024 byte pertama; buka dengan PyMuPDF dari memori; tolak `needs_pass` → `PDF_ENCRYPTED`; gagal parse / `is_repaired` dengan kerusakan berat → `PDF_CORRUPT`; `page_count > max_pages` → `TOO_MANY_PAGES`.
2. Per halaman: `width_pt`, `height_pt` (ukuran CropBox **sebelum** rotasi), `rotation` (dinormalisasi ke 0/90/180/270), `crop_box` dan `media_box` dalam **PDF user space (asal kiri-bawah)** termasuk nilai yang **diwarisi** dari node `/Pages`. Verifikasi konvensi koordinat PyMuPDF (`page.cropbox`, `page.mediabox`, `page.rotation`) terhadap fixture `cropbox-offset.pdf` & `inherited-boxes.pdf`; bila perlu baca nilai mentah dari objek PDF.
3. Tanda tangan: hitung signature field yang memiliki `/V` (pakai `pyhanko.pdf_utils.reader.PdfFileReader(...).embedded_signatures`), deteksi DocMDP (certification signature + level P).
4. Kembalikan juga `pdf_version`.

### 5. Endpoint (`app/api/v1/documents.py`)

1. `POST /api/v1/documents` (multipart `file`): tolak `Content-Length` > batas sebelum membaca; baca stream per chunk dan hentikan bila melebihi `TTE_MAX_UPLOAD_MB` → `413 FILE_TOO_LARGE`; MIME/ekstensi salah → `400 INVALID_FILE_TYPE`; inspeksi via worker; simpan; `201 DocumentMeta` (Lampiran A.2) + header `Location`.
2. `GET /api/v1/documents/{id}` → `DocumentMeta`.
3. `GET /api/v1/documents/{id}/file` → `application/pdf` inline, `Cache-Control: no-store`, `Content-Disposition: inline`, dukung `Range` bila mudah (Should; PDF.js dapat memakai range request).
4. `GET /api/v1/documents/{id}/download` → attachment dengan `filename*=UTF-8''<nama>_<kind>.pdf` (tanpa sufiks untuk `original`); emit audit `document.downloaded`; bila `TTE_DELETE_AFTER_DOWNLOAD=true` dan `kind != original`, hapus setelah respons terkirim (background task).
5. `DELETE /api/v1/documents/{id}` → `204`, cascade, audit `document.deleted`.
6. Skema Pydantic di `app/domain/schemas.py` sesuai Lampiran A.2 (nama field persis).
7. Audit `document.uploaded` dengan `document_id`, `sha256`, `size_bytes`, `page_count`, `actor`, `ip`, `user_agent` — **tanpa** nama berkas asli (hanya hash nama bila perlu).

### 6. Test

- Unit: sanitasi nama berkas, storage (atomic, TTL, owner, cascade), worker pool (timeout me-_recycle_ pool; `BUSY` saat antrean penuh; job crash).
- Integrasi (httpx `AsyncClient`): upload semua fixture Lampiran D → hasil sesuai (rotasi, CropBox user space, enkripsi 422, corrupt 422, not-a-pdf 400, >20MB 413, 200 halaman OK, 201 halaman 422 dengan `TTE_MAX_PAGES` diturunkan), GET file/download header, DELETE cascade, TTL kedaluwarsa → 404, janitor menghapus berkas.
- Performa: upload + inspect `multipage-20.pdf` < 1,5 detik (tandai `@pytest.mark.perf`).

## Di Luar Lingkup

Aset, stamp, PAdES, autentikasi API key (owner tetap `anonymous`), preview raster (FR-24, Should — boleh dibuat bila waktu memungkinkan dengan endpoint `GET /documents/{id}/pages/{n}/preview`, `scale` ≤ 3).

## Kriteria Selesai

- [ ] Semua endpoint dokumen sesuai PRD §7.2 & Lampiran A (nama field, status code, kode error).
- [ ] Inspeksi berjalan di worker pool; timeout & crash tertangani tanpa menjatuhkan API.
- [ ] CropBox/MediaBox dilaporkan dalam PDF user space, termasuk atribut warisan.
- [ ] TTL, janitor, cascade delete teruji.
- [ ] `make lint test` hijau.

## Verifikasi

```bash
make lint test
cd backend && uv run pytest tests/integration/test_documents.py -v
# manual
curl -s -F "file=@backend/tests/fixtures/out/rot90.pdf" localhost:8080/api/v1/documents | python -m json.tool
```

## Penutup

- Centang item P04 di `docs/TODO.md`.
- Commit: `feat(backend): document upload, inspection, ttl storage and worker pool (P04)`.
- Laporan sesuai format (sebutkan konvensi koordinat PyMuPDF yang ditemukan).
