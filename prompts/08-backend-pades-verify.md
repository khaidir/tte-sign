# P08 — Backend: PAdES Verify & Trust Store

> **Milestone:** M2 → **Gerbang G2** · **Bergantung:** P07 · **Estimasi:** 2 hari
> **Referensi:** PRD FR-13, FR-15, §6.3, §10.5, Lampiran A.2 (`VerificationReport`), A.4, D · PLAN §9 (G2)

## Peran

Anda adalah engineer validasi tanda tangan digital yang memahami ETSI EN 319 102-1 dan fitur validasi pyHanko.

## Konteks

PAdES sign berfungsi (P07). PKI uji dengan sertifikat valid, dicabut, kedaluwarsa, untrusted, serta mock OCSP/CRL/TSA tersedia (P03).

## Tujuan

Memverifikasi semua tanda tangan dalam PDF dan menghasilkan `VerificationReport` yang akurat, terstruktur, dan mudah dibaca (pesan Bahasa Indonesia), dengan indikasi ETSI.

## Tugas

### 1. Trust store (`app/services/trust_store.py`)

1. Muat semua sertifikat PEM/DER (termasuk bundel multi-sertifikat) dari `TTE_TRUST_DIR`; opsional tambah trust store sistem (`TTE_TRUST_SYSTEM=true`, via `certifi`/`/etc/ssl/certs`).
2. Pisahkan _trust anchor_ (self-signed CA) dan _intermediate_ (dipakai untuk melengkapi rantai).
3. Readiness check `trust_store` (jumlah anchor > 0 bila verify diaktifkan; bila kosong status `degraded` dengan pesan).
4. Fungsi `build_validation_context(for_signing: bool)` dipakai bersama P07 (refactor P07 bila perlu agar satu sumber).

### 2. Verifier (`app/services/pades_verifier.py`, job worker)

1. Baca PDF dengan `PdfFileReader`; iterasi `embedded_signatures` (urut revisi).
2. Per tanda tangan (pakai `validate_pdf_signature` dan/atau API AdES `pyhanko.sign.validation.ades` untuk indikasi ETSI bila tersedia di versi terpasang):
   - `integrity.intact` / `valid`; `coverage` (ENTIRE_FILE / ENTIRE_REVISION / PARTIAL);
   - `modifications.level` (NONE / FORM_FILLING / ANNOTATIONS / OTHER) dari analisis _diff_ pyHanko + deskripsi Bahasa Indonesia;
   - `signer` (CN, O, email, serial hex, issuer RFC 4514, not_before/after);
   - `trust` (trusted, trust_anchor, chain subject list);
   - `revocation` (GOOD / REVOKED / UNKNOWN, sumber EMBEDDED_OCSP / EMBEDDED_CRL / ONLINE_OCSP / ONLINE_CRL);
   - `signing_time` (klaim), `timestamp` (present, valid, time, tsa);
   - `pades_level` terdeteksi: B-B (tanpa signature timestamp), B-T (ada), B-LT (DSS berisi data validasi untuk rantai signer), B-LTA (document timestamp setelah DSS); `ltv_enabled`;
   - `reason`, `location`, `field_name`, `page`, `pdf_rect`, `is_certification`, `docmdp_permissions`;
   - `warnings[]` (mis. algoritma lemah SHA-1, sertifikat kedaluwarsa kini tetapi valid saat timestamp).
3. Indikasi:
   - `TOTAL_PASSED`: intact & valid & trusted & revocation GOOD (atau tervalidasi pada waktu timestamp) & modifikasi diizinkan.
   - `TOTAL_FAILED`: digest tidak cocok, tanda tangan invalid, sertifikat dicabut sebelum waktu tanda tangan, modifikasi tidak diizinkan.
   - `INDETERMINATE`: root tidak dipercaya, status pencabutan tidak diketahui, rantai tidak lengkap, dll. Isi `sub_indication` (mis. `NO_CERTIFICATE_CHAIN_FOUND`, `TRY_LATER`, `REVOKED_NO_POE`).
4. Ringkasan dokumen: `NO_SIGNATURE` / `VALID` (semua TOTAL_PASSED) / `INVALID` (ada TOTAL_FAILED) / `INDETERMINATE`, dengan `message` Bahasa Indonesia; `document.revisions`.
5. `TTE_VALIDATION_FETCH=false` → tidak ada akses jaringan; gunakan hanya data tertanam.
6. Parser error pada PDF → `PDF_CORRUPT`; PDF terenkripsi → `PDF_ENCRYPTED`.

### 3. Endpoint (`app/api/v1/verify.py`)

1. `POST /api/v1/verify` (multipart `file`, `store` opsional bool): validasi sama dengan upload (ukuran/magic); tanpa `store` berkas **tidak** disimpan setelah respons; dengan `store=true` simpan sebagai dokumen `original` dan sertakan `document_id` di laporan.
2. `GET /api/v1/documents/{id}/signatures` → laporan untuk dokumen tersimpan.
3. Audit `verify.performed` (sha256 dokumen, summary status, jumlah tanda tangan).

### 4. Korpus uji (`tests/integration/test_pades_verify.py`) — dibuat saat test dengan aplikasi (P07) atau pyHanko langsung

| Kasus                                                                                     | Harapan                                                                                |
| ----------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| Tanpa tanda tangan                                                                        | `NO_SIGNATURE`                                                                         |
| B-B valid, root dipercaya, OCSP online                                                    | `VALID`, `TOTAL_PASSED`, level B-B                                                     |
| B-T / B-LT / B-LTA valid                                                                  | `VALID`, level terdeteksi benar, timestamp valid, `ltv_enabled` untuk LT/LTA           |
| B-LT valid dengan `TTE_VALIDATION_FETCH=false`                                            | Tetap `TOTAL_PASSED` (data tertanam)                                                   |
| B-B dengan fetch dimatikan                                                                | `INDETERMINATE` (revocation UNKNOWN)                                                   |
| Diubah setelah tanda tangan (incremental update mengubah konten halaman)                  | `INVALID` atau `INDETERMINATE` sesuai analisis modifikasi, `modifications.level=OTHER` |
| Byte di dalam ByteRange diubah                                                            | `INVALID`, `TOTAL_FAILED`, `integrity.intact=false`                                    |
| Penanda tangan dicabut sebelum tanda tangan                                               | `INVALID`/`TOTAL_FAILED`, revocation REVOKED                                           |
| Root tidak dipercaya (`signer-untrusted`)                                                 | `INDETERMINATE`, trusted=false                                                         |
| Sertifikat kedaluwarsa saat tanda tangan (dibuat langsung dengan pyHanko, tanpa precheck) | `INVALID`/`INDETERMINATE` sesuai ETSI                                                  |
| Dua tanda tangan valid                                                                    | `VALID`, 2 entri, coverage pertama ENTIRE_REVISION, kedua ENTIRE_FILE                  |
| Stamp setelah tanda tangan (via `/stamp` dengan allow)                                    | modifikasi terdeteksi & dilaporkan                                                     |
| PDF rusak                                                                                 | `422 PDF_CORRUPT`                                                                      |

Semua kasus harus benar (**100%**). Laporan tiap kasus di-_snapshot_ (tanpa field waktu) agar regresi terdeteksi.

### 5. Performa

Verifikasi dokumen 20 halaman dengan 2 tanda tangan (tanpa fetch) < 3 detik (`@pytest.mark.perf`).

## Di Luar Lingkup

Halaman verifikasi frontend (P11), portal verifikasi publik (Fase 3).

## Kriteria Selesai

- [ ] Korpus 100% benar; snapshot tersimpan.
- [ ] Trust store & readiness check berfungsi; konteks validasi dipakai bersama sign & verify.
- [ ] `POST /verify` tidak meninggalkan berkas (dicek test: direktori data tidak bertambah).
- [ ] `make lint test` hijau.
- [ ] Paket bukti untuk **G2** siap: `docs/qa/g2-pades-evidence.md` berisi tabel korpus + hasil, contoh `VerificationReport`, hasil `pyhanko-cli`, dan instruksi validasi manual di Adobe Acrobat Reader (menambahkan root uji sebagai trusted certificate).

## Verifikasi

```bash
make lint test
cd backend && uv run pytest tests/integration/test_pades_verify.py -v
uv run pytest -m "perf or crossval" -v
```

## Penutup

- Centang item P08 di `docs/TODO.md`; tandai **G2 menunggu review**.
- Commit: `feat(backend): pades verification with etsi indications and trust store (P08)`.
- Laporan sesuai format. **Berhenti setelah prompt ini** sampai G2 disetujui (validasi manual Adobe Acrobat dilakukan manusia).
