# Test Odium PC Manager — milestone 0.2

Important: use only your own or explicitly authorized homebrew PKGs. Never upload commercial game backups or someone else's DLC/backport files to PUBLIC Hugging Face.

## Test 1: Windows interface — no network upload

1. Clone or download this GitHub repository on a Windows PC with Python 3.11+.
2. Double-click scripts/start-pc-manager.bat. It creates an isolated .venv and installs PySide6 on the first run.
3. Click Import PKG files; select a SMALL authorized homebrew .pkg. No files are modified or uploaded.
4. Review title, Game ID, type (base/update/dlc/backport), version, firmware and optional sha256 package dependencies.
5. Only if you possess redistribution rights, check the rights confirmation and click Approve reviewed metadata.
6. Click Export draft catalog; ensure the JSON shows published=false.
7. Minimize/close to Windows tray and restore from tray icon.
8. Share any crash messages, GUI screenshots and which step failed. Do NOT share credentials.

## Test 2: offline CLI upload plan

Open PowerShell in repo root, run:

    $env:PYTHONPATH='apps/pc-manager'
    $db = "$env:LOCALAPPDATA/Odium/PS4-PC-Manager/review.sqlite3"
    python -m odium_pc --db "$db" list
    python -m odium_pc --db "$db" recover
    python -m odium_pc --db "$db" upload-plan --repo OWNER/AUTHORIZED-DATASET

upload-plan shows stable paths but DOES NOT contact HF or upload.

## Test 3: optional actual PUBLIC upload (authorized homebrew ONLY)

Only when you have a PUBLIC Hugging Face DATASET repo and rights to publish the test PKG:

    .venv\Scripts\python.exe -m pip install -r apps/pc-manager/requirements-upload.txt
    hf auth login
    $env:PYTHONPATH='apps/pc-manager'
    $db = "$env:LOCALAPPDATA/Odium/PS4-PC-Manager/review.sqlite3"
    python -m odium_pc --db "$db" upload-stage --repo OWNER/AUTHORIZED-DATASET --confirm-public
    python -m odium_pc --db "$db" export-ready --repo OWNER/AUTHORIZED-DATASET --out catalog-ready.json

Uploaded PKGs become public immediately; a live catalog is NOT published. Re-running stage for identical verified files should avoid reupload. If the remote ETag is not a reliable SHA-256, stage fails closed.

## PS4 console

NOT YET READY. This milestone builds and tests C++ on desktop only. No legitimate Odium PS4 PKG can be downloaded yet.
