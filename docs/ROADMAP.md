# Delivery checkpoints

- [x] Initialize repository and CI.
- [x] Windows read-only PKG scan, SHA-256 fingerprint and SQLite review record.
- [x] Human approval gate for metadata and distribution rights.
- [x] Offline catalog draft + package/dependency validation, immutable ID convention.
- [x] Host-native C++ range planning baseline with tests.
- [ ] Windows premium GUI: bulk import/review, editable game relationships + install ordering.
- [ ] Real PS4 PKG PARAM.SFO parser and safer identity checks.
- [ ] IGDB and artwork acquisition on PC (credential protection, manual override and license metadata).
- [ ] HF publisher with verified uploads, atomic catalog revision, safe retry and Xet resume.
- [ ] Tray, startup recovery and worker queue; accurate status/throughput.
- [ ] PS4 renderer, input/audio/haptics, local game inventory and launch integration.
- [ ] PS4 HTTP range download with bounded HDD scheduler and durable chunk journal.
- [ ] Verified install orchestration, dependency selection, optional safe BGFT adapter.
- [ ] OpenOrbis packaging from pinned, trusted toolchain; real GoldHEN 9.00 PKG smoke test.

Always test download flow first with developer-authorized, small homebrew assets before attempting larger content.
