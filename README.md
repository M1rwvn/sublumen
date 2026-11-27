# Sublumen
**Find what the pixels hide.**

Sublumen is a steganography and digital-forensics workbench with a web UI and an API. It hides an encrypted message in an image (Stego Studio) and examines an image for signs that something was hidden: statistical tests, a machine-learning detector, and visual tools. Every step is kept in a case file with SHA-256 hashes, an audit trail and a reproducible PDF report, with the limits of each result stated next to the result.

**Who it is for:** forensic and security analysts who need a documented, repeatable first look at an image, researchers who want a transparent LSB-steganalysis baseline, and teams that want to embed and extract messages in a controlled way.

**Status at a glance**
- Works and tested: AES-256-GCM embedding and extraction, case and evidence handling with an audit trail, PDF reports, 6 statistical indicators, the v8 detector, a React UI (light and dark themes, Arabic text support, 0 axe violations on the audited screens), and an OpenAPI description. The test suite passes in CI (`pytest` for the backend, `vitest` and a build for the frontend).
- Measured on a locked test of unseen photos (`docs/locked_eval_v8.json`): the v8 detector separates clean from stego images with AUC 0.99 on lossless photos from two families it never saw in training. Clean false alarms are about 2-6% at the chosen threshold.
- **NOT VERIFIED:** Docker deployment; third-party steganography tools and non-LSB methods; JPEG-recompressed stego (mostly missed, about 7% recall); camera RAW and BOSSBase; running on other machines beyond CI. Details are in `docs/LIMITATIONS.md` and in the results section below.

![Demo case](docs/img/demo-case.png)

> **Models in this repository:** only `model_v8_hgb` (about 2 MB) is included. Older models (v1 to v7, up to 17 MB each) were left out to keep the repository small; the Models tab and benchmark docs still describe v7 and older, and the v7 comparison in the `locked` reproduction stage needs `backend/models/model_v7_svm_rbf.joblib`, which is not included. Everything about v8 can be rebuilt with `docs/REPRODUCE.md`.

## What is in it
| Area | What it does |
|---|---|
| Stego Studio | Argon2id key derivation + AES-256-GCM, then LSB embedding (sequential, or keyed pseudo-random order). Reports PSNR/SSIM. Extract needs the right password; tampering is rejected (GCM tag). |
| Forensics | Chi-square, RS estimate, LSB entropy/ratio, neighbour correlation, EXIF, C2PA Content Credentials check, SHA-256. |
| ML detector | `model_v8` (default): gradient boosting on 137 LSB/SPAM features + 700 SRM-lite residual co-occurrence features, scored over up to 8 evenly spaced 128px tiles. `model_v7` (default until v8): RBF-SVM on 12 position-free LSB features + 125 SPAM residual features, trained on Imagenette 160px crops, full-size decoded JPEG crops and synthetic covers, threshold set on validation data. `model_v6` and older stay selectable. RF, MLP, ensemble and calibrated variants are selectable. |
| Visual Lab / Compare | Bit planes, anomaly heatmap, difference map, SSIM dashboard and SSIM map. |
| Evidence | Case + evidence manager (originals stored read-only, SHA-256 at intake, audit trail), PDF report built only from stored records (same case = same bytes), Arabic text supported. |
| Benchmark Lab | Recorded attack-and-defense runs (replacement, keyed, LSB matching, JPEG, resize) with fixed seeds. |
| Platform | Flask + SQLAlchemy (SQLite or PostgreSQL), React/Vite UI (dark/light, mobile), role-based auth, upload validation, rate limits. |

![Compare and SSIM](docs/img/compare-ssim.png)

## Results (held-out, honest)
Two held-out sets, built from source photos never used for training or validation: **imagenette160** (450 clean covers: 300 crops of 160px Imagenette photos plus synthetic types) and **fullsize** (600 clean 128px crops of full-size decoded Imagenette JPEGs). 95% CIs are cluster bootstraps over covers (2000 resamples). Source: `docs/benchmark_v7.json` (`python -m sublumen.benchmark.run_v7`), also shown in the Benchmark Lab tab.

| Clean-PNG false alarms | v5 | v6 | v7 (default) |
|---|---|---|---|
| imagenette160 real photos (n=300) | 18.0% | 7.3% (4.7-10.3) | 2.3% (0.7-4.3) |
| fullsize crops (n=600) | 31.2% | 28.7% (25.0-32.3) | 7.5% (5.5-9.7) |

| Recall (v7, own threshold) | imagenette160 | fullsize |
|---|---|---|
| Sequential replacement 10% / 25% payload | 55% / 92% | 43% / 83% |
| LSB matching 25% / 50% payload | 45% / 62% | 37% / 55% |
| After JPEG q95 recompression (50% payload, replace) | 16% | 7% |

At a matched 5% false-alarm rate on the fullsize set, v7 beats v6 clearly (replace 25%: 0.80 vs 0.39; matching 50%: 0.50 vs 0.26). In a small check on 3 other photos (120 crops, 3 sources, noisy) v7 flags about 17% of clean crops (one photo 42%) versus 57% for v6.

![Analysis result: partly embedded photo](docs/img/analysis-result-embedded.png)

The screenshot shows a Kodak photo whose top half was overwritten with random LSBs: the model overlay scores the top tiles 1.00 and the clean bottom tiles 0.03-0.15. User guide: `docs/USER_GUIDE.md`. Setup and GitHub steps: `docs/GETTING_STARTED.md`. Reproduction: `docs/REPRODUCE.md`.

**v8 locked test** (`docs/locked_eval_v8.json`, scored once, log in `backend/data/pool/LOCKED_LOG.md`; photos never used for training or threshold choice, Flowers and Kodak are whole families unseen in training): AUC clean vs stego v7 -> v8: flowers 0.88 -> 0.995, Kodak 0.77 -> 0.996, pets 0.75 -> 0.989. v8 clean-PNG false alarms at the validation threshold: flowers 5.0%, Kodak 2.3%, pets 6.0%. Recall at that threshold for LSB matching 10% payload: 0.87-0.93 (v7 0.02-0.12). Small check with an independent plain LSB / random +-1 implementation on 14 full-size photos: all 20%-payload +-1 and 50% sequential LSB flagged; sequential LSB 10% (only the first 10% of pixels change): flowers 8/8, Kodak 0/6; 12% of clean JPEG-origin photos flagged. Still weak: JPEG-recompressed stego (about 7% recall), third-party tools and non-LSB methods NOT VERIFIED, small images less reliable.

Read the limits: v7 misses most JPEG-recompressed stego (v6 caught more of it but also flagged 12-21% of clean recompressed covers); LSB matching is still missed about half of the time; all photos are ImageNet-derived (not BOSSBase, not camera RAW). A single split with no cross-validation. See `docs/LIMITATIONS.md` and `docs/STATUS.md`.

## Run locally
    cd backend && pip install -r requirements.txt
    export SS_SECRET=$(openssl rand -hex 32) SS_ADMIN_EMAIL=you@x.org SS_ADMIN_PASSWORD='a-long-password'
    python -m flask --app wsgi run                 # http://localhost:5000  (UI is served from frontend-react/dist)
    cd frontend-react && npm install && npx vite build   # to (re)build the UI
Open the app, sign in, go to **Cases & Evidence**, click **load the demo case**.

PostgreSQL: set `SS_DB=postgresql+psycopg2://user:pass@host/db` (several gunicorn workers are safe; first boot is serialised by an advisory lock).
Docker: `POSTGRES_PASSWORD=... SS_SECRET=... SS_ADMIN_EMAIL=... SS_ADMIN_PASSWORD=... docker compose up --build` (config linted with hadolint and the compose-spec schema; `docker compose up` itself was NOT VERIFIED, no Docker engine was available).

## Tests
    cd backend && python -m pytest -q                      # some tests skip until datasets are built
    SS_TEST_DB=postgresql+psycopg2://... python -m pytest -q tests/test_api.py
    cd frontend-react && npx vitest run
    cd backend && PYTHONPATH=. BASE=http://localhost:5000 E=you@x.org P=... python ../ml/e2e/ui_e2e.py   # browser click-through

## Rebuild the ML evidence
    python -m sublumen.ml_engine.dataset --n-per-type 150 --out data/dataset_v1          # synthetic baseline
    # real photos: download Imagenette 160px (fast.ai, research use) to /tmp/real/imagenette2-160 (or set SS_REAL_DIR)
    python -m sublumen.ml_engine.dataset_v4 --out data/dataset_v4 --part 0 --parts 12     # repeat for parts 0..11, then concatenate part*.csv into dataset.csv
    python -m sublumen.ml_engine.train_v6 spam_all 0.05

## Documentation
- `docs/ARCHITECTURE.md` how the pieces fit
- `docs/THREAT_MODEL.md` what Sublumen protects, from whom, and what it does not
- `docs/LIMITATIONS.md` what does not work
- `docs/STATUS.md` full build log with VERIFIED / NOT VERIFIED labels

## Responsible use
Sublumen is for education, research, and evidence handling on images you are allowed to examine. A detector score is an indicator, never proof; the app deliberately never issues a "guilty" verdict.
