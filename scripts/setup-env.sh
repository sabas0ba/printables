#!/bin/sh
set -eu

environment=${PRINTABLES_VENV:-.venv}
UV_PROJECT_ENVIRONMENT="$environment" uv sync --locked --no-dev --python python3.12
uv pip check --python "$environment/bin/python"
