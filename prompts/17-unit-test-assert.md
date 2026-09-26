# P17 — Panduan Unit Test & Assert untuk Semua Prompt

> **Milestone:** Lintas (M0–M4) · **Bergantung:** P01 · **Estimasi:** Melekat di setiap prompt
> **Referensi:** PRD Lampiran A.4 (kode error), Lampiran C (koordinat), Lampiran D (matriks uji) · PLAN §7a (Strategi Unit Test & Assert)

## Peran

Anda adalah QA engineer yang menuliskan standar pengujian yang harus diikuti oleh setiap prompt implementasi. Dokumen ini adalah **panduan tetap** — bukan prompt sekali jalan — yang dirujuk oleh P04–P13 saat menulis test.

## Konteks

Setiap prompt implementasi (P04–P13) menghasilkan kode produksi **dan** test. Test yang ditulis harus konsisten dalam gaya, cakupan, dan pola assert. Dokumen ini menyediakan:

1. Pola assert standar untuk backend (pytest) dan frontend (vitest).
2. Organisasi file test.
3. Target cakupan per modul.
4. Aturan khusus untuk test PAdES, koordinat, dan keamanan.

## Tujuan

Memastikan setiap kode yang dikirim ke repo memiliki test yang:
- Mengikuti pola AAA (Arrange–Act–Assert) yang konsisten.
- Mencakup happy path, error path, boundary, dan negatif.
- Tidak bocor rahasia (passphrase, PKCS#12, kunci privat) ke log/audit/error.
- Dapat dijalankan secara deterministik dan independen.
- Memenuhi target cakupan per modul.

## Tugas

### 1. Terapkan Pola Assert Backend (pytest)

Setiap file test backend **wajib** menggunakan pola-pola berikut. Salin helper ini ke `backend/tests/conftest.py` atau file test masing-masing.

#### 1.1 Assert Problem Details (RFC 9457)

```python
# backend/tests/conftest.py atau helper terpisah

def assert_problem_details(resp, *, status, code, detail_contains=None):
    """Validasi respons error RFC 9457."""
    assert resp.status_code == status
    body = resp.json()
    assert body["code"] == code
    assert body["status"] == status
    assert "type" in body
    assert "title" in body
    assert "instance" in body
    assert "request_id" in body
    if detail_contains:
        assert detail_contains in body["detail"]
```

#### 1.2 Assert Audit Chain

```python
def assert_audit_chain_valid(records):
    """Verifikasi hash chain audit tidak rusak."""
    from app.core.audit import AuditLogger
    results = AuditLogger().verify_chain(records)
    assert all(r["_chain_valid"] for r in results)
```

#### 1.3 Assert Koordinat (property-based dengan hypothesis)

```python
from hypothesis import given, strategies as st, assume

@given(
    page_w=st.floats(min_value=100, max_value=3000),
    page_h=st.floats(min_value=100, max_value=3000),
    ratio_x=st.floats(min_value=0, max_value=1),
    ratio_y=st.floats(min_value=0, max_value=1),
    rotation=st.sampled_from([0, 90, 180, 270]),
)
def test_display_to_pdf_roundtrip(page_w, page_h, ratio_x, ratio_y, rotation):
    """Konversi display→pdf→display harus mengembalikan nilai awal."""
    from app.domain.coords import display_to_pdf, pdf_to_display
    u, v = ratio_x * page_w, ratio_y * page_h
    x, y = display_to_pdf(u, v, page_w, page_h, rotation)
    u2, v2 = pdf_to_display(x, y, page_w, page_h, rotation)
    assert u == pytest.approx(u2, abs=0.01)
    assert v == pytest.approx(v2, abs=0.01)
```

#### 1.4 Assert PAdES Signature

```python
def assert_signature_valid(sign_result: dict):
    """Validasi struktur respons SignResult."""
    assert "document" in sign_result
    assert sign_result["document"]["kind"] == "signed"
    assert sign_result["signature"]["field_name"].startswith("Signature")
    assert sign_result["signature"]["level_applied"] in ("B-B", "B-T", "B-LT", "B-LTA")
    assert sign_result["signature"]["digest_algorithm"] == "sha256"
    assert "signer" in sign_result["signature"]
    assert "common_name" in sign_result["signature"]["signer"]
```

#### 1.5 Assert Verification Report

```python
def assert_verification_passed(report: dict):
    """Validasi laporan verifikasi untuk tanda tangan yang valid."""
    assert report["summary"]["status"] == "VALID"
    assert report["summary"]["signature_count"] >= 1
    for sig in report["signatures"]:
        assert sig["indication"] == "TOTAL_PASSED"
        assert sig["integrity"]["intact"] is True
        assert sig["integrity"]["valid"] is True
        assert sig["trust"]["trusted"] is True
```

#### 1.6 Assert Tidak Bocor Rahasia

```python
def assert_no_secrets_in_log(caplog: pytest.LogCaptureFixture,
                              forbidden: list[str] | None = None) -> None:
    """Pastikan log tidak mengandung string terlarang."""
    forbidden = forbidden or ["passphrase", "pkcs12", "private_key"]
    for record in caplog.records:
        msg = record.getMessage().lower()
        for secret in forbidden:
            assert secret not in msg, \
                f"Secret '{secret}' leaked in log: {record.getMessage()}"
```

### 2. Terapkan Pola Assert Frontend (vitest)

Setiap file test frontend **wajib** mengikuti pola berikut.

#### 2.1 Assert Koordinat (paritas FE/BE)

```javascript
// frontend/tests/coords.test.js
import { describe, it, expect } from "vitest";
import { displayToPdf, pdfToDisplay } from "../src/coords.js";

// Test vector dari shared/test-vectors/coords.json
const vectors = [
  { pageW: 595.28, pageH: 841.89, u: 410.46, v: 36, rotation: 0,
    expectedX: 410.46, expectedY: 805.89 },
  { pageW: 595.28, pageH: 841.89, u: 100, v: 200, rotation: 90,
    expectedX: 100, expectedY: 200 },
  // ... muat dari shared/test-vectors/coords.json
];

describe.each(vectors)("coords parity", (v) => {
  it(`rotation ${v.rotation}: display→pdf`, () => {
    const [x, y] = displayToPdf(v.u, v.v, v.pageW, v.pageH, v.rotation);
    expect(x).toBeCloseTo(v.expectedX, 2);
    expect(y).toBeCloseTo(v.expectedY, 2);
  });

  it(`rotation ${v.rotation}: pdf→display`, () => {
    const [u, v2] = pdfToDisplay(v.expectedX, v.expectedY, v.pageW, v.pageH, v.rotation);
    expect(u).toBeCloseTo(v.u, 2);
    expect(v2).toBeCloseTo(v.v, 2);
  });
});
```

#### 2.2 Assert API Client (mock fetch)

```javascript
// frontend/tests/api.test.js
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ApiClient } from "../src/api/client.js";

describe("ApiClient", () => {
  let client;

  beforeEach(() => {
    client = new ApiClient("http://localhost");
  });

  it("handles successful response", async () => {
    const mockData = { id: "doc_123", status: "ok" };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(mockData), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    );
    const result = await client.request("/health/live");
    expect(result).toEqual(mockData);
  });

  it("handles problem details error", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({
        code: "PDF_CORRUPT",
        title: "Berkas PDF rusak",
        status: 422,
      }), {
        status: 422,
        headers: { "Content-Type": "application/problem+json" },
      })
    );
    await expect(client.request("/documents")).rejects.toThrow("PDF_CORRUPT");
  });

  it("handles network error", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("Network failure"));
    await expect(client.request("/documents")).rejects.toThrow("Network failure");
  });
});
```

#### 2.3 Assert UI State

```javascript
// frontend/tests/store.test.js
import { describe, it, expect, beforeEach } from "vitest";
import { createStore } from "../src/state/store.js";

describe("createStore", () => {
  let store;

  beforeEach(() => {
    store = createStore();
  });

  it("initializes with default state", () => {
    const state = store.getState();
    expect(state).toHaveProperty("document");
    expect(state).toHaveProperty("placements");
    expect(state.placements).toEqual([]);
  });

  it("updates placement on drag", () => {
    store.setPlacement({ page: 0, x: 0.5, y: 0.5, w: 0.25, h: 0.1 });
    const state = store.getState();
    expect(state.placement).toMatchObject({
      page: 0,
      x: expect.closeTo(0.5, 4),
      y: expect.closeTo(0.5, 4),
    });
  });

  it("subscribes to changes", () => {
    const listener = vi.fn();
    store.subscribe(listener);
    store.setPlacement({ page: 0, x: 0.1, y: 0.1, w: 0.2, h: 0.1 });
    expect(listener).toHaveBeenCalledTimes(1);
  });
});
```

### 3. Organisasi File Test

Setiap prompt implementasi **wajib** menempatkan test pada lokasi berikut:

| Prompt | Modul yang Diuji               | File Test Backend                          | File Test Frontend              |
| ------ | ------------------------------ | ------------------------------------------ | ------------------------------- |
| P04    | Storage, WorkerPool, pdf_inspect | `tests/unit/test_storage.py`              | —                               |
| P04    | Endpoint dokumen               | `tests/integration/test_documents.py`      | —                               |
| P04    | Janitor                        | `tests/unit/test_janitor.py`              | —                               |
| P05    | coords.py                      | `tests/unit/test_coords.py`               | `tests/coords.test.js`          |
| P05    | Asset service, text renderer   | `tests/unit/test_asset_service.py`        | —                               |
| P05    | Endpoint aset                  | `tests/integration/test_assets.py`        | —                               |
| P06    | StampEngine                    | `tests/unit/test_stamp_engine.py`         | —                               |
| P06    | Endpoint stamp                 | `tests/integration/test_stamp.py`         | —                               |
| P06    | Posisi visual                  | `tests/visual/test_position.py`           | —                               |
| P07    | PAdES signer                   | `tests/unit/test_pades_signer.py`         | —                               |
| P07    | Endpoint PAdES                 | `tests/integration/test_pades_sign.py`    | —                               |
| P08    | PAdES verifier, trust store    | `tests/unit/test_pades_verifier.py`       | —                               |
| P08    | Endpoint verify                | `tests/integration/test_pades_verify.py`  | —                               |
| P09    | API client, viewer             | —                                          | `tests/api.test.js`             |
| P10    | coords.js, store, overlay      | —                                          | `tests/coords.test.js`          |
| P10    | Validasi form                  | —                                          | `tests/validation.test.js`      |
| P11    | Dialog, state error            | —                                          | `tests/dialogs.test.js`         |
| P12    | Security, auth, rate limit     | `tests/unit/test_security.py`             | —                               |
| P12    | Endpoint auth                  | `tests/integration/test_auth.py`          | —                               |

### 4. Target Cakupan per Modul

Setiap prompt **wajib** memeriksa cakupan setelah menulis test. Gunakan perintah:

```bash
# Backend — cakupan semua modul
cd backend && uv run pytest --cov=app --cov-report=term-missing

# Backend — cakupan modul spesifik
cd backend && uv run pytest --cov=app.domain.coords --cov=app.services.stamp_engine --cov-report=term-missing

# Frontend — cakupan
cd frontend && npx vitest run --coverage
```

Target minimum:

| Modul                              | Target  | Prompt |
| ---------------------------------- | ------- | ------ |
| `app/domain/coords.py`             | ≥ 95%   | P05    |
| `app/services/stamp_engine.py`     | ≥ 90%   | P06    |
| `app/services/pades_signer.py`     | ≥ 85%   | P07    |
| `app/services/pades_verifier.py`   | ≥ 85%   | P08    |
| `app/core/errors.py`               | ≥ 95%   | P01    |
| `app/core/audit.py`                | ≥ 95%   | P01    |
| `app/core/security.py`             | ≥ 90%   | P12    |
| Modul backend lainnya              | ≥ 75%   | —      |
| `frontend/src/coords.js`           | ≥ 90%   | P10    |
| `frontend/src/api/client.js`       | ≥ 80%   | P09    |
| `frontend/src/state/store.js`      | ≥ 80%   | P09    |
| Modul frontend lainnya             | ≥ 70%   | —      |

### 5. Aturan Khusus per Domain

#### 5.1 Test Koordinat (P05, P10)

1. **Property-based roundtrip:** Gunakan `hypothesis` untuk menguji `display_to_pdf(pdf_to_display(x)) == x` pada rentang acak.
2. **Test vector bersama:** File `shared/test-vectors/coords.json` berisi minimal 20 kasus (4 rotasi × 5 ukuran kertas). Backend dan frontend membaca file yang sama.
3. **Posisi default:** Uji FR-07 untuk semua kombinasi rotasi dan CropBox. Deviasi maksimal 1 pt.
4. **Boundary:** u = 0, v = 0, u = Dw, v = Dh, w = 0, h = 0 (harus ditolak atau di-clamp).

#### 5.2 Test PAdES (P07, P08)

1. **Kebersihan log:** Setiap test PAdES wajib menggunakan fixture `caplog` dan memanggil `assert_no_secrets_in_log(caplog)`.
2. **Mock TSA/OCSP:** Test B-T/B-LT menggunakan fixture certomancer (P03). Jangan panggil TSA/OCSP nyata.
3. **Korpus verifikasi (P08):**
   - Dokumen valid → `TOTAL_PASSED`
   - Dokumen dimodifikasi setelah tanda tangan → `TOTAL_FAILED`
   - Byte PDF dirusak → `TOTAL_FAILED` atau `INDETERMINATE`
   - Sertifikat dicabut → `TOTAL_FAILED` dengan `revocation.status=REVOKED`
   - Sertifikat kedaluwarsa → `TOTAL_FAILED`
   - Root tidak dipercaya → `INDETERMINATE` (trust=trusted=false)
   - Multi-tanda tangan → semua `TOTAL_PASSED`
   - Dokumen tanpa tanda tangan → `NO_SIGNATURE`
4. **Validasi silang:** Setiap dokumen PAdES hasil test harus lolos `pyhanko sign validate` (jalankan di test integrasi atau skrip terpisah).

#### 5.3 Test Keamanan (P12)

1. **API key:** Test bahwa key salah → 401, key benar → 200, scope kurang → 403.
2. **Rate limit:** Test bahwa N request dalam T detik → 429.
3. **Kepemilikan:** Dokumen yang diunggah key A tidak dapat diakses key B → 404.
4. **Path traversal:** ID berisi `../` → 404, bukan akses file sistem.
5. **Body limit:** Request > batas → 413.

#### 5.4 Test Negatif & Boundary (Semua Prompt)

Setiap modul **wajib** memiliki minimal satu test untuk masing-masing:

1. **Input tidak valid:** `None`, string kosong, tipe salah, nilai di luar rentang.
2. **Boundary:** nilai minimum, maksimum, tepat di batas, tepat di luar batas.
3. **Keadaan kosong:** list kosong, dict kosong, string kosong, file 0 byte.
4. **Error propagation:** pastikan error dari dependency (IOError, TimeoutError) diterjemahkan ke `AppError` yang sesuai, bukan `500 INTERNAL_ERROR`.
5. **Idempotensi:** operasi yang sama dua kali memberikan hasil yang sama (atau error yang konsisten).

### 6. Integrasi dengan CI

Setiap prompt **wajib** memastikan test yang ditulis terintegrasi dengan CI:

1. Backend: `pytest --cov=app --cov-fail-under=75 --cov-report=term-missing` berjalan di job `backend` CI.
2. Frontend: `vitest run --coverage` berjalan di job `frontend` CI.
3. Test lambat (visual, validasi silang) diberi marker `pytest.mark.slow` dan tidak dijalankan di CI default.
4. Test yang membutuhkan container (E2E, smoke) tidak dijalankan di CI unit.

## Di Luar Lingkup

- Test E2E Playwright (ditangani P14).
- Test performa Locust/k6 (ditangani P14).
- Test keamanan ZAP/Trivy (ditangani P14).
- Checklist QA manual Adobe Acrobat (ditangani P14).

## Kriteria Selesai

Dokumen ini **bukan prompt sekali jalan** — melainkan panduan tetap. Kriteria selesai diukur per prompt implementasi:

- [ ] Setiap file test baru mengikuti pola assert di atas.
- [ ] Helper `assert_problem_details`, `assert_audit_chain_valid`, `assert_no_secrets_in_log` tersedia di `conftest.py`.
- [ ] Test koordinat menggunakan `hypothesis` property-based (backend) dan test vector bersama (frontend).
- [ ] Test PAdES memverifikasi kebersihan log.
- [ ] Test negatif & boundary ada untuk setiap modul baru.
- [ ] Cakupan modul inti memenuhi target §4.
- [ ] CI hijau dengan cakupan yang dilaporkan.

## Verifikasi (dijalankan di setiap prompt implementasi)

```bash
# Backend — semua test
cd backend && uv run pytest --cov=app --cov-fail-under=75 -v

# Backend — cakupan per modul inti
cd backend && uv run pytest --cov=app.domain.coords --cov=app.services --cov-report=term-missing

# Frontend — semua test
cd frontend && npx vitest run --coverage

# Pastikan tidak ada test yang dilewati tanpa alasan
cd backend && uv run pytest --co  # count test
```

## Penutup

- Dokumen ini adalah **panduan tetap** — tidak perlu dicentang di TODO.md sebagai item terpisah.
- Setiap prompt implementasi (P04–P13) **wajib** merujuk dokumen ini di bagian "Tugas" atau "Kriteria selesai".
- Bila ditemukan pola assert baru yang berguna, tambahkan ke PLAN.md §7a dan dokumen ini.
