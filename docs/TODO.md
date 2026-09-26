# TODO — Pelacakan Implementasi MVP

> Perbarui file ini setiap selesai mengerjakan prompt. Format catatan: `— catatan: <deviasi/keputusan/tautan bukti>`.
> Status: ⬜ belum · 🟨 berjalan · ✅ selesai · ⛔ terblokir

## Status Ringkas

| Prompt | Judul                                 | Status | Commit | Catatan                               |
| ------ | ------------------------------------- | ------ | ------ | ------------------------------------- |
| P00    | PRD, PLAN, TODO, prompt               | ✅     | —      | Dokumen perencanaan dibuat 26-09-2026 |
| P01    | Scaffold monorepo & fondasi           | ✅     |        |                                       |
| P02    | Spike kompatibilitas Alpine           | ✅     |        | 9/9 steps lulus; ADR-0001 & ADR-0002 |
| P03    | PKI uji & fixture PDF                 | ✅     |        | 50/50 test lulus                      |
| P04    | Backend: dokumen                      | ⬜     |        |                                       |
| P05    | Backend: aset & koordinat             | ⬜     |        |                                       |
| P06    | Backend: stamp engine                 | ⬜     |        |                                       |
| P07    | Backend: PAdES sign                   | ⬜     |        |                                       |
| P08    | Backend: PAdES verify                 | ⬜     |        | Gerbang **G2** setelah ini            |
| P09    | Frontend: upload & viewer             | ⬜     |        |                                       |
| P10    | Frontend: tanda tangan & placement    | ⬜     |        |                                       |
| P11    | Frontend: terapkan, unduh, verifikasi | ⬜     |        |                                       |
| P12    | Keamanan, auth, audit                 | ⬜     |        |                                       |
| P13    | Docker image Alpine                   | ⬜     |        |                                       |
| P14    | Testing & QA                          | ⬜     |        |                                       |
| P15    | Dokumentasi API & CLI                 | ⬜     |        |                                       |
| P16    | CI/CD & kesiapan rilis                | ⬜     |        | Gerbang **G3** setelah ini            |
| P17    | Panduan unit test & assert            | ✅     | —      | Dokumen panduan tetap; PLAN §7a diperbarui |

---

## P01 — Scaffold monorepo & fondasi

- [x] `git init`, `.gitignore`, `.editorconfig`, `.dockerignore`, `Makefile`
- [x] Backend uv project (Python 3.13), struktur `app/` sesuai PLAN §3
- [x] `config.py` memuat seluruh variabel Lampiran B dengan default & validasi
- [x] Error RFC 9457 (`AppError`, handler validasi → `VALIDATION_ERROR`, 500 → `INTERNAL_ERROR`)
- [x] Logging JSON + middleware `X-Request-ID` (tanpa log body)
- [x] Audit logger hash-chain (sink stdout) + unit test
- [x] `GET /api/v1/health/live`, `/health/ready`, `/config`
- [x] Mount static frontend (`index.html`, `verify.html`) bila direktori ada
- [x] Frontend Vite skeleton + eslint/prettier/vitest + proxy dev
- [x] CI dasar (lint + test backend & frontend)
- — catatan: ErrorCode pakai `enum.StrEnum` (Python 3.13); `[dependency-groups]` uv 0.12.x; `ServerErrorMiddleware` re-raise exception → test pakai `raise_server_exceptions=False`; ruff S101/S104/S106 di-ignore di tests/

## P02 — Spike kompatibilitas Alpine

- [x] `docker/spike/Dockerfile.spike` + `spike.py` (stamp, sign B-B visible, validate, render)
- [x] Hasil amd64: instal `--only-binary=:all:` gagal untuk pyHanko (C++ extensions) → fallback source compile dengan `build-base`
- [x] Hasil arm64: build gagal karena PyMuPDF membutuhkan `libclang` untuk kompilasi source pada arm64. Solusi: deploy amd64 native atau emulasi QEMU.
- [x] Ukuran image: 97.4 MB content, 383 MB disk, 92 MB gzipped (amd64)
- [x] `docs/adr/0001-alpine-native-deps.md` (Accepted)
- [x] `docs/adr/0002-pymupdf-license.md` (Accepted)
- [x] Versi dependency ter-_pin_ di `backend/pyproject.toml`
- [ ] **G1 disetujui** — catat keputusan lisensi & arm64 di sini

## P03 — PKI uji & fixture PDF

- [x] Konfigurasi certomancer: root, intermediate, signer (valid/kedaluwarsa/belum berlaku/dicabut/tanpa key usage/ECDSA), TSA, OCSP, CRL
- [x] Ekspor p12 uji + `make pki`
- [x] Fixture pytest: server mock TSA/OCSP/CRL lokal
- [x] Generator PDF fixture (Lampiran D) + `make fixtures`
- [x] `dev/trust/` berisi root uji untuk pengembangan lokal
- — catatan: certomancer 0.14.x API (`Animator` + `AnimatorArchStore`); `pem.armor()` untuk ekspor PEM; `package_pkcs12(password=)`; raw PDF string manipulation untuk JS injection; Pillow decompression bomb diatasi dgn baca raw PNG header; 50/50 test lulus

## P04 — Backend: dokumen

- [ ] `Storage` (berkas + sidecar JSON, atomic write, owner, parent_id, kind, TTL)
- [ ] Janitor TTL + pembersihan saat start
- [ ] `WorkerPool` (process pool, timeout, `BUSY`, pemulihan pool rusak)
- [ ] `pdf_inspect` (halaman, rotasi, CropBox/MediaBox user space, enkripsi, tanda tangan, DocMDP)
- [ ] `POST/GET/DELETE /documents`, `/file`, `/download` + validasi & batas
- [ ] Audit event dokumen
- [ ] Test unit & integrasi

## P05 — Backend: aset & koordinat

- [ ] Sanitasi gambar (Pillow, batas piksel, EXIF, re-encode PNG)
- [ ] Aset gambar tangan (trim + padding)
- [ ] Render teks (3 font OFL + lisensi, cek glyph, ≥ 300 DPI)
- [ ] `coords.py` (display↔pdf, 4 rotasi, CropBox offset, default FR-07, validasi)
- [ ] `shared/test-vectors/coords.json` + test property-based
- [ ] `POST /assets`, `POST /assets/text`, `GET/DELETE /assets/{id}`

## P06 — Backend: stamp engine

- [ ] Antarmuka `StampEngine` + `PyMuPdfStampEngine` (atau varian alternatif sesuai G1)
- [ ] Aset tegak pada rotasi 0/90/180/270
- [ ] `POST /documents/{id}/stamp` → dokumen `stamped` + `placements_applied`
- [ ] `409 EXISTING_SIGNATURES` + incremental bila diizinkan
- [ ] Uji visual matriks posisi/orientasi (≤ 1 pt)
- [ ] Performa 20 halaman ≤ 2 detik

## P07 — Backend: PAdES sign

- [ ] `SignerProvider` + `Pkcs12Provider` (memori saja) + `ServerSignerProvider`
- [ ] Validasi sertifikat pra-sign (masa berlaku, key usage, rantai)
- [ ] Appearance widget dari aset (+ detail opsional), kompensasi rotasi
- [ ] Level B-B, B-T, B-LT (Must), B-LTA (Should)
- [ ] Invisible signature, `extra_stamps`, penanda tangan kedua
- [ ] `POST /documents/{id}/pades` + mapping error
- [ ] Test kebersihan log (passphrase/p12 tidak bocor)
- [ ] Validasi silang dengan `pyhanko-cli`

## P08 — Backend: PAdES verify

- [ ] `TrustStore` (dir + opsional sistem) + readiness check
- [ ] `pades_verifier` (integritas, coverage, modifikasi, trust, revocation, timestamp, level, indikasi ETSI)
- [ ] `POST /verify`, `GET /documents/{id}/signatures`
- [ ] Korpus uji 100% benar (valid, diubah, byte rusak, dicabut, untrusted, multi, tanpa tanda tangan)
- [ ] **G2 disetujui**

## P09 — Frontend: upload & viewer

- [ ] API client (Problem Details, API key, request-id)
- [ ] Store state sederhana + i18n `id`
- [ ] Uploader drag-drop + progres + validasi
- [ ] Viewer PDF.js (worker lokal, scripting off, lazy, zoom, navigasi)
- [ ] Layout 3 kolom + responsif

## P10 — Frontend: tanda tangan & placement

- [ ] Tab Gambar, Teks (preview server), Gambar Tangan (signature_pad)
- [ ] `coords.js` lolos test vector bersama
- [ ] Posisi default kanan atas halaman 1
- [ ] Drag & resize (Pointer Events), clamp, kunci rasio, keyboard, ARIA
- [ ] Panel properti (halaman, X/Y/W/H pt) dua arah

## P11 — Frontend: terapkan, unduh, verifikasi

- [ ] Terapkan → preview hasil + "Ubah penempatan"
- [ ] Banner & konfirmasi dokumen bertanda tangan (409)
- [ ] Dialog unduh Stamp/PAdES (p12/segel, level, alasan, lokasi, persetujuan)
- [ ] Ringkasan tanda tangan setelah unduh
- [ ] Halaman verifikasi + unduh laporan JSON
- [ ] Hitung mundur TTL + hapus dari server
- [ ] E2E happy path minimal

## P12 — Keamanan, auth, audit

- [ ] Mode auth `none`/`apikey` (+ `proxy` Should), berkas API key ber-hash, tool pembuat key
- [ ] Scope per endpoint + kepemilikan dokumen/aset
- [ ] Rate limit + `TOO_MANY_ATTEMPTS` passphrase
- [ ] Security headers/CSP (PDF.js tetap berfungsi), CORS, body limit
- [ ] Audit file sink persisten + `verify_audit`
- [ ] Pemberitahuan privasi di UI

## P13 — Docker image Alpine

- [ ] `docker/Dockerfile` multi-stage sesuai PRD §9.5 & ADR-0001
- [ ] `requirements.txt` dengan hash dari `uv export`
- [ ] `docker-compose.yml` dengan hardening & secret
- [ ] `scripts/image-check.sh` (ukuran ≤ 120 MB, readiness ≤ 5 dtk, read-only, non-root)
- [ ] `scripts/smoke.sh` (upload → stamp → pades → verify)
- [ ] Graceful shutdown (SIGTERM) teruji

## P14 — Testing & QA

- [ ] E2E Playwright 3 engine (stamp, PAdES, verify, error, keyboard)
- [ ] Uji performa + `docs/qa/perf-report.md`
- [ ] Scan keamanan (pip-audit, npm audit, bandit, Trivy, ZAP baseline)
- [ ] `docs/qa/manual-checklist.md` (Adobe Acrobat, Safari iOS)
- [ ] Gerbang coverage di CI

## P15 — Dokumentasi API & CLI

- [ ] OpenAPI lengkap (tag, contoh, error, security scheme) + `docs/api/openapi.json`
- [ ] `docs/API.md` (auth, koordinat, curl end-to-end, kode error)
- [ ] CLI `tte` (upload, stamp, sign, verify, download)
- [ ] `docs/api/tte.http`

## P16 — CI/CD & kesiapan rilis

- [ ] Pipeline lengkap (lint, test, build, scan, SBOM, size/startup, smoke, e2e, drift OpenAPI)
- [ ] Renovate/Dependabot
- [ ] `docs/DEPLOY.md`, `docs/RUNBOOK.md`, `SECURITY.md`, `CHANGELOG.md`
- [ ] `docs/RELEASE-CHECKLIST-1.0.0.md` (PRD §17 dengan bukti)
- [ ] **G3 disetujui**
