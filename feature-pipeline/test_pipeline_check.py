"""Tests for pipeline_check.py. Run with: python3 -m unittest test_pipeline_check -v

Each test builds a throwaway git repo in a temp dir, since the append-only
and evidence checks compare the working tree against the last commit.
Stdlib only, no test framework dependency, consistent with the rest of
this project.
"""

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parent / "pipeline_check.py"


class PipelineCheckTest(unittest.TestCase):
    def setUp(self):
        self.repo = Path(tempfile.mkdtemp())
        subprocess.run(["git", "init", "-q"], cwd=self.repo, check=True)
        subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=self.repo, check=True)
        subprocess.run(["git", "config", "user.name", "t"], cwd=self.repo, check=True)

    def tearDown(self):
        shutil.rmtree(self.repo, ignore_errors=True)

    def write(self, name: str, content: str) -> None:
        (self.repo / name).write_text(content)

    def commit(self, message: str = "commit") -> None:
        subprocess.run(["git", "add", "-A"], cwd=self.repo, check=True)
        subprocess.run(["git", "commit", "-q", "-m", message], cwd=self.repo, check=True)

    def run_check(self, skip=None, **kwargs) -> subprocess.CompletedProcess:
        args = [sys.executable, str(SCRIPT)]
        for flag, value in kwargs.items():
            args += [f"--{flag.replace('_', '-')}", value]
        for s in skip or []:
            args += ["--skip", s]
        return subprocess.run(args, cwd=self.repo, capture_output=True, text=True)

    def test_clean_state_passes(self):
        self.write("todo.md", "- [ ] **Thing A**\n")
        self.write("testing.md", "## 1. Thing B\n\nDone, unverified.\n")
        self.write("releases.md", "# Releases\n\n## 2026-01-01 — v1\n\nShipped. https://ci.example.com/1\n")
        self.commit()
        result = self.run_check(open="todo.md", staging="testing.md", log="releases.md")
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_stuck_item_fails(self):
        self.write("todo.md", "- [ ] **Thing A**\n")
        self.write("testing.md", "## 1. Thing A\n\nDone, unverified.\n")
        self.write("releases.md", "# Releases\n")
        self.commit()
        result = self.run_check(open="todo.md", staging="testing.md", log="releases.md")
        self.assertEqual(result.returncode, 1)
        self.assertIn("stuck", result.stdout.lower())
        self.assertIn("thing a", result.stdout.lower())

    def test_edited_release_entry_fails_append_only(self):
        self.write("todo.md", "")
        self.write("testing.md", "")
        self.write("releases.md", "# Releases\n\n## 2026-01-01 — v1\n\nShipped. https://ci.example.com/1\n")
        self.commit()
        self.write("releases.md", "# Releases\n\n## 2026-01-01 — v1\n\nRewritten after the fact.\n")
        result = self.run_check(open="todo.md", staging="testing.md", log="releases.md")
        self.assertEqual(result.returncode, 1)
        self.assertIn("missing, edited", result.stdout.lower())

    def test_new_entry_with_evidence_passes(self):
        self.write("todo.md", "")
        self.write("testing.md", "")
        self.write("releases.md", "# Releases\n\n## 2026-01-01 — v1\n\nShipped. https://ci.example.com/1\n")
        self.commit()
        self.write(
            "releases.md",
            "# Releases\n\n## 2026-01-02 — v2\n\nShipped. build.log\n\n"
            "## 2026-01-01 — v1\n\nShipped. https://ci.example.com/1\n",
        )
        result = self.run_check(open="todo.md", staging="testing.md", log="releases.md")
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_new_entry_without_evidence_fails(self):
        self.write("todo.md", "")
        self.write("testing.md", "")
        self.write("releases.md", "# Releases\n\n## 2026-01-01 — v1\n\nShipped. https://ci.example.com/1\n")
        self.commit()
        self.write(
            "releases.md",
            "# Releases\n\n## 2026-01-02 — v2\n\nLooks good.\n\n"
            "## 2026-01-01 — v1\n\nShipped. https://ci.example.com/1\n",
        )
        result = self.run_check(open="todo.md", staging="testing.md", log="releases.md")
        self.assertEqual(result.returncode, 1)
        self.assertIn("evidence", result.stdout.lower())

    def test_missing_files_are_treated_as_empty(self):
        result = self.run_check(open="nope.md", staging="also-nope.md", log="still-nope.md")
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_skip_flag_disables_a_check(self):
        self.write("todo.md", "- [ ] **Thing A**\n")
        self.write("testing.md", "## 1. Thing A\n")
        self.write("releases.md", "# Releases\n")
        self.commit()
        result = self.run_check(open="todo.md", staging="testing.md", log="releases.md", skip=["stuck"])
        self.assertEqual(result.returncode, 0, result.stdout)


if __name__ == "__main__":
    unittest.main()
