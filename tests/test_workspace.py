import unittest
from peakclip.application.workspace import Workspace, MAX_TABS


class WorkspaceTabs(unittest.TestCase):
    def test_max_three_tabs(self):
        space = Workspace(lambda: None)
        self.assertEqual(len(space.tabs()), 1)
        self.assertTrue(space.new_tab()["ok"])
        self.assertTrue(space.new_tab()["ok"])
        self.assertEqual(len(space.tabs()), MAX_TABS)
        denied = space.new_tab()
        self.assertFalse(denied["ok"])
        self.assertIn("Máximo", denied["error"])
        first = space.tabs()[0]["id"]
        self.assertTrue(space.close_tab(first)["ok"])
        self.assertEqual(len(space.tabs()), 2)
        space.close()


if __name__ == "__main__":
    unittest.main()
