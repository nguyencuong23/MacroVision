import threading
import time
import unittest
from unittest.mock import patch
import engine
from test_queue_execution import FakeMSS,action,cond

class PriorityTests(unittest.TestCase):
    def test_first_tree_order_with_one_pass(self):
        rules=[('L1',cond('C1',[action('A',1)])),('L1',cond('C2',[action('B',1)])),('L2',cond('C1',[action('C',1)]))];events=[];done=threading.Event()
        w=engine.Engine(rules,7,False,lambda k,t:done.set() if t.startswith('Hoàn thành L2') else None)
        with patch.object(engine.mss,'mss',return_value=FakeMSS()),patch.object(w,'qualifies',return_value=(True,1,1,1)),patch.object(engine.win,'foreground',return_value=7),patch.object(engine.win,'key_down',side_effect=lambda k:events.append(k)),patch.object(engine.win,'key_up'):
            w.start();self.assertTrue(done.wait(3));w.stop();w.action_thread.join(1)
        self.assertEqual(events,[65,66,67])
    def test_stale_condition_observed_before_a_does_not_execute(self):
        rules=[('L1',cond('A',[action('A',1,100)])),('L2',cond('B',[action('B',1)]))];good={'A':True,'B':True};events=[];a_done=threading.Event();seen=[]
        def report(k,t):
            if t.startswith('Hoàn thành L1'):a_done.set()
        w=engine.Engine(rules,7,False,report)
        def qualifies(s,c):seen.append((c['name'],good[c['name']]));return good[c['name']],1,1,1
        def down(k):events.append(k);good['B']=False
        with patch.object(engine.mss,'mss',return_value=FakeMSS()),patch.object(w,'qualifies',side_effect=qualifies),patch.object(engine.win,'foreground',return_value=7),patch.object(engine.win,'key_down',side_effect=down),patch.object(engine.win,'key_up'):
            w.start();self.assertTrue(a_done.wait(2));time.sleep(.35);w.stop();w.action_thread.join(1)
        self.assertIn(('B',True),seen);self.assertIn(('B',False),seen);self.assertEqual(events,[65])
    def test_new_earlier_condition_waits_until_next_pass(self):
        rules=[('L1',cond('A',[action('A',1)])),('L2',cond('B',[action('B',1,80),action('C',2)])),('L3',cond('D',[action('D',1)]))];good={'A':False,'B':True,'D':True};events=[];done=threading.Event()
        w=engine.Engine(rules,7,False,lambda k,t:done.set() if t.startswith('Hoàn thành L1') else None)
        def qualifies(s,c):return good[c['name']],1,1,1
        def down(k):
            events.append(k)
            if k==66:good['A']=True
        with patch.object(engine.mss,'mss',return_value=FakeMSS()),patch.object(w,'qualifies',side_effect=qualifies),patch.object(engine.win,'foreground',return_value=7),patch.object(engine.win,'key_down',side_effect=down),patch.object(engine.win,'key_up'):
            w.start();self.assertTrue(done.wait(3));w.stop();w.action_thread.join(1)
        self.assertEqual(events,[66,67,68,65])
    def test_once_rearms_only_when_false_observed_after_chain(self):
        rules=[('L',cond('A',[action('A',1)]))];rules[0][1]['maximum']=10;rules[0][1]['release_stable']=0
        w=engine.Engine(rules,7,False,lambda *x:None);s=FakeMSS()
        with patch.object(engine.win,'foreground',return_value=7),patch.object(w,'qualifies',side_effect=[(True,1,1,1),(True,1,1,1),(False,0,0,1),(True,1,1,1)]):
            self.assertEqual(w.scan(s)[0],0);w.states[0]['armed']=False
            self.assertIsNone(w.scan(s)[0]);self.assertIsNone(w.scan(s)[0]);self.assertEqual(w.scan(s)[0],0)
    def test_stability_is_reset_after_a_chain(self):
        rules=[('L',cond('A',[action('A',1)]))];rules[0][1]['stable']=200
        w=engine.Engine(rules,7,False,lambda *x:None);s=FakeMSS()
        with patch.object(engine.win,'foreground',return_value=7),patch.object(w,'qualifies',return_value=(True,1,1,1)):
            self.assertIsNone(w.scan(s)[0]);w.states[0]['since']=time.monotonic()-.3;self.assertEqual(w.scan(s)[0],0)
            w.reset_stability();self.assertIsNone(w.scan(s)[0])
    def test_once_does_not_repeat_when_condition_stays_true(self):
        rules=[('L',cond('A',[action('A',1)]))];rules[0][1]['maximum']=10
        events=[];finished=threading.Event()
        w=engine.Engine(rules,7,False,lambda k,t:finished.set() if t.startswith('Hoàn thành') else None)
        with patch.object(engine.mss,'mss',return_value=FakeMSS()),patch.object(w,'qualifies',return_value=(True,1,1,1)),patch.object(engine.win,'foreground',return_value=7),patch.object(engine.win,'key_down',side_effect=lambda k:events.append(k)),patch.object(engine.win,'key_up'):
            w.start();self.assertTrue(finished.wait(2));time.sleep(.35);w.stop();w.action_thread.join(1)
        self.assertEqual(events,[65])
    def test_loop_mode_obeys_cooldown(self):
        rules=[('L',cond('A',[action('A',1)]))];rules[0][1].update(mode='Lặp',maximum=2,cool=220)
        downs=[];ups=[];done=threading.Event()
        def output(k,t):
            if t.startswith('Hoàn thành') and len(downs)==2:done.set()
        w=engine.Engine(rules,7,False,output)
        with patch.object(engine.mss,'mss',return_value=FakeMSS()),patch.object(w,'qualifies',return_value=(True,1,1,1)),patch.object(engine.win,'foreground',return_value=7),patch.object(engine.win,'key_down',side_effect=lambda k:downs.append(time.monotonic())),patch.object(engine.win,'key_up',side_effect=lambda k:ups.append(time.monotonic())):
            w.start();self.assertTrue(done.wait(2));w.stop();w.action_thread.join(1)
        self.assertEqual(len(downs),2);self.assertGreaterEqual(downs[1]-ups[0],.21)
    def test_failed_recheck_never_sends_action(self):
        rules=[('L',cond('A',[action('A',1)]))];w=engine.Engine(rules,7,False,lambda *a:None);calls=[];trigger=threading.Event();n=[0]
        def qualify(s,c):
            n[0]+=1
            if n[0]==1:return True,1,1,1
            trigger.set();return False,0,0,1
        with patch.object(engine.mss,'mss',return_value=FakeMSS()),patch.object(w,'qualifies',side_effect=qualify),patch.object(engine.win,'foreground',return_value=7),patch.object(engine.win,'key_down',side_effect=lambda k:calls.append(k)):
            w.start();self.assertTrue(trigger.wait(1));time.sleep(.1);w.stop();w.action_thread.join(1)
        self.assertEqual(calls,[])
