#!/usr/bin/env bash
# Demo: walk a throwaway project through all seven stations, no API key needed
# up through "see" and "survive". The final "run one milestone" station is
# shown as blocked-until-you-provide-a-task, since that step is the one that
# actually calls a model, everything before it is a deterministic file check.
set -euo pipefail

DEMO_DIR="$(mktemp -d)"
FACTORY="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/factory.py"

echo "=== demo project: $DEMO_DIR ==="
echo

echo "--- init ---"
python3 "$FACTORY" init "$DEMO_DIR"
python3 "$FACTORY" status "$DEMO_DIR"

echo
echo "--- write an incomplete spec, advance should block ---"
cat > "$DEMO_DIR/SPEC.md" <<'EOF'
# Spec

Platforms: iOS
EOF
python3 "$FACTORY" advance "$DEMO_DIR" || true

echo
echo "--- complete the spec, advance should pass ---"
cat > "$DEMO_DIR/SPEC.md" <<'EOF'
# Spec

Platforms: iOS

Data model: users, one signed-out home screen

Boundaries: no payments, no server component yet

Milestone 1: signed-out home screen a tester can open
EOF
python3 "$FACTORY" advance "$DEMO_DIR"

echo
echo "--- remember: add a thin CLAUDE.md ---"
cat > "$DEMO_DIR/CLAUDE.md" <<'EOF'
# Demo App

## Always
- Do not invent a new architecture.

## Skills
- ios-architecture
EOF
python3 "$FACTORY" advance "$DEMO_DIR"

echo
echo "--- pattern: add the ios-architecture skill the spec names ---"
mkdir -p "$DEMO_DIR/.claude/skills/ios-architecture"
cat > "$DEMO_DIR/.claude/skills/ios-architecture/SKILL.md" <<'EOF'
---
name: ios-architecture
description: MVVM, SwiftUI, @Observable.
---
EOF
python3 "$FACTORY" advance "$DEMO_DIR"

echo
echo "--- move: a no-op deploy script counts ---"
mkdir -p "$DEMO_DIR/scripts"
echo "print('not wired yet')" > "$DEMO_DIR/scripts/release.py"
python3 "$FACTORY" advance "$DEMO_DIR"

echo
echo "--- see: a baseline directory ---"
mkdir -p "$DEMO_DIR/visual-testing/baselines-ios"
touch "$DEMO_DIR/visual-testing/baselines-ios/signed_out_home.png"
python3 "$FACTORY" advance "$DEMO_DIR"

echo
echo "--- survive: this app is read-only so far, say so explicitly ---"
echo "Read-only so far, no payments or writes to wrap yet." > "$DEMO_DIR/SURVIVE.md"
python3 "$FACTORY" advance "$DEMO_DIR"

echo
echo "--- final status ---"
python3 "$FACTORY" status "$DEMO_DIR"

echo
echo "--- run-milestone needs a real provider, shown here as a dry call ---"
echo "python3 factory.py run-milestone \"$DEMO_DIR\" \"build the signed-out home screen\" --provider openai"

rm -rf "$DEMO_DIR"
echo
echo "=== demo complete, no API key was used ==="
