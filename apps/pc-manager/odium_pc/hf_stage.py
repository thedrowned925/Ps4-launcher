"""Explicit, fail-closed staging of approved packages to a PUBLIC Hugging Face dataset.

No catalog is published by this module. Uploaded packages are pinned to a commit
and verified with remote ETag (SHA-256) + size before local stage records are saved.

Real network access is opt-in from the CLI; tests inject fake remote adapters.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from typing import Any, Callable

from .catalog import CatalogError, immutable_remote_path, validate_catalog
from .store import PackageStore

REPO_ID = re.compile(r"^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$")
REVISION = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True)
class UploadTask:
    local_path: str
    package_id: str
    remote_path: str
    size_bytes: int
    sha256: str


def prepare_tasks(store: PackageStore, repo_id: str) -> list[UploadTask]:
    if not REPO_ID.fullmatch(repo_id):
        raise CatalogError("Expected an owner/dataset Hugging Face repo ID")
    catalog = store.export_draft()  # Checks reviewed dependencies and rights gate.
    if not catalog["games"]:
        raise CatalogError("No approved PKGs. Scan and manually review first.")
    rows = {f"sha256:{r['sha256']}": r for r in store.rows()
            if r["approved"] and r["rights_confirmed"]}
    result: list[UploadTask] = []
    for game in catalog["games"]:
        for pkg in game["packages"]:
            row = rows[pkg["package_id"]]
            result.append(UploadTask(
                local_path=row["path"],
                package_id=pkg["package_id"],
                remote_path=immutable_remote_path(game["game_id"], pkg["kind"],
                                                  pkg["sha256"]),
                size_bytes=pkg["size_bytes"], sha256=pkg["sha256"]))
    return result


def _validate_remote(metadata: Any, task: UploadTask, revision: str) -> None:
    # HF's LFS/Xet ETag is the source file SHA-256. A weak or missing ETag is
    # insufficient evidence for safe publication, even when size agrees.
    etag = getattr(metadata, "etag", None)
    size = getattr(metadata, "size", None)
    commit = getattr(metadata, "commit_hash", None)
    if not isinstance(etag, str) or etag.strip('"').lower() != task.sha256:
        raise CatalogError(
            f"Remote SHA-256 unavailable/mismatch for {task.remote_path}; "
            "file is not approved for catalog publication")
    if type(size) is not int or size != task.size_bytes:
        raise CatalogError(f"Remote size mismatch for {task.remote_path}")
    if commit != revision:
        raise CatalogError(f"Remote revision mismatch for {task.remote_path}")


def stage_approved(store: PackageStore, repo_id: str, *,
                   api: Any | None = None,
                   metadata: Callable[..., Any] | None = None,
                   url_builder: Callable[..., str] | None = None,
                   on_progress: Callable[[str], None] | None = None) -> list[dict[str, str]]:
    """Upload files WITHOUT changing catalog/current.json.

    Requires existing public dataset repo, a logged-in HF account/write token,
    and previously approved package metadata. Uses commit-level optimistic lock.
    """
    if api is None or metadata is None or url_builder is None:
        try:
            from huggingface_hub import HfApi, hf_hub_url
            from huggingface_hub.file_download import get_hf_file_metadata
        except ImportError as exc:
            raise RuntimeError(
                "Install huggingface_hub with Xet support before live uploading"
            ) from exc
        api = api or HfApi()
        metadata = metadata or get_hf_file_metadata
        url_builder = url_builder or hf_hub_url

    # Re-hash the original files. If a source changed, disapprove it and stop,
    # rather than uploading a different file under an approved fingerprint.
    recovery = store.recover_approved()
    bad = [(p, s) for p, s in recovery if s != "approved"]
    if bad:
        raise CatalogError(f"Source preflight failed (no upload): {bad}")
    tasks = prepare_tasks(store, repo_id)
    results: list[dict[str, str]] = []
    send = on_progress or (lambda msg: None)
    for task in tasks:
        info = api.repo_info(repo_id=repo_id, repo_type="dataset")
        if getattr(info, "private", None) is not False:
            raise CatalogError("Upload refused: repository must exist and be PUBLIC")
        revision = getattr(info, "sha", "")
        if not isinstance(revision, str) or not REVISION.fullmatch(revision):
            raise CatalogError("Could not pin remote dataset commit")
        matches = api.get_paths_info(repo_id=repo_id, repo_type="dataset",
                                     revision=revision, paths=[task.remote_path])
        already = any(getattr(item, "path", None) == task.remote_path for item in matches)
        if not already:
            send(f"Uploading {task.remote_path} from original source")
            commit = api.upload_file(
                path_or_fileobj=task.local_path, path_in_repo=task.remote_path,
                repo_id=repo_id, repo_type="dataset", parent_commit=revision,
                commit_message=f"Add reviewed immutable package {task.sha256[:12]}")
            revision = getattr(commit, "oid", "")
            if not isinstance(revision, str) or not REVISION.fullmatch(revision):
                raise CatalogError("Upload returned no verifiable commit SHA")
        else:
            send(f"Immutable remote path exists, checking: {task.remote_path}")

        # Resolve the *pinned* revision, not mutable main or a temporary CDN URL.
        url = url_builder(repo_id=repo_id, filename=task.remote_path,
                          revision=revision, repo_type="dataset")
        _validate_remote(metadata(url), task, revision)
        store.record_staged(task.local_path, repo_id=repo_id, revision=revision,
                            remote_path=task.remote_path, digest=task.sha256)
        send(f"Verified remote SHA-256 and size: {task.remote_path}")
        results.append({"package_id": task.package_id, "revision": revision,
                        "remote_path": task.remote_path, "repo_id": repo_id})
    return results


def create_ready_catalog(store: PackageStore, repo_id: str) -> dict[str, Any]:
    """Local export only. No network call or public index publication occurs."""
    catalog = copy.deepcopy(store.export_draft())
    staged = store.staged_rows(repo_id)
    for game in catalog["games"]:
        for pkg in game["packages"]:
            record = staged.get(pkg["package_id"])
            if not record:
                raise CatalogError("Package not staged/verified: " + pkg["package_id"])
            pkg["source"] = {
                "repo_id": repo_id, "revision": record["revision"],
                "path": record["remote_path"]}
    catalog["published"] = True  # Schema shape suitable for later publishing.
    validate_catalog(catalog)
    return catalog
