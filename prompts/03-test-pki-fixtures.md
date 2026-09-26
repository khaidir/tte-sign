# P03 — PKI Uji, Mock TSA/OCSP/CRL, dan Fixture PDF

> **Milestone:** M0 · **Bergantung:** P01 (P02 untuk versi dependency) · **Estimasi:** 1 hari
> **Referensi:** PRD Lampiran D (matriks uji), FR-12–FR-15 · PLAN D-11, §7

## Peran

Anda adalah test engineer yang berpengalaman dengan PKI X.509, RFC 3161, OCSP/CRL, dan struktur PDF.

## Konteks

Backend sudah memiliki dependency ter-_pin_ (P02) termasuk `certomancer` (dev) dan PyMuPDF. Belum ada data uji.

## Tujuan

Menyediakan PKI uji yang reprodusibel, layanan mock TSA/OCSP/CRL untuk test, dan kumpulan PDF fixture yang mencakup matriks Lampiran D, semuanya dapat dibuat ulang dengan satu perintah.

## Tugas

### 1. PKI uji (certomancer)

1. `backend/tests/pki/certomancer.yml` — arsitektur `tte-test`, semua subjek diberi `O=UJI — TIDAK UNTUK PRODUKSI`:
   - `root` — "Root CA Indonesia (UJI)", RSA-4096, 20 tahun.
   - `psre-ca` — "PSrE Contoh CA (UJI)", diterbitkan `root`, dengan CRL distribution point & AIA OCSP.
   - Sertifikat penanda tangan (diterbitkan `psre-ca`): `signer-valid` (RSA-2048, KU `digitalSignature, nonRepudiation`, email), `signer-ecdsa` (P-256), `signer-expired` (sudah kedaluwarsa), `signer-notyet` (belum berlaku), `signer-revoked` (dicabut, tercatat di CRL & OCSP), `signer-nokeyusage` (KU hanya `keyEncipherment`), `server-seal` ("PT Contoh Indonesia (Segel)").
   - `tsa` — sertifikat TSA (EKU `timeStamping`, _critical_).
   - `ocsp` — responder OCSP untuk `psre-ca`.
   - Root terpisah `untrusted-root` + `signer-untrusted`.
   - Layanan: TSA, OCSP, CRL dengan URL `http://127.0.0.1:<port>/...` (port dari variabel lingkungan uji).
2. `backend/tests/pki/build_pki.py`: membangkitkan semua sertifikat ke `backend/tests/pki/out/` (gitignored): PEM sertifikat, `*.p12` dengan passphrase `uji-rahasia` (didefinisikan sebagai konstanta test, bukan secret), rantai lengkap, dan `trust/` berisi root uji.
3. `make pki` menjalankan `build_pki.py`. Script idempoten dan deterministik sebisa mungkin (seed/konfigurasi tetap).

### 2. Mock layanan untuk test

1. Fixture pytest `pki_services` (scope session) di `backend/tests/conftest.py`: menjalankan Animator certomancer (WSGI) di thread lokal pada port bebas, menyediakan URL TSA/OCSP/CRL, dan mematikannya di akhir sesi.
2. Pastikan pyHanko (yang memakai `aiohttp`/`requests`) dapat mengakses layanan ini: buat test `tests/integration/test_pki_services.py` yang (a) meminta timestamp RFC 3161 dan memvalidasinya, (b) meminta status OCSP `signer-valid` = good dan `signer-revoked` = revoked, (c) mengunduh CRL.
3. Fixture tambahan: `p12_bytes(name)`, `trust_dir`, `signer_cert(name)`.

### 3. Fixture PDF

1. `backend/tests/fixtures/make_fixtures.py` (PyMuPDF; tanpa berkas biner di git) menghasilkan ke `backend/tests/fixtures/out/`:
   | Berkas                                                            | Isi                                                                               |
   | ----------------------------------------------------------------- | --------------------------------------------------------------------------------- |
   | `a4.pdf`, `letter.pdf`, `legal.pdf`, `f4.pdf`, `a4-landscape.pdf` | 1 halaman, teks penanda tiap sudut                                                |
   | `rot90.pdf`, `rot180.pdf`, `rot270.pdf`                           | A4 dengan `/Rotate`                                                               |
   | `cropbox-offset.pdf`                                              | MediaBox A4, CropBox `[50, 60, 545, 780]`                                         |
   | `cropbox-offset-rot90.pdf`                                        | Gabungan CropBox offset + rotasi 90                                               |
   | `multipage-20.pdf`, `multipage-200.pdf`                           | Banyak halaman (performa & batas)                                                 |
   | `inherited-boxes.pdf`                                             | MediaBox/Rotate diwarisi dari node `/Pages`                                       |
   | `form-fields.pdf`                                                 | Berisi AcroForm text field                                                        |
   | `with-js.pdf`                                                     | Berisi OpenAction JavaScript (harus tidak dieksekusi)                             |
   | `encrypted.pdf`                                                   | User password (AES-256)                                                           |
   | `corrupt.pdf`                                                     | PDF terpotong di tengah                                                           |
   | `not-a-pdf.pdf`                                                   | Berkas PNG yang diganti ekstensinya                                               |
   | `pdf20.pdf`                                                       | Header PDF 2.0                                                                    |
   | `large-21mb.pdf`                                                  | > 20 MB (gambar noise tak terkompresi) — dibuat hanya bila diminta flag `--large` |
2. Gambar aset uji: `asset-red.png` (persegi merah solid 600×200 dengan kotak biru di pojok kiri-atas sebagai penanda orientasi), `asset-sig.png` (transparan), `asset.jpg` (dengan EXIF orientation=6), `bomb.png` (header dimensi sangat besar untuk uji decompression bomb).
3. `make fixtures` menjalankan generator. Fixture pytest `fixture_pdf(name)` mengembalikan path/bytes dan membangkitkan otomatis bila belum ada.
4. Dokumen bertanda tangan (single/multi/DocMDP) **tidak** dibuat di sini — dibuat di test P07/P08 memakai aplikasi.

### 4. Trust store pengembangan

`dev/trust/` berisi root uji (disalin oleh `make pki`) dan README singkat. `make dev-backend` memakai `TTE_TRUST_DIR=dev/trust`.

## Di Luar Lingkup

Kode aplikasi (endpoint, signer, verifier).

## Kriteria Selesai

- [ ] `make pki fixtures` dari keadaan bersih sukses dan idempoten.
- [ ] Test layanan mock (TSA, OCSP good/revoked, CRL) hijau.
- [ ] Semua fixture Lampiran D tersedia; test kecil memverifikasi properti setiap fixture (rotasi, CropBox, enkripsi, jumlah halaman).
- [ ] Tidak ada kunci/p12 yang ter-_commit_ (`git status` bersih setelah generate).

## Verifikasi

```bash
make pki fixtures
cd backend && uv run pytest tests/integration/test_pki_services.py tests/unit/test_fixtures.py -v
git status --porcelain   # tidak boleh ada berkas out/ yang ter-track
```

## Penutup

- Centang item P03 di `docs/TODO.md`.
- Commit: `test: add certomancer test PKI, mock TSA/OCSP and PDF fixtures (P03)`.
- Laporan sesuai format.
