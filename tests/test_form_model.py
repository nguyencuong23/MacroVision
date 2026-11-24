import os
import tempfile
import unittest
import form_model

class FormModelTests(unittest.TestCase):
    def test_invalid_values(self):
        for key, value in [('hold',''), ('hold','0'), ('repeat','101'), ('sim','nan'), ('sim','1.1'), ('key','F6'), ('key','F7'), ('key','F8')]:
            with self.subTest(key=key,value=value):
                with self.assertRaises(ValueError): form_model.parse_field('action',key,value)
    def test_valid_values(self):
        self.assertEqual(form_model.parse_field('action','hold','150'),150)
        self.assertEqual(form_model.parse_field('action','key','f'), 'F')
        self.assertEqual(form_model.parse_field('condition', 'sim', '0.9'), 0.9)
    def test_atomic_write(self):
        with tempfile.TemporaryDirectory() as d:
            p=os.path.join(d,'local','session.json')
            form_model.atomic_json(p, {'text':'xin chào'})
            with open(p,encoding='utf-8') as f: self.assertIn('xin chào', f.read())
            form_model.atomic_json(p, {'text':'khác'})
            with open(p,encoding='utf-8') as f: self.assertIn('khác', f.read())

if __name__=='__main__': unittest.main()
