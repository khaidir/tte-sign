# P02 — Spike Kompatibilitas Alpine Linux (musl libc)

> **Milestone:** M0 → **Gerbang G1** · **Bergantung:** P01 · **Estimasi:** 1 hari
> **Referensi:** PRD FR-17, §9.3 (catatan Alpine), §9.5, R-01, R-02, R-03, A-10, A-11 · PLAN D-03, D-12, §9

## Peran

Anda adalah platform/DevOps engineer yang ahli container Alpine, musl libc, dan packaging Python native.

## Konteks

Fondasi repo dari P01 sudah ada. Belum ada Dockerfile. Temuan awal (PyPI, 26-09-2026):

- `pymupdf 1.28.2`: wheel **musllinux_1_2 hanya x86_64**; **tidak ada aarch64**. Lisensi **AGPL-3.0 atau komersial Artifex**.
- `pyhanko 0.37.0` (pure Python, butuh `cryptography>=48`, `lxml>=5.4`, `aiohttp`), `cryptography`, `lxml`, `pillow`, `pydantic-core`, `uvloop`, `httptools`, `aiohttp`, `uharfbuzz`, `python-pkcs11`: wheel musllinux tersedia untuk x86_64 & aarch64.
- Alpine terbaru: 3.24 (EOL 2028-06). Tag `python:3.13-alpine3.24` tersedia. Repo Alpine memiliki paket `py3-pymupdf` (x86_64 & aarch64) yang terikat Python sistem Alpine.

Tugas Anda **memverifikasi temuan ini secara empiris** — bukan hanya instalasi, melainkan eksekusi nyata.

## Tujuan

Membuktikan bahwa stamp (PyMuPDF), sign & validate PAdES (pyHanko), render raster, dan server FastAPI berjalan benar di `python:3.13-alpine3.24`, mengukur ukuran/startup, dan mendokumentasikan keputusan dalam ADR.

## Tugas

1. Buat `docker/spike/requirements-spike.txt` berisi: `pymupdf`, `pyhanko[image-support]`, `cryptography`, `pillow`, `lxml`, `aiohttp`, `fastapi`, `uvicorn[standard]`, `pydantic`, `fonttools`, `certomancer` (hanya untuk spike).
2. Buat `docker/spike/Dockerfile.spike` (multi-stage sederhana):
   - Stage `build`: `python:3.13-alpine3.24`, venv `/opt/venv`, `pip install --only-binary=:all: -r requirements-spike.txt`. **Jangan** menambah `build-base` di percobaan pertama; bila gagal, catat paket penyebab, lalu buat varian `Dockerfile.spike-src` yang membolehkan build dari source dan ukur durasinya.
   - Stage `runtime`: `python:3.13-alpine3.24` + `apk add --no-cache tini`, salin venv, jalankan `spike.py`.
3. Buat `docker/spike/spike.py` yang dalam satu proses:
   1. Membuat PDF 3 halaman dengan PyMuPDF (A4, halaman 2 `/Rotate 90`, halaman 3 CropBox ber-offset).
   2. Menempelkan PNG (dibuat dengan Pillow) ke halaman 1 & 2, simpan.
   3. Membuat PKI mini _in-memory_ (cryptography): root CA + sertifikat penanda tangan RSA-2048 (key usage `digitalSignature, nonRepudiation`), bungkus sebagai PKCS#12 (bytes, dengan passphrase), buka kembali dari bytes.
   4. Menandatangani PAdES B-B **visible** dengan pyHanko (`SigFieldSpec` + appearance bergambar), incremental.
   5. Memvalidasi tanda tangan dengan pyHanko menggunakan root tersebut sebagai trust root → `intact`, `valid`, `trusted` harus `True`.
   6. Merender halaman 1 ke PNG (PyMuPDF) dan memverifikasi ukuran piksel.
   7. Menjalankan FastAPI minimal via uvicorn (subprocess/thread) dan memanggil `/health` sekali.
   8. Mencetak JSON hasil: versi setiap paket, status setiap langkah, durasi (ms) per langkah, waktu `import fitz, pyhanko`.
4. Jalankan untuk **linux/amd64** dan coba **linux/arm64** (`docker buildx build --platform linux/arm64 ...` dengan QEMU). Untuk arm64, bila PyMuPDF gagal, uji dua opsi dan ukur: (a) build dari source di build stage (catat durasi & dependency apk yang dibutuhkan), (b) base `alpine:3.24` + `apk add python3 py3-pymupdf` + venv `--system-site-packages` untuk sisanya.
5. Ukur dan catat: ukuran image terkompresi (`docker save | gzip -c | wc -c`) & tidak terkompresi, ukuran `site-packages` per paket (top 10), `scanelf --needed` (paket `pax-utils` di stage terpisah) untuk menentukan library runtime yang benar-benar dibutuhkan, waktu start container sampai `/health` merespons.
6. Tulis `docs/adr/0001-alpine-native-deps.md` (format: Konteks, Opsi, Keputusan, Konsekuensi, Bukti) — keputusan base image, flag instalasi, paket apk runtime, strategi arm64 (rekomendasi + status _Proposed_ bila butuh G1).
7. Tulis `docs/adr/0002-pymupdf-license.md` berstatus **Proposed**: jelaskan kewajiban AGPL-3.0 untuk layanan jaringan, opsi (patuh AGPL / lisensi komersial Artifex / engine alternatif `pypdf` + stamp pyHanko + `pypdfium2` untuk raster), dampak ke kode (hanya `StampEngine` & render preview), dan rekomendasi. **Jangan memutuskan sendiri** — ini keputusan G1.
8. Pin versi yang terbukti bekerja ke `backend/pyproject.toml` (tambahkan dependency runtime: `pymupdf`, `pyhanko[image-support]`, `pyhanko-certvalidator`, `cryptography`, `pillow`, `fonttools`; dev: `certomancer`, `pyhanko-cli` bila CLI terpisah dari paket utama) lalu `uv lock`.
9. Simpan ringkasan hasil ke `docs/adr/0001-alpine-native-deps.md` bagian Bukti (tabel) — bukan file log mentah.

## Di Luar Lingkup

Dockerfile produksi (P13), fitur aplikasi, CI build image.

## Kriteria Selesai

- [ ] `spike.py` sukses di amd64: semua langkah `ok`, validasi PAdES `intact/valid/trusted = true`.
- [ ] Hasil arm64 terdokumentasi (sukses/gagal + opsi yang diuji + durasi/ukuran).
- [ ] Tabel ukuran image & startup tercatat; perkiraan terhadap target PRD (≤ 120 MB terkompresi, ≤ 5 dtk).
- [ ] Daftar paket apk runtime minimal berbasis `scanelf`.
- [ ] ADR-0001 & ADR-0002 ditulis; versi dependency ter-_pin_ dan `uv lock` sukses; `make test` tetap hijau.

## Verifikasi

```bash
docker buildx build --platform linux/amd64 -f docker/spike/Dockerfile.spike -t tte-spike:amd64 --load docker/spike
docker run --rm tte-spike:amd64
docker buildx build --platform linux/arm64 -f docker/spike/Dockerfile.spike -t tte-spike:arm64 --load docker/spike || true
docker image ls tte-spike
docker save tte-spike:amd64 | gzip -c | wc -c
cd backend && uv lock && uv sync && uv run pytest -q
```

## Penutup

- Centang item P02 di `docs/TODO.md`; tandai **G1 menunggu review** dan sebutkan keputusan yang dibutuhkan (lisensi PyMuPDF, arm64).
- Commit: `chore(spike): verify alpine musl compatibility and pin deps (P02)`.
- Laporan wajib menyertakan tabel hasil dan rekomendasi untuk G1. **Berhenti setelah prompt ini** sampai G1 disetujui.
