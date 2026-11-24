import threading
import time
import unittest
from unittest.mock import patch
import engine
import form_model
from test_queue_execution import FakeMSS,action,cond

class AfterDelayTests(unittest.TestCase):
    def test_next_group_starts_after_release_and_delay(self):
        a=action('A',1,20);a['after_delay']=180;b=action('B',2,20)
        rule=[('L',cond('C',[a,b]))];events=[];done=threading.Event()
        w=engine.Engine(rule,7,False,lambda k,t:done.set() if t.startswith('Hoàn thành') else None)
        with patch.object(engine.mss,'mss',return_value=FakeMSS()),patch.object(w,'qualifies',return_value=(True,1,1,1)),patch.object(engine.win,'foreground',return_value=7),patch.object(engine.win,'key_down',side_effect=lambda k:events.append(('down',k,time.monotonic()))),patch.object(engine.win,'key_up',side_effect=lambda k:events.append(('up',k,time.monotonic()))):
            w.start();self.assertTrue(done.wait(2));w.stop();w.action_thread.join(1)
        self.assertEqual([(x[0],x[1]) for x in events],[('down',65),('up',65),('down',66),('up',66)])
        self.assertGreaterEqual(events[2][2]-events[1][2],.17)
    def test_group_waits_concurrently_for_latest_individual_deadline(self):
        a=action('A',1,20);a['after_delay']=160;b=action('B',1,100);b['after_delay']=150
        events=[];t0=time.monotonic()
        with patch.object(engine.win,'foreground',return_value=7),patch.object(engine.win,'key_down'),patch.object(engine.win,'key_up',side_effect=lambda k:events.append((k,time.monotonic()))):
            self.assertTrue(engine.run_group([a,b],7,threading.Event()))
        elapsed=time.monotonic()-t0
        self.assertGreaterEqual(elapsed,.23);self.assertLess(elapsed,.40)
        self.assertAlmostEqual(engine.group_duration([a,b]),.25,places=3)
    def test_delay_only_after_final_repeat(self):
        a=action('A',1,10);a.update(repeat=3,interval=20,after_delay=150);times=[]
        with patch.object(engine.win,'foreground',return_value=7),patch.object(engine.win,'key_down',side_effect=lambda k:times.append(('down',time.monotonic()))),patch.object(engine.win,'key_up',side_effect=lambda k:times.append(('up',time.monotonic()))):
            self.assertTrue(engine.run_group([a],7,threading.Event()));finished=time.monotonic()
        self.assertLess(times[2][1]-times[1][1],.12);self.assertLess(times[4][1]-times[3][1],.12)
        self.assertGreaterEqual(finished-times[5][1],.14)
    def test_pause_freezes_delay_and_stop_interrupts(self):
        a=action('A',1,15);a['after_delay']=300;released=threading.Event();pause=threading.Event();stop=threading.Event();result=[]
        with patch.object(engine.win,'foreground',return_value=7),patch.object(engine.win,'key_down'),patch.object(engine.win,'key_up',side_effect=lambda k:released.set()):
            t=threading.Thread(target=lambda:result.append(engine.run_group([a],7,stop,pause=pause)));t.start();self.assertTrue(released.wait(1));pause.set();time.sleep(.35)
            self.assertTrue(t.is_alive());resumed=time.monotonic();pause.clear();t.join(1)
        self.assertFalse(t.is_alive());self.assertGreaterEqual(time.monotonic()-resumed,.20);self.assertEqual(result,[True])
        stop=threading.Event();released=threading.Event();result=[]
        with patch.object(engine.win,'foreground',return_value=7),patch.object(engine.win,'key_down'),patch.object(engine.win,'key_up',side_effect=lambda k:released.set()):
            t=threading.Thread(target=lambda:result.append(engine.run_group([a],7,stop)));t.start();self.assertTrue(released.wait(1));stop.set();t.join(.4)
        self.assertEqual(result,[False]);self.assertFalse(t.is_alive())
    def test_focus_loss_interrupts_wait(self):
        a=action('A',1,10);a['after_delay']=400;released=threading.Event();focus=[7];result=[]
        with patch.object(engine.win,'foreground',side_effect=lambda:focus[0]),patch.object(engine.win,'key_down'),patch.object(engine.win,'key_up',side_effect=lambda k:released.set()):
            t=threading.Thread(target=lambda:result.append(engine.run_group([a],7,threading.Event())));t.start();self.assertTrue(released.wait(1));focus[0]=8;t.join(.5)
        self.assertEqual(result,[False])
    def test_parse_and_validate(self):
        self.assertEqual(form_model.parse_field('action','after_delay','1200'),1200)
        with self.assertRaises(ValueError):form_model.parse_field('action','after_delay','60001')
        from test_engine import rule,act
        a=act();a['after_delay']=-1
        with self.assertRaisesRegex(ValueError,'chờ sau'):engine.validate(rule([a]))
