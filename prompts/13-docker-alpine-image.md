# P13 — Docker Image Produksi Berbasis Alpine

> **Milestone:** M4 · **Bergantung:** P02 (ADR-0001), P12 · **Estimasi:** 1,5 hari
> **Referensi:** PRD FR-17, NFR-OPS-01…04, NFR-HARD-01…07, §9.5, Lampiran B · PLAN D-10, D-12 · `docs/adr/0001-alpine-native-deps.md`

## Peran

Anda adalah platform engineer yang membangun image container minimal, aman, dan reprodusibel.

## Konteks

Aplikasi lengkap dan teruji secara lokal. ADR-0001 memuat keputusan base image, paket apk runtime, dan strategi arm64. Spike Dockerfile ada di `docker/spike/` (referensi, jangan dipakai untuk produksi).

## Tujuan

Menghasilkan satu image `tte-pdf` multi-stage berbasis Alpine yang memenuhi target ukuran (≤ 120 MB terkompresi), startup (≤ 5 dtk), dan hardening, beserta compose dan script pemeriksaan otomatis.

## Tugas

### 1. Dependency terkunci

1. `backend/requirements.txt` dari `uv export --no-dev --frozen --format requirements-txt` (dengan hash). Tambahkan target `make requirements` dan cek drift di CI (P16).
2. Pastikan semua paket runtime memiliki wheel musllinux untuk arsitektur target (sesuai ADR-0001); tidak ada dependency dev di image.

### 2. `docker/Dockerfile` (multi-stage, mengikuti PRD §9.5)

1. `ARG PYTHON_VERSION=3.13`, `ARG ALPINE_VERSION=3.24`, `ARG NODE_VERSION=24`; **pin base dengan digest** (`FROM python:3.13-alpine3.24@sha256:...`) — dapatkan digest via `docker buildx imagetools inspect`.
2. Stage `frontend-build`: `npm ci --ignore-scripts`, `npm run build`.
3. Stage `python-build`: venv `/opt/venv`, `pip install --require-hashes --only-binary=:all: -r requirements.txt` (sesuaikan bila ADR-0001 mengizinkan build dari source untuk paket tertentu), salin `backend/app`, `python -m compileall`, hapus `tests/`, `__pycache__` yang tidak perlu (pertahankan `.pyc` hasil compile), pip dari venv.
4. Stage `runtime`: `apk upgrade --no-cache`, `apk add --no-cache tini ca-certificates` + paket runtime dari hasil `scanelf` (ADR-0001); user `tte` 10001:10001 tanpa shell login; hapus pip sistem; salin venv, app, `frontend/dist` → `/opt/app/app/static`, font; direktori `/data` (milik 10001) & `/etc/tte/trust` (read-only); `ENV` non-rahasia saja; `USER 10001:10001`; `EXPOSE 8080`; `HEALTHCHECK` berbasis Python urllib; `ENTRYPOINT ["/sbin/tini","--"]`; `CMD ["python","-m","app"]`.
5. Label OCI (`title`, `description`, `version` via `ARG VERSION`, `revision` via `ARG GIT_SHA`, `created`, `source`, `licenses`).
6. `.dockerignore` ketat: `.git`, `**/node_modules`, `**/.venv`, `**/tests`, `docs`, `prompts`, `backend/tests/pki/out`, `*.p12`, `*.pfx`, `.env*`, `dev/`.
7. `app/__main__.py`: dukung `TTE_FORWARDED_ALLOW_IPS` (default `127.0.0.1`) untuk `proxy_headers`; graceful shutdown (`timeout_graceful_shutdown=20`), hentikan worker pool & janitor dengan rapi.
8. Pastikan multiprocessing `forkserver` berjalan dengan `--read-only` (socket/semaphore di `/tmp` atau `/dev/shm`; tmpfs `/tmp` disediakan).

### 3. `docker-compose.yml` (root)

Service `tte` dengan: `read_only: true`, `tmpfs` (`/tmp:noexec,nosuid,size=64m`, `/data:noexec,nosuid,size=512m,uid=10001,gid=10001`), `cap_drop: [ALL]`, `security_opt: [no-new-privileges:true]`, `pids_limit: 256`, `mem_limit: 1g`, `cpus: 2`, `healthcheck`, volume `./deploy/trust:/etc/tte/trust:ro`, secrets (`tte_api_keys`, `tte_server_signer_p12`, `tte_server_signer_passphrase`) dipetakan ke `TTE_*_FILE`, env contoh (`TTE_AUTH_MODE=apikey`, `TTE_TSA_URL`, `TTE_AUDIT_FILE=/data/audit/audit.jsonl` — catat bahwa di produksi audit sebaiknya ke volume persisten terpisah). Profil `dev` opsional: service `pki-mock` (certomancer Animator) untuk TSA/OCSP uji — **hanya** untuk pengembangan/E2E.

### 4. Script pemeriksaan

1. `scripts/image-check.sh`:
   - Build image (`docker buildx build --load`).
   - Ukuran: tidak terkompresi (`docker image inspect -f '{{.Size}}'`) ≤ 300 MB; terkompresi (`docker save | gzip -c | wc -c`) ≤ 120 MB → gagal bila melebihi (ambang via env).
   - Jalankan dengan flag hardening lengkap (PRD §9.5 contoh `docker run`) → ukur waktu hingga `/api/v1/health/ready` 200 (≤ 5 dtk, ambang via env).
   - Verifikasi: `docker exec ... id -u` = 10001; tidak ada `gcc`, `pip` (`command -v`) ; filesystem root read-only (`touch /opt/app/x` gagal); `/data` writable.
   - Graceful shutdown: kirim `SIGTERM` saat request PAdES berjalan → request selesai atau ditolak rapi, container keluar ≤ 25 dtk dengan exit code 0.
2. `scripts/smoke.sh <base_url>`: dengan `curl` + `jq` — `config`, upload `a4.pdf`, aset teks, stamp, unduh, PAdES B-B dengan p12 uji (dari `backend/tests/pki/out`), verify → `VALID`, delete. Keluar non-zero pada kegagalan. Mendukung `X-API-Key` via env.
3. Target Makefile: `docker-build`, `docker-run` (compose up), `image-check`, `smoke`.

### 5. Multi-arch

Build `linux/amd64` wajib. `linux/arm64` sesuai ADR-0001 (build, jalankan `smoke.sh` di bawah QEMU bila memungkinkan; bila ditunda, catat di TODO).

### 6. Lint & scan lokal

`hadolint docker/Dockerfile` (via container `hadolint/hadolint`), `trivy image --severity HIGH,CRITICAL --ignore-unfixed tte-pdf:dev` (via container `aquasec/trivy`) — catat hasil; perbaiki temuan yang dapat diperbaiki.

## Di Luar Lingkup

Pipeline CI (P16), penandatanganan image (P16), Kubernetes manifest.

## Kriteria Selesai

- [ ] `make image-check` lolos: ukuran, startup, non-root, read-only, tanpa tool build, graceful shutdown.
- [ ] `make smoke` lolos terhadap container yang berjalan dengan hardening penuh.
- [ ] Hadolint tanpa error; Trivy 0 High/Critical yang _fixable_.
- [ ] `docker compose up` berjalan dengan secret & trust store contoh.
- [ ] Hasil ukur (ukuran, startup) dicatat di `docs/qa/image-report.md`.

## Verifikasi

```bash
make requirements docker-build image-check
docker compose up -d && make smoke BASE_URL=http://localhost:8080 && docker compose down
docker run --rm -i hadolint/hadolint < docker/Dockerfile
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy image --severity HIGH,CRITICAL --ignore-unfixed tte-pdf:dev
```

## Penutup

- Centang item P13 di `docs/TODO.md`.
- Commit: `build(docker): hardened multi-stage alpine production image (P13)`.
- Laporan sesuai format (sertakan tabel ukuran per layer terbesar & waktu startup).
