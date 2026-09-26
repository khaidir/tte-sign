# P01 — Scaffold Monorepo & Fondasi Backend/Frontend

> **Milestone:** M0 · **Bergantung:** — · **Estimasi:** 0,5–1 hari
> **Referensi:** PRD §7.2, FR-16, FR-18, NFR-OBS, Lampiran A.1, A.4, B · PLAN §2, §3, §10

## Peran

Anda adalah senior full-stack engineer (Python/FastAPI & JavaScript) yang membangun fondasi proyek produksi dengan standar kualitas tinggi.

## Konteks

Repo hanya berisi `CLAUDE.md`, `README.md`, `docs/`, dan `prompts/`. Belum ada git, kode, atau tooling.

## Tujuan

Menyiapkan monorepo yang dapat di-_build_, di-_lint_, dan di-_test_, berisi kerangka backend FastAPI (config, error, logging, audit, health, config publik) dan kerangka frontend Vite, sehingga prompt berikutnya hanya menambah fitur.

## Tugas

### 1. Repo & tooling

1. `git init` (branch `main`). Buat `.gitignore` (Python, Node, `.venv`, `dist`, `node_modules`, `backend/tests/pki/out/`, `backend/tests/fixtures/out/`, `.data/`, `*.p12`, `*.pfx` kecuali di `backend/tests/pki/out`), `.editorconfig`, `.dockerignore` (awal; disempurnakan di P13).
2. Buat struktur direktori sesuai PLAN §3 (folder kosong diberi `.gitkeep` bila perlu).
3. `Makefile` dengan target: `setup`, `dev-backend`, `dev-frontend`, `lint`, `format`, `test`, `test-backend`, `test-frontend`, `build-frontend`, `pki`, `fixtures`, `docker-build`, `docker-run`, `smoke` (target yang belum ada implementasinya mencetak pesan "belum tersedia (PNN)" dan keluar 0).

### 2. Backend (`backend/`)

1. Proyek **uv**, `requires-python = ">=3.13,<3.14"`. Dependency awal: `fastapi`, `uvicorn[standard]`, `pydantic>=2`, `pydantic-settings`, `python-multipart`, `orjson`. Dev: `pytest`, `pytest-cov`, `pytest-asyncio`, `httpx`, `hypothesis`, `ruff`, `mypy`. Konfigurasi ruff (line length 100, rule set `E,F,I,B,UP,S,ASYNC`) dan pytest (`asyncio_mode=auto`) di `pyproject.toml`.
2. `app/config.py`: kelas `Settings` (pydantic-settings, prefix `TTE_`) memuat **seluruh** variabel PRD Lampiran B dengan default dan validasi (mis. `TTE_ALLOWED_LEVELS` di-_parse_ menjadi list enum `PadesLevel`, `TTE_DEFAULT_LEVEL` harus termasuk di dalamnya). Dukungan membaca nilai dari berkas untuk variabel berakhiran `_FILE`. Fungsi `get_settings()` ter-_cache_.
3. `app/core/errors.py`:
   - `AppError(Exception)` dengan `code`, `status`, `title`, `detail`, `extra`.
   - Katalog `ErrorCode` (enum) berisi **semua** kode PRD Lampiran A.4, beserta `status` dan `title` Bahasa Indonesia default.
   - Handler FastAPI: `AppError` → `application/problem+json` (RFC 9457: `type`, `title`, `status`, `code`, `detail`, `instance`, `request_id`); `RequestValidationError` → `400 VALIDATION_ERROR` dengan `errors[]` (lokasi + pesan, **tanpa** menyertakan nilai input); `HTTPException` 404/405 → Problem Details; exception tak terduga → `500 INTERNAL_ERROR` tanpa detail internal (stack trace hanya di log server, tanpa isi request).
4. `app/core/logging.py`: logging JSON ke stdout (field: `ts`, `level`, `logger`, `msg`, `request_id`, extra). `request_id` disimpan di `contextvars`.
5. `app/core/middleware.py`: middleware `X-Request-ID` (terima dari header bila valid `^[A-Za-z0-9._-]{1,64}$`, jika tidak buat `req_<ulid>`), pantulkan di respons, log akses (method, path template, status, durasi ms, ukuran respons) — **tidak pernah** me-log body atau query string berisi data sensitif.
6. `app/core/ids.py`: generator ID `doc_`, `ast_`, `req_` (26 karakter base32 Crockford dari 16 byte `secrets.token_bytes`, diawali timestamp ms ala ULID).
7. `app/core/audit.py`: `AuditLogger` dengan metode `emit(event: str, **fields)`. Setiap record: `ts`, `event`, `request_id`, field lain, `prev_hash`, `hash = sha256(prev_hash + canonical_json(record_tanpa_hash))`. Sink awal: stdout (logger `audit`). Siapkan antarmuka sink agar P12 dapat menambah file sink. Daftar field yang dilarang (`passphrase`, `pkcs12`, `private_key`, `content`, `image`) → `ValueError` bila dikirim.
8. `app/api/v1/health.py`: `GET /api/v1/health/live` → `{"status":"ok"}`; `GET /api/v1/health/ready` → `{"status":"ready","checks":{...}}` dengan registri _check_ yang dapat ditambah modul lain (awal: `data_dir` dapat ditulis).
9. `app/api/v1/config.py`: `GET /api/v1/config` → `PublicConfig` (PRD Lampiran A.2) dari `Settings`; field yang belum tersedia bernilai aman (mis. `server_signer.available=false`, `tsa_configured` dari settings).
10. `app/main.py`: `create_app()` → FastAPI (`title="TTE PDF API"`, `version` dari paket, `openapi_url="/api/openapi.json"`, `docs_url="/api/docs"` bila `TTE_API_DOCS_ENABLED`), daftarkan middleware, handler error, router v1. Mount static dari `app/static/` bila ada: `/` → `index.html`, `/verify` → `verify.html`, aset di `/assets-static` atau sesuai output Vite (sesuaikan `base` Vite).
11. `app/__main__.py`: `python -m app` menjalankan uvicorn dengan host/port/workers dari settings, `proxy_headers=True`, `server_header=False`, `log_config=None` (memakai logging JSON).
12. Test: `tests/unit/test_errors.py`, `test_audit.py` (chain valid; mengubah satu record merusak verifikasi; field terlarang ditolak), `test_ids.py`, `tests/integration/test_health_config.py` (termasuk header `X-Request-ID`).

### 3. Frontend (`frontend/`)

1. Vite (Vanilla JS, ES2020), multi-page: `index.html` (editor) dan `verify.html` (verifikasi) sebagai input build.
2. Dependency: `pdfjs-dist`, `signature_pad`. Dev: `vite`, `vitest`, `jsdom`, `eslint` (flat config), `prettier`, `@playwright/test`.
3. `vite.config.js`: `server.proxy['/api'] → http://localhost:8080`; `build.outDir = 'dist'`; tanpa CDN.
4. `src/main.js` & `src/verify.js`: render shell kosong (judul "TTE PDF", placeholder langkah) + `src/i18n/id.js` (kamus string awal).
5. `src/styles/tokens.css`: design token warna/spasi/tipografi (CSS variables) — font sistem, tanpa Google Fonts.
6. Skrip npm: `dev`, `build`, `preview`, `lint`, `format`, `test` (vitest run), `test:e2e` (playwright; konfigurasi dibuat di P11/P14).
7. Satu test vitest sederhana (kamus i18n memuat kunci wajib).

### 4. CI dasar

`.github/workflows/ci.yml`: job `backend` (setup uv, `uv sync`, `ruff check`, `ruff format --check`, `pytest --cov`) dan job `frontend` (Node 24, `npm ci`, lint, test, build).

## Di Luar Lingkup

Endpoint dokumen/aset/stamp/PAdES, Dockerfile produksi, autentikasi API key, rate limit.

## Kriteria Selesai

- [ ] `make setup && make lint && make test` hijau dari clone bersih.
- [ ] `make dev-backend` → `curl localhost:8080/api/v1/health/live` = `{"status":"ok"}`; `/api/docs` tampil.
- [ ] Request dengan body tidak valid menghasilkan `400` Problem Details `code=VALIDATION_ERROR` + `X-Request-ID`.
- [ ] Error tak terduga → `500 INTERNAL_ERROR` tanpa stack trace di respons.
- [ ] Audit hash-chain teruji (valid & tamper terdeteksi).
- [ ] `npm run build` menghasilkan `frontend/dist/index.html` dan `verify.html`.
- [ ] CI workflow valid (sintaks) dan menjalankan lint + test.

## Verifikasi

```bash
make setup
make lint
make test
cd backend && uv run python -m app &  # lalu:
curl -si localhost:8080/api/v1/health/live
curl -si localhost:8080/api/v1/config
curl -si -X POST localhost:8080/api/v1/does-not-exist
cd frontend && npm run build && ls dist
```

## Penutup

- Centang item P01 di `docs/TODO.md`, isi kolom status & commit.
- Commit: `chore: scaffold monorepo and backend/frontend foundations (P01)`.
- Kirim laporan sesuai format di `prompts/00-README.md`.
