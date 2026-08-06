#!/bin/bash
# Run the project test suite.
# Usage: bash scripts/test.sh [pytest-pattern]
#
# Exits nonzero on any test failure.
set -e

PATTERN="${1:-}"

if [ -n "$PATTERN" ]; then
  python3 -m pytest -q -k "$PATTERN"
else
  python3 -m pytest -q
fi
