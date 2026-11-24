import threading,time,unittest
from unittest.mock import patch
import numpy as np
import app,engine,form_model,prefs_store
from test_queue_execution import FakeMSS,action,cond

def rule(*actions):
    c=cond('C',list(actions));c.update(stability_window=500,stable=0,maximum=1,release_stable=500,unlimited=False,confirm_activation=True);return c

class PatchTests(unittest.TestCase):
    def run_engine(self, c, qualify, down, up, output):
        w=engine.Engine([('L',c)],7,False,output)
        return w
    def test_two_presses_then_change_runs_remaining_without_replaying_first(self):
        first=action('A',1,30);first.update(repeat=5,interval=1,after_delay=110);second=action('B',2,20)
        c=rule(first,second);events=[];msgs=[];done=threading.Event()
        def down(k):events.append(('down',k,time.monotonic()))
        def up(k):events.append(('up',k,time.monotonic()))
        def qualifies(*_):return (sum(v==('down',65) for v in [(e[0],e[1]) for e in events])<2,1,1,1)
        def out(k,v):msgs.append((k,v));done.set() if k=='log' and v.startswith('Hoàn thành') else None
        w=engine.Engine([('L',c)],7,False,out)
        with patch.object(engine.mss,'mss',return_value=FakeMSS()),patch.object(engine.win,'foreground',return_value=7),patch.object(w,'qualifies',side_effect=qualifies),patch.object(engine.win,'key_down',side_effect=down),patch.object(engine.win,'key_up',side_effect=up):
            w.start();self.assertTrue(done.wait(3));w.stop();w.action_thread.join(1)
        self.assertEqual([(x,y) for x,y,_ in events],[('down',65),('up',65),('down',65),('up',65),('down',66),('up',66)])
        self.assertGreaterEqual(events[2][2]-events[1][2],.14);self.assertGreaterEqual(events[4][2]-events[3][2],.10)
        self.assertTrue(any('Xác nhận dấu hiệu không còn đạt' in v for k,v in msgs if k=='condition'))
        self.assertTrue(any('xác nhận lần 2' in v for k,v in msgs if k=='action'))
    def test_change_after_first_press_never_repeats_first(self):
        events=[];done=threading.Event();c=rule(action('A',1,20),action('B',2,20))
        def qual(*_):return (not events,1,1,1)
        w=engine.Engine([('L',c)],7,False,lambda k,v:done.set() if k=='log' and v.startswith('Hoàn thành') else None)
        with patch.object(engine.mss,'mss',return_value=FakeMSS()),patch.object(engine.win,'foreground',return_value=7),patch.object(w,'qualifies',side_effect=qual),patch.object(engine.win,'key_down',side_effect=lambda k:events.append(k)),patch.object(engine.win,'key_up'):
            w.start();self.assertTrue(done.wait(2));w.stop();w.action_thread.join(1)
        self.assertEqual(events,[65,66])
    def test_never_changed_f8_stops_and_does_not_run_second(self):
        events=[];first=threading.Event();c=rule(action('A',1,30),action('B',2,20));w=engine.Engine([('L',c)],7,False,lambda *_:None)
        def down(k):events.append(('down',k));first.set()
        def up(k):events.append(('up',k))
        with patch.object(engine.mss,'mss',return_value=FakeMSS()),patch.object(engine.win,'foreground',return_value=7),patch.object(w,'qualifies',return_value=(True,1,1,1)),patch.object(engine.win,'key_down',side_effect=down),patch.object(engine.win,'key_up',side_effect=up):
            w.start();self.assertTrue(first.wait(1));w.stop();w.action_thread.join(1)
        self.assertFalse(w.alive());self.assertEqual(events,[('down',65),('up',65)])
    def test_pause_during_confirm_prevents_new_press_until_resume(self):
        events=[];released=threading.Event();done=threading.Event();c=rule(action('A',1,20),action('B',2,20))
        def qual(*_):return (sum(k==65 and typ=='down' for typ,k in events)<2,1,1,1)
        def up(k):events.append(('up',k));released.set() if k==65 else None
        w=engine.Engine([('L',c)],7,False,lambda k,v:done.set() if k=='log' and v.startswith('Hoàn thành') else None)
        with patch.object(engine.mss,'mss',return_value=FakeMSS()),patch.object(engine.win,'foreground',return_value=7),patch.object(w,'qualifies',side_effect=qual),patch.object(engine.win,'key_down',side_effect=lambda k:events.append(('down',k))),patch.object(engine.win,'key_up',side_effect=up):
            w.start();self.assertTrue(released.wait(1));w.pause();time.sleep(.3);self.assertEqual(sum(x==('down',65) for x in events),1)
            w.resume();self.assertTrue(done.wait(2));w.stop();w.action_thread.join(1)
        self.assertEqual([k for typ,k in events if typ=='down'],[65,65,66])
    def test_focus_loss_releases_held_key_and_never_runs_rest(self):
        events=[];fg=[7];interrupted=threading.Event();c=rule(action('A',1,500),action('B',2,20))
        def down(k):events.append(('down',k));fg[0]=8
        def out(k,v):interrupted.set() if 'Chuỗi bị ngắt' in v else None
        w=engine.Engine([('L',c)],7,False,out)
        with patch.object(engine.mss,'mss',return_value=FakeMSS()),patch.object(engine.win,'foreground',side_effect=lambda:fg[0]),patch.object(engine.win,'describe_window',side_effect=lambda x:f'HWND={x}'),patch.object(w,'qualifies',return_value=(True,1,1,1)),patch.object(engine.win,'key_down',side_effect=down),patch.object(engine.win,'key_up',side_effect=lambda k:events.append(('up',k))):
            w.start();self.assertTrue(interrupted.wait(1));w.stop();w.action_thread.join(1)
        self.assertEqual(events,[('down',65),('up',65)])
    def test_mouse_confirmation_then_keyboard(self):
        mouse=action('A',1,20);mouse.update(type='Chuột trái',mouse_mode='Nhấn tại con trỏ hiện tại',mouse_api='SendInput')
        c=rule(mouse,action('B',2,20));events=[];done=threading.Event()
        def qual(*_):return (not any(v=='mouse-down' for v in events),1,1,1)
        def mouse_down(*_):events.append('mouse-down');return 'nhấn tại vị trí hiện tại'
        w=engine.Engine([('L',c)],7,False,lambda k,v:done.set() if k=='log' and v.startswith('Hoàn thành') else None)
        with patch.object(engine.mss,'mss',return_value=FakeMSS()),patch.object(engine.win,'foreground',return_value=7),patch.object(w,'qualifies',side_effect=qual),patch.object(engine.win,'mouse_down',side_effect=mouse_down),patch.object(engine.win,'mouse_up',side_effect=lambda *_:events.append('mouse-up')),patch.object(engine.win,'key_down',side_effect=lambda k:events.append(k)),patch.object(engine.win,'key_up'):
            w.start();self.assertTrue(done.wait(2));w.stop();w.action_thread.join(1)
        self.assertEqual(events,['mouse-down','mouse-up',66])
    def test_unlimited_later_cycles_not_capped_but_mode_still_applies(self):
        c=rule(action('A',1,10));c.update(confirm_activation=False,unlimited=True,mode='Lặp',cool=0,maximum=1);downs=[];done=threading.Event()
        def out(k,v):done.set() if k=='log' and v.startswith('Hoàn thành') and len(downs)>=3 else None
        w=engine.Engine([('L',c)],7,False,out)
        with patch.object(engine.mss,'mss',return_value=FakeMSS()),patch.object(engine.win,'foreground',return_value=7),patch.object(w,'qualifies',return_value=(True,1,1,1)),patch.object(engine.win,'key_down',side_effect=lambda k:downs.append(k)),patch.object(engine.win,'key_up'):
            w.start();self.assertTrue(done.wait(2));w.stop();w.action_thread.join(1)
        self.assertGreaterEqual(len(downs),3)
    def test_first_group_multiple_actions_rejected_only_if_confirm_enabled(self):
        c=rule(action('A',1),action('B',1));c.update(template=np.zeros((4,4,3),dtype=np.uint8),mask=np.ones((4,4),dtype=np.uint8),region={'left':0,'top':0,'width':4,'height':4})
        with self.assertRaisesRegex(ValueError,'nhóm thao tác đầu tiên'):engine.validate([{'name':'L','conditions':[c]}])
        c['confirm_activation']=False;self.assertEqual(len(engine.validate([{'name':'L','conditions':[c]}])),1)
    def test_old_scripts_defaults_false_and_roundtrip(self):
        a=app.new_condition();a.pop('unlimited');a.pop('confirm_activation');f={'id':'f','name':'L','conditions':[a]}
        fs=app.deserialize(app.serialize([f]));self.assertFalse(fs[0]['conditions'][0]['unlimited']);self.assertFalse(fs[0]['conditions'][0]['confirm_activation'])
        fs[0]['conditions'][0].update(unlimited=True,confirm_activation=True);again=app.deserialize(app.serialize(fs));self.assertTrue(again[0]['conditions'][0]['unlimited']);self.assertTrue(again[0]['conditions'][0]['confirm_activation'])
    def test_defaults_boolean_parse(self):
        self.assertTrue(form_model.parse_field('condition','unlimited',True));self.assertFalse(form_model.parse_field('condition','confirm_activation',False))
        self.assertEqual(prefs_store.checked_preferences({'condition':{'unlimited':True,'confirm_activation':True}})['condition'],{'unlimited':True,'confirm_activation':True})
