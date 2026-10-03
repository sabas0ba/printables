"""Validate committed printable meshes against the v0.3 inspection report."""
import json
from build import OUT, PARTS, inspect


def main():
    report = json.loads((OUT / "validation.json").read_text())
    for part, quantity in PARTS.items():
        actual = inspect(OUT / f"{part}.stl")
        for key, value in actual.items():
            if report[part][key] != value:
                raise SystemExit(f"{part}: stale validation field {key}")
        if report[part]["quantity"] != quantity:
            raise SystemExit(f"{part}: stale quantity")
        print(f"Validated snapshot: {part}")


if __name__ == "__main__":
    main()
