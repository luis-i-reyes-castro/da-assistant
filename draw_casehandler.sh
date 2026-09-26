#!/usr/bin/env bash

set -euo pipefail

repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$repo_dir"

PYTHONPATH="$repo_dir/../..${PYTHONPATH:+:$PYTHONPATH}" \
    python3 -m case_handlers.da_assistant.casehandler
