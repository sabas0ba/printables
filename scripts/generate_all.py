"""Regenerate all committed geometry and views; optionally verify exact bytes."""

import argparse
import hashlib
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
MODELS = {
    "mi-vacuum-cleaner-mini": ("holder.stl", "views.png", "preview.png"),
    "chili-drying-rack": ("rack.stl", "base.stl", "drip-tray.stl", "basket.stl",
                         "month-dial.stl", "day-dial.stl", "dial-clip.stl",
                         "basket-detail.png", "views.png",
                         "preview.png", "assembly.png", "drawer.png", "accessories.png"),
    "raspberry-pi-5-nvme-case": ("tray.stl", "lid.stl", "reference-assembly.stl",
                                 "views.png", "preview.png", "section.png"),
    "stackchan-hats": ("validation.json", "images/*.png", "stl/*.stl"),
}


def outputs():
    """Committed outputs; glob patterns expand to the files currently present."""
    paths = []
    for model, names in MODELS.items():
        for name in names:
            if "*" in name:
                paths.extend(sorted((ROOT / model).glob(name)))
            else:
                paths.append(ROOT / model / name)
    return paths


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="compare with committed outputs")
    args = parser.parse_args()
    previous = {path: path.read_bytes() for path in outputs()} if args.check else {}

    for model in MODELS:
        for name in ("generate.py", "render.py"):
            subprocess.run([sys.executable, str(ROOT / model / name)], cwd=ROOT, check=True)

    subprocess.run([sys.executable, str(ROOT / "slipper-stand/scripts/check.py")],
                   cwd=ROOT, check=True)
    current = outputs()
    if args.check and set(current) != set(previous):
        changed = sorted(str(p.relative_to(ROOT)) for p in set(current) ^ set(previous))
        raise SystemExit(f"Generated file set differs: {', '.join(changed)}")
    for path in current:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        print(f"{path.relative_to(ROOT)}  sha256:{digest}")
        if args.check and path.read_bytes() != previous[path]:
            raise SystemExit(f"Generated output differs: {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

