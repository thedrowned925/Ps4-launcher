# Odium PS4 Launcher

Windows package catalog manager + planned native PlayStation 4 (GoldHEN 9.00) launcher.

**Status: milestone 0.2 — Windows GUI/CLI review alpha, explicit Hugging Face package staging and portable transfer planner.** There is no PS4-installable PKG, tested console UI, or published online game catalog yet. No PKG has yet been built or tested on console.

## Components

| Component | Technology | Current state |
|---|---|---|
| PC Manager core | Python 3.11+, standard library | PKG header check, streamed SHA-256, SQLite review/approval, draft catalog export |
| PS4 transfer core | Portable C++17 | Range planner + host-native tests; not wired to native PS4 networking |
| Shared catalog | JSON specification | Validated package dependencies, firmware metadata, immutable IDs |
| Windows desktop UI | PySide6 | Alpha: batch import, local approval, draft export; NO upload |
| Hugging Face upload staging | huggingface_hub + Xet | CLI opt-in upload, hash/size verification and pinned revision; NO catalog publication |
| PS4 app/PKG | Planned: OpenOrbis | Not implemented |

## Run PC Manager prototype

Requires Python 3.11 or later; no dependency installation required for the CLI.

```sh
cd apps/pc-manager
python -m odium_pc scan "D:/Packages/authorized-demo.pkg"
python -m odium_pc list
python -m odium_pc approve "D:/Packages/authorized-demo.pkg" --game-id demo --game-title "Demo" --kind base --rights-confirmed
python -m odium_pc export --out catalog-draft.json
```

The demo commands require a real PS4 PKG. Source files are opened **read-only**. The approval operation records your *explicit confirmation of distribution rights*; it does not upload anything. Draft catalog output has no remote URL and cannot be installed by the PS4 app.

Test:
```sh
python -m unittest discover -s apps/pc-manager/tests -v
cmake -S apps/ps4-launcher -B /tmp/odium-build
cmake --build /tmp/odium-build
ctest --test-dir /tmp/odium-build --output-on-failure
```

Run the alpha GUI using [PC Manager instructions](apps/pc-manager/README.md) and follow [Windows testing steps](docs/TESTING.md). See [architecture](docs/ARCHITECTURE.md) and [roadmap](docs/ROADMAP.md).

## Security

- All rights to PKGs and artwork must be cleared before uploading to any **public** Hugging Face repository; owning a commercial game does not grant redistribution rights.
- No credentials in Git, client-side firmware modifications, or silent overwrites of package versions.
- Never treat a filename heuristic or claimed backport target as proof of runtime compatibility.
- PS4 homebrew APIs and native packaging must be validated against a real device and installed OpenOrbis toolchain; host compilation is **not** PS4 compilation.

Project created with assistance from AI; review and testing required before use.
