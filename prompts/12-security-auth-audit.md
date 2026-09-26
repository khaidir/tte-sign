# P12 — Keamanan: Autentikasi API Key, Kepemilikan, Rate Limit, Headers, Audit, Privasi

> **Milestone:** M4 · **Bergantung:** P08, P11 · **Estimasi:** 2 hari
> **Referensi:** PRD FR-14 (AC-2/3), FR-18, FR-21, NFR-SEC-01…10, NFR-PRIV, NFR-AUD-01, §11.4 · PLAN §11

## Peran

Anda adalah application security engineer yang menerapkan kontrol keamanan tanpa merusak fungsionalitas.

## Konteks

Semua fitur fungsional MVP sudah ada. Owner dokumen masih `anonymous`; server signer masih selalu ditolak; audit hanya ke stdout.

## Tujuan

Menerapkan kontrol keamanan MVP secara menyeluruh: autentikasi & otorisasi berbasis API key dengan scope, isolasi kepemilikan, rate limiting, security headers/CSP, body limit, audit trail persisten ber-_hash chain_, dan pemberitahuan privasi.

## Tugas

### 1. Autentikasi & otorisasi (`app/core/security.py`)

1. `TTE_AUTH_MODE`:
   - `none`: semua scope dianggap terpenuhi **kecuali** `sign:server` (selalu butuh API key valid dengan scope tersebut); `actor="anonymous"`.
   - `apikey`: semua endpoint `/api/v1/*` wajib `X-API-Key` kecuali `health/*` dan `config`.
   - `proxy` (Should): identitas dari header yang dikonfigurasi (`TTE_PROXY_USER_HEADER`, default `X-Forwarded-User`) **hanya** bila request berasal dari IP tepercaya (`TTE_PROXY_TRUSTED_IPS`); scope default dari konfigurasi.
2. Berkas `TTE_API_KEYS_FILE` (YAML atau JSON): daftar `{id, hash, scopes, expires_at?, description?}`; `hash` = `scrypt` atau `sha256` dengan salt (`sha256$<salt_hex>$<hash_hex>`); perbandingan _constant-time_; muat ulang saat SIGHUP (Should).
3. Tool: `python -m app.tools.apikey create --id eoffice --scopes doc:read,doc:write,sign:pades,verify` → cetak key sekali (`tte_<random 32 byte base64url>`) + baris hash untuk berkas.
4. Dependency FastAPI `require_scopes(*scopes)` di setiap router sesuai tabel PRD §7.2; `401 UNAUTHORIZED` / `403 FORBIDDEN`; audit `auth.failed` (id key bila dikenal, IP, path) tanpa menulis key.
5. **Kepemilikan:** `owner` = id API key / user proxy / `anonymous`. Semua akses dokumen/aset memeriksa owner (sudah didukung storage P04) → `404` seragam. Test: key A tidak dapat membaca, men-_stamp_, men-_sign_, atau menghapus dokumen key B.
6. Server signer: izinkan hanya bila key memiliki `sign:server`; audit menyertakan `actor` dan `signer=server`.
7. Frontend (mode `apikey`): bila `config.auth_mode === "apikey"` dan belum ada key di `sessionStorage`, tampilkan modal input API key sebelum unggah; tombol "Keluar" menghapus key.

### 2. Rate limiting (`app/core/ratelimit.py`)

1. Token bucket in-memory per `(actor|ip, grup)`: `upload` 30/menit, `pades` 10/menit, `verify` 30/menit, `assets` 60/menit; dapat dikonfigurasi `TTE_RATE_LIMIT_<GRUP>`.
2. Kegagalan passphrase: 5 per 15 menit per IP+actor → `429 TOO_MANY_ATTEMPTS` (reset saat sukses).
3. `429` menyertakan `Retry-After`; audit `ratelimit.triggered`.
4. Dokumentasikan bahwa limiter per-proses (bila `TTE_WEB_CONCURRENCY>1`, batas efektif dikali jumlah proses) — Fase 2: Redis.

### 3. Headers, CORS, body limit

1. Middleware security headers sesuai NFR-SEC-02 untuk respons HTML/static; untuk API: `X-Content-Type-Options`, `Cache-Control: no-store`, `Referrer-Policy`. HSTS bila `TTE_HSTS=true`.
2. **Uji CSP dengan PDF.js dan signature_pad** (Playwright: tidak ada pelanggaran CSP di console). Bila PDF.js membutuhkan pengecualian (mis. `blob:` untuk worker/font), tambahkan seminimal mungkin dan catat alasannya di komentar.
3. CORS: default tidak ada origin lintas domain; `TTE_CORS_ORIGINS` untuk integrasi; `allow_credentials=false`.
4. Body limit global (ASGI middleware) berdasarkan `Content-Length` dan stream counting: dokumen `TTE_MAX_UPLOAD_MB` + 1 MB overhead multipart; endpoint JSON 64 KB.
5. `TrustedHostMiddleware` bila `TTE_ALLOWED_HOSTS` diisi.

### 4. Audit trail

1. File sink `TTE_AUDIT_FILE` (append-only, `O_APPEND`, `fsync` per record atau per batch kecil); saat startup baca `hash` terakhir untuk melanjutkan chain; rotasi diserahkan ke infrastruktur (dokumentasikan).
2. `python -m app.tools.verify_audit <file>` → keluar 0 bila chain utuh; tampilkan baris pertama yang rusak bila tidak.
3. Pastikan semua event PRD FR-18 AC-1 dipancarkan; lengkapi yang belum (mis. `document.downloaded`, `asset.created`).
4. Test: memodifikasi/menghapus satu baris → `verify_audit` gagal pada baris yang tepat.

### 5. Privasi & kebersihan data

1. Pemberitahuan privasi singkat di UI (footer/tautan): data yang diproses, masa simpan 30 menit, tidak ada pihak ketiga, kunci p12 tidak disimpan.
2. Test kebersihan menyeluruh: jalankan skenario lengkap (upload, aset teks dengan nama, stamp, PAdES sukses & passphrase salah, verify) lalu pindai seluruh log & audit: tidak ada passphrase, bytes p12 (base64/hex), PEM kunci privat, teks nama dari aset teks di log aplikasi (boleh di metadata aset, tidak di log), nama berkas asli.
3. `bandit -r backend/app` tanpa temuan High (tambahkan ke `make lint`).

## Di Luar Lingkup

OIDC/SSO penuh (Fase 2), enkripsi at-rest (Should — boleh bila waktu cukup: AES-256-GCM per berkas dengan kunci dari `TTE_STORAGE_KEY_FILE`), Redis rate limit.

## Kriteria Selesai

- [ ] Matriks otorisasi (endpoint × scope × mode) teruji otomatis.
- [ ] Isolasi kepemilikan teruji untuk semua endpoint dokumen/aset/stamp/pades/signatures.
- [ ] Rate limit & `TOO_MANY_ATTEMPTS` teruji.
- [ ] CSP aktif tanpa pelanggaran di alur E2E utama.
- [ ] Audit file + `verify_audit` berfungsi; semua event FR-18 ada.
- [ ] Test kebersihan data hijau; bandit bersih; `make lint test` hijau.

## Verifikasi

```bash
make lint test
cd backend && uv run pytest tests/integration/test_security.py tests/integration/test_audit_file.py -v
uv run python -m app.tools.verify_audit /tmp/tte-audit-test.jsonl
cd ../frontend && npx playwright test --project=chromium
```

## Penutup

- Centang item P12 di `docs/TODO.md`.
- Commit: `feat(security): api keys with scopes, ownership, rate limits, csp and audit chain (P12)`.
- Laporan sesuai format (sertakan matriks otorisasi dan pengecualian CSP bila ada).
