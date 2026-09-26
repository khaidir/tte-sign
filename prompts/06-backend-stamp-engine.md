# P06 — Backend: Stamp Engine & Endpoint Stamp

> **Milestone:** M1 · **Bergantung:** P05 · **Estimasi:** 2 hari
> **Referensi:** PRD FR-10, FR-19, FR-22, NFR-PERF-03, §9.4, Lampiran A.2 (`StampRequest`), Lampiran C, D · PLAN D-03, D-06, §7 (uji visual)

## Peran

Anda adalah backend engineer spesialis manipulasi PDF yang memastikan hasil akurat hingga ukuran point.

## Konteks

`coords.py` dan aset PNG tersedia (P05). Keputusan G1 menentukan engine:

- **Default:** `PyMuPdfStampEngine`.
- **Varian (bila G1 menolak AGPL):** `PypdfStampEngine` — buat overlay satu halaman berisi gambar (mis. dengan pyHanko `pdf_utils` / content stream manual) dan gabungkan dengan `pypdf` (`page.merge_transformed_page`), render uji memakai `pypdfium2`.

## Tujuan

Menempelkan aset ke halaman PDF pada posisi yang **identik** dengan preview (≤ 1 pt) dan tampak tegak di semua rotasi, lalu menghasilkan dokumen turunan `stamped` melalui API.

## Tugas

### 1. Antarmuka (`app/services/stamp_engine.py`)

```python
class StampEngine(Protocol):
    def apply(self, pdf: bytes, placements: list[ResolvedPlacementJob], *, incremental: bool) -> bytes: ...
```

`ResolvedPlacementJob` = data _picklable_: `page`, `pdf_rect` (user space), `rotation`, `png_bytes`. Engine dipilih via `TTE_STAMP_ENGINE` (`pymupdf` default). Fungsi job top-level untuk worker pool.

### 2. `PyMuPdfStampEngine`

1. Konversi `pdf_rect` (user space, asal kiri-bawah) ke sistem koordinat PyMuPDF. Pelajari konvensi PyMuPDF (koordinat _unrotated_, sumbu Y ke bawah, relatif MediaBox; gunakan `page.transformation_matrix` / `page.rotation_matrix` sesuai dokumentasi versi terpasang). **Buktikan dengan test**, jangan berasumsi.
2. Tempel dengan `page.insert_image(rect, stream=png, keep_proportion=False, overlay=True, rotate=...)` sehingga aset tampil **tegak** pada tampilan halaman berotasi.
3. Simpan: non-incremental → `doc.tobytes(garbage=1, deflate=True)` (tanpa menghapus objek yang diperlukan); incremental (dokumen bertanda tangan & diizinkan) → simpan ke berkas sementara di `TTE_DATA_DIR/tmp/` lalu `saveIncr()`, baca bytes, hapus berkas sementara di `finally`.
4. Jangan menyentuh halaman lain, anotasi, tautan, atau form field.

### 3. Endpoint `POST /api/v1/documents/{id}/stamp`

1. Body `StampRequest` (Lampiran A.2). Placement tanpa `rect` → posisi default FR-07.
2. Dokumen `has_signatures=true`: tanpa `options.allow_existing_signatures=true` → `409 EXISTING_SIGNATURES` (detail menjelaskan risiko); dengan flag → incremental + `warnings: ["EXISTING_SIGNATURES_MAY_BE_INVALIDATED"]`. Dokumen DocMDP P=1 → `409 DOCMDP_LOCKED`.
3. Jalankan engine di worker pool; inspeksi ulang hasil; simpan sebagai dokumen baru `kind=stamped`, `parent_id=id`; tambahkan ke `children` induk.
4. Respons `201`: `DocumentMeta` + `placements_applied[{page, pdf_rect}]` + `warnings[]`.
5. Audit `stamp.applied`: `document_id` (induk & hasil), `sha256_before`, `sha256_after`, `placements` (page + pdf_rect + asset sha256), `actor`.

### 4. Uji visual posisi & orientasi (`tests/visual/test_stamp_positions.py`)

1. Untuk setiap fixture di matriks {A4, Letter, F4, A4-landscape} × {rot0, rot90, rot180, rot270} × {CropBox normal, CropBox offset}: stamp `asset-red.png` pada 3 posisi (default kanan atas, tengah, kiri bawah dalam rasio).
2. Render halaman hasil pada 144 DPI (render mengikuti rotasi tampilan), cari bounding box piksel merah → konversi ke pt tampilan → bandingkan dengan `DisplayRect` yang diharapkan: **toleransi ≤ 1 pt**.
3. Orientasi: kotak biru penanda harus berada di pojok **kiri-atas** bounding box pada tampilan (membuktikan aset tegak).
4. Pastikan teks asli halaman masih dapat diekstrak (konten tidak rusak).

### 5. Test lain

- `409` untuk dokumen bertanda tangan (buat dokumen bertanda tangan sederhana memakai pyHanko + p12 uji langsung di test).
- Placement di luar batas → 422; halaman invalid → 422; aset milik orang lain/tidak ada → 404 `ASSET_NOT_FOUND`.
- Performa: 20 halaman, 1 placement < 2 detik (`@pytest.mark.perf`).
- Hasil stamp dapat di-_stamp_ lagi (turunan dari turunan).

## Di Luar Lingkup

PAdES, multi-placement > `TTE_MAX_PLACEMENTS` (tetap dibatasi config; logika mendukung banyak placement), preview raster.

## Kriteria Selesai

- [ ] Matriks uji visual hijau (≤ 1 pt, orientasi benar) untuk semua kombinasi.
- [ ] `StampEngine` terisolasi; hanya modul ini yang mengimpor PyMuPDF untuk stamp.
- [ ] Endpoint sesuai kontrak (201/404/409/422) dan audit tercatat.
- [ ] `make lint test` hijau.

## Verifikasi

```bash
make lint test
cd backend && uv run pytest tests/visual -v
uv run pytest -m perf -v
```

## Penutup

- Centang item P06 di `docs/TODO.md` (sebutkan engine yang dipakai).
- Commit: `feat(backend): stamp engine with rotation-aware placement (P06)`.
- Laporan sesuai format, sertakan tabel ringkas hasil uji visual (deviasi maksimum per rotasi).
