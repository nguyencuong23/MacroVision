import threading
import unittest
from unittest.mock import patch
import app
import engine
import form_model
from test_queue_execution import FakeMSS, action, cond

class WindowTests(unittest.TestCase):
    def setUp(self):
        self.c=cond('C',[action('A',1)]);self.c.update(stable=250,stability_window=1000,maximum=10)
        self.logs=[];self.w=engine.Engine([('L',self.c)],7,False,lambda k,v:self.logs.append((k,v)))
        self.good=True
    def scan(self,t,good=True):
        with patch.object(engine.win,'foreground',return_value=7),patch.object(engine.time,'monotonic',return_value=t),patch.object(self.w,'qualifies',return_value=(good,.95 if good else .6,.8,1)):
            return self.w.scan(FakeMSS())[0]
    def test_stable_before_deadline_selects_immediately_on_observation(self):
        self.assertIsNone(self.scan(10));self.assertIsNone(self.scan(10.2));self.assertEqual(self.scan(10.26),0)
    def test_deadline_stops_too_late_then_next_scan_is_new_window(self):
        self.c.update(stable=250,stability_window=400)
        self.assertIsNone(self.scan(10));self.assertIsNone(self.scan(10.2,False));self.assertIsNone(self.scan(10.3));self.assertIsNone(self.scan(10.41))
        self.assertTrue(any('hết 400 ms xét ổn định' in m for k,m in self.logs if k=='log'))
        self.assertIsNone(self.scan(10.51));self.assertEqual(self.scan(10.80),0)
    def test_flicker_resets_stable_but_not_window(self):
        self.scan(10);self.scan(10.2,False);self.scan(10.3);self.assertIsNone(self.scan(10.49));self.assertEqual(self.scan(10.56),0)
    def test_search_starts_before_match_and_match_restarts_timer(self):
        self.assertIsNone(self.scan(10,False));self.assertEqual(self.w.states[0]['window_since'],10);self.assertEqual(self.w.states[0]['window_phase'],'search')
        self.assertIsNone(self.scan(10.4,True));self.assertEqual(self.w.states[0]['window_since'],10.4);self.assertEqual(self.w.states[0]['window_phase'],'stable')
        self.assertEqual(self.scan(10.66,True),0)
    def test_zero_stable_immediately(self):
        self.c['stable']=0;self.assertEqual(self.scan(10),0)
    def test_window_is_reset_on_pause_focus_or_chain(self):
        self.scan(10);self.w.reset_stability();self.assertIsNone(self.w.states[0]['window_since']);self.assertIsNone(self.scan(30))
        with patch.object(engine.win,'foreground',return_value=8):self.w.scan(FakeMSS())
        self.assertIsNone(self.w.states[0]['window_since']);self.scan(40);self.w.pause();self.w.resume()
        self.assertIsNone(self.w.states[0]['window_since'])
    def test_higher_priority_wait_blocks_lower_until_timeout_then_lower_can_run(self):
        self.c.update(stable=250,stability_window=400);b=cond('B',[action('B',1)]);b.update(stable=250,stability_window=1000)
        events=[];w=engine.Engine([('L1',self.c),('L2',b)],7,False,lambda k,v:events.append((k,v)))
        vals={'C':True,'B':True}
        def qualifies(_s,c):return vals[c['name']],.95 if vals[c['name']] else .6,.9,1
        def scan(t):
            with patch.object(engine.win,'foreground',return_value=7),patch.object(engine.time,'monotonic',return_value=t),patch.object(w,'qualifies',side_effect=qualifies):return w.scan(FakeMSS())[0]
        self.assertIsNone(scan(10));self.assertIsNone(w.states[1]['window_since'])
        vals['C']=False;self.assertIsNone(scan(10.2));self.assertIsNone(w.states[1]['window_since'])
        vals['C']=True;self.assertIsNone(scan(10.41));self.assertEqual(w.pass_cursor,1)
        self.assertIsNone(scan(10.55));self.assertEqual(scan(10.7),1)
        self.assertTrue(any('hết 400 ms xét ổn định' in text for k,text in events if k=='log'))
        self.assertFalse(hasattr(w,'jobs'))
    def test_higher_priority_stabilizes_before_lower_even_if_lower_immediate(self):
        self.c.update(stable=250,stability_window=1000);b=cond('B',[action('B',1)]);b['stable']=0
        w=engine.Engine([('L1',self.c),('L2',b)],7,False,lambda *a:None)
        def scan(t):
            with patch.object(engine.win,'foreground',return_value=7),patch.object(engine.time,'monotonic',return_value=t),patch.object(w,'qualifies',return_value=(True,.95,.9,1)):return w.scan(FakeMSS())[0]
        self.assertIsNone(scan(10));self.assertEqual(scan(10.26),0)
    def test_higher_cooldown_or_unarmed_does_not_block(self):
        b=cond('B',[action('B',1)]);b['stable']=0
        w=engine.Engine([('L1',self.c),('L2',b)],7,False,lambda *a:None);w.states[0]['armed']=False
        with patch.object(engine.win,'foreground',return_value=7),patch.object(w,'qualifies',return_value=(True,.95,.9,1)):
            self.assertEqual(w.scan(FakeMSS())[0],1)
    def test_full_pass_restarts_only_after_all_unavailable(self):
        b=cond('B',[action('B',1)]);b.update(stable=250,stability_window=400)
        w=engine.Engine([('L1',self.c),('L2',b)],7,False,lambda *a:None);vals={'C':True,'B':False}
        def qualifies(_,c):return vals[c['name']],.95 if vals[c['name']] else .5,.9,1
        def scan(t):
            with patch.object(engine.win,'foreground',return_value=7),patch.object(engine.time,'monotonic',return_value=t),patch.object(w,'qualifies',side_effect=qualifies):return w.scan(FakeMSS())[0]
        self.c['stability_window']=400;scan(10);vals['C']=False;scan(10.2);scan(10.41)
        self.assertEqual(w.pass_cursor,1);scan(10.82);self.assertEqual(w.pass_cursor,0)
        vals['C']=True;self.assertIsNone(scan(10.9));self.assertEqual(w.states[0]['window_since'],10.9)
    def test_no_stale_lower_match_after_higher_times_out(self):
        self.c.update(stable=250,stability_window=400);b=cond('B',[action('B',1)]);b.update(stable=0,stability_window=1000)
        w=engine.Engine([('L1',self.c),('L2',b)],7,False,lambda *a:None);vals={'C':True,'B':True}
        def qualifies(_,c):return vals[c['name']],.95 if vals[c['name']] else .5,.9,1
        def scan(t):
            with patch.object(engine.win,'foreground',return_value=7),patch.object(engine.time,'monotonic',return_value=t),patch.object(w,'qualifies',side_effect=qualifies):return w.scan(FakeMSS())[0]
        self.assertIsNone(scan(10));vals['C']=False;self.assertIsNone(scan(10.2));vals['B']=False
        self.assertIsNone(scan(10.41));self.assertEqual(w.pass_cursor,1);self.assertIsNone(scan(11.42));self.assertEqual(w.pass_cursor,0)
    def test_stop_does_not_wait_for_window(self):
        self.c['stability_window']=10000;w=engine.Engine([('L',self.c)],7,False,lambda *_:None)
        checked=threading.Event()
        def qualifies(*_):checked.set();return True,1,1,1
        with patch.object(engine.mss,'mss',return_value=FakeMSS()),patch.object(engine.win,'foreground',return_value=7),patch.object(w,'qualifies',side_effect=qualifies),patch.object(engine.win,'key_down') as down:
            w.start();self.assertTrue(checked.wait(1));w.stop();w.action_thread.join(.5);self.assertFalse(w.alive());down.assert_not_called()
    def test_old_script_compatibility_and_roundtrip(self):
        a=app.new_condition();a.pop('stability_window');a['stable']=3000
        fs=app.deserialize(app.serialize([{'id':'1','name':'L','conditions':[a]}]))
        self.assertEqual(fs[0]['conditions'][0]['stability_window'],3500)
        fs[0]['conditions'][0]['stability_window']=4300
        self.assertEqual(app.deserialize(app.serialize(fs))[0]['conditions'][0]['stability_window'],4300)
    def test_form_limits(self):
        self.assertEqual(form_model.parse_field('condition','stability_window','2000'),2000)
        for x in ('0','-1','60001','abc'):
            with self.assertRaises(ValueError):form_model.parse_field('condition','stability_window',x)
    def test_validation_rejects_window_shorter_than_stability(self):
        import numpy as np
        self.c.update(template=np.ones((4,4,3),dtype='uint8'),mask=np.ones((4,4),dtype='uint8'),region={'left':0,'top':0,'width':4,'height':4},stable=250,stability_window=100)
        with self.assertRaisesRegex(ValueError,'không được nhỏ hơn'):engine.validate([{'name':'L','conditions':[self.c]}])
