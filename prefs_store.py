"""Application settings and last-used form defaults."""
import json
import os
import sys
from pathlib import Path
import form_model

SETTINGS_NAME = 'settings.json'
LEGACY_DEFAULT_NAME = 'MacroVision-defaults.json'

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
        self.settings_file = self.base / SETTINGS_NAME
        self.directory = self.base
        self.show_log = False
        self.preferences = {'condition': {}, 'action': {}}
        self.recovered_settings = None
        if self.settings_file.exists():
            try:
                with open(self.settings_file,encoding='utf-8') as f: info=json.load(f)
                if info.get('kind') != 'MacroVision-settings' or info.get('version') != 1 or not os.path.isabs(info.get('directory',str(self.base))) or not isinstance(info.get('show_log',False), bool):
                    raise ValueError('File thiết lập không hợp lệ: ' + str(self.settings_file))
                self.show_log = info.get('show_log', False)
                self.preferences = checked_preferences(info.get('preferences', {'condition': {}, 'action': {}}))
                old_directory = Path(info.get('directory', self.base))
            except (OSError, UnicodeError, ValueError, TypeError, AttributeError):
                backup = self.settings_file.with_name(self.settings_file.name + '.invalid')
                suffix = 1
                while backup.exists():
                    backup = self.settings_file.with_name(self.settings_file.name + f'.invalid.{suffix}')
                    suffix += 1
                self.settings_file.replace(backup)
                self.recovered_settings = backup
                self.save_settings()
                return
        else:
            old_directory = self.base
        legacy_file = old_directory / LEGACY_DEFAULT_NAME
        if legacy_file.is_file():
            with open(legacy_file, encoding='utf-8') as f: legacy=json.load(f)
            if legacy.get('kind') != 'MacroVision-defaults' or legacy.get('version') != 1:
                raise ValueError('File thiết lập cũ không hợp lệ: ' + str(legacy_file))
            if not self.preferences['condition'] and not self.preferences['action']:
                self.preferences = checked_preferences(legacy.get('preferences'))
            self.save_settings()
            legacy_file.unlink()
    @property
    def path(self): return self.settings_file
    def load(self): return self.preferences
    def save(self, preferences):
        self.preferences = checked_preferences(preferences)
        self.save_settings()
    def save_settings(self):
        form_model.atomic_json(self.settings_file,{'kind':'MacroVision-settings','version':1,'directory':str(self.directory),'show_log':self.show_log,'preferences':self.preferences})
