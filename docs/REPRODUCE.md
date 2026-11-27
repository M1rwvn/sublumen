# Reproducing the results
Run from `backend/`. The photo sets are public downloads and are not in the repo. Expected layout under `$SS_PHOTOS` (default `/tmp/real`):
`full_big/train/all/*.JPEG` (Imagenette full-size), `pets/images/*.jpg` (Oxford-IIIT Pets), `flowers/jpg/*.jpg` (Flowers102), `kodak/*.png` (Kodak, kodim01..24).
Sources: https://thor.robots.ox.ac.uk/pets/images.tar.gz , https://www.robots.ox.ac.uk/~vgg/data/flowers/102/102flowers.tgz , https://r0k.us/graphics/kodak/kodak/kodimNN.png , Imagenette from https://github.com/fastai/imagenette.
1. Tests: `pip install -r requirements.txt && python -m pytest -q` (6 tests skip without datasets).
2. Smoke run, minutes, proves the pipeline executes (numbers are meaningless): `SS_SMOKE=1 SS_PHOTOS=... SS_POOL=/tmp/pool SS_MODELS_OUT=/tmp/out python -m sublumen.ml_engine.repro all`
3. Full run, hours on one CPU, resumable per stage: `SS_PHOTOS=... python -m sublumen.ml_engine.repro all` (stages: covers, features, assemble, select, train, locked, export; run one stage with its name). Splits are fixed by file-name hash and photo family. The locked test is scored through `lockeval.py` and every look is logged in `data/pool/LOCKED_LOG.md`.
4. v7 benchmark with CIs: `python -m sublumen.benchmark.run_v7` (needs the v5 full-size dataset).
Status: the smoke run completed end to end in a fresh clone and fresh virtualenv in the author's sandbox. The full run was done in stages by hand earlier (same code); a single full `repro all` on another machine is NOT VERIFIED. Re-running will give slightly different numbers if the photo downloads differ.
