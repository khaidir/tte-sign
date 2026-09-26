# CLAUDE.md — Mini App TTE PDF

Aplikasi web untuk tanda tangan PDF: **Stamp** (visual) dan **PAdES** (tanda tangan digital bersertifikat), dengan REST API dan deployment Docker Alpine.

## Sumber kebenaran

| Dokumen           | Isi                                                                                                                           |
| ----------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| `docs/PRD.md`     | Requirement (FR/NFR), kontrak API (Lampiran A), env var (Lampiran B), rumus koordinat (Lampiran C), matriks uji (Lampiran D). |
| `docs/PLAN.md`    | Keputusan teknis (D-01…D-15), struktur repo, milestone, gerbang review.                                                       |
| `docs/TODO.md`    | Status pekerjaan per prompt. Perbarui setiap selesai.                                                                         |
| `prompts/NN-*.md` | Instruksi eksekusi bertahap. Kerjakan **hanya** lingkup prompt yang sedang dijalankan.                                        |
| `docs/adr/`       | Keputusan arsitektur. Buat ADR baru bila menyimpang dari PRD/PLAN.                                                            |

Bila PRD dan kode bertentangan, ikuti PRD dan laporkan. Bila PRD ambigu, pilih opsi paling aman, catat di laporan, dan lanjutkan.

## Stack

- Backend: Python 3.13, FastAPI, Uvicorn, Pydantic v2, pyHanko (PAdES), PyMuPDF (stamp/inspect/render, di balik `StampEngine`), Pillow, uv.
- Frontend: Vanilla JS (ES modules) + Vite, pdfjs-dist, signature_pad, Pointer Events native.
- Test: pytest, hypothesis, httpx, certomancer (PKI/TSA/OCSP uji), vitest, Playwright.
- Container: `python:3.13-alpine3.24` multi-stage, tini, non-root UID 10001.

## Perintah umum

```bash
make setup          # uv sync + npm ci
make dev-backend    # uvicorn di :8080 (reload)
make dev-frontend   # vite di :5173 (proxy /api -> :8080)
make lint           # ruff + eslint
make test           # pytest + vitest
make pki fixtures   # PKI uji & PDF fixture
make docker-build   # image produksi
make smoke          # smoke test ke container
```

## Aturan wajib

1. **Rahasia:** PKCS#12, passphrase, kunci privat, isi dokumen, dan gambar tanda tangan **tidak boleh** muncul di log, audit, pesan error, traceback, atau disk (kecuali dokumen/aset di `TTE_DATA_DIR`). Jangan pernah me-log body request.
2. **Koordinat:** semua konversi melalui `backend/app/domain/coords.py` dan `frontend/src/coords.js`; keduanya harus lolos `shared/test-vectors/coords.json`.
3. **PDF:** operasi PyMuPDF/pyHanko berjalan di worker pool (`services/worker_pool.py`), bukan di thread event loop. PAdES selalu incremental.
4. **Kontrak API:** ubah PRD Lampiran A dan ekspor OpenAPI pada commit yang sama. Error memakai RFC 9457 dengan `code` dari Lampiran A.4.
5. **Bahasa:** kode & komentar dalam bahasa Inggris; teks UI, `title`/`detail` error, dan dokumentasi dalam Bahasa Indonesia.
6. **Dependency:** tambah dependency hanya bila perlu; cek ketersediaan wheel musllinux (Alpine). Frontend tidak memakai CDN.
7. **Test:** setiap fitur disertai test; jangan menandai prompt selesai sebelum `make lint test` hijau.
8. **PKI uji** diberi label `UJI — TIDAK UNTUK PRODUKSI` dan tidak pernah dipakai di image produksi.

## Alur kerja per prompt

1. Baca prompt, bagian PRD/PLAN yang dirujuk, dan `docs/TODO.md`.
2. Implementasi → test → verifikasi sesuai bagian "Verifikasi" prompt.
3. Centang item di `docs/TODO.md` (tambahkan catatan deviasi bila ada).
4. Commit dengan Conventional Commits, menyebut ID prompt (mis. `feat(backend): pades sign (P07)`).
5. Laporkan: yang dikerjakan, bukti verifikasi, deviasi, pertanyaan terbuka.
