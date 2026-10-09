"""PC Manager CLI: local review, optional explicit HF staging (never auto-publishes)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .ingest import inspect_pkg
from .store import PackageStore


def run() -> None:
    parser = argparse.ArgumentParser(prog="odium-pc", description="Odium package review CLI")
    parser.add_argument("--db", default="odium-pc.sqlite3",
                        help="Local review database location")
    sub = parser.add_subparsers(dest="command", required=True)
    p_scan = sub.add_parser("scan", help="Read-only scan of PKG files")
    p_scan.add_argument("files", nargs="+")
    sub.add_parser("list", help="View local review queue")
    p_approve = sub.add_parser("approve", help="Explicitly approve one scanned PKG")
    p_approve.add_argument("path")
    p_approve.add_argument("--game-id", required=True)
    p_approve.add_argument("--game-title", required=True)
    p_approve.add_argument("--kind", choices=["base", "update", "dlc", "backport"], required=True)
    p_approve.add_argument("--version", default="1.00")
    p_approve.add_argument("--target-firmware")
    p_approve.add_argument("--requires", action="append", default=[], help="sha256:<64 hex>")
    p_approve.add_argument("--rights-confirmed", action="store_true")
    sub.add_parser("recover", help="Re-hash approved packages after interruptions")
    p_export = sub.add_parser("export", help="Export offline non-installable draft")
    p_export.add_argument("--out", required=True)
    p_plan = sub.add_parser("upload-plan", help="Show remote paths; no network upload")
    p_plan.add_argument("--repo", required=True, help="Public owner/dataset on Hugging Face")
    p_upload = sub.add_parser("upload-stage", help="Explicitly upload approved PKGs, NOT catalog")
    p_upload.add_argument("--repo", required=True)
    p_upload.add_argument("--confirm-public", action="store_true",
                          help="Acknowledge uploads are public, authorized and irreversible")
    p_ready = sub.add_parser("export-ready", help="Export local catalog with pinned verified URLs")
    p_ready.add_argument("--repo", required=True)
    p_ready.add_argument("--out", required=True)
    args = parser.parse_args()
    with PackageStore(args.db) as store:
        if args.command == "scan":
            for file in args.files:
                probe = inspect_pkg(file)
                store.put_probe(probe)
                print(f"REVIEW: {probe.filename} [{probe.guessed_kind}?] {probe.size_bytes} bytes "
                      f"SHA256={probe.sha256}")
        elif args.command == "list":
            for row in store.rows():
                print(f"{row['state']:>11} | {row['filename']} | "
                      f"{row['game_id'] or '?'} | {row['guessed_kind']}?")
        elif args.command == "approve":
            store.approve(args.path, game_id=args.game_id,
                          game_title=args.game_title, kind=args.kind,
                          version=args.version, target_firmware=args.target_firmware,
                          required_package_ids=args.requires,
                          rights_confirmed=args.rights_confirmed)
            print("APPROVED locally; no network upload performed.")
        elif args.command == "recover":
            for path, status in store.recover_approved():
                print(f"{status}: {path}")
        elif args.command == "upload-plan":
            from .hf_stage import prepare_tasks
            for task in prepare_tasks(store, args.repo):
                print(f"{task.size_bytes:>15} bytes {task.sha256} "
                      f"{task.local_path} -> {task.remote_path}")
            print("DRY RUN ONLY: Nothing uploaded.")
        elif args.command == "upload-stage":
            if not args.confirm_public:
                parser.error("Explicit --confirm-public required before uploading")
            from .hf_stage import stage_approved
            staged = stage_approved(store, args.repo, on_progress=print)
            print(f"VERIFIED {len(staged)} package(s); catalog was NOT published.")
        elif args.command == "export-ready":
            from .hf_stage import create_ready_catalog
            catalog = create_ready_catalog(store, args.repo)
            out = Path(args.out)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
            print(f"Locally saved {out}. NOT published online.")
        elif args.command == "export":
            catalog = store.export_draft()
            out = Path(args.out)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
            print(f"Saved offline draft to {out} (not published/PS4 installable).")


if __name__ == "__main__":
    run()
