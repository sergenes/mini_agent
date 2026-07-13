import unittest

from tools import _safe_path


class SafePathTests(unittest.TestCase):
    def test_allows_paths_inside_workspace(self):
        path = _safe_path("notes/example.txt")

        self.assertEqual(path.name, "example.txt")
        self.assertIn("workspace", path.parts)

    def test_rejects_parent_directory_escape(self):
        with self.assertRaisesRegex(ValueError, "escapes the workspace"):
            _safe_path("../outside.txt")

    def test_rejects_sibling_prefix_escape(self):
        with self.assertRaisesRegex(ValueError, "escapes the workspace"):
            _safe_path("../workspace2/outside.txt")


if __name__ == "__main__":
    unittest.main()
