"""Macro Vision multi-flow prototype. GUI must run on Windows."""
import base64
import copy
import json
import os
import queue
import re
import sys
import threading
import time
import uuid
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import cv2
import mss
import numpy as np
import windows_input as win
import engine
import once_engine
import keyboard_keys
import form_model
import prefs_store
from mask_editor import MaskEditor, photo


def new_id(): return uuid.uuid4().hex

def app_resource(name): return Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent)) / name

def new_condition():
    return {'id': new_id(), 'name': 'Điều kiện mới', 'region': None, 'template': None, 'mask': None,
            'sim': .96, 'bright': 0., 'color_sim': 0., 'stable': 250, 'stability_window': 2000, 'release_stable': 500, 'mode': 'Một lần', 'cool': 2000, 'maximum': 10, 'unlimited': False, 'confirm_activation': False, 'actions': []}

def new_action():
    return {'id': new_id(), 'type': 'Phím', 'order': 1, 'hold': 250, 'key': '1', 'x': 100, 'y': 100, 'repeat': 1, 'interval': 200, 'after_delay': 0, 'mouse_mode': 'Đến tọa độ', 'mouse_api': 'SendInput'}


def encode_image(img):
    if img is None: return None
    ok, data = cv2.imencode('.png', img)
    if not ok: raise ValueError('Không mã hóa được ảnh.')
    return base64.b64encode(data).decode('ascii')

def decode_image(data, flag):
    if data is None: return None
    raw = base64.b64decode(data, validate=True)
    if len(raw) > 25_000_000: raise ValueError('Ảnh trong cấu hình quá lớn.')
    img = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), flag)
    if img is None: raise ValueError('Ảnh cấu hình không hợp lệ.')
    return img

def serialize(flows):
    data = copy.deepcopy(flows)
    for flow in data:
        for c in flow['conditions']:
            c['template'] = encode_image(c['template']); c['mask'] = encode_image(c['mask'])
    return {'version': 1, 'flows': data}

def deserialize(data):
    if data['version'] != 1 or not isinstance(data['flows'], list): raise ValueError('Định dạng script không hợp lệ.')
    flows = data['flows']
    for flow in flows:
        for c in flow['conditions']:
            c['template'] = decode_image(c['template'], cv2.IMREAD_COLOR)
            c['mask'] = decode_image(c['mask'], cv2.IMREAD_GRAYSCALE)
            c.setdefault('color_sim', 0.)
            c.setdefault('unlimited', False); c.setdefault('confirm_activation', False)
            c.setdefault('release_stable', 500)
            c.setdefault('stability_window', max(2000, c.get('stable', 250) + 500))
            for action in c['actions']:
                action.setdefault('repeat', 1); action.setdefault('interval', 200); action.setdefault('after_delay', 0); action.setdefault('mouse_mode', 'Đến tọa độ'); action.setdefault('mouse_api', 'SendInput')
    return flows


class App(tk.Tk):
    def __init__(self, prompt_on_start=True):
        super().__init__()
        self.title('Macro Vision'); self.geometry('1100x760'); self.minsize(940, 650)
        if os.name == 'nt': self.iconbitmap(default=str(app_resource('icon.ico')))
        self.update_idletasks()
        self.geometry(f'+{(self.winfo_screenwidth() - 1100) // 2}+{(self.winfo_screenheight() - 760) // 2}')
        self.script_mode='Lặp lại'
        self.flows = []; self.item_map = {}; self.selected = None; self.vars = {}; self.messages = queue.Queue()
        self.key_capture_focused = False
        self.engine = None; self.pending = False; self.countdown_token = 0; self.hotkey_states = {'F6': False, 'F7': False, 'F8': False}
        self.preferences = {'condition': {}, 'action': {}}
        self.show_log = False
        self.anti_detect = False
        self.preferences_error = None; self.preference_store = None
        try:
            self.preference_store = prefs_store.PreferencesStore()
            self.preferences = self.preference_store.load()
            self.show_log = self.preference_store.show_log
            self.anti_detect = self.preference_store.anti_detect
        except Exception as e:
            self.preferences_error = str(e); self.preference_store = None
        self.form_errors = {}; self.save_job = None; self.selection_guard = False
        self.session_path = None; self.dirty = False
        self.autosave_status = tk.StringVar(value='')
        self.protocol('WM_DELETE_WINDOW', self.close)
        top = ttk.Frame(self, padding=(0, 0)); top.pack(fill='x')
        script_menu = tk.Menu(self, tearoff=False)
        script_menu.add_command(label='Mới', command=self.new_script)
        script_menu.add_command(label='Mở', command=self.load_script)
        script_menu.add_command(label='Lưu', command=self.save_script)
        script_label = ttk.Label(top, text='Script', padding=(8, 6), cursor='hand2')
        script_label.pack(side='left')
        script_label.bind('<Enter>', lambda e: script_menu.post(script_label.winfo_rootx(), script_label.winfo_rooty() + script_label.winfo_height()))
        script_label.bind('<Button-1>', lambda e: script_menu.post(script_label.winfo_rootx(), script_label.winfo_rooty() + script_label.winfo_height()))
        self.display_menu = tk.Menu(self, tearoff=False)
        self.display_label = ttk.Label(top, text='Hiển thị', padding=(8, 6), cursor='hand2')
        self.display_label.pack(side='left')
        self.display_label.bind('<Enter>', lambda e: self.post_display_menu())
        self.display_label.bind('<Button-1>', lambda e: self.post_display_menu())
        self.anti_detect_var=tk.BooleanVar(value=self.anti_detect)
        ttk.Checkbutton(top,text='Chế độ chống phát hiện',variable=self.anti_detect_var,command=self.toggle_anti_detect).pack(side='right',padx=8)
        ttk.Separator(self, orient='horizontal').pack(fill='x')
        outer = ttk.Panedwindow(self, orient='horizontal'); outer.pack(fill='both', expand=True, padx=8)
        left = ttk.Frame(outer, padding=5); right = ttk.Frame(outer, padding=8); outer.add(left, weight=2); outer.add(right, weight=3)
        tree_head=ttk.Frame(left);tree_head.pack(fill='x')
        ttk.Label(tree_head, text='Cấu trúc script').pack(side='left')
        self.script_mode_var=tk.StringVar(value=self.script_mode)
        self.script_mode_box=ttk.Combobox(tree_head,textvariable=self.script_mode_var,values=('Lặp lại','Một lần'),state='readonly',width=12)
        self.script_mode_box.pack(side='right');ttk.Label(tree_head,text='Mode:').pack(side='right',padx=(4,4))
        self.script_mode_box.bind('<<ComboboxSelected>>',self.change_script_mode)
        self.tree = ttk.Treeview(left, show='tree', selectmode='browse'); self.tree.pack(fill='both', expand=True, pady=4)
        self.tree.bind('<<TreeviewSelect>>', self.select)
        self.drag_source = None; self.drag_started = False; self.drag_point = None; self.drag_scroll_job = None
        self.drop_line = tk.Frame(self.tree, bg='#1976d2', height=3)
        self.tree.bind('<ButtonPress-1>', self.drag_press, add='+')
        self.tree.bind('<B1-Motion>', self.drag_motion, add='+')
        self.tree.bind('<ButtonRelease-1>', self.drag_release, add='+')
        self.tree.bind('<Escape>', self.drag_cancel, add='+')
        tools = ttk.Frame(left); tools.pack(fill='x')
        for label, cmd in [('＋ Luồng', self.add_flow), ('＋ Điều kiện', self.add_condition), ('＋ Thao tác', self.add_action), ('Xóa mục', self.delete_item)]:
            ttk.Button(tools, text=label, command=cmd).pack(side='left', padx=2)
        self.right = right; self.render_panel()
        bottom = ttk.Frame(self, padding=8); bottom.pack(fill='x')
        self.start_button = ttk.Button(bottom, text='Bắt đầu · F6', command=self.start); self.start_button.pack(side='left', padx=(0,8))
        self.pause_button = ttk.Button(bottom, text='Tạm dừng · F7', command=self.toggle_pause, state='disabled'); self.pause_button.pack(side='left', padx=(0,8))
        ttk.Button(bottom, text='Dừng · F8', command=self.stop).pack(side='left')
        self.status = tk.StringVar(value='F6 bắt đầu · F7 tạm dừng/tiếp tục · F8 dừng hẳn.')
        self.log_panel = ttk.Frame(self, padding=(12, 0))
        log_head = ttk.Frame(self.log_panel); log_head.pack(fill='x')
        ttk.Label(log_head, text='Nhật ký').pack(side='left')
        self.logbox = tk.Text(self.log_panel, height=6, wrap='word', state='disabled'); self.logbox.pack(fill='x', pady=(0,8))
        if self.show_log: self.log_panel.pack(fill='x')
        self.refresh_display_menu()
        self.tick_job = self.after(30, self.tick)
        self.update_storage_status()
        if self.preferences_error: self.log('LỖI THIẾT LẬP: ' + self.preferences_error)
        elif self.preference_store and self.preference_store.recovered_settings: self.log('settings.json cũ không đọc được; đã lưu bản cũ tại ' + str(self.preference_store.recovered_settings) + ' và tạo thiết lập mới.')

    def refresh_display_menu(self):
        self.display_menu.delete(0, 'end')
        self.display_menu.add_command(label='Ẩn nhật ký' if self.show_log else 'Hiển thị nhật ký', command=self.toggle_log)
    def toggle_anti_detect(self):
        enabled=self.anti_detect_var.get()
        if self.preference_store:
            self.preference_store.anti_detect=enabled
            try:self.preference_store.save_settings()
            except Exception as e:
                self.preference_store.anti_detect=self.anti_detect
                self.anti_detect_var.set(self.anti_detect)
                messagebox.showerror('Không thể lưu cài đặt',str(e));return
        self.anti_detect=enabled
        self.status.set('Chế độ chống phát hiện ' + ('bật' if enabled else 'tắt') + ' · áp dụng từ lần chạy tiếp theo.')
    def post_display_menu(self):
        self.display_menu.post(self.display_label.winfo_rootx(), self.display_label.winfo_rooty() + self.display_label.winfo_height())
    def toggle_log(self):
        show = not self.show_log
        if self.preference_store:
            self.preference_store.show_log = show
            try: self.preference_store.save_settings()
            except Exception as e:
                self.preference_store.show_log = self.show_log
                messagebox.showerror('Không thể lưu cài đặt', str(e)); return
        self.show_log = show
        if show: self.log_panel.pack(fill='x')
        else: self.log_panel.pack_forget()
        self.refresh_display_menu()
    def log(self, msg):
        self.logbox.config(state='normal'); self.logbox.insert('end', time.strftime('%H:%M:%S ') + msg + '\n'); self.logbox.see('end'); self.logbox.config(state='disabled')
    def log_action(self, msg):
        self.logbox.config(state='normal'); self.logbox.insert('end', msg + '\n'); self.logbox.see('end'); self.logbox.config(state='disabled')
    def update_storage_status(self):
        if self.preferences_error:
            self.autosave_status.set('LỖI thiết lập: ' + self.preferences_error + ' · Kiểm tra quyền ghi tại thư mục ứng dụng.')
        elif self.preference_store:
            self.autosave_status.set('Thiết lập tự lưu: ' + str(self.preference_store.path) + ' · Script lưu riêng bằng nút Lưu script.')
    def cancel_pending_save(self):
        if self.save_job is not None:
            try: self.after_cancel(self.save_job)
            except tk.TclError: pass
            self.save_job = None
    def schedule_preferences_save(self):
        self.cancel_pending_save()
        if self.preference_store: self.save_job = self.after(500, self.persist_preferences)
    def persist_preferences(self):
        self.cancel_pending_save()
        if not self.preference_store: return False
        try:
            self.preference_store.save(self.preferences); self.preferences_error = None; self.update_storage_status(); return True
        except Exception as e:
            self.preferences_error = str(e); self.update_storage_status(); self.log('LỖI LƯU THIẾT LẬP: ' + str(e)); return False
    def schedule_save(self):
        # Script never autosaves: defaults are persisted independently.
        self.dirty = True
    def script_payload(self):
        data=serialize(self.flows);data['script_mode']=self.script_mode;return data
    def change_script_mode(self, event=None):
        requested=self.script_mode_var.get()
        if requested not in ('Lặp lại','Một lần') or not self.ensure_valid():
            self.script_mode_var.set(self.script_mode);return
        if requested==self.script_mode:return
        self.script_mode=requested;self.schedule_save();self.render_panel()
        self.status.set('Mode: '+requested+' · thay đổi áp dụng từ lần chạy tiếp theo.')
    def prepare_switch(self):
        if self.dirty:
            return messagebox.askyesno('Chưa lưu script', 'Script có thay đổi chưa lưu. Bỏ các thay đổi và tiếp tục?')
        return True
    def parse_script_file(self, path):
        if os.path.getsize(path) > 60_000_000: raise ValueError('File quá lớn.')
        with open(path, encoding='utf-8') as inp: data = json.load(inp)
        legacy = isinstance(data, dict) and 'script' in data and 'flows' not in data
        if legacy:
            if data.get('version') != 1: raise ValueError('Phiên bản phiên cũ không được hỗ trợ.')
            script = data['script']
        else: script = data
        mode=script.get('script_mode','Lặp lại')
        if mode not in ('Lặp lại','Một lần'): raise ValueError('Mode script không hợp lệ.')
        flows = deserialize(script)
        return flows, mode, legacy
    def active_field(self, key):
        if self.selected and self.selected[0]=='condition' and key=='maximum' and self.vars.get('unlimited') and self.vars['unlimited'].get(): return False
        if not self.selected or self.selected[0] != 'action': return True
        kind = self.vars['type'].get()
        mode = self.vars['mouse_mode'].get()
        if key == 'key': return kind == 'Phím'
        if key == 'mouse_mode': return kind != 'Phím'
        if key in ('x','y'): return kind != 'Phím' and mode != 'Nhấn tại con trỏ hiện tại'
        return True
    def refresh_errors(self):
        self.form_errors = {}
        if self.selected:
            for key, var in self.vars.items():
                if not self.active_field(key): continue
                try: form_model.parse_field(self.selected[0], key, var.get())
                except ValueError as e: self.form_errors[key] = str(e)
        if self.form_errors:
            k = next(iter(self.form_errors)); self.autosave_status.set(f'Giá trị chưa hợp lệ: {k} — {self.form_errors[k]} (chưa lưu giá trị này)')
    def on_field_change(self, key):
        if not self.selected or key not in self.vars: return
        kind, f, c, a = self.selected
        obj = f if kind == 'flow' else c if kind == 'condition' else a
        if self.active_field(key):
            try:
                value = form_model.parse_field(kind, key, self.vars[key].get())
                obj[key] = value
                if kind in self.preferences:
                    allowed = form_model.CONDITION_DEFAULT_FIELDS if kind=='condition' else form_model.ACTION_DEFAULT_FIELDS
                    if key in allowed:
                        self.preferences[kind][key] = value; self.schedule_preferences_save()
                self.update_tree_item(obj, kind)
                self.schedule_save()
            except ValueError: pass
        if kind=='condition' and key=='unlimited' and 'maximum' in self.field_widgets:
            self.field_widgets['maximum'][1].configure(state='disabled' if self.vars['unlimited'].get() else 'normal')
        self.refresh_errors()
    def update_tree_item(self, obj, kind):
        if not self.tree.exists(obj['id']): return
        if kind == 'flow': label = '🗂 ' + obj['name']
        elif kind == 'condition': label = '◉ ' + obj['name']
        else:
            label = obj['key'] if obj['type']=='Phím' else (obj['type']+' · tại chỗ' if obj.get('mouse_mode')=='Nhấn tại con trỏ hiện tại' else f"{obj['type']} ({obj['x']}, {obj['y']})")
            label = f"{obj['order']} · {label}"
        self.tree.item(obj['id'], text=label)
    def ensure_valid(self):
        self.refresh_errors()
        if self.form_errors:
            key=next(iter(self.form_errors)); messagebox.showerror('Giá trị chưa hợp lệ', f"{key}: {self.form_errors[key]}\nVui lòng sửa trước khi chuyển mục hoặc chạy."); return False
        return True
    def refresh_tree(self, select_id=None):
        for item in self.tree.get_children(): self.tree.delete(item)
        self.item_map = {}
        for f in self.flows:
            self.tree.insert('', 'end', iid=f['id'], text='🗂 '+f['name'], open=True); self.item_map[f['id']] = ('flow', f, None, None)
            for c in f['conditions']:
                self.tree.insert(f['id'], 'end', iid=c['id'], text='◉ '+c['name'], open=True); self.item_map[c['id']] = ('condition', f, c, None)
                for a in c['actions']:
                    label = a['key'] if a['type']=='Phím' else (f"{a['type']} · tại chỗ" if a.get('mouse_mode') == 'Nhấn tại con trỏ hiện tại' else f"{a['type']} ({a['x']}, {a['y']})")
                    self.tree.insert(c['id'], 'end', iid=a['id'], text=f"{a['order']} · {label}")
                    self.item_map[a['id']] = ('action', f, c, a)
        self.selected = None; self.render_panel()
        if select_id and select_id in self.item_map:
            self.tree.selection_set(select_id); self.tree.see(select_id)
        self.schedule_save()
    def select(self, _=None):
        if self.selection_guard: return
        sel = self.tree.selection()
        next_selected = self.item_map.get(sel[0]) if sel else None
        old_id = self.selected[3]['id'] if self.selected and self.selected[0]=='action' else self.selected[2]['id'] if self.selected and self.selected[0]=='condition' else self.selected[1]['id'] if self.selected else None
        next_id = sel[0] if sel else None
        if old_id == next_id: return
        if self.form_errors:
            if old_id and self.tree.exists(old_id):
                self.selection_guard=True; self.tree.selection_set(old_id); self.selection_guard=False
                self.ensure_valid(); return
        self.selected = next_selected
        self.render_panel()
    def drag_press(self, event):
        self.drag_cancel()
        row=self.tree.identify_row(event.y)
        # Do not turn clicks on the expand/collapse triangle into a drag.
        if row and 'indicator' not in self.tree.identify('element', event.x, event.y):
            self.drag_source=row;self.drag_origin=(event.x,event.y);self.drag_point=(event.x,event.y)

    def drag_motion(self, event):
        if not self.drag_source:return
        self.drag_point=(event.x,event.y)
        if not self.drag_started:
            dx=event.x-self.drag_origin[0];dy=event.y-self.drag_origin[1]
            if dx*dx+dy*dy<25:return
            self.drag_started=True
        self.update_drag_indicator()
        if self.drag_scroll_job is None:
            self.drag_scroll_job=self.after(120,self.drag_autoscroll)
        return 'break'

    def drag_autoscroll(self):
        self.drag_scroll_job=None
        if not self.drag_started or not self.drag_point:return
        x,y=self.drag_point;height=self.tree.winfo_height()
        if y<24:self.tree.yview_scroll(-1,'units')
        elif y>height-24:self.tree.yview_scroll(1,'units')
        self.update_drag_indicator()
        self.drag_scroll_job=self.after(120,self.drag_autoscroll)

    def drag_drop_target(self,source,target,after):
        """Return destination parent iid and pre-removal index, or None."""
        if source not in self.item_map or target not in self.item_map or source==target:return None
        kind=self.item_map[source][0];target_kind=self.item_map[target][0]
        if kind==target_kind:
            parent=self.tree.parent(target)
            return parent,self.tree.index(target)+(1 if after else 0)
        if kind=='condition' and target_kind=='flow':
            return target,len(self.tree.get_children(target))
        if kind=='action' and target_kind=='condition':
            return target,len(self.tree.get_children(target))
        return None

    def update_drag_indicator(self):
        self.drop_line.place_forget()
        if not self.drag_source or not self.drag_point:return
        x,y=self.drag_point;width=self.tree.winfo_width();height=self.tree.winfo_height()
        if x<0 or x>=width:return
        row=self.tree.identify_row(max(0,min(height-1,y)))
        if not row:return
        box=self.tree.bbox(row)
        if not box:return
        _,top,_,h=box;after=y>=top+h/2
        location=self.drag_drop_target(self.drag_source,row,after)
        if location is None:return
        parent,_=location
        # A parent row means append into that parent; same-kind rows mean before/after.
        child_target=self.item_map[row][0]!=self.item_map[self.drag_source][0]
        line_y=top+h-2 if child_target or after else max(0,top-1)
        self.drop_line.place(x=2,y=line_y,width=max(1,width-4),height=3)
        self.drop_line.lift()

    def drag_release(self,event):
        if not self.drag_source:return
        source=self.drag_source;started=self.drag_started
        self.drag_cancel()
        if not started:return
        width=self.tree.winfo_width();height=self.tree.winfo_height()
        if event.x<0 or event.x>=width or event.y<0 or event.y>=height:return 'break'
        target=self.tree.identify_row(event.y)
        if not target:return 'break'
        box=self.tree.bbox(target)
        if not box:return 'break'
        location=self.drag_drop_target(source,target,event.y>=box[1]+box[3]/2)
        if location is not None and self.ensure_valid():
            self.move_tree_item(source,*location)
        return 'break'

    def drag_cancel(self, event=None):
        if self.drag_scroll_job is not None:
            try:self.after_cancel(self.drag_scroll_job)
            except tk.TclError:pass
        self.drag_scroll_job=None;self.drag_source=None;self.drag_started=False;self.drag_point=None
        if hasattr(self,'drop_line'):self.drop_line.place_forget()

    def move_tree_item(self,source,parent,index):
        """Reorder the model and tree, preserving descendants and action numbers."""
        if source not in self.item_map:return False
        kind,old_flow,old_condition,action=self.item_map[source]
        if kind=='flow':
            if parent!='':return False
            src=self.flows;dst=self.flows;obj=old_flow;new_flow=old_flow;new_condition=None
        elif kind=='condition':
            info=self.item_map.get(parent)
            if not info or info[0]!='flow':return False
            new_flow=info[1];src=old_flow['conditions'];dst=new_flow['conditions'];obj=old_condition;new_condition=obj
        else:
            info=self.item_map.get(parent)
            if not info or info[0]!='condition':return False
            new_flow,new_condition=info[1],info[2];src=old_condition['actions'];dst=new_condition['actions'];obj=action
        # Compare IDs rather than equality (conditions contain numpy images).
        src_index=next((i for i,v in enumerate(src) if v['id']==source),None)
        if src_index is None or not isinstance(index,int) or not 0<=index<=len(dst):return False
        if src is dst and src_index<index:index-=1
        if src is dst and src_index==index:return False
        src.pop(src_index);dst.insert(index,obj)
        self.tree.move(source,parent,index)
        if kind=='condition':
            self.item_map[source]=('condition',new_flow,obj,None)
            for a in obj['actions']:self.item_map[a['id']]=('action',new_flow,obj,a)
        elif kind=='action':self.item_map[source]=('action',new_flow,new_condition,obj)
        self.selection_guard=True
        try:self.tree.selection_set(source);self.tree.focus(source);self.tree.see(source)
        finally:self.selection_guard=False
        self.selected=self.item_map[source];self.render_panel();self.schedule_save()
        if kind=='action':
            self.status.set('Đã di chuyển thao tác. Số thứ tự không đổi; hãy kiểm tra nhóm cùng số. Áp dụng từ lần chạy sau.')
        else:self.status.set('Đã sắp xếp cấu trúc. Thay đổi áp dụng từ lần chạy sau; nhớ lưu script.')
        return True

    def add_flow(self):
        if not self.ensure_valid(): return
        f = {'id': new_id(), 'name': f'Luồng {len(self.flows)+1}', 'conditions': []}; self.flows.append(f); self.refresh_tree(f['id'])
    def add_condition(self):
        if not self.ensure_valid(): return
        if not self.selected: messagebox.showinfo('Chọn luồng', 'Chọn một luồng trước.'); return
        f = self.selected[1]; c = new_condition(); c.update(self.preferences['condition']); c['name'] = f"Điều kiện {len(f['conditions'])+1}"; f['conditions'].append(c); self.refresh_tree(c['id'])
    def add_action(self):
        if not self.ensure_valid(): return
        if not self.selected or not self.selected[2]: messagebox.showinfo('Chọn điều kiện', 'Chọn một điều kiện trước.'); return
        c = self.selected[2]; a = new_action(); a.update(self.preferences['action'])
        if c['actions']: a['order'] = max(v['order'] for v in c['actions'])+1
        c['actions'].append(a); self.refresh_tree(a['id'])
    def delete_item(self):
        if not self.ensure_valid(): return
        if not self.selected: return
        kind, f, c, a = self.selected
        if not messagebox.askyesno('Xóa', 'Xóa mục đang chọn và toàn bộ mục bên trong?'): return
        if kind == 'flow': self.flows.remove(f); select_id = None
        elif kind == 'condition': f['conditions'].remove(c); select_id = f['id']
        else: c['actions'].remove(a); select_id = c['id']
        self.refresh_tree(select_id)
    def field(self, frame, label, name, value, choices=None):
        row = len(self.vars)
        lab = ttk.Label(frame, text=label); lab.grid(row=row, column=0, sticky='w', pady=4, padx=(0,10))
        var = tk.StringVar(value=str(value)); self.vars[name] = var
        if choices: widget = ttk.Combobox(frame, textvariable=var, values=choices, state='readonly', width=24)
        else: widget = ttk.Entry(frame, textvariable=var, width=27)
        widget.grid(row=row, column=1, sticky='w', pady=4)
        if name=='key' and self.selected and self.selected[0]=='action':
            widget.bind('<KeyPress>',self.capture_key_press)
            widget.bind('<FocusIn>',lambda _event:setattr(self,'key_capture_focused',True))
            widget.bind('<FocusOut>',lambda _event:setattr(self,'key_capture_focused',False))
        self.field_widgets[name] = (lab, widget)
        return widget
    def capture_key_press(self,event):
        """Edit whole key tokens; consume keystrokes instead of inserting text."""
        widget=event.widget
        name=keyboard_keys.from_tk_event(event)
        if name in ('F6','F7','F8'):
            self.status.set('F6–F8 không dùng trong ô phím; rời ô để điều khiển app.')
            return 'break'
        if name is None:
            self.status.set('Phím này chưa được hỗ trợ hoặc hệ điều hành không chuyển phím cho app.')
            return 'break'
        text=widget.get();spans=list(re.finditer(r'\S+',text));tokens=[m.group() for m in spans]
        cursor=widget.index('insert')
        try:selection=(widget.index('sel.first'),widget.index('sel.last'))
        except tk.TclError:selection=None
        selected=[i for i,m in enumerate(spans) if selection and m.start()<selection[1] and m.end()>selection[0]]
        if selected:
            position=selected[0]
            tokens=[t for i,t in enumerate(tokens) if i not in selected]
        else:
            position=sum(m.end()<=cursor for m in spans)
            for i,m in enumerate(spans):
                if m.start()<cursor<m.end():
                    position=i+(1 if cursor>=(m.start()+m.end())/2 else 0);break
        if name=='Backspace':
            if not selected:
                inside=next((i for i,m in enumerate(spans) if m.start()<cursor<m.end()),None)
                remove=inside if inside is not None else position-1
                if 0<=remove<len(tokens):tokens.pop(remove);position=remove
        else:
            # A chord cannot press the same physical key twice at once.
            try:
                code=keyboard_keys.parse_token(name)[1]
                if any(keyboard_keys.parse_token(t)[1]==code for t in tokens):
                    self.status.set('Phím đã có trong tổ hợp; một phím chỉ được thêm một lần.')
                    return 'break'
            except ValueError:return 'break'
            tokens.insert(position,name);position+=1
        value=' '.join(tokens);widget.delete(0,'end');widget.insert(0,value)
        charpos=len(' '.join(tokens[:position]))
        if 0<position<len(tokens):charpos+=1
        widget.icursor(charpos)
        return 'break'

    def render_panel(self):
        self.key_capture_focused=False
        for w in self.right.winfo_children(): w.destroy()
        self.vars = {}; self.field_widgets = {}; self.form_errors = {}
        if not self.selected:
            ttk.Label(self.right, text='Tạo một luồng để bắt đầu.', font=('Segoe UI', 12)).pack(anchor='w'); return
        kind, f, c, a = self.selected
        title = {'flow':'Cấu hình luồng', 'condition':'Cấu hình điều kiện', 'action':'Cấu hình thao tác'}[kind]
        ttk.Label(self.right, text=title, font=('Segoe UI', 13, 'bold')).pack(anchor='w', pady=(0,8))
        form = ttk.Frame(self.right); form.pack(anchor='w')
        if kind == 'flow': self.field(form, 'Tên luồng', 'name', f['name'])
        elif kind == 'condition':
            for label, key in [('Tên điều kiện','name'), ('Độ giống tối thiểu (0–1)','sim'), ('Độ giống màu tối thiểu (0–1)','color_sim'), ('Độ sáng tối thiểu (0–1)','bright'), ('Ổn định ít nhất (ms)','stable')]: self.field(form, label, key, c[key])
            if self.script_mode=='Lặp lại':
                self.field(form, 'Thời gian tìm / xét ổn định (ms)', 'stability_window', c['stability_window'])
                self.field(form, 'Không đạt ổn định để chạy lại (ms)', 'release_stable', c['release_stable'])
                self.field(form, 'Cách kích hoạt', 'mode', c['mode'], ('Một lần', 'Lặp'))
                for label, key in [('Nghỉ sau chuỗi (ms)','cool'), ('Số lần tối đa','maximum')]: self.field(form, label, key, c[key])
                unlimited=tk.BooleanVar(value=c.get('unlimited',False));self.vars['unlimited']=unlimited
                ttk.Checkbutton(form,text='Không giới hạn',variable=unlimited).grid(row=len(self.vars)-2,column=2,sticky='w',padx=5)
                self.field_widgets['maximum'][1].configure(state='disabled' if unlimited.get() else 'normal')
            confirm_row=form.grid_size()[1]
            confirm=tk.BooleanVar(value=c.get('confirm_activation',False));self.vars['confirm_activation']=confirm
            ttk.Checkbutton(form,text='Xác nhận đã kích hoạt',variable=confirm).grid(row=confirm_row,column=0,columnspan=3,sticky='w',pady=3)
        else:
            self.field(form, 'Số thứ tự', 'order', a['order'])
            action_type_widget = self.field(form, 'Loại thao tác', 'type', a['type'], ('Phím', 'Chuột trái', 'Chuột phải'))
            mouse_mode_widget = self.field(form, 'Vị trí chuột', 'mouse_mode', a.get('mouse_mode', 'Đến tọa độ'), ('Đến tọa độ', 'Nhấn tại con trỏ hiện tại', 'Tọa độ; nếu lỗi nhấn tại chỗ'))
            mouse_mode_widget.config(width=35)
            for label, key in [('Bấm phím để chọn','key'), ('Tọa độ chuột X','x'), ('Tọa độ chuột Y','y'), ('Thời gian nhấn giữ (ms)','hold'), ('Số lần lặp thao tác','repeat'), ('Nghỉ giữa các lần (ms)','interval'), ('Chờ sau thao tác (ms)','after_delay')]:
                self.field(form, label, key, a.get(key, 1 if key == 'repeat' else 200 if key == 'interval' else 0 if key == 'after_delay' else ''))
        for key, var in self.vars.items():
            var.trace_add('write', lambda *_args, k=key: self.on_field_change(k))
        if kind == 'condition':
            bar = ttk.Frame(self.right); bar.pack(anchor='w', pady=8)
            ttk.Button(bar, text='Chụp và chọn vùng', command=self.capture_region).pack(side='left', padx=(0,4))
            ttk.Button(bar, text='Sửa mặt nạ', command=self.edit_mask).pack(side='left', padx=4)
            if c['region'] is None:
                text = 'Chưa chọn ảnh'
            else:
                text = 'Đã chọn vùng ảnh'
            ttk.Label(self.right, text=text, wraplength=540).pack(anchor='w')
            if c['template'] is not None:
                image = c['template'].copy()
                if c['mask'] is not None:
                    sel = c['mask'] > 0; image[sel] = (image[sel].astype(np.float32)*.65 + np.array([0,255,0])*.35).astype(np.uint8)
                h,w = image.shape[:2]; scale = min(2, 360/w, 150/h)
                self.preview = photo(cv2.resize(image, (max(1,int(w*scale)), max(1,int(h*scale)))))
                ttk.Label(self.right, image=self.preview).pack(anchor='w', pady=8)
            if self.script_mode=='Lặp lại': ttk.Label(self.right, text='Một lần: cần không đạt ổn định rồi đạt lại. Lặp: chạy tiếp sau khoảng nghỉ.').pack(anchor='w')
        if kind == 'action':
            marker_button = ttk.Button(self.right, text='Đặt/kéo điểm chuột', command=self.marker_overlay)
            marker_button.pack(anchor='w')
            def update_type(_=None):
                is_key = self.vars['type'].get() == 'Phím'
                at_current = self.vars['mouse_mode'].get() == 'Nhấn tại con trỏ hiện tại'
                for field_name in ('key', 'mouse_mode', 'x', 'y'):
                    visible = is_key if field_name == 'key' else (not is_key if field_name == 'mouse_mode' else not is_key and not at_current)
                    for widget in self.field_widgets[field_name]:
                        if visible: widget.grid()
                        else: widget.grid_remove()
                if is_key or at_current: marker_button.pack_forget()
                else: marker_button.pack(anchor='w')
            action_type_widget.bind('<<ComboboxSelected>>', update_type)
            mouse_mode_widget.bind('<<ComboboxSelected>>', update_type)
            update_type()
    def get_condition(self):
        if not self.selected or self.selected[2] is None:
            messagebox.showinfo('Chọn điều kiện', 'Hãy chọn một điều kiện hoặc thao tác trong điều kiện.'); return None
        return self.selected[2]
    def capture_region(self):
        if not self.ensure_valid(): return
        c = self.get_condition()
        if c is None: return
        self.withdraw(); self.after(500, lambda:self._region_overlay(c))
    def screenshot_overlay(self):
        with mss.mss() as s:
            mon = s.monitors[1]; screen = np.array(s.grab(mon))[:,:,:3].copy()
        overlay = tk.Toplevel(self); overlay.overrideredirect(True); overlay.attributes('-topmost', True)
        overlay.geometry(f"{mon['width']}x{mon['height']}+{mon['left']}+{mon['top']}")
        canvas = tk.Canvas(overlay, width=mon['width'], height=mon['height'], cursor='crosshair', highlightthickness=0); canvas.pack()
        pic = photo(screen); canvas.create_image(0,0, image=pic, anchor='nw'); overlay.pic = pic
        return mon, screen, overlay, canvas
    def _region_overlay(self, c):
        try:
            mon, screen, over, canvas = self.screenshot_overlay()
            canvas.create_text(12,12,anchor='nw',text='Kéo chọn vùng · Esc hủy',fill='red',font=('Segoe UI',16,'bold'))
            start=[0,0]; rect=[None]
            def down(e):
                start[:] = [e.x,e.y]
                if rect[0]: canvas.delete(rect[0])
                rect[0] = canvas.create_rectangle(e.x,e.y,e.x,e.y,outline='red',width=2)
            def move(e):
                if rect[0]: canvas.coords(rect[0],start[0],start[1],e.x,e.y)
            def cancel(e=None): over.destroy(); self.deiconify(); self.lift()
            def up(e):
                x1,x2=sorted((max(0,min(mon['width'],start[0])),max(0,min(mon['width'],e.x))))
                y1,y2=sorted((max(0,min(mon['height'],start[1])),max(0,min(mon['height'],e.y))))
                if x2-x1<5 or y2-y1<5: return
                c['region']={'left':int(mon['left']+x1),'top':int(mon['top']+y1),'width':int(x2-x1),'height':int(y2-y1)}
                c['template']=screen[y1:y2,x1:x2].copy(); c['mask']=None
                cancel(); self.refresh_tree(c['id']); self.after(100, lambda:self._mask_for(c))
            canvas.bind('<ButtonPress-1>',down); canvas.bind('<B1-Motion>',move); canvas.bind('<ButtonRelease-1>',up); over.bind('<Escape>',cancel); over.focus_force()
        except Exception as e: self.deiconify(); messagebox.showerror('Chụp màn hình',str(e))
    def edit_mask(self):
        if not self.ensure_valid(): return
        c=self.get_condition()
        if c is not None: self._mask_for(c)
    def _mask_for(self,c):
        if c['template'] is None: messagebox.showinfo('Ảnh mẫu','Chụp vùng trước.'); return
        def save(mask): c['mask']=mask; self.refresh_tree(c['id'])
        MaskEditor(self,c['template'],save,c['mask'])
    def marker_overlay(self):
        c=self.get_condition()
        if c is None: return
        if not self.ensure_valid(): return
        actions=[a for a in c['actions'] if a['type']!='Phím' and a.get('mouse_mode', 'Đến tọa độ') != 'Nhấn tại con trỏ hiện tại']
        if not actions: messagebox.showinfo('Chưa có chuột','Thêm thao tác chuột trái/phải có chế độ tọa độ vào điều kiện.'); return
        self.withdraw(); self.after(500,lambda:self._markers(c,actions))
    def _markers(self,c,actions):
        try:
            mon, screen, over, canvas=self.screenshot_overlay()
            canvas.create_rectangle(0,0,mon['width'],40,fill='#151b25',outline='')
            canvas.create_text(12,20,anchor='w',text='Kéo các số tới vị trí nhấn · Enter: lưu · Esc: hủy',fill='white',font=('Segoe UI',14,'bold'))
            selected_id = self.selected[3]['id'] if self.selected and self.selected[0] == 'action' else c['id']
            markers={}; originals={a['id']:(a['x'],a['y']) for a in actions}; active=[None]; last_dragged=[None]
            for index,a in enumerate(actions):
                x=max(20,min(mon['width']-20,a['x']-mon['left'])); y=max(60,min(mon['height']-20,a['y']-mon['top']))
                # Separate default overlapping markers so each can be grabbed.
                if originals[a['id']]==(100,100): x=80+index*42; y=80
                tag='marker'+str(index)
                canvas.create_oval(x-17,y-17,x+17,y+17,fill='#ffae00',outline='#111',width=2,tags=(tag,))
                canvas.create_text(x,y,text=str(a['order']),fill='black',font=('Segoe UI',12,'bold'),tags=(tag,))
                markers[tag]={'action':a,'x':x,'y':y}
                def select(e,t=tag): active[0]=t
                canvas.tag_bind(tag,'<ButtonPress-1>',select)
            def drag(e):
                tag=active[0]
                if not tag:return
                m=markers[tag]; last_dragged[0]=tag; x=max(0,min(mon['width']-1,e.x)); y=max(0,min(mon['height']-1,e.y))
                canvas.move(tag,x-m['x'],y-m['y']); m['x']=x; m['y']=y
            canvas.bind('<B1-Motion>',drag); canvas.bind('<ButtonRelease-1>',lambda e:active.__setitem__(0,None))
            def finish(save):
                if save:
                    for m in markers.values(): m['action']['x']=int(m['x']+mon['left']); m['action']['y']=int(m['y']+mon['top'])
                    if last_dragged[0]:
                        chosen=markers[last_dragged[0]]['action']; self.preferences['action'].update(x=chosen['x'],y=chosen['y']); self.schedule_preferences_save()
                over.destroy(); self.deiconify(); self.lift(); self.refresh_tree(selected_id)
            over.bind('<Return>',lambda e:finish(True)); over.bind('<Escape>',lambda e:finish(False)); over.focus_force()
        except Exception as e: self.deiconify(); messagebox.showerror('Đặt điểm chuột',str(e))
    def new_script(self):
        if self.pending or self.engine and self.engine.alive():
            messagebox.showwarning('Đang chạy', 'Hãy dừng script trước khi tạo script mới.'); return
        if not self.ensure_valid() or not self.prepare_switch(): return
        self.session_path = None; self.flows = []; self.script_mode='Lặp lại'; self.script_mode_var.set(self.script_mode); self.refresh_tree(); self.dirty = False
        self.status.set('Script mới. Lưu script khi bạn muốn.'); self.log('Đã tạo script mới.')
    def save_script(self):
        if not self.ensure_valid(): return
        path = self.session_path
        if path is None:
            path = filedialog.asksaveasfilename(defaultextension='.json', filetypes=[('Script Macro Vision','*.json')], title='Lưu script')
            if not path: return
        reserved=[prefs_store.application_dir() / prefs_store.SETTINGS_NAME]
        if self.preference_store: reserved.append(self.preference_store.path)
        if any(os.path.normcase(os.path.abspath(path)) == os.path.normcase(os.path.abspath(p)) for p in reserved):
            messagebox.showerror('Không thể lưu','Đây là file thiết lập của ứng dụng. Hãy chọn file script khác.'); return
        try:
            form_model.atomic_json(path,self.script_payload()); self.session_path=path; self.dirty=False; self.log('Đã lưu script: '+path)
        except Exception as e: messagebox.showerror('Không thể lưu script',str(e))
    def load_script(self):
        if not self.ensure_valid(): return
        if self.pending or self.engine and self.engine.alive():
            messagebox.showwarning('Đang chạy', 'Hãy dừng trước khi mở script khác.'); return
        path = filedialog.askopenfilename(filetypes=[('Script Macro Vision','*.json')], title='Chọn script để mở')
        if not path: return
        try: flows, loaded_mode, legacy = self.parse_script_file(path)
        except Exception as e: messagebox.showerror('Mở', str(e)); return
        if not self.prepare_switch(): return
        self.session_path = None if legacy else path; self.flows = flows; self.script_mode=loaded_mode; self.script_mode_var.set(loaded_mode); self.refresh_tree(); self.dirty = False
        self.log('Đã mở script: ' + path + (' (phiên cũ chỉ đọc; lưu ra file mới)' if legacy else ''))
    def start(self):
        if not self.ensure_valid(): return
        if self.pending or self.engine and self.engine.alive(): return
        try:
            snapshot=copy.deepcopy(self.flows); rules=once_engine.validate(snapshot) if self.script_mode=='Một lần' else engine.validate(snapshot)
        except Exception as e: messagebox.showerror('Chưa thể chạy',str(e)); return
        self.pending=True; self.countdown_token += 1; token = self.countdown_token; self.start_button.config(state='disabled'); self.pause_button.config(state='disabled')
        self.begin(rules,token,self.script_mode)
    def begin(self,rules,token,script_mode='Lặp lại'):
        if not self.pending or token != self.countdown_token:return
        hwnd=win.foreground(); self.pending=False
        engine_class=once_engine.OnceEngine if script_mode=='Một lần' else engine.Engine
        self.engine=engine_class(rules,hwnd,False,lambda k,v:self.messages.put((k,v)),self.anti_detect); self.engine.start(); self.pause_button.config(state='normal', text='Tạm dừng · F7'); self.log('Cửa sổ đích: ' + win.window_title(hwnd)); self.log('Đã bắt đầu. Các chỉnh sửa mới chỉ áp dụng cho lần chạy sau.')
    def toggle_pause(self):
        if self.pending:
            self.log('F7 khả dụng sau khi bắt đầu; F8 để dừng.')
            return
        if not self.engine or not self.engine.alive() or self.engine.stop_event.is_set():
            self.log('Không có script đang chạy để tạm dừng/tiếp tục.')
            return
        if self.engine.pause_event.is_set():
            if win.foreground() != self.engine.target:
                self.status.set('Hãy trở về cửa sổ đích rồi nhấn F7 để tiếp tục.')
                self.log('Chưa tiếp tục: cửa sổ đích không ở phía trước.')
                return
            self.engine.resume(); self.pause_button.config(text='Tạm dừng · F7')
            self.status.set('Đang tiếp tục. F7 tạm dừng · F8 dừng hẳn.')
            self.log('F7: tiếp tục từ thao tác còn lại.')
        else:
            self.engine.pause(); self.pause_button.config(text='Tiếp tục · F7')
            self.status.set('Tạm dừng: lần nhấn/giữ đang diễn ra sẽ kết thúc trước khi nghỉ.')
            self.log('F7: yêu cầu tạm dừng; đợi nhả lần nhấn/giữ đang diễn ra.')
    def stop(self):
        self.pending=False; self.countdown_token += 1
        if self.engine: self.engine.stop()
        self.status.set('Đang dừng...'); self.log('Đã yêu cầu dừng.');
        if not self.engine or not self.engine.alive(): self.start_button.config(state='normal')
    def tick(self):
        try:
            down = {'F6': win.f6_down(), 'F7': win.f7_down(), 'F8': win.f8_down()}
            pressed = {key for key in down if down[key] and not self.hotkey_states[key]}
            self.hotkey_states = down
            if self.key_capture_focused: pressed.clear()
            if 'F8' in pressed:
                if self.pending or self.engine and self.engine.alive(): self.stop()
            elif 'F7' in pressed: self.toggle_pause()
            elif 'F6' in pressed: self.start()
            while True:
                kind,msg=self.messages.get_nowait()
                if kind=='status':
                    if not self.engine or not self.engine.pause_event.is_set(): self.status.set(msg)
                elif kind in ('action','condition'): self.log_action(msg)
                elif kind=='log':
                    # Keep errors/interruptions visible even with detailed diagnostics hidden.
                    important=('LỖI', 'CẢNH BÁO', 'FOCUS', 'Chuỗi bị ngắt')
                    if any(word in msg for word in important): self.log(msg)
                else: self.log(msg)
        except queue.Empty: pass
        if self.engine and not self.engine.alive() and not self.pending:
            self.start_button.config(state='normal'); self.pause_button.config(state='disabled', text='Tạm dừng · F7')
        self.tick_job = self.after(30,self.tick)
    def close(self):
        if self.engine: self.engine.stop()
        self.pending=False; self.countdown_token += 1
        if not self.engine or not self.engine.alive(): self.start_button.config(state='normal')
        if not self.ensure_valid(): return
        if self.dirty and not messagebox.askyesno('Chưa lưu script','Script có thay đổi chưa lưu. Vẫn thoát và bỏ các thay đổi?'): return
        if self.save_job is not None and not self.persist_preferences():
            if not messagebox.askyesno('Lỗi lưu thiết lập','Không lưu được thiết lập mới. Vẫn thoát?'): return
        self.pending=False
        if self.engine:
            self.engine.stop(); self.engine.action_thread.join(timeout=1)
        try: self.after_cancel(self.tick_job)
        except tk.TclError: pass
        self.destroy()

if __name__=='__main__':
    if os.name!='nt': print('Ứng dụng chỉ hỗ trợ Windows.'); raise SystemExit(1)
    win.dpi_aware(); App().mainloop()
