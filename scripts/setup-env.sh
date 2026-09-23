#!/bin/sh
set -eu

environment=${PRINTABLES_VENV:-.venv}
uv venv --python python3.12 "$environment"
uv pip install --python "$environment/bin/python" --no-deps -r requirements.lock
uv pip check --python "$environment/bin/python"
