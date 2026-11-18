import sys,unittest
from pathlib import Path
from unittest.mock import patch
from peakclip.infrastructure import paths

class Paths(unittest.TestCase):
    def test_ui_index_dev(self):
        self.assertEqual(paths.ui_index(),paths.project_root()/'ui'/'index.html')
    def test_ui_index_frozen_uses_meipass(self):
        meipass=Path('C:/fake/_internal')
        with patch.object(sys,'frozen',True,create=True),patch.object(sys,'_MEIPASS',str(meipass),create=True):
            self.assertEqual(paths.ui_index(),meipass/'ui'/'index.html')
            self.assertEqual(paths.bundle_root(),meipass)

if __name__=='__main__':unittest.main()
