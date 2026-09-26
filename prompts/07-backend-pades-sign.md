# P07 — Backend: PAdES Sign (B-B, B-T, B-LT, B-LTA)

> **Milestone:** M2 · **Bergantung:** P06 · **Estimasi:** 3 hari
> **Referensi:** PRD FR-11 (AC-3), FR-12, FR-14, FR-15, FR-19, FR-22, §5.2, §11.4, NFR-SEC-03/09, Lampiran A.2 (`PadesRequest`, `SignResult`), A.4 · PLAN D-02, D-04

## Peran

Anda adalah security/backend engineer yang ahli PKI, CMS/CAdES, dan PAdES (ETSI EN 319 142), serta pyHanko.

## Konteks

Dokumen, aset, koordinat, dan stamp engine tersedia. PKI uji + mock TSA/OCSP/CRL tersedia (P03). pyHanko ter-_pin_ (0.37.x). **Periksa API pyHanko di versi terpasang** (docstring/sumber/`pyhanko.readthedocs.io`) — nama kelas di bawah adalah panduan, test adalah penentu.

## Tujuan

Menandatangani PDF sesuai PAdES Baseline dengan tampilan visual sebagai _signature widget appearance_, incremental, dengan kunci dari PKCS#12 (memori saja) atau server signer, serta level B-B/B-T/B-LT (Must) dan B-LTA (Should).

## Tugas

### 1. Signer provider (`app/signers/`)

1. `base.py`: `SignerProvider` (Protocol) dengan `describe() -> SignerInfo` dan `build_signer() -> pyhanko.sign.signers.Signer`. Dokumentasikan di docstring bahwa Fase 2 akan menambah `RemotePsreProvider` memakai pola _interrupted signing_ pyHanko (digest → tanda tangan eksternal → embed) sehingga API tidak berubah.
2. `pkcs12.py`: `Pkcs12Provider(p12_bytes: bytes, passphrase: bytes)`:
   - Buka **dari bytes di memori** (mis. `cryptography...pkcs12.load_key_and_certificates` lalu bangun `SimpleSigner` dengan `SimpleCertificateStore`, atau loader bytes pyHanko bila tersedia). **Dilarang** menulis ke disk/tempfile.
   - Passphrase salah → `PKCS12_BAD_PASSPHRASE`; format rusak → `PKCS12_INVALID`; ukuran > 100 KB → `PKCS12_INVALID`.
   - Setelah dipakai, hapus referensi (`del`), dan jangan sertakan objek/bytes dalam exception message.
3. `server.py`: `ServerSignerProvider` memuat `TTE_SERVER_SIGNER_P12_FILE` + `TTE_SERVER_SIGNER_PASSPHRASE_FILE` saat startup (bila dikonfigurasi); simpan bytes di memori proses utama; `PublicConfig.server_signer` diisi `available`, `common_name`, `not_after`. Pemakaian mensyaratkan scope `sign:server` — di P07 buat dependency `require_server_signer_access()` yang **selalu** menolak (`403 SERVER_SIGNER_FORBIDDEN`) kecuali flag test/konfigurasi `TTE_AUTH_MODE=apikey` + scope (disempurnakan di P12). Jangan membuat server signer dapat dipakai anonim.
4. Validasi pra-sign (`app/signers/precheck.py`): sertifikat berlaku saat ini (`CERT_EXPIRED`, `CERT_NOT_YET_VALID`), KU mengandung `digitalSignature` atau `nonRepudiation` (`CERT_KEY_USAGE`), rantai dapat dibangun hingga root (pakai sertifikat tambahan dari p12 + intermediate di `TTE_TRUST_DIR`; bila tidak lengkap untuk B-LT → `CERT_CHAIN_INCOMPLETE`), algoritma kunci RSA ≥ 2048 / EC P-256+.

### 2. Appearance (`app/services/pades_appearance.py`)

1. Komposisi PNG appearance dengan Pillow: aset tanda tangan; bila `appearance.show_details=true`, tambahkan blok teks di bawah/samping aset berisi "Ditandatangani secara elektronik oleh:", nama (CN), waktu (WIB, format `DD-MM-YYYY HH:mm`), dan alasan — memakai `text_renderer` (font sans).
2. **Kompensasi rotasi:** untuk halaman `/Rotate R`, putar PNG **berlawanan arah jarum jam sebesar R** (`Image.rotate(R, expand=True)`) sehingga setelah halaman dirotasi saat ditampilkan, tanda tangan tampak tegak. Rect widget = `pdf_rect` dari `coords.py` (sudah dalam user space).
3. Gunakan style pyHanko berbasis gambar tanpa border dan tanpa teks bawaan (mis. `StaticStampStyle` dengan `background=PdfImage(...)`, atau `TextStampStyle(stamp_text="", border_width=0, background=..., background_opacity=1)` — pilih yang menghasilkan gambar memenuhi rect tanpa distorsi; verifikasi visual).

### 3. Signer PAdES (`app/services/pades_signer.py`, job top-level untuk worker)

1. Input job (picklable): `pdf_bytes`, `p12_bytes` + `passphrase` (atau bytes server signer), `level`, `field_name`, `page`, `pdf_rect | None`, `appearance_png | None`, `metadata` (reason/location/contact/name), `tsa_url`, `trust_dir`, `validation_fetch`, `extra_stamps[]`.
2. Bila `extra_stamps` tidak kosong: dokumen harus belum bertanda tangan (else `EXTRA_STAMPS_NOT_ALLOWED`); jalankan `StampEngine.apply` dulu (non-incremental), lalu tanda tangani hasilnya.
3. `PdfSignatureMetadata`: `field_name` (default `Signature{n+1}`, unik), `subfilter=PADES`, `md_algorithm="sha256"`, `reason`, `location`, `contact_info`, `name`; B-LT/B-LTA: `embed_validation_info=True` + `validation_context` (trust roots dari `TTE_TRUST_DIR`, `allow_fetching=TTE_VALIDATION_FETCH`); B-LTA: `use_pades_lta=True`.
4. `PdfSigner(..., timestamper=HTTPTimeStamper(tsa_url) if level != B-B, new_field_spec=SigFieldSpec(field_name, on_page=page, box=pdf_rect) | invisible, stamp_style=...)`; tulis via `IncrementalPdfFileWriter` (selalu incremental).
5. Level B-T+ tanpa `TTE_TSA_URL` → `TSA_NOT_CONFIGURED` (dicek sebelum job). Level tidak diizinkan → `LEVEL_NOT_ALLOWED`.
6. Error mapping: kegagalan TSA (koneksi/HTTP/format) → `TSA_UNAVAILABLE`; kegagalan pengambilan OCSP/CRL untuk B-LT → `REVOCATION_UNAVAILABLE`. **Tidak ada penurunan level otomatis.** Retry 2× dengan backoff untuk TSA.
7. Kembalikan bytes hasil + ringkasan `signature` (Lampiran A.2 `SignResult.signature`).

### 4. Endpoint `POST /api/v1/documents/{id}/pades`

1. Multipart: `request` (JSON `PadesRequest`), `pkcs12` (file, wajib bila `signer.source=pkcs12`), `passphrase` (field teks). Parse `request` manual dengan Pydantic → error `VALIDATION_ERROR`.
2. `consent.accepted` harus `true` → else `CONSENT_REQUIRED`. DocMDP P=1 → `DOCMDP_LOCKED`.
3. Resolve placement (`coords`) & aset → appearance PNG; jalankan job di worker; inspeksi hasil; simpan dokumen `kind=signed`, `parent_id=id`.
4. Respons `201 SignResult`.
5. Audit `pades.signed` (document ids, sha256 before/after, signer subject/serial/issuer, level, field_name, consent statement_version) atau `pades.failed` (error_code). **Tidak ada** passphrase/p12/kunci.
6. Kebersihan rahasia: form field `passphrase` dan `pkcs12` tidak pernah masuk log/traceback; exception handler 500 tidak menyertakan argumen job.

### 5. Test (`tests/integration/test_pades_sign.py`)

- B-B visible (A4 & rot90 & CropBox offset) → divalidasi pyHanko langsung: `intact`, `valid`, `trusted` (trust = root uji), `coverage` = ENTIRE_FILE; rect widget sama dengan `pdf_rect` harapan; render visual: aset tegak & di posisi harapan (≤ 1 pt, pakai util uji P06).
- B-T (mock TSA) → token timestamp ada & valid. B-LT → DSS berisi OCSP/CRL untuk signer & TSA. B-LTA → document timestamp ada.
- Invisible signature; ECDSA P-256; field name kustom & duplikat (harus unik).
- Penanda tangan kedua pada dokumen yang sudah ditandatangani → kedua tanda tangan valid; `extra_stamps` pada dokumen bertanda tangan → 409.
- Negatif: passphrase salah (422), p12 rusak (422), `signer-expired`/`signer-notyet`/`signer-nokeyusage` (422 kode sesuai), TSA mati (502 `TSA_UNAVAILABLE`), OCSP mati untuk B-LT (502), tanpa consent (422), server signer tanpa izin (403).
- **Kebersihan log:** jalankan alur sukses & gagal dengan `caplog`/capture stdout; assert passphrase, potongan base64 dari p12, dan PEM kunci privat tidak muncul di log maupun audit.
- **Validasi silang:** simpan contoh hasil ke `backend/tests/out/samples/` (gitignored) dan jalankan `pyhanko sign validate --trust <root.pem> <file>` (paket `pyhanko-cli` bila CLI terpisah) di test bertanda `@pytest.mark.crossval`.

## Di Luar Lingkup

Endpoint verify (P08), rate limit passphrase (P12), remote signing/PKCS#11 (Fase 2), DocMDP certification (FR-26, Should — boleh bila waktu cukup: `certify=true` + `docmdp` 1/2/3).

## Kriteria Selesai

- [ ] Semua test positif & negatif hijau untuk B-B, B-T, B-LT; B-LTA hijau (atau dicatat sebagai Should yang tertunda).
- [ ] PKCS#12 terbukti tidak pernah ditulis ke disk (grep kode: tidak ada `tempfile`/`open(..., 'wb')` di jalur signer) dan tidak bocor ke log.
- [ ] Tanda tangan kedua tidak merusak yang pertama.
- [ ] Validasi silang `pyhanko-cli` sukses untuk sampel semua level.
- [ ] `make lint test` hijau.

## Verifikasi

```bash
make lint test
cd backend && uv run pytest tests/integration/test_pades_sign.py -v
uv run pytest -m crossval -v
```

## Penutup

- Centang item P07 di `docs/TODO.md`.
- Commit: `feat(backend): pades signing with pkcs12 and server signer providers (P07)`.
- Laporan sesuai format — sebutkan API pyHanko yang dipakai (kelas/fungsi) dan perbedaan dari panduan prompt.
