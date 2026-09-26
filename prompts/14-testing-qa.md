# P14 — Testing & QA Menyeluruh

> **Milestone:** M4 · **Bergantung:** P13 · **Estimasi:** 3 hari
> **Referensi:** PRD §8 (seluruh NFR), §12 (metrik kualitas), Lampiran D · PLAN §7

## Peran

Anda adalah QA lead yang membangun bukti kualitas rilis: fungsional, lintas browser, performa, dan keamanan.

## Konteks

Aplikasi dan image produksi siap. Test unit/integrasi backend dan sebagian E2E sudah ada.

## Tujuan

Menutup celah pengujian, mengukur NFR terhadap target PRD, dan menghasilkan laporan QA yang menjadi bukti gerbang G3.

## Tugas

### 1. E2E lintas browser (Playwright)

1. Konfigurasi proyek `chromium`, `firefox`, `webkit` + satu profil mobile (`Pixel 7` atau `iPhone 14`) untuk alur sentuh dasar.
2. Target: container produksi via `docker compose --profile dev up` (termasuk `pki-mock` untuk TSA/OCSP) — bukan server dev.
3. Skenario:
   | ID     | Skenario                                                                                                             |
   | ------ | -------------------------------------------------------------------------------------------------------------------- |
   | E2E-01 | Unggah → tanda tangan **Gambar** → default kanan atas → drag → Terapkan → unduh stamp                                |
   | E2E-02 | Tanda tangan **Teks** → resize rasio terkunci → keyboard geser → Terapkan → unduh                                    |
   | E2E-03 | **Gambar Tangan** (simulasi pointer) → Gunakan → Terapkan                                                            |
   | E2E-04 | PAdES **B-T** dengan p12 uji → unduh → verifikasi `VALID`, level B-T                                                 |
   | E2E-05 | PAdES **B-LT** → verifikasi `ltv_enabled`                                                                            |
   | E2E-06 | Penanda tangan kedua pada hasil E2E-04 → verifikasi 2 tanda tangan `VALID`                                           |
   | E2E-07 | Error: PDF terenkripsi, bukan PDF, > batas ukuran, passphrase salah, sertifikat kedaluwarsa                          |
   | E2E-08 | Dokumen bertanda tangan → banner → Stamp → modal 409                                                                 |
   | E2E-09 | Halaman berotasi 90° → default kanan atas tampilan → PAdES → tanda tangan tegak (bandingkan screenshot render hasil) |
   | E2E-10 | Mode `apikey`: tanpa key → modal; key salah → error; key benar → alur jalan                                          |
   | E2E-11 | Zoom 50% ↔ 200% tidak mengubah posisi pt                                                                             |
   | E2E-12 | Tidak ada request eksternal & tidak ada pelanggaran CSP di seluruh skenario                                          |
4. Aksesibilitas: `@axe-core/playwright` pada editor, dialog unduh, halaman verifikasi → 0 pelanggaran _serious/critical_.

### 2. Performa (`tests/perf/`)

1. Script **Locust** (atau k6) untuk: upload+inspect, stamp, PAdES B-B, PAdES B-T (mock TSA), verify — dengan dokumen `multipage-20.pdf`.
2. Jalankan terhadap container dengan batas `--cpus 2 --memory 2g`; ukur p50/p95/p99, throughput, error rate; uji konkurensi 20 sign paralel (NFR-PERF-07) dan perilaku `503 BUSY`.
3. Ukur memori idle & puncak (`docker stats`).
4. Tulis `docs/qa/perf-report.md`: tabel hasil vs target NFR-PERF-01…08, lingkungan uji, catatan bottleneck & rekomendasi.

### 3. Keamanan

1. `pip-audit` (dari `requirements.txt`), `npm audit --omit=dev`, `bandit`, Trivy image — 0 High/Critical yang _fixable_ (catat pengecualian dengan justifikasi).
2. **OWASP ZAP baseline** (`zaproxy/zap-stable zap-baseline.py`) terhadap container → 0 temuan High; tinjau Medium.
3. Uji negatif manual/otomatis: path traversal pada ID (`../`), ID acak tebakan → 404, upload PDF dengan JavaScript (`with-js.pdf`) tidak mengeksekusi skrip di viewer, SVG/HTML yang diganti ekstensi → ditolak, header `Host` palsu (bila `TTE_ALLOWED_HOSTS`), request besar tanpa `Content-Length` (chunked) dihentikan pada batas.
4. Uji fuzz ringan: 200 PDF termutasi acak (byte flip/truncate dari fixture) → tidak ada 500 dan worker pool tetap sehat (hypothesis atau script).
5. Tulis `docs/qa/security-report.md`.

### 4. Cakupan & gerbang

1. Tegakkan `--cov-fail-under` backend (75% total; 85% untuk `app/domain/coords.py`, `app/services/stamp_engine.py`, `app/services/pades_*.py` via laporan per-file) dan cakupan vitest modul logika ≥ 70%.
2. Tandai test lambat (`perf`, `crossval`, `e2e`) agar dapat dijalankan terpisah di CI.

### 5. Checklist QA manual (`docs/qa/manual-checklist.md`)

- Validasi PAdES di **Adobe Acrobat Reader** (Windows/macOS): menambahkan root uji ke _Trusted Certificates_, hasil B-B/B-T/B-LT/B-LTA, tampilan panel tanda tangan, klik appearance membuka detail.
- Validasi di validator lain yang tersedia (mis. Foxit, atau validator EU DSS demo **hanya dengan dokumen uji tanpa data pribadi**).
- Safari iOS/iPadOS & Chrome Android: gambar tangan, drag/resize sentuh, unduh berkas.
- Tampilan pada A4, F4, landscape, rotasi; cetak hasil ke PDF printer untuk memastikan stamp tercetak.
- Kolom hasil: Lulus/Gagal/Catatan/Penguji/Tanggal.

## Di Luar Lingkup

Perbaikan fitur besar (buat issue/TODO bila ditemukan bug besar dan laporkan), pentest pihak ketiga.

## Kriteria Selesai

- [ ] E2E-01…E2E-12 hijau di Chromium, Firefox, WebKit (profil mobile: E2E-01/03 minimal).
- [ ] axe: 0 pelanggaran serious/critical.
- [ ] `perf-report.md` menunjukkan target NFR-PERF tercapai (atau gap + rencana tindak lanjut).
- [ ] `security-report.md`: 0 High/Critical fixable, ZAP 0 High, fuzz tanpa 500.
- [ ] Gerbang cakupan aktif; `manual-checklist.md` siap diisi.

## Verifikasi

```bash
docker compose --profile dev up -d
cd frontend && npx playwright test
cd ../backend && uv run pytest --cov=app --cov-fail-under=75
uv run locust -f tests/perf/locustfile.py --headless -u 20 -r 5 -t 3m --host http://localhost:8080
docker run --rm --network host zaproxy/zap-stable zap-baseline.py -t http://localhost:8080 -I
```

## Penutup

- Centang item P14 di `docs/TODO.md`; tautkan laporan QA.
- Commit: `test: cross-browser e2e, performance and security qa reports (P14)`.
- Laporan sesuai format; daftar bug yang ditemukan beserta status perbaikan.
