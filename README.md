# printables

3D-printable designs and source files.

| Design | Files | Notes |
| --- | --- | --- |
| [Mi Vacuum Cleaner Mini holder](mi-vacuum-cleaner-mini/README.md) | STL, CadQuery source, three views and preview | Horizontal cradle with nozzle and charging-port access |

## Reproducing the outputs

The Nix flake pins the Python and `uv` toolchain; `requirements.in` lists
direct and transitive Python package versions, while `requirements.lock` adds
distribution SHA-256 hashes. Installation rejects packages whose hashes do
not match. The Docker image uses the same flake and a fixed Nix base-image
digest. On Linux, run:

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

The `--check` mode compares STL and PNG files byte-for-byte with the committed
artifacts. CI performs that check inside the container with networking disabled.

When deliberately updating a dependency, edit `requirements.in`, regenerate
the lock, then rebuild and run the container check:

```sh
nix develop --command uv pip compile --no-deps --generate-hashes \
  --output-file requirements.lock requirements.in
```

Unless otherwise noted, this repository is licensed under
[CC BY-SA 4.0](LICENSE.md).
