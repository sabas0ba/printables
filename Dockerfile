# Same pinned Nix toolchain as `nix develop`; based on sabas0ba/dotfiles.
ARG NIX_VERSION=2.35.1
ARG NIX_IMAGE_DIGEST=sha256:377d4887aca98f0dfa12971c1ea6d6a625a435d8b610d4c95a436843da6fbfd1
FROM nixos/nix:${NIX_VERSION}@${NIX_IMAGE_DIGEST}

RUN mkdir -p /etc/nix \
    && printf '%s\n' 'experimental-features = nix-command flakes' \
      'sandbox = false' 'filter-syscalls = false' >> /etc/nix/nix.conf

WORKDIR /workspace
COPY flake.nix flake.lock pyproject.toml uv.lock ./
COPY scripts/setup-env.sh ./scripts/setup-env.sh

# Keep the Python environment outside /workspace so bind mounts do not hide it.
ENV PRINTABLES_VENV=/opt/printables-venv
RUN nix develop --command sh scripts/setup-env.sh

COPY . .
CMD ["nix", "develop", "--offline", "--command", "/opt/printables-venv/bin/python", "scripts/generate_all.py", "--check"]
