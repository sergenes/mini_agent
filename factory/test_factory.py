"""Tests for factory.py. Run with: python3 -m unittest test_factory -v

Stdlib only. The run-milestone command needs a live provider, so it is only
checked for correct blocking behavior here, not for an actual model call.
"""

import shutil
import tempfile
import unittest
from pathlib import Path

import factory


class FactoryGatesTest(unittest.TestCase):
    def setUp(self):
        self.project = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.project, ignore_errors=True)

    def write(self, name: str, content: str) -> None:
        path = self.project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    # -- describe --

    def test_describe_fails_with_no_spec(self):
        result = factory.check_describe(self.project)
        self.assertFalse(result.ok)

    def test_describe_fails_with_incomplete_spec(self):
        self.write("SPEC.md", "# Spec\n\nPlatforms: iOS\n")
        result = factory.check_describe(self.project)
        self.assertFalse(result.ok)
        self.assertTrue(any("milestone 1" in r for r in result.reasons))

    def test_describe_passes_with_complete_spec(self):
        self.write(
            "SPEC.md",
            "# Spec\n\nPlatforms: iOS\n\nData model: users, posts\n\n"
            "Boundaries: no payments\n\nMilestone 1: signed-out home\n",
        )
        result = factory.check_describe(self.project)
        self.assertTrue(result.ok, result.reasons)

    # -- remember --

    def test_remember_fails_with_no_file(self):
        result = factory.check_remember(self.project)
        self.assertFalse(result.ok)

    def test_remember_fails_when_too_long(self):
        self.write("CLAUDE.md", ("- rule\n" * 100) + "load the deploy skill\n")
        result = factory.check_remember(self.project, max_lines=60)
        self.assertFalse(result.ok)
        self.assertTrue(any("budget" in r for r in result.reasons))

    def test_remember_fails_with_no_skill_pointer(self):
        self.write("CLAUDE.md", "# Product\n\nJust a note, no pointers.\n")
        result = factory.check_remember(self.project)
        self.assertFalse(result.ok)

    def test_remember_passes(self):
        self.write("CLAUDE.md", "# Product\n\nLoad the deploy skill before shipping.\n")
        result = factory.check_remember(self.project)
        self.assertTrue(result.ok, result.reasons)

    # -- pattern --

    def test_pattern_passes_with_no_platforms_named(self):
        self.write("SPEC.md", "# Spec\n\nA CLI tool.\n")
        result = factory.check_pattern(self.project)
        self.assertTrue(result.ok)

    def test_pattern_fails_when_skill_missing(self):
        self.write("SPEC.md", "# Spec\n\nPlatforms: iOS and web\n")
        result = factory.check_pattern(self.project)
        self.assertFalse(result.ok)

    def test_pattern_passes_when_skill_present(self):
        self.write("SPEC.md", "# Spec\n\nPlatforms: iOS\n")
        self.write(".claude/skills/ios-architecture/SKILL.md", "---\nname: ios-architecture\n---\n")
        result = factory.check_pattern(self.project)
        self.assertTrue(result.ok, result.reasons)

    # -- move --

    def test_move_fails_with_no_script(self):
        result = factory.check_move(self.project)
        self.assertFalse(result.ok)

    def test_move_passes_with_noop_script(self):
        self.write("scripts/release.py", "print('not wired yet')\n")
        result = factory.check_move(self.project)
        self.assertTrue(result.ok)

    # -- see --

    def test_see_fails_with_no_baseline(self):
        result = factory.check_see(self.project)
        self.assertFalse(result.ok)

    def test_see_passes_with_baseline_dir(self):
        self.write("visual-testing/baselines-ios/home.png", "not a real png, just a marker")
        result = factory.check_see(self.project)
        self.assertTrue(result.ok)

    # -- survive --

    def test_survive_fails_with_nothing(self):
        result = factory.check_survive(self.project)
        self.assertFalse(result.ok)

    def test_survive_passes_with_note(self):
        self.write("SURVIVE.md", "Read-only toy, nothing to wrap.\n")
        result = factory.check_survive(self.project)
        self.assertTrue(result.ok)

    def test_survive_passes_with_code_tag(self):
        self.write("tools.py", "def charge_card():\n    pass  # @survive: retry + circuit breaker applied\n")
        result = factory.check_survive(self.project)
        self.assertTrue(result.ok)


class FactoryStateMachineTest(unittest.TestCase):
    def setUp(self):
        self.project = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.project, ignore_errors=True)

    def write(self, name: str, content: str) -> None:
        path = self.project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def test_init_starts_at_describe(self):
        factory.cmd_init(self.project)
        self.assertEqual(factory.current_station(self.project), "describe")

    def test_advance_blocked_without_gate(self):
        factory.cmd_init(self.project)
        rc = factory.cmd_advance(self.project)
        self.assertEqual(rc, 1)
        self.assertEqual(factory.current_station(self.project), "describe")

    def test_advance_through_first_three_stations(self):
        factory.cmd_init(self.project)
        self.write(
            "SPEC.md",
            "# Spec\n\nPlatforms: iOS\n\nData model: users\n\n"
            "Boundaries: none\n\nMilestone 1: home screen\n",
        )
        self.assertEqual(factory.cmd_advance(self.project), 0)
        self.assertEqual(factory.current_station(self.project), "remember")

        self.write("CLAUDE.md", "# Product\n\nLoad the deploy skill.\n")
        self.assertEqual(factory.cmd_advance(self.project), 0)
        self.assertEqual(factory.current_station(self.project), "pattern")

        self.write(".claude/skills/ios-architecture/SKILL.md", "---\nname: ios-architecture\n---\n")
        self.assertEqual(factory.cmd_advance(self.project), 0)
        self.assertEqual(factory.current_station(self.project), "move")

    def test_run_milestone_blocked_before_run_station(self):
        factory.cmd_init(self.project)
        rc = factory.cmd_run_milestone(self.project, "do something", "openai", None)
        self.assertEqual(rc, 1)

    def test_state_persists_across_loads(self):
        factory.cmd_init(self.project)
        self.write(
            "SPEC.md",
            "# Spec\n\nPlatforms: none\n\nData model: none\n\n"
            "Boundaries: none\n\nMilestone 1: none\n",
        )
        factory.cmd_advance(self.project)
        # simulate a fresh process reading state back from disk
        self.assertEqual(factory.current_station(self.project), "remember")


class FactoryScaffoldTest(unittest.TestCase):
    def setUp(self):
        self.project = Path(tempfile.mkdtemp())
        factory.cmd_init(self.project)

    def tearDown(self):
        shutil.rmtree(self.project, ignore_errors=True)

    def test_scaffold_writes_spec_at_describe(self):
        rc = factory.cmd_scaffold(self.project)
        self.assertEqual(rc, 0)
        self.assertTrue((self.project / "SPEC.md").exists())

    def test_scaffold_template_passes_its_own_gate(self):
        # honest limit: presence, not quality, applies to a scaffolded file too
        factory.cmd_scaffold(self.project)
        result = factory.check_describe(self.project)
        self.assertTrue(result.ok, result.reasons)

    def test_scaffold_does_not_overwrite_existing_file(self):
        self.project.joinpath("SPEC.md").write_text("my real spec\n")
        factory.cmd_scaffold(self.project)
        self.assertEqual(self.project.joinpath("SPEC.md").read_text(), "my real spec\n")

    def test_scaffold_writes_claude_md_at_remember(self):
        factory.cmd_advance(self.project)  # blocked, stays at describe without a spec
        self.project.joinpath("SPEC.md").write_text(
            "Platforms: web\nData model: x\nBoundaries: x\nMilestone 1: x\n"
        )
        factory.cmd_advance(self.project)
        self.assertEqual(factory.current_station(self.project), "remember")
        factory.cmd_scaffold(self.project)
        self.assertTrue((self.project / "CLAUDE.md").exists())

    def test_scaffold_writes_release_stub_at_move(self):
        self.project.joinpath("SPEC.md").write_text("Platforms: none\nData model: x\nBoundaries: x\nMilestone 1: x\n")
        factory.cmd_advance(self.project)
        self.project.joinpath("CLAUDE.md").write_text("# P\n\nLoad a skill.\n")
        factory.cmd_advance(self.project)  # remember -> pattern
        factory.cmd_advance(self.project)  # pattern -> move (no platforms named, gate passes)
        self.assertEqual(factory.current_station(self.project), "move")
        factory.cmd_scaffold(self.project)
        self.assertTrue((self.project / "scripts" / "release.py").exists())

    def test_scaffold_is_noop_at_run_station(self):
        for _ in range(6):
            factory.cmd_advance(self.project)
        # advance stays blocked without real gates satisfied; force the index directly
        state = factory.load_state(self.project)
        state["station_index"] = len(factory.STATIONS) - 1
        factory.save_state(self.project, state)
        rc = factory.cmd_scaffold(self.project)
        self.assertEqual(rc, 0)


class FactoryJsonGateResultTest(unittest.TestCase):
    def setUp(self):
        self.project = Path(tempfile.mkdtemp())
        factory.cmd_init(self.project)

    def tearDown(self):
        shutil.rmtree(self.project, ignore_errors=True)

    def test_fail_payload_shape(self):
        result = factory.check_describe(self.project)
        payload = factory.gate_result_payload("describe", self.project, result)
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["station"], "describe")
        self.assertEqual(payload["status"], "fail")
        self.assertTrue(payload["blocking"])
        self.assertTrue(payload["blockers"])
        self.assertEqual(payload["suggested_next"]["command"], "scaffold")

    def test_pass_payload_suggests_advance(self):
        self.project.joinpath("SPEC.md").write_text(
            "Platforms: none\nData model: x\nBoundaries: x\nMilestone 1: x\n"
        )
        result = factory.check_describe(self.project)
        payload = factory.gate_result_payload("describe", self.project, result)
        self.assertEqual(payload["status"], "pass")
        self.assertFalse(payload["blocking"])
        self.assertEqual(payload["blockers"], [])
        self.assertEqual(payload["suggested_next"]["command"], "advance")


if __name__ == "__main__":
    unittest.main()
