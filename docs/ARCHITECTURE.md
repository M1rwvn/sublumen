# Architecture
```
React UI (Vite, dist/) --HTTPS/JSON--> Flask API (sublumen/api) --> services --> SQLAlchemy --> SQLite | PostgreSQL
                                          |-- stego_core      Argon2id + AES-256-GCM, LSB embed/extract (sequential, keyed), PSNR/SSIM, LSB matching (benchmark only)
                                          |-- forensics_core  chi-square, RS, entropy, EXIF, compare, visual lab, C2PA
                                          |-- ml_engine       features (28 LSB + 125 SPAM), datasets, training, Detector (threshold-aware)
                                          |-- evidence_svc    cases, evidence, analysis runs, audit, model + benchmark registry
                                          |-- report_svc      PDF built only from stored rows (reportlab, Arabic via embedded Noto Sans Arabic)
                                          |-- security        auth (Argon2id hashes, signed expiring tokens, roles), validation, rate limits
                                          |-- benchmark       seeded attack/defense runs, JSON results in docs/
```
Data flow for an analysis: upload -> validate (magic bytes, size, pixel cap) -> SHA-256 -> original saved read-only under a random name -> `POST /analyses` runs statistics, C2PA check and the selected model -> result JSON stored with the run and an audit event -> report generation reads only stored rows (hence byte-identical re-generation).

Key decisions
- No verdicts: the API returns indicators and a model score with limitations, `verdict` is always null.
- Models are files (`models/<name>_<algo>.joblib` + `.metrics.json`) registered at startup; the default is one constant (`DEFAULT_MODEL`).
- Detector accepts a decision threshold chosen on validation data, never on test data.
- Payload magic bytes stay `SSX1` (file-format id kept from the original project name).
- First boot (create tables, register models, seed admin) is serialised with a PostgreSQL advisory lock so several gunicorn workers can start together.
