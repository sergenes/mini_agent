#!/bin/bash
# Web deployment.
# Usage: bash scripts/deploy.sh [environment]
#
# Reads FIREBASE_PROJECT from scripts/cd_secrets.env if present.
# Exits nonzero on any failure.
set -e

ENVIRONMENT="${1:-production}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/cd_secrets.env" ]; then
  source "$SCRIPT_DIR/cd_secrets.env"
fi

FIREBASE_PROJECT="${FIREBASE_PROJECT:-my-project-id}"

echo "→ Building..."
npm run build

echo "→ Deploying to Firebase Hosting ($ENVIRONMENT / $FIREBASE_PROJECT)..."
firebase deploy --only hosting --project "$FIREBASE_PROJECT"

echo "✓ Deployed successfully."
