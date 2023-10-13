#!/usr/bin/env sh
set -eu

python_bin="${PYTHON:-python3}"
venv_dir="${VENV:-.venv}"
extras="test"

if [ "${1:-}" = "--rl" ]; then
  extras="test,rl"
elif [ "$#" -gt 0 ]; then
  echo "usage: $0 [--rl]" >&2
  exit 2
fi

"$python_bin" -m venv "$venv_dir"
"$venv_dir/bin/python" -m pip install --upgrade pip
"$venv_dir/bin/python" -m pip install -e ".[${extras}]"

echo "Environment ready. Activate it with: . $venv_dir/bin/activate"
