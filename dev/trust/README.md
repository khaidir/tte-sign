# Trust Store Pengembangan — TTE

Direktori ini berisi sertifikat root CA uji untuk pengembangan lokal.

## Cara pakai

```bash
export TTE_TRUST_DIR=$(pwd)/dev/trust
make dev-backend
```

## Isi

- `tte-test-root.pem` — Root CA Indonesia (UJI)
- `psre-ca.pem` — PSrE Contoh CA (UJI)

Dibuat oleh `make pki`. Jangan gunakan di produksi.
