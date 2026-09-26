# Mini App TTE PDF

Aplikasi web mini untuk **Tanda Tangan Elektronik (TTE) pada PDF**: unggah PDF, buat tanda tangan (gambar, teks, atau goresan tangan), geser dan ubah ukurannya, lalu unduh sebagai **stamp visual** atau sebagai dokumen bertanda tangan digital **PAdES** menggunakan Sertifikat Elektronik. Tersedia REST API dan dikemas sebagai Docker image berbasis Alpine Linux.

> Status: **tahap perencanaan** — kode belum diimplementasikan. Implementasi dilakukan bertahap melalui `prompts/`.

## Dokumen

| Dokumen                                      | Deskripsi                                                         |
| -------------------------------------------- | ----------------------------------------------------------------- |
| [docs/PRD.md](docs/PRD.md)                   | Product Requirements Document lengkap                             |
| [docs/PLAN.md](docs/PLAN.md)                 | Rencana implementasi, keputusan teknis, milestone, gerbang review |
| [docs/TODO.md](docs/TODO.md)                 | Checklist pelacakan per tahap                                     |
| [prompts/00-README.md](prompts/00-README.md) | Panduan menjalankan 16 prompt implementasi bertahap               |
| [CLAUDE.md](CLAUDE.md)                       | Aturan kerja untuk agen AI (Claude Code)                          |

## Memulai implementasi

1. Pastikan prasyarat di [docs/PLAN.md §8](docs/PLAN.md#8-prasyarat-lingkungan) tersedia.
2. Buka Claude Code di direktori ini.
3. Jalankan prompt secara berurutan, dimulai dari [prompts/01-scaffold-monorepo.md](prompts/01-scaffold-monorepo.md).

## Ringkasan teknis

- **Backend:** Python 3.13 · FastAPI · pyHanko (PAdES B-B/B-T/B-LT/B-LTA) · PyMuPDF (stamp)
- **Frontend:** JavaScript · Vite · PDF.js · signature_pad
- **Deploy:** Docker multi-stage `python:3.13-alpine3.24`, non-root, read-only filesystem
