#!/bin/bash
# One-time setup. Safe to run multiple times.
#
# Checks required CLIs are installed and creates the secrets template
# if it doesn't exist yet.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

check_cmd() {
  if command -v "$1" &>/dev/null; then
    echo "✓ $1"
  else
    echo "✗ $1 — $2"
    MISSING=1
  fi
}

echo "Checking required tools..."
MISSING=0
check_cmd firebase    "npm install -g firebase-tools"
check_cmd xcrun       "Install Xcode from the App Store"
check_cmd xcodebuild  "Install Xcode from the App Store"
check_cmd python3     "Install Python 3 from https://python.org"
check_cmd git         "Install git from https://git-scm.com"

if [ "$MISSING" -eq 1 ]; then
  echo ""
  echo "Install the tools listed above, then re-run setup.sh."
  exit 1
fi

echo ""
echo "Checking Python dependencies..."
python3 -c "import google.oauth2" 2>/dev/null \
  && echo "✓ google-auth" \
  || echo "  (optional) pip install google-api-python-client google-auth  # needed for Android"

echo ""
echo "Checking secrets file..."
if [ -f "$SCRIPT_DIR/cd_secrets.env" ]; then
  echo "✓ scripts/cd_secrets.env exists"
else
  cp "$SCRIPT_DIR/cd_secrets.env.example" "$SCRIPT_DIR/cd_secrets.env"
  echo "Created scripts/cd_secrets.env — fill in your credentials before running release.py."
fi

echo ""
echo "Setup complete."
