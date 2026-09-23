"""Regenerate all committed geometry and views; optionally verify exact bytes."""

import argparse
import hashlib
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "mi-vacuum-cleaner-mini"
OUTPUTS = [MODEL / name for name in ("holder.stl", "views.png", "preview.png")]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="compare with committed outputs")
    args = parser.parse_args()
    previous = {path: path.read_bytes() for path in OUTPUTS} if args.check else {}

    for script in (MODEL / "generate.py", MODEL / "render.py"):
        subprocess.run([sys.executable, str(script)], cwd=ROOT, check=True)

    for path in OUTPUTS:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        print(f"{path.relative_to(ROOT)}  sha256:{digest}")
        if args.check and path.read_bytes() != previous[path]:
            raise SystemExit(f"Generated output differs: {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
