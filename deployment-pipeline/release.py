#!/usr/bin/env python3
"""
Mobile release automation for iOS and Android.

Usage:
  python3 release.py --ios              # build → archive → export → upload to TestFlight
  python3 release.py --android          # build AAB → upload to Play Store open testing track
  python3 release.py --ios --dry-run    # validate credentials without building
  python3 release.py --android --dry-run

Configuration:
  1. Edit the paths in the "Project paths" section below.
  2. Copy scripts/cd_secrets.env.example to scripts/cd_secrets.env and fill in your credentials.
  3. Edit ExportOptions.plist with your Apple Team ID.
"""

import argparse
import configparser
import os
import re
import subprocess
import sys
from pathlib import Path

# ─── Project paths — edit these for your project ──────────────────────────────
IOS_PROJECT    = Path("../MyApp/ios/MyApp.xcodeproj")
IOS_SCHEME     = "MyApp"
IOS_PBXPROJ    = IOS_PROJECT / "project.pbxproj"
EXPORT_OPTS    = Path(__file__).parent / "ExportOptions.plist"

ANDROID_DIR    = Path("../MyApp/android")
ANDROID_GRADLE = ANDROID_DIR / "app/build.gradle.kts"
ANDROID_PKG    = "com.example.myapp"
# ──────────────────────────────────────────────────────────────────────────────

_DIR          = Path(__file__).parent
SECRETS_FILE  = _DIR / "scripts" / "cd_secrets.env"
VERSIONS_FILE = _DIR / "scripts" / "versions.cfg"
BUILD_DIR     = _DIR / ".build"


def load_secrets() -> dict:
    secrets = dict(os.environ)
    if SECRETS_FILE.exists():
        for line in SECRETS_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                secrets[k.strip()] = v.strip()
    return secrets


def load_versions() -> configparser.ConfigParser:
    cfg = configparser.ConfigParser()
    if VERSIONS_FILE.exists():
        cfg.read(VERSIONS_FILE)
    if "ios" not in cfg:
        cfg["ios"] = {"build": "0", "version": "1.0.0"}
    if "android" not in cfg:
        cfg["android"] = {"build": "0", "version": "1.0.0"}
    return cfg


def save_versions(cfg: configparser.ConfigParser) -> None:
    with VERSIONS_FILE.open("w") as f:
        cfg.write(f)


def run(cmd: list, **kwargs) -> None:
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    subprocess.run(cmd, check=True, **kwargs)


def pbxproj_set(key: str, value: str) -> None:
    text = IOS_PBXPROJ.read_text()
    updated = re.sub(rf"({re.escape(key)}\s*=\s*)\S+;", rf"\g<1>{value};", text)
    IOS_PBXPROJ.write_text(updated)


def gradle_set_version(build_code: int, version_name: str) -> None:
    text = ANDROID_GRADLE.read_text()
    text = re.sub(r"(versionCode\s*=\s*)\d+", rf"\g<1>{build_code}", text)
    text = re.sub(r'(versionName\s*=\s*)"[^"]+"', rf'\g<1>"{version_name}"', text)
    ANDROID_GRADLE.write_text(text)


def deploy_ios(dry_run: bool = False) -> None:
    secrets = load_secrets()
    apple_id     = secrets.get("APPLE_ID", "")
    app_password = secrets.get("APP_SPECIFIC_PASSWORD", "")

    if not apple_id or not app_password:
        print("ERROR: APPLE_ID and APP_SPECIFIC_PASSWORD must be set in scripts/cd_secrets.env")
        sys.exit(1)

    if dry_run:
        print(f"✓ APPLE_ID present: {apple_id}")
        print(f"✓ APP_SPECIFIC_PASSWORD present")
        print(f"✓ IOS_PROJECT: {IOS_PROJECT}")
        print(f"✓ IOS_SCHEME:  {IOS_SCHEME}")
        print(f"✓ ExportOptions.plist: {EXPORT_OPTS}")
        return

    cfg       = load_versions()
    new_build = int(cfg["ios"]["build"]) + 1
    version   = cfg["ios"]["version"]

    print(f"→ iOS build {new_build} ({version})")

    pbxproj_set("CURRENT_PROJECT_VERSION", str(new_build))

    archive = BUILD_DIR / f"MyApp-{new_build}.xcarchive"
    export  = BUILD_DIR / f"MyApp-{new_build}-export"
    ipa     = export / f"{IOS_SCHEME}.ipa"
    BUILD_DIR.mkdir(parents=True, exist_ok=True)

    run([
        "xcodebuild", "archive",
        "-project", str(IOS_PROJECT),
        "-scheme", IOS_SCHEME,
        "-configuration", "Release",
        "-archivePath", str(archive),
        "-destination", "generic/platform=iOS",
        "-allowProvisioningUpdates",
    ])

    run([
        "xcodebuild", "-exportArchive",
        "-archivePath", str(archive),
        "-exportPath", str(export),
        "-exportOptionsPlist", str(EXPORT_OPTS),
        "-allowProvisioningUpdates",
    ])

    run([
        "xcrun", "altool", "--upload-app",
        "--type", "ios",
        "--file", str(ipa),
        "--username", apple_id,
        "--password", app_password,
    ])

    cfg["ios"]["build"] = str(new_build)
    save_versions(cfg)
    print(f"✓ iOS build {new_build} uploaded to TestFlight")


def deploy_android(dry_run: bool = False) -> None:
    secrets = load_secrets()

    service_account_json = secrets.get("GOOGLE_PLAY_SERVICE_ACCOUNT_JSON", "")
    keystore_path        = secrets.get("ANDROID_KEYSTORE_PATH", "")
    keystore_password    = secrets.get("ANDROID_KEYSTORE_PASSWORD", "")
    key_alias            = secrets.get("ANDROID_KEY_ALIAS", "")
    key_password         = secrets.get("ANDROID_KEY_PASSWORD", "")

    if not service_account_json:
        print("ERROR: GOOGLE_PLAY_SERVICE_ACCOUNT_JSON must be set in scripts/cd_secrets.env")
        sys.exit(1)
    if not all([keystore_path, keystore_password, key_alias, key_password]):
        print("ERROR: Android signing secrets missing from scripts/cd_secrets.env")
        sys.exit(1)

    if dry_run:
        print(f"✓ GOOGLE_PLAY_SERVICE_ACCOUNT_JSON: {service_account_json}")
        print(f"✓ ANDROID_KEYSTORE_PATH: {keystore_path}")
        print(f"✓ ANDROID_PKG: {ANDROID_PKG}")
        return

    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build as google_build
        from googleapiclient.http import MediaFileUpload
    except ImportError:
        print("ERROR: Run: pip install google-api-python-client google-auth")
        sys.exit(1)

    cfg        = load_versions()
    new_code   = int(cfg["android"]["build"]) + 1
    version    = cfg["android"]["version"]

    print(f"→ Android build {new_code} ({version})")

    gradle_set_version(new_code, version)

    signing_env = {
        **os.environ,
        "ANDROID_KEYSTORE_PATH":     keystore_path,
        "ANDROID_KEYSTORE_PASSWORD": keystore_password,
        "ANDROID_KEY_ALIAS":         key_alias,
        "ANDROID_KEY_PASSWORD":      key_password,
    }
    run(["./gradlew", "bundleRelease", "--no-daemon"], cwd=ANDROID_DIR, env=signing_env)

    aab = ANDROID_DIR / "app/build/outputs/bundle/release/app-release.aab"

    creds = service_account.Credentials.from_service_account_file(
        service_account_json,
        scopes=["https://www.googleapis.com/auth/androidpublisher"],
    )
    service = google_build("androidpublisher", "v3", credentials=creds)

    edit = service.edits().insert(packageName=ANDROID_PKG).execute()
    service.edits().bundles().upload(
        packageName=ANDROID_PKG,
        editId=edit["id"],
        media_body=MediaFileUpload(str(aab), resumable=True),
    ).execute()
    service.edits().tracks().update(
        packageName=ANDROID_PKG,
        editId=edit["id"],
        track="openTesting",
        body={"releases": [{"versionCodes": [str(new_code)], "status": "completed"}]},
    ).execute()
    service.edits().commit(packageName=ANDROID_PKG, editId=edit["id"]).execute()

    cfg["android"]["build"] = str(new_code)
    save_versions(cfg)
    print(f"✓ Android build {new_code} uploaded to Play Store (openTesting)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Mobile release automation (iOS + Android)")
    parser.add_argument("--ios",     action="store_true", help="Deploy iOS to TestFlight")
    parser.add_argument("--android", action="store_true", help="Deploy Android to Play Store open testing track")
    parser.add_argument("--dry-run", action="store_true", help="Validate credentials without building or uploading")
    args = parser.parse_args()

    if not args.ios and not args.android:
        parser.print_help()
        sys.exit(1)

    if args.ios:
        deploy_ios(dry_run=args.dry_run)
    if args.android:
        deploy_android(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
