# P05 — Backend: Aset Tanda Tangan & Modul Koordinat

> **Milestone:** M1 · **Bergantung:** P04 · **Estimasi:** 1,5 hari
> **Referensi:** PRD FR-04, FR-05, FR-06, FR-07, §9.4, Lampiran A.2 (`AssetMeta`, `TextAssetRequest`, `Placement`), Lampiran C · PLAN D-05, D-06

## Peran

Anda adalah backend engineer yang teliti dalam geometri PDF dan pemrosesan gambar yang aman.

## Konteks

Endpoint dokumen, storage, dan worker pool sudah ada (P04). Fixture gambar uji tersedia (P03).

## Tujuan

(1) Menyediakan aset tanda tangan tersanitasi untuk tiga tipe (gambar, teks, gambar tangan) sebagai PNG RGBA; (2) menyediakan modul koordinat murni yang menjadi satu-satunya sumber kebenaran konversi display ↔ PDF, beserta test vector bersama untuk frontend.

## Tugas

### 1. Modul koordinat (`app/domain/coords.py`) — kerjakan pertama, test-first

1. Tipe: `PageGeometry(crop_box: tuple[float,float,float,float], rotation: int)` dengan properti `W`, `H`, `display_w`, `display_h`; `DisplayRect(x, y, w, h)` (pt, asal kiri-atas halaman tampilan); `PdfRect(x0, y0, x1, y1)` (user space).
2. Fungsi murni:
   - `ratio_to_display(rect_ratio, geom) -> DisplayRect`
   - `display_to_pdf(rect: DisplayRect, geom) -> PdfRect` — rumus tabel Lampiran C untuk R = 0/90/180/270.
   - `pdf_to_display(rect: PdfRect, geom) -> DisplayRect` (invers).
   - `resolve_placement(placement, geom) -> PdfRect` — menerima `unit=ratio|pt`, `origin=top-left|pdf`; validasi rasio ∈ [0,1], `x+w ≤ 1`, `y+h ≤ 1` (toleransi 0,001), minimum 24×12 pt → `PLACEMENT_OUT_OF_BOUNDS`; halaman di luar jangkauan → `INVALID_PAGE`.
   - `default_display_rect(geom, aspect, margin=TTE_DEFAULT_MARGIN_PT) -> DisplayRect` — aturan FR-07 persis (`w = clamp(0.25·Dw, 100, 200)`, batas tinggi 30%, `x = Dw − margin − w`, `y = margin`).
3. Test:
   - Tabel eksplisit untuk 4 rotasi × {CropBox = MediaBox, CropBox `[50,60,545,780]`}; contoh Lampiran C (A4, rasio 3 → `[410.46, 756.28, 559.28, 805.89]`) harus persis (toleransi 0,01).
   - Hypothesis: `pdf_to_display(display_to_pdf(r)) ≈ r` untuk semua rotasi dan CropBox acak; rect hasil selalu di dalam CropBox bila input valid.
4. **Test vector bersama:** script `backend/tests/unit/gen_coord_vectors.py` menulis `shared/test-vectors/coords.json` (≥ 40 kasus: input geometri + rect rasio/pt → rect display pt, rect PDF, dan kasus posisi default untuk beberapa aspek). Test pytest memuat berkas ini dan memastikan implementasi cocok. Berkas di-_commit_ (dipakai vitest di P10). Test gagal bila berkas usang terhadap generator.

### 2. Aset gambar & gambar tangan (`app/services/asset_service.py`, dijalankan di worker)

1. `sanitize_image(data: bytes, kind: Literal["image","drawn"]) -> dict`:
   - Validasi magic bytes PNG/JPEG; ukuran ≤ `TTE_MAX_IMAGE_MB` → `IMAGE_TOO_LARGE`.
   - `PIL.Image.MAX_IMAGE_PIXELS = 16_000_000`; `DecompressionBombWarning` diperlakukan sebagai error → `IMAGE_INVALID`; dimensi ≤ 4000×4000.
   - `Image.open` → `verify()` → buka ulang → `ImageOps.exif_transpose` → konversi `RGBA` → simpan PNG baru (tanpa metadata/EXIF/ICC teks), `optimize=True`.
   - `drawn`: trim ke bounding box piksel non-transparan + padding 4%; tolak bila kosong → `IMAGE_INVALID`.
   - Kembalikan bytes PNG, `width_px`, `height_px`, `aspect_ratio`, `sha256`.
2. Could (boleh dilewati): `remove_white_background` untuk JPG dengan ambang luminansi.

### 3. Aset teks (`app/services/text_renderer.py`)

1. Bundel 3 font berlisensi **SIL OFL** di `app/assets/fonts/` beserta berkas lisensinya: `script` (mis. _Dancing Script_ atau _Great Vibes_), `sans` (_Noto Sans_), `serif` (_Noto Serif_). Unduh dari repositori resmi Google Fonts (`github.com/google/fonts`, folder `ofl/`). Bila tidak ada akses jaringan, berhenti dan minta berkas font kepada pengguna.
2. `render_text(lines, font, color, align) -> PNG`: validasi (`lines` 1–4 baris, masing-masing ≤ 80 karakter, baris pertama wajib); cek setiap karakter tersedia di `cmap` font (fontTools) → bila tidak, `UNSUPPORTED_CHARACTERS` dengan daftar karakter; render dengan Pillow `ImageFont.truetype` pada ukuran dasar yang menghasilkan lebar ±1200 px (setara ≥ 300 DPI untuk lebar 200 pt), baris pertama lebih besar (1,0×) dan baris berikutnya 0,55×, spasi antarbaris 1,2; latar transparan; trim + padding 4%.
3. Warna: `#RRGGBB` tervalidasi; default `#0B1F4B`.

### 4. Endpoint (`app/api/v1/assets.py`)

1. `POST /api/v1/assets` (multipart `type=image|drawn`, `file`) → `201 AssetMeta`.
2. `POST /api/v1/assets/text` (JSON `TextAssetRequest`) → `201 AssetMeta`; simpan `text_lines` di metadata aset (untuk audit), bukan di log.
3. `GET /api/v1/assets/{id}` → `image/png`, `Cache-Control: no-store`.
4. `DELETE /api/v1/assets/{id}` → `204`.
5. Aset memiliki `owner` dan TTL sama dengan dokumen; audit `asset.created` (type, sha256, dimensi — tanpa isi gambar/teks).

### 5. Skema `Placement`

Tambahkan ke `app/domain/schemas.py` persis seperti Lampiran A.2 (`rect` opsional → posisi default). Tambahkan helper `resolve_placements(doc_meta, placements, assets) -> list[ResolvedPlacement(page, pdf_rect, display_rect, asset_id, rotation)]` yang juga memverifikasi aset ada dan milik pemanggil, serta jumlah placement ≤ `TTE_MAX_PLACEMENTS` → `TOO_MANY_PLACEMENTS`.

## Di Luar Lingkup

Penempelan aset ke PDF (P06), PAdES (P07), frontend.

## Kriteria Selesai

- [ ] `coords.py` 100% tercakup test; property-based test hijau; contoh Lampiran C persis.
- [ ] `shared/test-vectors/coords.json` ter-_commit_ dan sinkron dengan generator.
- [ ] Sanitasi gambar menolak bomb, format salah, ukuran besar; EXIF orientasi diterapkan lalu dibuang (cek dengan Pillow: tidak ada `exif` di output).
- [ ] Render teks 3 font, diakritik (mis. "Ç, é, ñ, ö") benar, karakter tak didukung (mis. emoji) → 422.
- [ ] Endpoint aset sesuai kontrak; `make lint test` hijau.

## Verifikasi

```bash
make lint test
cd backend && uv run pytest tests/unit/test_coords.py tests/unit/test_asset_service.py tests/integration/test_assets.py -v
uv run python tests/unit/gen_coord_vectors.py --check
curl -s -H 'Content-Type: application/json' -d '{"lines":["Budi Santoso","Kepala Divisi"],"font":"script"}' localhost:8080/api/v1/assets/text
```

## Penutup

- Centang item P05 di `docs/TODO.md`.
- Commit: `feat(backend): signature assets, text renderer and coordinate module (P05)`.
- Laporan sesuai format (sertakan nama font & lisensi yang dipakai).
