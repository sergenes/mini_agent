---
name: deploy
description: >-
  One-command iOS TestFlight and Android Play uploads via
  deployment-pipeline/release.py, plus infra_tools.py wrappers. Use when
  releasing, bumping build numbers, wiring agent-callable deploy tools, or
  editing files under deployment-pipeline/.
---

# Deploy

From `deployment-pipeline/`:

```bash
python3 release.py --ios
python3 release.py --android
python3 release.py --dry-run
```

`--ios` bumps `CURRENT_PROJECT_VERSION`, archives, exports IPA, uploads with `xcrun altool`. `--android` bumps `versionCode` / `versionName`, builds a signed AAB, uploads to Play Open Testing.

Credentials: `scripts/cd_secrets.env` (gitignored). Build numbers: `scripts/versions.cfg`.

Edit project paths at the top of `release.py` (`IOS_PROJECT`, `ANDROID_DIR`, and friends) for the app you are shipping. Mini_agent does not contain Xcode or Gradle projects; this folder is the template the series walks through. Production paths for Agents At Work live in the agent-bridge repo's `release.py`.

`infra_tools.py` exposes `run_tests`, `git_status`, `git_commit_push`, `deploy_web`, `deploy_mobile`, `remote_trigger` as JSON-schema tools. Add those schemas to the agent the same way as `tools.py`.
