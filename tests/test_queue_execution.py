import threading
import unittest
from unittest.mock import patch
import engine

class FakeMSS:
    def __enter__(self):return self
    def __exit__(self,*args):pass

def action(key,order,hold=10):
    return {'type':'Phím','key':key,'order':order,'hold':hold,'repeat':1,'interval':0,'x':0,'y':0}

def cond(name,actions):
    return {'name':name,'actions':actions,'cool':200,'stable':0,'mode':'Một lần','maximum':1,'sim':.9,'bright':0.}

class ScanExecutionTests(unittest.TestCase):
    def test_chains_never_interleave_and_scans_are_not_done_during_chain(self):
        rules=[('A',cond('A',[action('A',1,30),action('B',2,30)])),('B',cond('B',[action('C',1,20)]))]
        events=[];done=threading.Event();in_action=threading.Event();during_scan=[]
        def report(k,t):
            if t.startswith('Chạy A'):in_action.set()
            if t.startswith('Hoàn thành A'):in_action.clear()
            if t.startswith('Hoàn thành B'):done.set()
        w=engine.Engine(rules,7,False,report)
        def qualifies(s,c):
            if in_action.is_set():during_scan.append(c['name'])
            return True,1,1,1
        with patch.object(engine.mss,'mss',return_value=FakeMSS()),patch.object(w,'qualifies',side_effect=qualifies),patch.object(engine.win,'foreground',return_value=7),patch.object(engine.win,'key_down',side_effect=lambda k:events.append(('down',k))),patch.object(engine.win,'key_up',side_effect=lambda k:events.append(('up',k))):
            w.start();self.assertTrue(done.wait(3));w.stop();w.action_thread.join(1)
        self.assertEqual(events,[('down',65),('up',65),('down',66),('up',66),('down',67),('up',67)])
        self.assertEqual(during_scan,[]);self.assertFalse(hasattr(w,'jobs'))
    def test_error_stops_before_second_condition(self):
        rules=[('A',cond('A',[action('A',1),action('B',2)])),('B',cond('B',[action('C',1)]))];done=threading.Event();calls=[]
        w=engine.Engine(rules,7,False,lambda k,t:done.set() if k=='thread_done' else None)
        def fail(k):
            calls.append(k)
            if k==66:raise RuntimeError('error')
        with patch.object(engine.mss,'mss',return_value=FakeMSS()),patch.object(w,'qualifies',return_value=(True,1,1,1)),patch.object(engine.win,'foreground',return_value=7),patch.object(engine.win,'key_down',side_effect=fail),patch.object(engine.win,'key_up'):
            w.start();self.assertTrue(done.wait(3));w.action_thread.join(1)
        self.assertEqual(calls,[65,66]);self.assertTrue(w.stop_event.is_set())
