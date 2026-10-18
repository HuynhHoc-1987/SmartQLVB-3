import tempfile,unittest
from pathlib import Path
import server
class TestSettings(unittest.TestCase):
 def test_default_and_custom(self):
  with tempfile.TemporaryDirectory() as d:
   server.SETTINGS_FILE=Path(d)/'settings.json'
   server.CLASSIFIED=Path(d)/'default'
   self.assertEqual(Path(server.settings()['classification_root']),server.CLASSIFIED.resolve())
   target=Path(d)/'custom'
   c=server.save_settings({'classification_root':str(target),'ai_mode':'rules'})
   self.assertTrue(target.is_dir())
   self.assertEqual(c['classification_root'],str(target.resolve()))
   self.assertEqual(server.settings()['classification_root'],str(target.resolve()))
   c=server.save_settings({'classification_root':''})
   self.assertEqual(c['classification_root'],str(server.CLASSIFIED.resolve()))
if __name__=='__main__':unittest.main()
