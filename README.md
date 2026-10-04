# printables

3D-printable designs and source files.

| Design | Files | Notes |
| --- | --- | --- |
| [Mi Vacuum Cleaner Mini holder](mi-vacuum-cleaner-mini/README.md) | STL, CadQuery source, three views and preview | Horizontal cradle with nozzle and charging-port access |
| [Stackable chili drying basket](chili-drying-rack/README.md) | STL, CadQuery source, dimensioned views and assembly preview | Sliding baskets, V supports, harvest-date wheels and removable drip tray; all printed |
| [ThinkPad E14 stand](thinkpad-e14-stand/README.md) | STL, CadQuery source, three views, preview and usage views | One reclined slot for closed storage or display-only open use; trays for the AC adapter and a mouse |
| [Tool-free slipper stand](slipper-stand/README.md) | STL, OpenSCAD source, assembly and joint previews | Four pairs; inward-facing soles; rounded edges and printed locking pins; prototype |

## Reproducing the outputs

The Nix flake pins the Python and `uv` toolchain. `pyproject.toml` defines
direct dependencies and version constraints; `uv.lock` records the exact
resolved versions and distribution SHA-256 hashes. The Docker image uses the
same flake and a fixed Nix base-image digest. On Linux, run:

```sh
nix develop --command sh scripts/setup-env.sh
nix develop --command .venv/bin/python scripts/generate_all.py --check
```

Or use Docker, without installing Python packages on the host:

```sh
docker build -t printables-check .
docker run --rm --network none printables-check
```

To write regenerated files into your checkout, bind-mount it and omit
`--check`:

```sh
docker run --rm -v "$PWD:/workspace" printables-check \
  nix develop --offline --command /opt/printables-venv/bin/python scripts/generate_all.py
```

For the CadQuery designs, `--check` compares STL and PNG files byte-for-byte
with the committed artifacts. CI performs that check inside the container with
networking disabled. The OpenSCAD slipper stand is a v0.3 snapshot: the same
command validates its committed printable meshes and report, without regenerating
its geometry or previews. See its README for separate regeneration commands.

When deliberately updating a dependency, edit `pyproject.toml`, regenerate
the lock, then rebuild and run the container check:

```sh
nix develop --command uv lock
```

Unless otherwise noted, this repository is licensed under
[CC BY-SA 4.0](LICENSE.md).

