# Deployment Pipeline

One-command release automation for iOS (TestFlight) and Android (Play Store), plus agent-callable wrappers so an AI agent can trigger a release itself.

Part of the [mini_agent](../README.md) project. Accompanies the Medium article series:
- **Part 5:** [The Agent Built the Feature in Four Minutes. Deploying It Took Me Forty.](https://medium.com/@sergey-nes/9eec9ba3c206) — `deployment-pipeline/`

---

## Files

| File | Role |
|------|------|
| `release.py` | CLI — `--ios`, `--android`, `--dry-run` |
| `infra_tools.py` | Agent-callable wrappers: `run_tests`, `git_status`, `git_commit_push`, `deploy_web`, `deploy_mobile`, `remote_trigger` |
| `ExportOptions.plist` | iOS export options template (edit `teamID`) |
| `scripts/setup.sh` | One-time environment check; creates `cd_secrets.env` from the template |
| `scripts/deploy.sh` | Web deploy (Firebase Hosting example) |
| `scripts/test.sh` | Runs `pytest` |
| `scripts/versions.cfg` | Build number tracking, auto-bumped by `release.py` |
| `scripts/cd_secrets.env.example` | Secrets template. Copy to `cd_secrets.env`, which is gitignored |

---

## How it works

`release.py --ios` bumps the build number in `project.pbxproj`, archives with `xcodebuild`, exports the IPA, and uploads to TestFlight with `xcrun altool`. `release.py --android` bumps `versionCode` and `versionName` in `build.gradle.kts`, builds a signed AAB with Gradle, and uploads through the Google Play Developer API to the Open Testing track.

Both commands read credentials from `scripts/cd_secrets.env`, which is never committed, and track build numbers in `scripts/versions.cfg`, so every run picks up where the last one left off.

`--dry-run` checks that the right secrets and paths are present without building or uploading anything. Run it after a fresh clone to confirm the environment is configured before a real release.

`infra_tools.py` wraps `release.py`, `scripts/deploy.sh`, `pytest`, and `git` as plain Python functions with JSON schemas, so an agent can call `deploy_mobile("ios")` the same way it calls any other tool.

---

## Setup

### 1. Edit project paths

At the top of `release.py`:

```python
IOS_PROJECT    = Path("../MyApp/ios/MyApp.xcodeproj")
IOS_SCHEME     = "MyApp"
ANDROID_DIR    = Path("../MyApp/android")
ANDROID_GRADLE = ANDROID_DIR / "app/build.gradle.kts"
ANDROID_PKG    = "com.example.myapp"
```

### 2. Check dependencies and create the secrets file

```bash
bash scripts/setup.sh
```

Checks for `firebase`, `xcrun`, `xcodebuild`, `python3`, and `git`, plus the optional `google-api-python-client` and `google-auth` packages needed for Android uploads. Creates `scripts/cd_secrets.env` from the template on first run.

### 3. Fill in credentials

Edit `scripts/cd_secrets.env`:

```bash
APPLE_ID=you@example.com
APP_SPECIFIC_PASSWORD=xxxx-xxxx-xxxx-xxxx     # appleid.apple.com → Security → App-Specific Passwords

ANDROID_KEYSTORE_PATH=/absolute/path/to/release.jks
ANDROID_KEYSTORE_PASSWORD=
ANDROID_KEY_ALIAS=
ANDROID_KEY_PASSWORD=
GOOGLE_PLAY_SERVICE_ACCOUNT_JSON=/absolute/path/to/service-account.json

FIREBASE_PROJECT=my-project-id
REMOTE_TRIGGER_WEBHOOK_URL=
```

### 4. Edit `ExportOptions.plist`

Replace `YOUR_TEAM_ID` with your 10-character Apple Team ID (developer.apple.com/account → Membership Details).

### 5. Validate

```bash
python3 release.py --ios --dry-run
python3 release.py --android --dry-run
```

Each prints which required values it found, without touching Xcode or Gradle.

---

## iOS — one-time setup

- **Apple ID and app-specific password.** A regular Apple ID password doesn't work for `altool` uploads. Generate a dedicated app-specific password at appleid.apple.com and put it in `cd_secrets.env`, not your account password.
- **Skip the encryption compliance question.** Add this to your app's `Info.plist`:
  ```xml
  <key>ITSAppUsesNonExemptEncryption</key>
  <false/>
  ```
  Without it, every upload sits in "waiting for review" until someone opens App Store Connect and answers the question by hand. With it, the build goes live on TestFlight as soon as the upload finishes, and TestFlight notifies your testers automatically.
- **Provisioning.** `-allowProvisioningUpdates` lets `xcodebuild` fetch and refresh provisioning profiles on its own. The app still needs to already be registered in your Apple Developer account with automatic signing enabled.

---

## Android — one-time setup

- **Signing.** Android needs a release keystore and four credentials: `ANDROID_KEYSTORE_PATH`, `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS`, `ANDROID_KEY_PASSWORD`. If you don't have a keystore yet, generate one with `keytool` and keep it outside version control.
- **Play Store API access.** Create a service account in Google Cloud Console, enable the Google Play Developer API, download the JSON key, and grant the account "Release manager" permissions in Play Console under Setup → API access. Store the JSON path in `GOOGLE_PLAY_SERVICE_ACCOUNT_JSON`.
- **The first upload has to be manual.** The Play Developer API refuses uploads for an app that has never been published. Upload the very first build through the Play Console by hand; every release after that can go through `release.py`.
- **AAB, not APK.** Google Play has required the Android App Bundle format for new submissions since August 2021. The `bundleRelease` Gradle task produces one automatically.
- **No automatic tester notification, and a timing gap to know about.** Unlike TestFlight, Play Store open testing doesn't push a notification when a new build arrives, and the build isn't visible to testers until Google's own processing finishes, which can lag behind the moment the upload completes. Check the Play Console before telling anyone a release is out.

---

## Command reference

```bash
python3 release.py --ios                  # build, archive, export, upload to TestFlight
python3 release.py --android              # build AAB, upload to Play Store (Open Testing)
python3 release.py --ios --android        # both

python3 release.py --ios --dry-run        # validate iOS credentials only
python3 release.py --android --dry-run    # validate Android credentials only

bash scripts/deploy.sh                    # web deploy (Firebase Hosting example)
bash scripts/deploy.sh staging            # deploy to a named environment

bash scripts/test.sh                      # run pytest
bash scripts/test.sh test_deploy          # run pytest -k test_deploy
```

---

## Wiring into the agent

```python
from deployment_pipeline.infra_tools import TOOL_FUNCTIONS as INFRA_FN
from deployment_pipeline.infra_tools import TOOL_SCHEMAS   as INFRA_SCHEMAS

all_tools     = TOOL_SCHEMAS + INFRA_SCHEMAS
all_functions = {**TOOL_FUNCTIONS, **INFRA_FN}
```

Available tools: `run_tests(pattern?)`, `git_status()`, `git_commit_push(message)`, `deploy_web(environment?)`, `deploy_mobile(platform)`, `remote_trigger(task)`. Each returns a plain string, success or failure plus the last chunk of output, so the agent can read the result directly.

---

## Notes

- **Build numbers are tracked automatically.** `scripts/versions.cfg` stores the last iOS build number and Android `versionCode`, and both are bumped on every successful deploy. Don't edit the file by hand unless you're recovering from a failed release.
- **Secrets never touch git.** `scripts/cd_secrets.env` is gitignored; only `cd_secrets.env.example`, with placeholder values, is committed.
- **`--dry-run` doesn't build anything.** It only checks that the secrets and paths `release.py` needs are present, so a fresh clone can be validated before a real release runs.
- **Web deployment is a separate, optional path.** `scripts/deploy.sh` is a minimal example for Firebase Hosting. Swap in whatever CLI matches your stack (`gcloud`, `aws`, `doctl`); the shape, build then one deploy command, stays the same.

---

## A note on this project

This automates a real release process end to end, but it assumes a fairly standard setup: a single Xcode scheme, a single Gradle module, automatic signing on iOS, and no code review gate beyond TestFlight or Play Store's own review. Larger projects with multiple flavors, build variants, or a staged rollout process will need to extend `release.py` rather than use it as-is.

I built this to show the automation is genuinely simple once the one-time credential setup is done, not to cover every CI/CD edge case. If your setup is more complex and you'd like help adapting it, reach me on [LinkedIn](https://www.linkedin.com/in/sergey-neskoromny/) or [Medium](https://sergey-nes.medium.com/).
