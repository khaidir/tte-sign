# P16 — CI/CD & Kesiapan Rilis 1.0.0

> **Milestone:** M4 → **Gerbang G3** · **Bergantung:** P13, P14, P15 · **Estimasi:** 1,5 hari
> **Referensi:** PRD FR-17, NFR-SEC-08, NFR-HARD-05/06, §12, §17 (Checklist MVP) · PLAN §9 (G3), §11

## Peran

Anda adalah release engineer yang memastikan setiap rilis dapat dibangun ulang, diverifikasi, dan dioperasikan.

## Konteks

Fitur, image, QA, dan dokumentasi API selesai. CI saat ini hanya lint + test dasar (P01).

## Tujuan

Pipeline CI/CD lengkap yang menegakkan seluruh gerbang kualitas, dokumentasi operasional, dan laporan checklist MVP dengan bukti — siap untuk review G3.

## Tugas

### 1. Pipeline CI (`.github/workflows/ci.yml` + `release.yml`)

Job CI (setiap PR & push ke `main`):

1. `backend`: `uv sync --frozen`, ruff (lint+format check), bandit, mypy (modul inti), pytest (unit+integrasi) dengan gerbang cakupan, cek drift `requirements.txt` & `docs/api/openapi.json` & `shared/test-vectors/coords.json`, pip-audit.
2. `frontend`: `npm ci --ignore-scripts`, eslint, prettier check, vitest + cakupan, build, `npm audit --omit=dev --audit-level=high`.
3. `image`: Buildx (cache GHA), hadolint, build `linux/amd64` (+ `linux/arm64` sesuai ADR-0001), `scripts/image-check.sh` (ukuran & startup), Trivy (`--exit-code 1 --severity HIGH,CRITICAL --ignore-unfixed`), SBOM Syft (SPDX JSON) sebagai artefak.
4. `e2e`: compose `--profile dev` + Playwright (Chromium, Firefox, WebKit) + `scripts/smoke.sh`; unggah laporan Playwright sebagai artefak.
5. `crossval` (nightly/terjadwal): `pytest -m "crossval or perf"`.
   Job rilis (tag `v*.*.*`):
6. Build & push multi-arch ke registry (`ghcr.io/<org>/tte-pdf:<versi>` dan digest), lampirkan SBOM, **cosign sign** (keyless OIDC) — Should; buat GitHub Release dengan changelog.
7. Semua action di-_pin_ ke commit SHA; `permissions` minimal per job.

### 2. Pemeliharaan dependency

`renovate.json` (atau `.github/dependabot.yml`) untuk: base image digest (Docker), `uv.lock`, `package-lock.json`, GitHub Actions — dengan grouping & jadwal mingguan. Rebuild image terjadwal mingguan (NFR-HARD-05).

### 3. Dokumentasi operasional

1. `docs/DEPLOY.md`: prasyarat, `docker run` & compose dengan hardening, reverse proxy (contoh Nginx/Traefik dengan TLS, `client_max_body_size`, header forwarded, `TTE_FORWARDED_ALLOW_IPS`), konfigurasi env (tabel Lampiran B final), secret (API keys, server signer), trust store (Root CA Indonesia + CA PSrE: cara mendapatkan & memasang), TSA, mode air-gapped, sizing (CPU/RAM per beban), skala horizontal (batasan & opsi).
2. `docs/RUNBOOK.md`: health & metrik, membaca log/audit, `verify_audit`, rotasi API key, rotasi/penggantian server signer, pembaruan trust store, TSA/OCSP down, `503 BUSY`/tuning worker, disk `/data` penuh, prosedur insiden (dugaan kebocoran kunci/dokumen: cabut sertifikat di PSrE, rotasi, investigasi audit).
3. `SECURITY.md`: pelaporan kerentanan, model ancaman ringkas, kontrol yang diterapkan.
4. `CHANGELOG.md` (Keep a Changelog) untuk `1.0.0`.
5. Tinjau ulang teks legal di UI (label mode, disclaimer, persetujuan, privasi) terhadap PRD §11.4; kumpulkan dalam `docs/legal/ui-copy.md` untuk review Legal.

### 4. Laporan checklist MVP

1. `docs/RELEASE-CHECKLIST-1.0.0.md`: salin PRD §17; untuk setiap butir isi **status** dan **bukti** (tautan job CI/artefak, path laporan QA, perintah + ringkasan output). Butir yang belum terpenuhi → alasan + rencana + pemilik.
2. Rangkum juga pemenuhan FR Must (FR-01…FR-21) dan NFR utama dalam tabel.
3. Pastikan keputusan G1 (lisensi PyMuPDF, arm64) tercermin di dokumen rilis.

### 5. Finalisasi

- Versi aplikasi `1.0.0` di `pyproject.toml` & `package.json`; `GET /api/v1/config.version` sesuai.
- `docs/TODO.md` diperbarui penuh; tandai **G3 menunggu review**.

## Di Luar Lingkup

Deploy ke lingkungan produksi nyata, pembuatan tag rilis (dilakukan manusia setelah G3).

## Kriteria Selesai

- [ ] Workflow CI hijau di branch `main` (atau simulasi lokal dengan `act` bila repo belum di-_push_; catat).
- [ ] Workflow rilis tervalidasi (dry-run tanpa push).
- [ ] Dokumen DEPLOY, RUNBOOK, SECURITY, CHANGELOG, ui-copy lengkap.
- [ ] `RELEASE-CHECKLIST-1.0.0.md` berisi status + bukti untuk seluruh butir PRD §17.
- [ ] Tidak ada butir Must yang terbuka tanpa rencana dan persetujuan.

## Verifikasi

```bash
make lint test openapi requirements
make docker-build image-check
docker compose --profile dev up -d && make smoke BASE_URL=http://localhost:8080 && (cd frontend && npx playwright test) ; docker compose down
# opsional bila tersedia:
act -j backend -j frontend
```

## Penutup

- Centang item P16 di `docs/TODO.md`.
- Commit: `ci: full pipeline, release workflow and operational docs (P16)`.
- Laporan akhir MVP: ringkasan pencapaian vs PRD, daftar gap, risiko terbuka, dan permintaan review **G3**.
