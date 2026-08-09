#!/usr/bin/env sh
set -eu

python3 -m pip install -e ".[build]"
pyinstaller packaging/pyinstaller/mvd-edge-agent.spec
