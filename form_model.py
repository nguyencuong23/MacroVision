"""Pure form parsing and safe local persistence."""
import json
import math
import os
from pathlib import Path
import tempfile
import windows_input as win
import keyboard_keys

CONDITION_DEFAULT_FIELDS = ('sim','bright','color_sim','stable','stability_window','release_stable','mode','cool','maximum','unlimited','confirm_activation')
ACTION_DEFAULT_FIELDS = ('type','key','x','y','hold','repeat','interval','after_delay','mouse_mode','mouse_api')
MOUSE_MODES = ('Đến tọa độ', 'Nhấn tại con trỏ hiện tại', 'Tọa độ; nếu lỗi nhấn tại chỗ')

def parse_field(kind, key, raw):
    text = str(raw).strip()
    if key in ('unlimited','confirm_activation'):
        if isinstance(raw,bool): return raw
        if text.lower() in ('true','1'): return True
        if text.lower() in ('false','0'): return False
        raise ValueError('Giá trị tích chọn không hợp lệ.')
    if key == 'name':
        if not text: raise ValueError('Tên không được để trống.')
        if len(text)>120: raise ValueError('Tên tối đa 120 ký tự.')
        return text
    limits = {'stable': (0,30000), 'stability_window': (1,60000), 'release_stable': (0,30000), 'cool': (200,3600000), 'maximum': (1,10000),
              'order': (1,999), 'hold': (10,5000), 'repeat': (1,100), 'interval': (0,60000), 'after_delay': (0,60000),
              'x': (-100000,100000), 'y': (-100000,100000)}
    if key in limits:
        try: val = int(text)
        except ValueError: raise ValueError('Phải là số nguyên.') from None
        lo,hi=limits[key]
        if not lo<=val<=hi: raise ValueError(f'Phải từ {lo} đến {hi}.')
        return val
    if key in ('sim','bright','color_sim'):
        try: val=float(text)
        except ValueError: raise ValueError('Phải là một số từ 0 đến 1.') from None
        if not math.isfinite(val) or not 0<=val<=1: raise ValueError('Phải là một số từ 0 đến 1.')
        return val
    if key=='mode':
        if text not in ('Một lần','Lặp'): raise ValueError('Chế độ không hợp lệ.')
    elif key=='type':
        if text not in ('Phím','Chuột trái','Chuột phải'): raise ValueError('Loại thao tác không hợp lệ.')
    elif key=='mouse_api':
        if text not in ('SendInput','mouse_event'): raise ValueError('API chuột không hợp lệ.')
    elif key=='mouse_mode':
        if text not in MOUSE_MODES: raise ValueError('Chế độ chuột không hợp lệ.')
    elif key=='key':
        names,_=keyboard_keys.parse_chord(text)
        return ' '.join(names)
    else: raise ValueError('Trường không được hỗ trợ.')
    return text

def atomic_json(path, data):
    path=Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    name=None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent, delete=False, suffix='.tmp') as f:
            name=f.name; json.dump(data, f, ensure_ascii=False, indent=2); f.flush(); os.fsync(f.fileno())
        os.replace(name,path); name=None
    finally:
        if name:
            try: os.unlink(name)
            except OSError: pass
