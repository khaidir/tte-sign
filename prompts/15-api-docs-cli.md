# P15 — Dokumentasi API (OpenAPI) & CLI `tte`

> **Milestone:** M4 · **Bergantung:** P12 · **Estimasi:** 1,5 hari
> **Referensi:** PRD FR-16, FR-25, §7.2, Lampiran A (seluruhnya), §9.4 · PLAN §10 (kontrak API)

## Peran

Anda adalah developer experience engineer yang membuat API mudah diintegrasikan dan terdokumentasi dengan baik.

## Konteks

Semua endpoint ada dan aman. OpenAPI otomatis FastAPI tersedia tetapi belum dirapikan.

## Tujuan

OpenAPI 3.1 yang lengkap dan akurat, dokumentasi integrasi `docs/API.md`, berkas contoh request, dan CLI `tte` untuk integrasi berbasis skrip.

## Tugas

### 1. OpenAPI

1. Tag: `Kesehatan`, `Konfigurasi`, `Dokumen`, `Aset`, `Stamp`, `PAdES`, `Verifikasi`; `summary` & `description` Bahasa Indonesia di setiap operasi (sertakan scope yang dibutuhkan).
2. `examples` untuk setiap skema request/response (gunakan nilai dari PRD Lampiran A.2 yang konsisten dengan Lampiran C).
3. Deklarasikan respons error per operasi (`responses={...}`) dengan skema `ProblemDetails` dan daftar `code` yang mungkin.
4. Security scheme `ApiKeyAuth` (`in: header`, `name: X-API-Key`); operasi publik ditandai tanpa security.
5. Endpoint multipart `/pades`: dokumentasikan bagian `request` (JSON `PadesRequest`), `pkcs12`, `passphrase` dengan benar (`encoding` `request: contentType application/json`). Uji bahwa Swagger UI dapat mengirimnya.
6. Script `backend/scripts/export_openapi.py` → `docs/api/openapi.json` (terurut, deterministik); target `make openapi`; test yang gagal bila berkas usang (drift).
7. Validasi skema dengan `openapi-spec-validator` (dev dependency).

### 2. `docs/API.md` (Bahasa Indonesia)

1. Pengantar, base URL, versi, autentikasi & scope (tabel), rate limit, format error + tabel kode (sinkron dengan Lampiran A.4), header (`X-Request-ID`, `Retry-After`).
2. **Konvensi koordinat** (dari PRD §9.4 & Lampiran C) dengan diagram ASCII halaman, contoh rasio vs pt, rotasi, dan contoh posisi default.
3. Tutorial end-to-end dengan `curl`: stamp, PAdES (p12 & segel), verifikasi, multi-penanda tangan, hapus.
4. Panduan level PAdES (kapan memakai B-B/B-T/B-LT/B-LTA) dan kebutuhan TSA/OCSP.
5. Catatan keamanan untuk integrator (jangan menyimpan p12 di sistem perantara, gunakan TLS, rotasi API key).
6. `docs/api/tte.http` (format REST Client/HTTPie-compatible) berisi seluruh alur.

### 3. CLI `tte` (`backend/app/cli.py`, Typer + httpx)

1. Entry point `[project.scripts] tte = "app.cli:main"`; tersedia di image (`tte --help`).
2. Opsi global: `--api-url` (env `TTE_API_URL`, default `http://localhost:8080`), `--api-key` (env `TTE_API_KEY`), `--json` (keluaran JSON mentah), `--timeout`.
3. Perintah:
   - `tte upload FILE` → cetak `document_id`.
   - `tte asset image FILE` / `tte asset text --line "Budi" --line "Kepala Divisi" --font script`.
   - `tte stamp DOC_ID --asset ASSET_ID [--page 0] [--rect x,y,w,h] [--unit ratio|pt]` (tanpa `--rect` → posisi default).
   - `tte sign DOC_ID --p12 FILE [--passphrase-env VAR | --passphrase-stdin] --level B-T [--asset ... --page ... --rect ...] [--reason ... --location ...] --consent` atau `--server-signer`. **Tidak ada** opsi `--passphrase <nilai>` langsung (hindari bocor ke riwayat shell).
   - `tte verify FILE|--document DOC_ID` → ringkasan tabel atau JSON; exit code 0 = `VALID`, 1 = `INVALID`, 2 = `INDETERMINATE`, 3 = `NO_SIGNATURE`, 10+ = error.
   - `tte download DOC_ID -o OUT.pdf`, `tte delete DOC_ID`.
   - Pintasan `tte sign-file IN.pdf -o OUT.pdf --p12 ... --level B-T` (upload → sign → download → delete).
4. Error API ditampilkan `code: title — detail (request_id)` ke stderr.
5. Test CLI dengan `typer.testing.CliRunner` terhadap app in-process (httpx `ASGITransport`).

### 4. README

Perbarui `README.md`: status, fitur, quickstart Docker, tautan ke `docs/API.md` dan Swagger `/api/docs`.

## Di Luar Lingkup

SDK klien bahasa lain, portal developer.

## Kriteria Selesai

- [ ] `docs/api/openapi.json` valid (`openapi-spec-validator`) dan tanpa drift.
- [ ] Setiap operasi memiliki summary, contoh, dan respons error terdokumentasi.
- [ ] Tutorial `curl` di `docs/API.md` dijalankan ulang terhadap container dan berhasil (sertakan catatan di laporan).
- [ ] CLI mencakup semua perintah dengan test; `tte sign-file` bekerja end-to-end.
- [ ] `make lint test` hijau.

## Verifikasi

```bash
make openapi lint test
cd backend && uv run python -m openapi_spec_validator ../docs/api/openapi.json
uv run tte --help
TTE_P12_PASS=uji-rahasia uv run tte sign-file tests/fixtures/out/a4.pdf -o /tmp/a4_signed.pdf \
  --p12 tests/pki/out/signer-valid.p12 --passphrase-env TTE_P12_PASS --level B-B --consent
uv run tte verify /tmp/a4_signed.pdf
```

## Penutup

- Centang item P15 di `docs/TODO.md`.
- Commit: `docs(api): complete openapi, integration guide and tte cli (P15)`.
- Laporan sesuai format.
