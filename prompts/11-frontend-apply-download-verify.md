# P11 — Frontend: Terapkan, Unduh (Stamp/PAdES), dan Halaman Verifikasi

> **Milestone:** M3 · **Bergantung:** P06, P07, P08, P10 (dan G2 disetujui) · **Estimasi:** 2,5 hari
> **Referensi:** PRD FR-10, FR-11, FR-13, FR-14, FR-15, FR-19, FR-20, §6.1, §10.4, §10.5, §10.6, §11.4 · Lampiran A.2

## Peran

Anda adalah senior frontend engineer yang membangun alur transaksi sensitif dengan UX yang jelas dan aman.

## Konteks

Placement lengkap (P10). Endpoint `/stamp`, `/pades`, `/verify`, `/signatures` berfungsi (P06–P08).

## Tujuan

Menyelesaikan alur end-to-end: **Terapkan** → preview hasil → **Unduh** sebagai stamp atau PAdES, serta halaman **Verifikasi**, dengan penanganan error dan status hukum yang jujur.

## Tugas

### 1. Terapkan (`src/dialogs/apply.js`)

1. Klik **Terapkan Tanda Tangan** → `POST /documents/{id}/stamp` dengan `toApiPlacement()` untuk setiap placement.
2. `409 EXISTING_SIGNATURES` → modal peringatan: "Dokumen ini sudah memiliki tanda tangan digital. Menerapkan stamp dapat membuat tanda tangan tersebut tidak valid. Untuk mempertahankannya, pilih 'Tandatangani dengan Sertifikat Elektronik' saat mengunduh." Tombol: **Tetap terapkan** (kirim ulang dengan `allow_existing_signatures: true`) / **Batal**.
3. Sukses → simpan `result` di store, viewer `reload(result.links.file)` dalam mode `preview` dengan badge "Pratinjau hasil"; tombol footer berubah menjadi **Unduh PDF** + tautan **Ubah penempatan** (kembali ke mode edit dengan dokumen asli & placement utuh).
4. Banner dokumen bertanda tangan (FR-19) tampil sejak dokumen diunggah bila `has_signatures`.

### 2. Dialog Unduh (`src/dialogs/download.js`) — sesuai wireframe PRD §10.4

1. Opsi radio: **PDF dengan stamp visual** ("Cepat, untuk keperluan internal. Bukan TTE tersertifikasi.") dan **Tandatangani dengan Sertifikat Elektronik (PAdES)** ("Menjamin keutuhan dokumen & identitas penanda tangan."), tautan "Pelajari perbedaan" (modal ringkasan PRD §5.2).
2. Opsi PAdES nonaktif dengan penjelasan bila `config.pades_levels` kosong.
3. Form PAdES:
   - Sumber sertifikat: **Berkas .p12/.pfx** (input file `accept=".p12,.pfx"`, ≤ 100 KB) atau **Segel organisasi** (hanya tampil bila `config.server_signer.available`; tampilkan CN & masa berlaku).
   - Passphrase (`type=password`, tombol tampil/sembunyi, `autocomplete="off"`); peringatan kunci privat (FR-14 AC-5).
   - Level: pilihan dari `config.pades_levels` dengan penjelasan singkat (B-B dasar; B-T + timestamp; B-LT + data validasi jangka panjang; B-LTA + arsip); default `config.default_level`; level yang butuh TSA dinonaktifkan bila `!config.tsa_configured`.
   - Alasan (default "Persetujuan dokumen"), Lokasi, Kontak (opsional), toggle "Tampilkan detail penanda tangan pada tanda tangan".
   - Checkbox persetujuan wajib (teks FR-11 AC-2); `statement_version` konstanta `2026-09-v1`.
4. Submit stamp → unduh `GET result.links.download`.
5. Submit PAdES → `FormData`: `request` (Blob JSON `application/json`: placement utama = placement pertama/terpilih, `extra_stamps` = sisanya, `level`, `signer`, `metadata`, `appearance`, `consent`), `pkcs12`, `passphrase` → `POST /documents/{originalId}/pades` (dokumen **asli**, bukan hasil stamp).
6. Setelah sukses: unduh `signed` via `fetch` → Blob → `<a download>` + `URL.revokeObjectURL`; tampilkan kartu ringkasan (CN, penerbit, waktu TSA, level, SHA-256 dengan tombol salin) dan tautan "Verifikasi dokumen ini".
7. Keamanan klien: kosongkan field passphrase & referensi berkas p12 setelah submit (sukses/gagal); jangan simpan di store/`localStorage`; jangan log ke console.
8. Pemetaan error ke UI: `PKCS12_BAD_PASSPHRASE` → error di field passphrase; `PKCS12_INVALID` → field berkas; `CERT_*` → pesan dengan saran "perbarui sertifikat di PSrE"; `TSA_UNAVAILABLE`/`REVOCATION_UNAVAILABLE` → pesan + tombol **Coba lagi** dan saran memilih level lebih rendah secara sadar; `CONSENT_REQUIRED` → sorot checkbox; `TOO_MANY_ATTEMPTS`/`RATE_LIMITED` → tampilkan waktu tunggu dari `Retry-After`; lainnya → toast + `request_id`.

### 3. Halaman Verifikasi (`verify.html`, `src/verify.js`) — sesuai PRD §10.5

1. Drop zone PDF → `POST /verify`; juga dapat dibuka dari editor dengan `?document=<id>` → `GET /documents/{id}/signatures`.
2. Banner ringkasan berwarna sesuai status (`VALID` hijau, `INVALID` merah, `INDETERMINATE` kuning, `NO_SIGNATURE` abu) + ikon + teks (warna tidak menjadi satu-satunya penanda).
3. Kartu per tanda tangan: penanda tangan, penerbit & status trust, waktu (TSA bila ada; format WIB), level PAdES, integritas, pencabutan, alasan/lokasi, indikasi ETSI; bagian **Detail teknis** (collapsible) berisi rantai sertifikat, coverage, modifikasi, peringatan.
4. Tombol **Unduh laporan JSON**.

### 4. Retensi & sesi

- Hitung mundur TTL di footer; saat habis → modal "Sesi dokumen berakhir, unggah ulang".
- Tombol **Hapus dari server** → `DELETE /documents/{id}` → reset state.
- `beforeunload` tidak perlu memblokir; hapus otomatis dokumen lama saat unggah dokumen baru (sudah di P09).

### 5. Aksesibilitas

Modal: fokus terkunci & dikembalikan saat ditutup, `aria-modal`, `aria-labelledby`; semua kontrol dapat dioperasikan keyboard; status proses via `aria-busy` + `aria-live`.

### 6. Test

- vitest: pembangun `FormData` PAdES (struktur JSON sesuai Lampiran A.2), pemetaan error → field.
- Playwright (Chromium): (1) stamp end-to-end → unduh → berkas PDF valid (magic bytes) ; (2) PAdES B-B dengan `signer-valid.p12` uji → unduh → buka halaman verifikasi dengan berkas tersebut → `VALID` (backend dev memakai trust dir uji); (3) passphrase salah → error di field; (4) dokumen bertanda tangan → banner & modal 409. Gunakan fixture PKI dari P03 (mock TSA opsional; B-B cukup di sini).

## Di Luar Lingkup

Autentikasi API key UI (P12), E2E lintas browser penuh (P14), i18n Inggris.

## Kriteria Selesai

- [ ] Alur Stamp dan PAdES end-to-end berfungsi di browser; hasil PAdES terverifikasi `VALID` di halaman verifikasi.
- [ ] Passphrase & p12 tidak tersisa di state/DOM setelah submit (cek di test: input kosong, store tanpa field tersebut).
- [ ] Semua kode error PAdES utama dipetakan ke pesan yang dapat ditindaklanjuti.
- [ ] Halaman verifikasi menampilkan semua status dengan benar untuk sampel korpus P08.
- [ ] `npm run lint && npm test && npm run build` hijau; Playwright Chromium hijau.

## Verifikasi

```bash
cd frontend && npm run lint && npm test && npm run build
npx playwright test --project=chromium
```

## Penutup

- Centang item P11 di `docs/TODO.md`.
- Commit: `feat(frontend): apply, download dialog with pades and verify page (P11)`.
- Laporan sesuai format (sertakan tangkapan layar editor, dialog unduh, dan halaman verifikasi di `docs/qa/screenshots/`).
