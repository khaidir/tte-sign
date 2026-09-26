# Panduan Menjalankan Prompt Implementasi

Folder ini berisi **16 prompt bertahap** untuk membangun MVP Mini App TTE PDF dengan agen AI (Claude Code). Setiap prompt adalah satu unit kerja yang dapat diverifikasi.

## Urutan

| #   | File                                                                         | Milestone   | Bergantung |
| --- | ---------------------------------------------------------------------------- | ----------- | ---------- |
| 01  | [01-scaffold-monorepo.md](01-scaffold-monorepo.md)                           | M0          | —          |
| 02  | [02-spike-alpine-compat.md](02-spike-alpine-compat.md)                       | M0 → **G1** | 01         |
| 03  | [03-test-pki-fixtures.md](03-test-pki-fixtures.md)                           | M0          | 01         |
| 04  | [04-backend-documents.md](04-backend-documents.md)                           | M1          | 03         |
| 05  | [05-backend-assets-coords.md](05-backend-assets-coords.md)                   | M1          | 04         |
| 06  | [06-backend-stamp-engine.md](06-backend-stamp-engine.md)                     | M1          | 05         |
| 07  | [07-backend-pades-sign.md](07-backend-pades-sign.md)                         | M2          | 06         |
| 08  | [08-backend-pades-verify.md](08-backend-pades-verify.md)                     | M2 → **G2** | 07         |
| 09  | [09-frontend-viewer.md](09-frontend-viewer.md)                               | M3          | 04         |
| 10  | [10-frontend-signature-placement.md](10-frontend-signature-placement.md)     | M3          | 05, 09     |
| 11  | [11-frontend-apply-download-verify.md](11-frontend-apply-download-verify.md) | M3          | 06–08, 10  |
| 12  | [12-security-auth-audit.md](12-security-auth-audit.md)                       | M4          | 08, 11     |
| 13  | [13-docker-alpine-image.md](13-docker-alpine-image.md)                       | M4          | 02, 12     |
| 14  | [14-testing-qa.md](14-testing-qa.md)                                         | M4          | 13         |
| 15  | [15-api-docs-cli.md](15-api-docs-cli.md)                                     | M4          | 12         |
| 16  | [16-release-readiness.md](16-release-readiness.md)                           | M4 → **G3** | 13–15      |

## Cara Menjalankan

1. Buka Claude Code di root repo (`tte/`). `CLAUDE.md` otomatis dimuat sebagai konteks.
2. Mulai sesi baru (atau `/clear`) untuk setiap prompt agar konteks tetap bersih.
3. Kirim pesan pembuka berikut, ganti `NN`:

   ```text
   Jalankan prompt di prompts/NN-*.md. Baca dulu CLAUDE.md, docs/TODO.md, dan bagian
   PRD/PLAN yang dirujuk prompt. Kerjakan hanya lingkup prompt ini, verifikasi semua
   kriteria selesai, perbarui docs/TODO.md, commit, lalu laporkan hasilnya.
   ```

4. Periksa laporan agen: bukti verifikasi, deviasi, pertanyaan terbuka.
5. Pada gerbang **G1/G2/G3** (lihat `docs/PLAN.md §9`), hentikan dan lakukan review manusia sebelum lanjut.

**Mode paralel (opsional):** setelah P04, jalur backend (P05 → P08) dan frontend (P09 → P10) dapat dijalankan di dua sesi/worktree terpisah, lalu digabung sebelum P11.

## Struktur Setiap Prompt

| Bagian               | Isi                                                 |
| -------------------- | --------------------------------------------------- |
| Header               | Milestone, dependensi, estimasi, referensi PRD/PLAN |
| **Peran**            | Persona engineer yang dijalankan agen               |
| **Konteks**          | Status repo yang diharapkan sebelum mulai           |
| **Tujuan**           | Hasil akhir dalam 1–3 kalimat                       |
| **Tugas**            | Langkah implementasi terperinci                     |
| **Di luar lingkup**  | Hal yang **tidak** boleh dikerjakan di prompt ini   |
| **Kriteria selesai** | Checklist yang harus terbukti                       |
| **Verifikasi**       | Perintah yang wajib dijalankan dan lolos            |
| **Penutup**          | Update TODO, pesan commit, format laporan           |

## Aturan Umum untuk Agen

- Ikuti `CLAUDE.md` (aturan rahasia, koordinat, worker pool, bahasa, kontrak API).
- Bila API library berbeda dari contoh di prompt, periksa dokumentasi/versi terpasang (`uv run python -c "import pyhanko; print(pyhanko.__version__)"`, docstring, atau sumber paket) lalu sesuaikan. Test adalah penentu kebenaran.
- Jangan menghapus atau melemahkan test agar lolos. Bila test tidak mungkin lolos, laporkan alasannya.
- Jangan mengubah kontrak API tanpa memperbarui PRD Lampiran A.
- Bila butuh keputusan produk/legal, berhenti dan ajukan pertanyaan beserta rekomendasi.

## Format Laporan Akhir (wajib)

```markdown
## Laporan PNN — <judul>

**Status:** Selesai / Sebagian / Terblokir
**Dikerjakan:** <ringkas per poin>
**Bukti verifikasi:** <perintah + ringkasan output>
**Deviasi dari PRD/PLAN:** <tidak ada / daftar + alasan + ADR>
**Pertanyaan terbuka / risiko:** <daftar>
**Langkah berikut:** PNN+1
```
