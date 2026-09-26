# ADR-0001: Alpine Linux sebagai Base Image

**Status:** Accepted
**Date:** 2025-07-13
**Deciders:** Tech Lead

## Context

Aplikasi TTE (Tanda Tangan Elektronik) perlu di-deploy sebagai container Docker. Pilihan base image menentukan ukuran image, keamanan, kompatibilitas library, dan biaya infrastruktur.

Opsi yang dipertimbangkan:
1. **`python:3.13-slim`** (Debian-based) — ~120 MB, glibc, wheel universal.
2. **`python:3.13-alpine3.24`** (musl-based) — ~50 MB, ukuran final lebih kecil.
3. **`python:3.13`** (Debian full) — ~340 MB, banyak bloat.

## Keputusan

**Gunakan `python:3.13-alpine3.24` sebagai base image.**

Alasan:
- Ukuran image final ~97 MB (content) / ~383 MB (disk) vs ~200+ MB untuk slim.
- Semua dependency kritis (PyMuPDF 1.28.2, pyHanko 0.37.0, Pillow 12.3.0, cryptography 50.0.1, FastAPI 0.141.1, lxml 6.1.3, aiohttp 3.14.3, fonttools 4.66.0) terverifikasi kompatibel dengan musl (spike P02).
- Alpine memiliki track record keamanan yang baik dengan permukaan serang minimal.
- Multi-stage build memisahkan build-time deps (build-base, libffi-dev, dll.) dari runtime.

## Konsekuensi

### Positif
- Ukuran image lebih kecil → biaya penyimpanan dan transfer lebih rendah.
- Permukaan serang lebih kecil.
- Build lebih cepat setelah layer di-cache.

### Negatif
- **Hanya linux/amd64** — arm64 build gagal karena PyMuPDF membutuhkan `libclang` untuk kompilasi source pada arm64 (musl). Solusi: gunakan emulasi QEMU + `--platform linux/amd64` pada host arm64, atau deploy ke node amd64 native.
- Beberapa package (pyHanko, PyMuPDF) harus dikompilasi dari source karena wheel `musllinux` tidak tersedia untuk semua arsitektur.
- Build-time dependencies (build-base, libffi-dev, openssl-dev, dll.) menambah ~300 MB di stage build, tapi tidak terbawa ke runtime.

### Runtime packages (apk)
- `tini` — init system untuk sinyal handling.
- `libstdc++` — C++ standard library (dibutuhkan PyMuPDF/pyHanko).
- `libgcc` — GCC runtime (dibutuhkan PyMuPDF).

### Build-time packages (apk)
- `build-base`, `libffi-dev`, `openssl-dev`, `bzip2-dev`, `zlib-dev`, `xz-dev`, `readline-dev`, `sqlite-dev`, `jpeg-dev`, `freetype-dev`, `lcms2-dev`, `openjpeg-dev`, `tiff-dev`, `libxml2-dev`, `libxslt-dev`, `harfbuzz-dev`

## Referensi
- Hasil spike: `docker/spike/spike.py` — 9/9 steps lulus.
- Image size: 97.4 MB content, 383 MB disk (amd64), 92 MB gzipped.
