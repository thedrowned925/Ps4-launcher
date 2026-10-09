# Odium architecture / decisions

## Requirements (approved by project owner)

- PS4 with firmware **9.00**, **GoldHEN**, ~1 TB internal mechanical HDD; the exact console model is unknown.
- Windows PC Manager: import multiple **.pkg** files without copying; streamed hash; propose metadata; **mandatory human review** of title/package type/dependencies/backport targets; publish immutable versions. Background tray worker, auto-resume on Windows sign-in (future milestones).
- PS4 Launcher: library + catalog hybrid, locally enumerate installed titles, launch installed games, manually select Base/Update/DLC/Backport; infer missing dependencies and **ask for approval of the full plan**.
- One active game download, persistent unbounded queue. Within that download adaptive HTTP ranges are allowed. Direct-to-file avoids a second full-size merge. Slow mechanical HDD: bounded memory and write reordering.
- Download integrity takes priority over background transfer. BGFT integration is conditional on pre-install verification being achievable; otherwise foreground with safe pause/resume.
- Persist chunk journal, pin immutable remote commit/path/size/hash; confirm SHA-256 *before* installation. Fail closed if source changes or install status is uncertain.
- After separately verified successful installation only, remove the managed temporary PKG. Never delete a temporary PKG on install failure or uncertain status. Stop the entire queue on install failure.
- Public Hugging Face content only when redistribution is authorized; no PS4 token, Windows token stays in OS credentials/environment, never in Git.
- PC artwork auto-match IGDB/SteamGridDB with manual corrections, copyright and API terms respected; hashes and lazy disk cache on PS4.
- Launcher starts with local cached catalog, verifies new catalog at startup, offers manual refresh (no repeated polling). Atomic catalog replacement on successful validation only.
- UI: minimal, premium, calm charcoal/neutral; large horizontal cinematic hero (subtle pan/zoom), vertical cover grids; deep technical progress panel as optional view. Premium sounds and subtle DualShock 4 haptics; 60 FPS **target**, not guarantee.

## Separation of responsibilities

**PC Manager** owns file analysis, human review, immutable upload path assignment, remote publishing, image preparation and signed/pinned catalog generation. Publishing must occur **after** all verified blobs are present.

**PS4 Launcher** consumes read-only catalog, inventories installed titles, plans manual installations and performs guarded download/install operations. The PS4 never calls IGDB directly or stores an HF write token.

**Shared catalog v1** records game IDs, packages, package IDs, type, SHA-256, size, dependency list and optional firmware compatibility metadata. An unpublished local draft has \`published: false\`; a published PS4-installable catalog must supply per-package immutable \`source\` with repo/revision/path.

## Integrity invariants

1. Content-addressed package ID: SHA-256 digest, not a mutable filename.
2. Download tasks bind to repo, commit, path, SHA-256, and byte length, never mutable \`main\`.
3. Remote changes don't mutate in-flight tasks.
4. Resume requires re-validation of durable chunks; journal marked only after durable writes.
5. Install never begins before complete verified byte stream and dependency validation.
6. No cleanup until installation result + installed application identity/version checked.
7. Catalog draft may contain warnings/incomplete mappings; publication must reject missing sources, wrong IDs and dependency cycles.

## Current milestone limitations

The PC CLI validates only a recognized PS4 PKG header \`0x7F434E54\` and its hash; it does **not** parse PARAM.SFO, decrypt anything, validate PKG signatures or automatically certify DLC/backport compatibility. These require later readers/integrations. No upload or PS4 system calls are included yet.

The C++ host transfer planner is platform-neutral and tested on desktop; no claims of native PS4 build or reliable BGFT support are made.

## Proposed repo layout

\`\`\`
apps/pc-manager/      # Python core, then PySide6 desktop UI
apps/ps4-launcher/    # C++ core, then PS4 platform layer and renderer
shared/               # Catalog schemas and examples
docs/                 # Design + integration decisions
.github/workflows/    # Host tests; PS4 packaging later after toolchain validation
\`\`\`
