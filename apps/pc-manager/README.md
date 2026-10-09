# Odium PC Manager

## Milestone 0.1

The **CLI** works with Python 3.11+ and no external packages. The **alpha UI**
supports multiple-PKG import in a background hashing thread, local review,
metadata editing, manual rights confirmation and export of an **offline**
catalog draft. It is **not an uploader** yet; no files are sent to Hugging Face.

### Windows alpha GUI

From the repository root:

\`\`\`powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r apps/pc-manager/requirements-gui.txt
$env:PYTHONPATH="apps/pc-manager"
python -m odium_pc.gui
\`\`\`

The GUI saves metadata at \`%LOCALAPPDATA%\Odium\PS4-PC-Manager\review.sqlite3\`.
It does not copy, modify or delete source PKGs. Package type detection is only
a filename **guess**; you must manually confirm game identity, firmware,
dependencies, and redistribution rights.

A tray icon lets you hide/reopen the review window. Actual background **uploads**,
resume on Windows sign-in, catalog publishing and IGDB are later milestones;
the menu currently does not advertise unimplemented upload controls.

### Headless/CLI

\`\`\`powershell
$env:PYTHONPATH="apps/pc-manager"
python -m odium_pc --db review.sqlite3 scan "D:\Demo\Authorized.pkg"
python -m odium_pc --db review.sqlite3 list
python -m odium_pc --db review.sqlite3 recover
python -m odium_pc --db review.sqlite3 export --out draft.json
\`\`\`
