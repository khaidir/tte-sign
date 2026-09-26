# P10 — Frontend: Panel Tanda Tangan & Placement (Drag, Resize, Posisi Default)

> **Milestone:** M3 · **Bergantung:** P05 (API aset & test vector), P09 · **Estimasi:** 3 hari
> **Referensi:** PRD FR-03–FR-09, FR-22, §9.4, §10.2, §10.3, §10.6, NFR-A11Y-01, Lampiran C · PLAN D-06

## Peran

Anda adalah senior frontend engineer yang ahli interaksi pointer/touch, geometri, dan aksesibilitas.

## Konteks

Viewer dengan `.overlay-layer` per halaman dan store tersedia (P09). API aset tersedia (P05). `shared/test-vectors/coords.json` sudah ada.

## Tujuan

Pengguna membuat tanda tangan (Gambar/Teks/Gambar Tangan), tanda tangan muncul di **kanan atas halaman pertama**, lalu dapat digeser, di-resize, dipindah halaman, dan diatur presisi lewat panel properti — dengan posisi yang identik dengan perhitungan backend.

## Tugas

### 1. `src/coords.js` (port dari `coords.py`)

1. Fungsi: `displaySizePt(page)`, `ratioToDisplayPt(rect, page)`, `displayPtToRatio(rect, page)`, `defaultDisplayRect(page, aspect, margin=36)`, `clampRect(rect, page, minW=24, minH=12)`, `toApiPlacement(placement)` (rasio, 6 desimal, `origin:"top-left"`, `unit:"ratio"`).
2. vitest memuat `../shared/test-vectors/coords.json` (sesuaikan path/alias Vite) dan memastikan semua kasus display & default cocok (toleransi 0,01 pt). **Tidak boleh** ada implementasi koordinat lain di frontend.

### 2. Panel tanda tangan (`src/signature/`)

1. `panel.js`: tab **Gambar | Teks | Gambar Tangan** (role `tablist`, navigasi panah), tab terakhir diingat di `localStorage` (bungkus try/catch).
2. `imageTab.js`: drop zone PNG/JPG + pilih berkas; validasi klien (tipe, ≤ `config.max_image_mb`); unggah `POST /assets` `type=image`; preview dari `GET /assets/{id}`; tombol **Gunakan**.
3. `textTab.js`: field Nama (wajib), Jabatan, Baris tambahan; pilihan gaya (script/sans/serif), warna (hitam/biru tua/kustom), perataan; preview dari `POST /assets/text` dengan _debounce_ 400 ms (batalkan request sebelumnya dengan `AbortController`); tampilkan error `UNSUPPORTED_CHARACTERS` di field. **Gunakan** memakai aset terakhir.
4. `drawTab.js`: `signature_pad` pada canvas DPR-aware (resize tanpa kehilangan goresan: simpan `toData()` → `fromData()`), warna (hitam/biru), ketebalan 3 level, **Undo** (hapus goresan terakhir), **Bersihkan**; `touch-action: none` agar halaman tidak scroll; **Gunakan** nonaktif bila kosong; ekspor PNG → `POST /assets` `type=drawn`.
5. Setelah **Gunakan**: tambah placement (MVP: bila `config.max_placements = 1`, placement lama diganti setelah konfirmasi), posisi = `defaultDisplayRect(page 0, aspect)`, scroll ke halaman 1, fokus kotak, highlight ≤ 1 detik.

### 3. Overlay placement (`src/overlay/`)

1. `placementView.js`: elemen `div.placement` absolut di `.overlay-layer` halaman terkait; posisi dari rasio × ukuran halaman px (dihitung ulang saat `viewer:zoom`); menampilkan `<img>` aset (`draggable=false`), border putus-putus saat terpilih, 4 handle sudut (Must) + 4 handle sisi (Should), ukuran target sentuh ≥ 24 px.
2. `interactions.js` berbasis **Pointer Events**: `pointerdown` → `setPointerCapture`; drag memindah; resize dari handle; `requestAnimationFrame` untuk update; clamp di batas halaman; kunci rasio aspek aktif default (toggle di panel; Shift saat resize membalik sementara); ukuran min 24×12 pt; tooltip X/Y saat drag. Should: drag lintas halaman (lepas di halaman lain memindahkan placement, posisi disesuaikan & di-clamp).
3. Keyboard: kotak `tabindex=0`, `role="group"`, `aria-label` ("Tanda tangan di halaman 1, x 410, y 36 pt"); panah = 1 pt, Shift+panah = 10 pt, Alt+panah = resize 1 pt, `Delete/Backspace` hapus (dengan undo toast), `Esc` batal pilih. Pengumuman perubahan via `aria-live`.
4. Semua perubahan disimpan di store sebagai **rasio** (bukan px).

### 4. Panel properti (`src/signature/properties.js`)

Halaman (select 1..N), X, Y, W, H dalam pt (asal kiri-atas, 1 desimal), toggle **Kunci rasio**, tombol **Hapus**; sinkron dua arah dengan kotak; input di-clamp dan divalidasi; pindah halaman mempertahankan posisi relatif lalu clamp.

### 5. Integrasi viewer

- Tandai thumbnail halaman yang memiliki placement (✎) bila sidebar ada.
- Tombol **Terapkan Tanda Tangan** aktif bila ada ≥ 1 placement (aksinya diimplementasi P11).
- Mode `preview` menyembunyikan overlay dan menonaktifkan interaksi.

### 6. Test

- vitest: coords (test vector), clamp & aspect lock, reducer placement (tambah/geser/resize/hapus/pindah halaman), konversi keyboard step.
- Playwright (Chromium + WebKit): buat tanda tangan teks → kotak muncul kanan atas halaman 1 (assert posisi dalam pt dari panel properti = nilai default harapan untuk A4); drag dengan mouse (`page.mouse`) → nilai X/Y berubah & tetap dalam batas; resize dari handle sudut dengan rasio terkunci; operasi keyboard; zoom 50%/200% tidak mengubah nilai pt; halaman `rot90.pdf` default tetap di kanan atas tampilan; gambar tangan (simulasi goresan) → Gunakan aktif.

## Di Luar Lingkup

Pemanggilan `/stamp`/`/pades`, dialog unduh, halaman verifikasi, undo/redo penuh (FR-27, Could).

## Kriteria Selesai

- [ ] Ketiga tipe tanda tangan dapat dibuat dan dipakai.
- [ ] Posisi default kanan atas halaman 1 sesuai FR-07 (termasuk halaman berotasi).
- [ ] Drag/resize halus di mouse & touch (uji manual di perangkat sentuh atau emulasi), clamp & kunci rasio berfungsi, keyboard penuh.
- [ ] Semua test vector koordinat lolos di vitest.
- [ ] `npm run lint && npm test && npm run build` hijau; Playwright hijau di Chromium & WebKit.

## Verifikasi

```bash
cd frontend && npm run lint && npm test && npm run build
npx playwright test --project=chromium --project=webkit
```

## Penutup

- Centang item P10 di `docs/TODO.md`.
- Commit: `feat(frontend): signature panel and drag-resize placement overlay (P10)`.
- Laporan sesuai format.
