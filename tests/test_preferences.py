import json
from pathlib import Path
import tempfile
import unittest
import prefs_store

class PreferencesTests(unittest.TestCase):
    def test_validation_and_isolation(self):
        with tempfile.TemporaryDirectory() as d:
            store=prefs_store.PreferencesStore(d)
            store.save({'condition':{'stable':'400','sim':'nan','region':'bad'},'action':{'hold':'500','key':'J','order':99}})
            data=store.load();self.assertEqual(data['condition'],{'stable':400});self.assertEqual(data['action'],{'hold':500,'key':'J'})
            raw=json.loads(store.path.read_text(encoding='utf8'));self.assertNotIn('flows',raw);self.assertNotIn('template',str(raw));self.assertIn('preferences',raw)
    def test_invalid_existing_file_never_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            store=prefs_store.PreferencesStore(d);store.path.write_text('not my data',encoding='utf8')
            with self.assertRaises(Exception):store.save({'condition':{},'action':{}})
            self.assertEqual(store.path.read_text(encoding='utf8'),'not my data')
    def test_defaults_and_log_roundtrip_in_settings_file(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);store=prefs_store.PreferencesStore(base);store.show_log=True
            store.save({'condition':{'stable':600},'action':{'hold':500}})
            another=prefs_store.PreferencesStore(base);self.assertEqual(another.path,base/'settings.json')
            self.assertEqual(another.load()['action']['hold'],500);self.assertTrue(another.show_log)
