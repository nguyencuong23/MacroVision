import threading
import time
import unittest
from unittest.mock import patch
import engine

class FakeMSS:
    def __enter__(self): return self
    def __exit__(self,*args): pass

def action(key='A',order=1,hold=120,repeat=1,interval=0):
    return {'type':'Phím','key':key,'order':order,'hold':hold,'repeat':repeat,'interval':interval,'x':0,'y':0}

def condition(name, actions): return {'name':name,'actions':actions,'cool':200,'stable':0,'mode':'Một lần','maximum':1,'sim':.9,'bright':0.}

class PauseTests(unittest.TestCase):
    def test_pause_finishes_held_press_and_resumes_without_duplicate(self):
        started=threading.Event(); released=threading.Event(); stop=threading.Event(); pause=threading.Event(); events=[]; result=[]
        def down(k): events.append(('down',k)); started.set()
        def up(k): events.append(('up',k)); released.set()
        with patch.object(engine.win,'foreground',return_value=7), \
             patch.object(engine.win,'key_down',side_effect=down), \
             patch.object(engine.win,'key_up',side_effect=up):
            t=threading.Thread(target=lambda:result.append(engine.run_group([action(repeat=2,interval=30)],7,stop,pause=pause)))
            t.start(); self.assertTrue(started.wait(1)); pause.set()
            self.assertTrue(released.wait(1)); time.sleep(.15)
            self.assertEqual(events,[('down',65),('up',65)])
            self.assertTrue(t.is_alive()); pause.clear(); t.join(2)
        self.assertFalse(t.is_alive()); self.assertEqual(result,[True])
        self.assertEqual(events,[('down',65),('up',65),('down',65),('up',65)])
    def test_interval_is_frozen_while_paused(self):
        first_up=threading.Event(); second_down=threading.Event(); stop=threading.Event(); pause=threading.Event(); events=[]; result=[]
        def down(k):
            events.append(('down',time.monotonic()))
            if len([x for x in events if x[0]=='down']) == 2: second_down.set()
        def up(k): events.append(('up',time.monotonic())); first_up.set()
        with patch.object(engine.win,'foreground',return_value=7), \
             patch.object(engine.win,'key_down',side_effect=down), \
             patch.object(engine.win,'key_up',side_effect=up):
            t=threading.Thread(target=lambda:result.append(engine.run_group([action(hold=30,repeat=2,interval=250)],7,stop,pause=pause)))
            t.start(); self.assertTrue(first_up.wait(1)); pause.set(); time.sleep(.35)
            self.assertFalse(second_down.is_set())
            resumed=time.monotonic(); pause.clear(); self.assertTrue(second_down.wait(1)); t.join(1)
        self.assertGreaterEqual(events[2][1]-resumed,.15)
        self.assertEqual(result,[True])
    def test_stop_while_paused_never_sends_next_press(self):
        started=threading.Event(); released=threading.Event(); stop=threading.Event(); pause=threading.Event(); events=[]; result=[]
        def down(k): events.append('down'); started.set()
        def up(k): events.append('up'); released.set()
        with patch.object(engine.win,'foreground',return_value=7), \
             patch.object(engine.win,'key_down',side_effect=down), \
             patch.object(engine.win,'key_up',side_effect=up):
            t=threading.Thread(target=lambda:result.append(engine.run_group([action(repeat=2,interval=20)],7,stop,pause=pause)))
            t.start(); self.assertTrue(started.wait(1)); pause.set(); self.assertTrue(released.wait(1)); stop.set(); t.join(2)
        self.assertEqual(events,['down','up']); self.assertEqual(result,[False]); self.assertFalse(t.is_alive())
    def test_stop_immediately_releases_active_hold(self):
        started=threading.Event(); stop=threading.Event(); pause=threading.Event(); events=[]; result=[]
        def down(k): events.append('down'); started.set()
        def up(k): events.append('up')
        with patch.object(engine.win,'foreground',return_value=7), \
             patch.object(engine.win,'key_down',side_effect=down), \
             patch.object(engine.win,'key_up',side_effect=up):
            t=threading.Thread(target=lambda:result.append(engine.run_group([action(hold=1000)],7,stop,pause=pause)))
            t.start(); self.assertTrue(started.wait(1)); pause.set(); stop.set(); t.join(.5)
        self.assertFalse(t.is_alive()); self.assertEqual(result,[False]); self.assertEqual(events,['down','up'])
    def test_paused_engine_waits_before_next_group_and_condition(self):
        rules=[('A',condition('A',[action('A',1,40),action('B',2,20)])), ('B',condition('B',[action('C',1,20)]))]
        started=threading.Event(); finished=threading.Event(); events=[]; outputs=[]
        def report(kind,text):
            outputs.append(text)
            if text.startswith('Hoàn thành B / B'):finished.set()
        work=engine.Engine(rules,7,False,report)
        def down(k):
            events.append(('down',k))
            if k==65: work.pause(); started.set()
        def up(k): events.append(('up',k))
        with patch.object(engine.mss,'mss',return_value=FakeMSS()), \
             patch.object(work,'qualifies',return_value=(True,1.,1.,1.)), \
             patch.object(engine.win,'foreground',return_value=7), \
             patch.object(engine.win,'key_down',side_effect=down), \
             patch.object(engine.win,'key_up',side_effect=up):
            work.start(); self.assertTrue(started.wait(1)); time.sleep(.18)
            self.assertEqual(events,[('down',65),('up',65)])
            work.resume(); self.assertTrue(finished.wait(3)); work.stop(); work.action_thread.join(1)
        self.assertEqual(events,[('down',65),('up',65),('down',66),('up',66),('down',67),('up',67)])
    def test_reserved_control_keys(self):
        import form_model
        for key in ('F6','F7','F8'):
            with self.assertRaises(ValueError):form_model.parse_field('action','key',key)

if __name__=='__main__': unittest.main()
