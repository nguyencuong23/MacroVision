"""Capture actual Tk key events and exercise chord safety with mocked Win32."""
import os,tempfile,threading,time,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import app,keyboard_keys as keys,engine,windows_input as win
from test_queue_execution import action,cond

class KeyLogicTests(unittest.TestCase):
    def test_old_shift_and_literal_shift_letters_are_distinct(self):
        self.assertEqual(keys.parse_chord('SHIFT')[1],[0x10])
        self.assertEqual(keys.parse_chord('S H I F T')[1],list(map(ord,'SHIFT')))
        self.assertEqual(keys.parse_chord('a  SPACE Home esc')[0],['A','Space','Home','Esc'])
    def test_backspace_reserved_f6_f7_f8_rejected_and_duplicates_rejected(self):
        for text in ('Backspace','F6','F7','F8','A F6','A A','SHIFT shift'):
            with self.subTest(text=text):
                with self.assertRaises(ValueError):keys.parse_chord(text)
    def test_event_mapping_shift_home_space_and_punctuation(self):
        for sym,name in [('Shift_L','Shift'),('Shift_R','Shift'),('Escape','Esc'),('Home','Home'),('space','Space'),('BackSpace','Backspace'),('F6','F6'),('KP_5','Numpad5'),('semicolon','Semicolon')]:
            with self.subTest(sym=sym):self.assertEqual(keys.from_tk_event(SimpleNamespace(keysym=sym,keycode=0)),name)
    def test_windows_event_uses_physical_vk_not_layout_character(self):
        with patch.object(keys.os,'name','nt'):
            self.assertEqual(keys.from_tk_event(SimpleNamespace(keysym='exclam',keycode=0x31)),'1')
            self.assertEqual(keys.from_tk_event(SimpleNamespace(keysym='odiaeresis',keycode=0xba)),'Semicolon')
            self.assertEqual(keys.from_tk_event(SimpleNamespace(keysym='Home',keycode=0x24)),'Home')
    def test_keys_pressed_and_released_as_a_chord_reverse_order(self):
        events=[];a=action('S H I F T',1,20)
        with patch.object(win,'foreground',return_value=7),patch.object(win,'key_down',side_effect=lambda k:events.append(('down',k))),patch.object(win,'key_up',side_effect=lambda k:events.append(('up',k))):
            self.assertTrue(engine.run_group([a],7,threading.Event()))
        self.assertEqual(events,[('down',ord(k)) for k in 'SHIFT']+[('up',ord(k)) for k in 'TFIHS'])
    def test_stop_and_focus_loss_release_all_pressed_keys(self):
        events=[];stop=threading.Event();a=action('A B C',1,300)
        def down(v):events.append(('down',v));stop.set() if v==66 else None
        with patch.object(win,'foreground',return_value=7),patch.object(win,'key_down',side_effect=down),patch.object(win,'key_up',side_effect=lambda k:events.append(('up',k))):
            self.assertFalse(engine.run_group([a],7,stop))
        self.assertEqual(events,[('down',65),('down',66),('up',66),('up',65)])
    def test_partial_send_failure_releases_attempted_and_previously_pressed(self):
        events=[];a=action('A B C',1,30)
        def down(k):
            events.append(('down',k))
            if k==66:raise RuntimeError('failure')
        with patch.object(win,'foreground',return_value=7),patch.object(win,'key_down',side_effect=down),patch.object(win,'key_up',side_effect=lambda k:events.append(('up',k))):
            with self.assertRaises(RuntimeError):engine.run_group([a],7,threading.Event())
        self.assertEqual(events,[('down',65),('down',66),('up',66),('up',65)])
    def test_release_failure_attempts_every_key_and_retries_failed(self):
        events=[];calls={}
        def up(k):
            events.append(k);calls[k]=calls.get(k,0)+1
            if k==66 and calls[k]==1:raise RuntimeError('up failed')
        with patch.object(win,'foreground',return_value=7),patch.object(win,'key_down'),patch.object(win,'key_up',side_effect=up):
            with self.assertRaises(RuntimeError):engine.run_group([action('A B C',1,20)],7,threading.Event())
        self.assertEqual(events,[67,66,65,66])
    def test_same_group_shared_key_rejected_but_other_groups_allowed(self):
        import numpy as np
        c=cond('C',[action('Ctrl A',1),action('A B',1)]);c.update(template=np.zeros((4,4,3),np.uint8),mask=np.ones((4,4),np.uint8),region={'left':0,'top':0,'width':4,'height':4})
        script=[{'name':'L','conditions':[c]}]
        with self.assertRaisesRegex(ValueError,'phím trùng nhau'):engine.validate(script)
        c['actions'][1]['order']=2;self.assertEqual(len(engine.validate(script)),1)
    def test_extended_key_flags_for_home_and_ordinary_shift(self):
        sent=[]
        with patch.object(win,'KEYBDINPUT',create=True,side_effect=lambda *v:v),patch.object(win,'INPUT',create=True,side_effect=lambda **v:v),patch.object(win,'_send',side_effect=sent.append):
            win._key(0x24,False);win._key(0x24,True);win._key(0x10,False)
        self.assertEqual([v['ki'][2] for v in sent],[1,3,0])

@unittest.skipUnless(os.name!='nt' and os.environ.get('DISPLAY'),'Requires Xvfb/display')
class CaptureUITests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name)
        self.patches=[patch.object(app.prefs_store,'application_dir',return_value=self.base)]+[patch.object(app.win,n,return_value=False) for n in ('f6_down','f7_down','f8_down')]
        for p in self.patches:p.start()
        self.r=app.App();self.r.add_flow();self.r.update();self.r.add_condition();self.r.update();self.r.add_action();self.r.update()
        self.entry=self.r.field_widgets['key'][1];self.entry.focus_force();self.r.update()
        self.entry.selection_range(0,'end')
    def tearDown(self):
        try:self.r.after_cancel(self.r.tick_job);self.r.cancel_pending_save();self.r.destroy()
        except Exception:pass
        for p in reversed(self.patches):p.stop()
        self.tmp.cleanup()
    def press(self,sym):
        self.entry.event_generate('<KeyPress>',keysym=sym);self.r.update()
        self.entry.event_generate('<KeyRelease>',keysym=sym);self.r.update()
    def test_typing_shift_spells_five_keys_not_shift_key(self):
        for sym in 'shift':self.press(sym)
        self.assertEqual(self.entry.get(),'S H I F T');self.assertEqual(self.r.selected[3]['key'],'S H I F T')
    def test_actual_shift_esc_home_space_are_captured(self):
        for sym in ('Shift_L','Escape','Home','space'):self.press(sym)
        self.assertEqual(self.entry.get(),'Shift Esc Home Space');self.assertEqual(self.r.selected[3]['key'],'Shift Esc Home Space')
    def test_backspace_deletes_preceding_token_at_cursor_and_selected_token(self):
        for sym in ('a','b','c'):self.press(sym)
        self.entry.icursor(2);self.press('BackSpace');self.assertEqual(self.entry.get(),'B C')
        self.entry.icursor(1);self.press('BackSpace');self.assertEqual(self.entry.get(),'C')
        self.entry.selection_range(0,'end');self.press('BackSpace');self.assertEqual(self.entry.get(),'');self.assertIn('key',self.r.form_errors)
    def test_typing_in_middle_inserts_token_at_cursor(self):
        for sym in ('a','c'):self.press(sym)
        self.entry.icursor(2);self.press('b');self.assertEqual(self.entry.get(),'A B C')
    def test_f6_f7_f8_ignored_and_global_hotkeys_suppressed_while_focused(self):
        self.press('a');before=self.entry.get()
        for k in ('F6','F7','F8'):self.press(k);self.assertEqual(self.entry.get(),before)
        self.assertTrue(self.r.key_capture_focused);self.r.after_cancel(self.r.tick_job)
        with patch.object(app.win,'f6_down',return_value=True),patch.object(self.r,'start') as start:
            self.r.tick();self.r.after_cancel(self.r.tick_job);start.assert_not_called()
        self.entry.master.focus_force();self.r.update();self.assertFalse(self.r.key_capture_focused)
    def test_no_duplicate_keys_in_single_chord(self):
        self.press('a');self.press('a');self.assertEqual(self.entry.get(),'A')
    def test_hotkeys_f6_f7_f8_suppressed_in_focused_field(self):
        self.assertTrue(self.r.key_capture_focused)
        for name,method in [('f6_down','start'),('f7_down','toggle_pause'),('f8_down','stop')]:
            self.r.hotkey_states={'F6':False,'F7':False,'F8':False}
            self.r.after_cancel(self.r.tick_job)
            with patch.object(app.win,name,return_value=True),patch.object(self.r,method) as call:
                self.r.tick();self.r.after_cancel(self.r.tick_job);call.assert_not_called()
        self.r.tick()
    def test_tab_and_delete_are_captured_not_used_for_navigation(self):
        for sym in ('Tab','Delete','Left'):self.press(sym)
        self.assertEqual(self.entry.get(),'Tab Delete Left');self.assertIs(self.r.focus_get(),self.entry)
    def test_recorded_chord_roundtrip_in_script(self):
        for sym in ('Shift_L','a','Home','space'):self.press(sym)
        data=self.r.script_payload();flows=app.deserialize(data)
        self.assertEqual(flows[0]['conditions'][0]['actions'][0]['key'],'Shift A Home Space')
        self.assertEqual(win.parse_chord(flows[0]['conditions'][0]['actions'][0]['key']),[0x10,65,0x24,0x20])
class ChordSafetyMoreTests(unittest.TestCase):
    def test_focus_loss_mid_chord_stops_and_releases_pressed_only(self):
        focus=[7];events=[]
        def down(k):
            events.append(('down',k))
            if k==65:focus[0]=8
        with patch.object(win,'foreground',side_effect=lambda:focus[0]),patch.object(win,'describe_window',side_effect=lambda x:str(x)),patch.object(win,'key_down',side_effect=down),patch.object(win,'key_up',side_effect=lambda k:events.append(('up',k))):
            self.assertFalse(engine.run_group([action('A B',1,30)],7,threading.Event()))
        self.assertEqual(events,[('down',65),('up',65)])
    def test_repeat_releases_all_keys_before_next_chord(self):
        a=action('Shift A',1,15);a.update(repeat=2,interval=15);ev=[]
        with patch.object(win,'foreground',return_value=7),patch.object(win,'key_down',side_effect=lambda k:ev.append(('down',k))),patch.object(win,'key_up',side_effect=lambda k:ev.append(('up',k))):
            self.assertTrue(engine.run_group([a],7,threading.Event()))
        self.assertEqual(ev,[('down',16),('down',65),('up',65),('up',16)]*2)
    def test_legacy_shift_is_one_key(self):
        ev=[]
        with patch.object(win,'foreground',return_value=7),patch.object(win,'key_down',side_effect=lambda k:ev.append(('down',k))),patch.object(win,'key_up',side_effect=lambda k:ev.append(('up',k))):
            self.assertTrue(engine.run_group([action('SHIFT',1,10)],7,threading.Event()))
        self.assertEqual(ev,[('down',16),('up',16)])
