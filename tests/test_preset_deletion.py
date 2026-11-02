import tempfile,unittest
from pathlib import Path
from hockey_editor.preferences import read,write,presets,delete_preset

class PresetDeletion(unittest.TestCase):
    def test_deletes_selected_shared_or_legacy_without_reappearing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'preferences.json'
            data={'shared_presets':{'Same':{'settings':{}}},'ru_hockey':{'logo_folder':'keep','presets':{'Same':{'settings':{'width':1280}},'Other':{'settings':{}}}}}
            write(data,path)
            delete_preset('ru_hockey','Same [ru_hockey]',path)
            self.assertEqual(set(presets('uz_football',path)),{'Same','Other'})
            self.assertEqual(read(path)['ru_hockey']['logo_folder'],'keep')
            delete_preset('ru_hockey','Same',path)
            self.assertEqual(set(presets('ru_hockey',path)),{'Other'})
            with self.assertRaises(ValueError):delete_preset('ru_hockey','Missing',path)
            self.assertEqual(set(presets('ru_hockey',path)),{'Other'})
