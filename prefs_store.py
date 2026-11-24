"""Last-used form defaults, kept independently of scripts."""
import json
import os
import sys
from pathlib import Path
import form_model

DEFAULT_NAME = 'MacroVision-defaults.json'
LOCATION_NAME = 'MacroVision-location.json'

def application_dir():
    return Path(sys.executable if getattr(sys, 'frozen', False) else __file__).resolve().parent

def checked_preferences(value):
    if not isinstance(value, dict): raise ValueError('Thiết lập mặc định không hợp lệ.')
    result = {'condition': {}, 'action': {}}
    for kind, allowed in [('condition',form_model.CONDITION_DEFAULT_FIELDS), ('action',form_model.ACTION_DEFAULT_FIELDS)]:
        fields = value.get(kind, {})
        if not isinstance(fields, dict): continue
        for key, val in fields.items():
            if key in allowed:
                try: result[kind][key] = form_model.parse_field(kind,key,val)
                except (ValueError,TypeError): pass
    return result

class PreferencesStore:
    def __init__(self, base=None):
        self.base = Path(base) if base is not None else application_dir()
        self.location_file = self.base / LOCATION_NAME
        self.directory = self.base
        if self.location_file.exists():
            with open(self.location_file,encoding='utf-8') as f: info=json.load(f)
            if info.get('kind') != 'MacroVision-defaults-location' or info.get('version') != 1 or not os.path.isabs(info.get('directory','')):
                raise ValueError('File vị trí thiết lập không hợp lệ: ' + str(self.location_file))
            self.directory = Path(info['directory'])
    @property
    def path(self): return self.directory / DEFAULT_NAME
    def load(self):
        if not self.path.exists(): return {'condition': {}, 'action': {}}
        with open(self.path,encoding='utf-8') as f: data=json.load(f)
        if data.get('kind') != 'MacroVision-defaults' or data.get('version') != 1:
            raise ValueError('File thiết lập không hợp lệ: ' + str(self.path))
        return checked_preferences(data.get('preferences'))
    def save(self, preferences):
        # Never overwrite an unrelated file accidentally using this reserved name.
        if self.path.exists(): self.load()
        form_model.atomic_json(self.path,{'kind':'MacroVision-defaults','version':1,'preferences':checked_preferences(preferences)})
    def relocate(self, directory, preferences):
        destination=Path(directory).resolve()
        if not destination.is_dir(): raise ValueError('Thư mục không tồn tại.')
        old=self.directory; self.directory=destination
        try:
            self.save(preferences)
            form_model.atomic_json(self.location_file,{'kind':'MacroVision-defaults-location','version':1,'directory':str(destination)})
        except Exception:
            self.directory=old
            raise
