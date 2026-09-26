# P09 — Frontend: Upload & Viewer PDF.js

> **Milestone:** M3 · **Bergantung:** P04 (API dokumen) · **Estimasi:** 2 hari
> **Referensi:** PRD FR-01, FR-02, §10.1, §10.2, §10.6, NFR-SEC-02 (CSP), NFR-PRIV-01, §8.4 · PLAN D-09

## Peran

Anda adalah senior frontend engineer (JavaScript vanilla, PDF.js) yang peduli performa, aksesibilitas, dan keamanan.

## Konteks

Skeleton Vite dari P01 ada. API `/api/v1/config` dan `/api/v1/documents` berfungsi. Belum ada UI fungsional.

## Tujuan

Pengguna dapat mengunggah PDF (drag-drop/pilih), melihat seluruh halaman dengan PDF.js (lazy, zoom, navigasi), dengan tata letak editor 3 kolom yang siap menerima panel tanda tangan dan overlay placement di P10.

## Tugas

### 1. Infrastruktur UI

1. `src/api/client.js`: wrapper `fetch` — base `/api/v1`, header `X-API-Key` dari `sessionStorage` bila ada (dipakai P12), `X-Request-ID` baru per request; parse `application/problem+json` menjadi `ApiError { status, code, title, detail, requestId, errors }`; timeout via `AbortController`. Fungsi `uploadWithProgress(url, formData, onProgress)` memakai `XMLHttpRequest` (progres unggah).
2. `src/state/store.js`: store observable kecil (`getState`, `setState(patch)`, `subscribe`) berisi `config`, `document`, `pages`, `zoom`, `currentPage`, `placements`, `assets`, `mode` (`edit|preview`), `result`.
3. `src/i18n/id.js` + helper `t(key, params)`; semua teks UI melalui kamus.
4. `src/ui/`: komponen kecil `toast` (dengan `aria-live="polite"`), `spinner`, `stepper` (① Unggah ② Tempatkan ③ Unduh), `banner`, `modal` (fokus terkunci, `Esc` menutup) — dipakai P10/P11.
5. `src/styles/`: layout grid 3 kolom (sidebar thumbnail 160 px — dapat disembunyikan, viewer fleksibel, panel kanan 320 px), footer aksi, responsif: < 768 px panel kanan menjadi _bottom sheet_, sidebar disembunyikan.

### 2. Uploader (`src/upload/uploader.js`)

1. Zona drop layar penuh saat tidak ada dokumen + tombol "Pilih PDF" (`<input type=file accept="application/pdf">`).
2. Validasi klien: ekstensi/MIME `.pdf`, ukuran ≤ `config.max_upload_mb`; pesan error sesuai kamus.
3. Unggah dengan progres (tampil untuk > 1 MB); tangani error API (`PDF_ENCRYPTED`, `PDF_CORRUPT`, `FILE_TOO_LARGE`, `TOO_MANY_PAGES`, `INVALID_FILE_TYPE`) dengan pesan jelas + `request_id` kecil untuk dukungan.
4. Mengunggah dokumen baru saat sudah ada dokumen → konfirmasi, lalu `DELETE` dokumen lama sebelum unggah.

### 3. Viewer (`src/viewer/pdfViewer.js`)

1. `pdfjs-dist`: `GlobalWorkerOptions.workerSrc = new URL('pdfjs-dist/build/pdf.worker.min.mjs', import.meta.url)` (di-_bundle_ lokal, tanpa CDN). `getDocument({ url: links.file, isEvalSupported: false, enableXfa: false, disableAutoFetch: false })`; **jangan** mengaktifkan scripting.
2. Untuk setiap halaman buat wrapper `.page` berukuran sesuai viewport (dari `page.getViewport({ scale })` — rotasi `/Rotate` diterapkan otomatis) berisi `<canvas>` dan `.overlay-layer` (absolut, untuk P10). Simpan `data-page-index` dan ukuran tampilan dalam pt (`viewport` pada scale 1 = pt).
3. Render **lazy** dengan `IntersectionObserver` (render halaman ±1 di sekitar viewport; bebaskan canvas halaman yang jauh untuk dokumen besar). Canvas memakai `devicePixelRatio` agar tajam.
4. Zoom: Fit lebar (default), Fit halaman, 50–200% (langkah 10%), `Ctrl/Cmd + scroll` opsional; pertahankan posisi baca saat zoom. Emit event `viewer:zoom` dengan faktor pt→px agar overlay P10 menyesuaikan.
5. Navigasi: "Hal. X / N", input lompat halaman, tombol berikut/sebelum, sinkron dengan scroll.
6. Should: sidebar thumbnail (render skala kecil, lazy), klik untuk lompat; penanda halaman yang punya placement (diisi P10).
7. Sediakan API modul: `loadDocument(meta)`, `getPageElement(index)`, `getPageDisplaySizePt(index)`, `scrollToPage(index)`, `setMode('edit'|'preview')`, `reload(url)`.

### 4. Kerangka panel kanan

Placeholder panel "Tanda Tangan" (diisi P10) dan footer dengan tombol **Terapkan Tanda Tangan** (disabled) serta info TTL "Dokumen dihapus otomatis dalam mm:ss" berdasarkan `expires_at`.

### 5. Test

- vitest: `client.js` (parsing Problem Details, timeout, header), `store.js`, validasi uploader, i18n (semua kunci yang dipakai ada).
- Playwright (awal): konfigurasi `frontend/playwright.config.js` yang menjalankan backend (`make dev-backend`) + `vite preview`; test: unggah `a4.pdf` → halaman tampil; unggah `encrypted.pdf` → pesan error; unggah `rot90.pdf` → halaman berorientasi lanskap. Jalankan minimal di Chromium untuk prompt ini.

## Di Luar Lingkup

Panel tanda tangan, overlay placement, dialog unduh, halaman verifikasi.

## Kriteria Selesai

- [ ] Unggah & render berfungsi untuk seluruh fixture valid; error ditampilkan untuk fixture invalid.
- [ ] Halaman pertama tampil ≤ 1,5 detik untuk `multipage-20.pdf` di mesin dev (ukur dengan `performance.now()` dan catat).
- [ ] Tidak ada request ke domain eksternal (cek tab Network / Playwright `page.on('request')`).
- [ ] Zoom tidak menggeser posisi baca; rotasi halaman sesuai Acrobat.
- [ ] `npm run lint && npm test && npm run build` hijau; Playwright Chromium hijau.

## Verifikasi

```bash
cd frontend && npm run lint && npm test && npm run build
npx playwright test --project=chromium
```

## Penutup

- Centang item P09 di `docs/TODO.md`.
- Commit: `feat(frontend): pdf upload and lazy pdf.js viewer (P09)`.
- Laporan sesuai format (sertakan hasil ukur waktu render).
