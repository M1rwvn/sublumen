# Run locally and publish to GitHub
## Run
1. Install Python 3.10+ and Node 18+.
2. `bash scripts/setup_and_run.sh` (creates `.venv`, installs, builds the UI, runs the tests, starts the app on http://localhost:5000). Change the admin password with `SS_ADMIN_PASSWORD=... scripts/setup_and_run.sh`.
3. Manual route: see the README ("Run").
## Publish to GitHub yourself
1. Unpack the sources: save the delivered files in one folder (`sublumen-unpacker.py`, `sublumen-bundle.part1`, `sublumen-bundle.part2`), then `cat sublumen-bundle.part* > bundle.txt && python3 sublumen-unpacker.py unpack bundle.txt sublumen && cd sublumen`.
2. `git init -b main && git add -A && git commit -m "Sublumen"` (the delivered history may be included instead).
3. Create an empty repository on GitHub, then `git remote add origin <url> && git push -u origin main`.
4. Before pushing: pick a license (the LICENSE file is only a placeholder), and check that no secret is in the tree (`SS_SECRET` and passwords are environment variables, never files).
5. The large `data/` folder is ignored on purpose; the trained models are in `backend/models` (the repo holds 74 MB of models; the text bundle carries only v8 and v7).
