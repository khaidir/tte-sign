# ADR-0002: Lisensi PyMuPDF (AGPL-3.0)

**Status:** Accepted
**Date:** 2025-07-13
**Deciders:** Tech Lead

## Context

Aplikasi TTE menggunakan PyMuPDF untuk operasi PDF: membaca, memanipulasi, dan merender halaman. PyMuPDF dilisensikan di bawah **GNU Affero General Public License v3.0 (AGPL-3.0)**.

AGPL-3.0 mewajibkan:
1. Setiap pengguna yang berinteraksi dengan aplikasi melalui jaringan berhak menerima source code.
2. Setiap modifikasi harus didistribusikan dengan lisensi yang sama.
3. Linking dengan kode berlisensi AGPL mengharuskan seluruh aplikasi dirilis sebagai AGPL.

## Keputusan

**Tetap gunakan PyMuPDF dengan lisensi AGPL-3.0.**

Alasan:
1. TTE adalah aplikasi internal/terbatas — tidak didistribusikan secara komersial sebagai produk SaaS publik.
2. Jika di masa depan TTE perlu lisensi yang lebih permisif, opsi migrasi:
   - **pdf-lib (MIT)** — murni JavaScript, fitur terbatas (tidak ada rendering).
   - **pdfium (Apache 2.0)** — via `pypdfium2`, rendering kuat, tidak ada stamping.
   - **pyHanko (MIT)** — sudah digunakan untuk PAdES, bisa diperluas untuk operasi stamp sederhana.
   - **Kombo**: pdfium (render) + pyHanko (stamp/sign) — kedua MIT.
3. Biaya lisensi komersial PyMuPDF (perusahaan) belum diperlukan saat ini.

## Konsekuensi

### Positif
- Akses ke PyMuPDF yang matang, cepat, dan fitur-lengkap.
- Tidak ada biaya lisensi tambahan.

### Negatif
- Seluruh kode TTE otomatis berlisensi AGPL-3.0 (viral clause).
- Tidak bisa didistribusikan sebagai bagian dari produk proprietary tanpa membuka source.
- Jika ada klien yang keberatan dengan AGPL, perlu migrasi library.

## Mitigasi

1. **Abstraksi di belakang `StampEngine`** — semua operasi PyMuPDF dienkapsulasi di satu modul (`backend/app/services/stamp_engine.py`). Migrasi ke library lain hanya perlu menulis ulang satu file.
2. **Dokumentasi** — lisensi dicatat di `README.md` dan `NOTICE.txt`.
3. **Review berkala** — evaluasi opsi alternatif setiap rilis major.

## Referensi
- PyMuPDF license: https://pymupdf.readthedocs.io/en/latest/license.html
- AGPL-3.0: https://www.gnu.org/licenses/agpl-3.0.html
