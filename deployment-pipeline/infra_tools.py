"""
Deployment and CI/CD tools for the mini agent.

Tools: run_tests, git_status, git_commit_push, deploy_web, deploy_mobile, notify, remote_trigger.

To wire these into the agent, merge TOOL_FUNCTIONS and TOOL_SCHEMAS with the
ones in tools.py, or pass them directly to run_agent():

    from deployment_pipeline.infra_tools import TOOL_FUNCTIONS as INFRA_FN
    from deployment_pipeline.infra_tools import TOOL_SCHEMAS   as INFRA_SCHEMAS

    all_tools     = TOOL_SCHEMAS + INFRA_SCHEMAS
    all_functions = {**TOOL_FUNCTIONS, **INFRA_FN}
"""

import json
import os
import subprocess
import urllib.request
from pathlib import Path

_DIR = Path(__file__).parent


def run_tests(pattern: str = "") -> str:
    cmd = ["python3", "-m", "pytest", "-q"]
    if pattern:
        cmd += ["-k", pattern]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=_DIR.parent)
    output = (result.stdout + result.stderr).strip()
    status = "PASS" if result.returncode == 0 else "FAIL"
    return f"{status}\n{output[-3000:]}"


def git_status() -> str:
    result = subprocess.run(
        ["git", "status", "--short"], capture_output=True, text=True
    )
    return result.stdout.strip() or "clean"


def git_commit_push(message: str) -> str:
    try:
        subprocess.run(["git", "add", "-A"], check=True)
        subprocess.run(["git", "commit", "-m", message], check=True)
        subprocess.run(["git", "push"], check=True)
        return f"committed and pushed: {message}"
    except subprocess.CalledProcessError as e:
        return f"Error: {e}"


def deploy_web(environment: str = "production") -> str:
    script = _DIR / "scripts" / "deploy.sh"
    result = subprocess.run(
        ["bash", str(script), environment],
        capture_output=True, text=True,
    )
    output = (result.stdout + result.stderr).strip()[-2000:]
    status = "success" if result.returncode == 0 else "failed"
    return f"{status}\n{output}"


def deploy_mobile(platform: str) -> str:
    if platform not in ("ios", "android"):
        return f"Error: platform must be 'ios' or 'android', got '{platform}'"
    result = subprocess.run(
        ["python3", str(_DIR / "release.py"), f"--{platform}"],
        capture_output=True, text=True,
    )
    output = (result.stdout + result.stderr).strip()[-2000:]
    status = "success" if result.returncode == 0 else "failed"
    return f"{status}\n{output}"


def notify(message: str) -> str:
    script = _DIR / "scripts" / "notify.sh"
    result = subprocess.run(
        ["bash", str(script), message],
        capture_output=True, text=True,
    )
    return "sent" if result.returncode == 0 else f"failed: {result.stderr.strip()}"


def remote_trigger(task: str) -> str:
    url = os.environ.get("REMOTE_TRIGGER_WEBHOOK_URL", "")
    if not url:
        return "Error: REMOTE_TRIGGER_WEBHOOK_URL not set"
    payload = json.dumps({"task": task}).encode()
    req = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return f"triggered: HTTP {resp.status}"
    except Exception as e:
        return f"Error: {e}"


# --- Registry: name → callable ---

TOOL_FUNCTIONS: dict = {
    "run_tests":       run_tests,
    "git_status":      git_status,
    "git_commit_push": git_commit_push,
    "deploy_web":      deploy_web,
    "deploy_mobile":   deploy_mobile,
    "notify":          notify,
    "remote_trigger":  remote_trigger,
}

# --- Schemas (OpenAI function-calling format) ---

TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "run_tests",
            "description": "Run the project test suite with pytest. Returns PASS/FAIL and a summary.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Optional pytest -k filter, e.g. 'test_deploy'",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_status",
            "description": "Return uncommitted changes in the git working tree (git status --short).",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_commit_push",
            "description": "Stage all changes, commit with the given message, and push to the remote.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Commit message"}
                },
                "required": ["message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "deploy_web",
            "description": "Deploy the web app by running scripts/deploy.sh.",
            "parameters": {
                "type": "object",
                "properties": {
                    "environment": {
                        "type": "string",
                        "description": "Target environment: 'production' or 'staging'. Defaults to 'production'.",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "deploy_mobile",
            "description": "Build and upload a mobile release via release.py.",
            "parameters": {
                "type": "object",
                "properties": {
                    "platform": {
                        "type": "string",
                        "enum": ["ios", "android"],
                        "description": "Target platform: 'ios' (TestFlight) or 'android' (Play Store).",
                    }
                },
                "required": ["platform"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "notify",
            "description": "Send a Telegram notification (requires TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in scripts/cd_secrets.env).",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Message to send"}
                },
                "required": ["message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remote_trigger",
            "description": "POST a task description to REMOTE_TRIGGER_WEBHOOK_URL for async pickup.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": "Task description to post to the webhook",
                    }
                },
                "required": ["task"],
            },
        },
    },
]
