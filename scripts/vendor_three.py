"""Fetch or verify the vendored three.js files listed in site/vendor/three.toml.

The files are taken from the pinned commit of the upstream Git repository with
`git show`; nothing from the npm registry is used and no upstream code is run.

  vendor_three.py           fetch the files and require the recorded hashes
  vendor_three.py --record  fetch the files and record their hashes
  vendor_three.py --check   verify the committed files offline
"""

import argparse
from dataclasses import dataclass
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import tomllib


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "site/vendor/three.toml"
VENDOR_DIR = ROOT / "site/vendor/three"
WORK_DIR = ROOT / ".work/three-src"
MANIFEST_HEADER = """\
# Vendored three.js files for the STL viewer on the GitHub Pages site.
# Fetched from the upstream Git tag, not from the npm registry.
# `scripts/vendor_three.py` fetches the files; `--check` verifies the hashes offline.
"""


@dataclass(frozen=True)
class VendoredFile:
    source: str
    target: str
    sha256: str


@dataclass(frozen=True)
class Manifest:
    repository: str
    tag: str
    commit: str
    license: str
    files: tuple[VendoredFile, ...]


def load_manifest(path: Path = MANIFEST) -> Manifest:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    files = tuple(VendoredFile(f["source"], f["target"], f["sha256"]) for f in data["files"])
    return Manifest(data["repository"], data["tag"], data["commit"], data["license"], files)


def format_manifest(manifest: Manifest) -> str:
    lines = [MANIFEST_HEADER,
             f'repository = "{manifest.repository}"',
             f'tag = "{manifest.tag}"',
             f'commit = "{manifest.commit}"',
             f'license = "{manifest.license}"']
    for item in manifest.files:
        lines += ["", "[[files]]",
                  f'source = "{item.source}"',
                  f'target = "{item.target}"',
                  f'sha256 = "{item.sha256}"']
    return "\n".join(lines) + "\n"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def check(manifest: Manifest, vendor_dir: Path = VENDOR_DIR, root: Path = ROOT) -> list[str]:
    """Return a list of problems with the files on disk; empty if they match."""
    problems = []
    expected = {item.target for item in manifest.files}
    for item in manifest.files:
        path = vendor_dir / item.target
        if not path.is_file():
            problems.append(f"missing: {path.relative_to(root)}")
        elif sha256(path.read_bytes()) != item.sha256:
            problems.append(f"hash mismatch: {path.relative_to(root)}")
    for path in sorted(p for p in vendor_dir.rglob("*") if p.is_file()):
        if path.relative_to(vendor_dir).as_posix() not in expected:
            problems.append(f"not in manifest: {path.relative_to(root)}")
    return problems


def git(*args: str) -> bytes:
    return subprocess.run(["git", "-C", str(WORK_DIR), *args],
                          check=True, capture_output=True).stdout


def fetch(manifest: Manifest) -> dict[str, bytes]:
    """Fetch the pinned commit without blobs, then read only the listed files."""
    shutil.rmtree(WORK_DIR, ignore_errors=True)
    WORK_DIR.mkdir(parents=True)
    git("init", "--quiet")
    git("fetch", "--quiet", "--depth", "1", "--filter=blob:none",
        manifest.repository, manifest.commit)
    fetched = git("rev-parse", "FETCH_HEAD").decode().strip()
    if fetched != manifest.commit:
        raise SystemExit(f"Fetched {fetched}, expected {manifest.commit}")
    return {item.source: git("show", f"{manifest.commit}:{item.source}")
            for item in manifest.files}


def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="verify committed files offline")
    mode.add_argument("--record", action="store_true", help="record hashes of fetched files")
    args = parser.parse_args()
    manifest = load_manifest()

    if args.check:
        problems = check(manifest)
        for problem in problems:
            print(problem, file=sys.stderr)
        if problems:
            raise SystemExit(1)
        print(f"three.js {manifest.tag}: {len(manifest.files)} files match")
        return

    contents = fetch(manifest)
    if args.record:
        manifest = Manifest(manifest.repository, manifest.tag, manifest.commit, manifest.license,
                            tuple(VendoredFile(f.source, f.target, sha256(contents[f.source]))
                                  for f in manifest.files))
    for item in manifest.files:
        if sha256(contents[item.source]) != item.sha256:
            raise SystemExit(f"Hash mismatch for {item.source}; use --record after review")

    shutil.rmtree(VENDOR_DIR, ignore_errors=True)
    for item in manifest.files:
        path = VENDOR_DIR / item.target
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(contents[item.source])
    MANIFEST.write_text(format_manifest(manifest), encoding="utf-8")
    print(f"three.js {manifest.tag}: wrote {len(manifest.files)} files")


if __name__ == "__main__":
    main()
