import unittest,threading
from unittest.mock import patch
import engine
from test_queue_execution import FakeMSS,action,cond

class CheckLogTests(unittest.TestCase):
    def setUp(self):
        a=cond('Điều kiện 1',[action('1',1)]);a.update(stable=250,stability_window=500,maximum=10)
        self.out=[];self.w=engine.Engine([('Luồng 1',a)],7,False,lambda k,v:self.out.append((k,v)))
    def scan(self,t,good,sim=None,bright=.5):
        sim=(.95 if good else .8) if sim is None else sim
        with patch.object(engine.win,'foreground',return_value=7),patch.object(engine.time,'monotonic',return_value=t),patch.object(self.w,'qualifies',return_value=(good,sim,bright,1)):
            return self.w.scan(FakeMSS())[0]
    def negative(self):return [v for k,v in self.out if k=='condition' and 'Chưa kích hoạt' in v]
    def test_no_negative_before_any_activation_even_if_timeout(self):
        self.scan(10,False);self.scan(10.51,False);self.assertEqual(self.negative(),[])
    def test_negative_only_after_full_search_time_and_not_again_in_next_pass(self):
        self.w.log_failures=True;self.scan(10,False);self.scan(10.49,False);self.assertEqual(self.negative(),[])
        self.scan(10.51,False);self.assertEqual(len(self.negative()),1)
        self.assertRegex(self.negative()[0],r'Luồng 1 / Điều kiện 1: Chưa kích hoạt \(Độ ổn định: 0/500, Độ giống: 0\.8000/0\.9000, Độ giống màu: 1\.0000/0\.0000, Độ sáng: 0\.5000/0\.0000\)')
        self.assertFalse(self.w.log_failures);self.scan(11,False);self.scan(11.51,False);self.assertEqual(len(self.negative()),1)
        self.w.log_failures=True;self.scan(12,False);self.scan(12.51,False);self.assertEqual(len(self.negative()),2)
    def test_no_negative_during_wait_then_timeout_reports_last_observed_stability(self):
        self.w.log_failures=True;self.scan(10,True);self.scan(10.1,False);self.scan(10.2,True);self.scan(10.3,False);self.scan(10.35,True);self.scan(10.49,True)
        self.assertEqual(self.negative(),[]);self.scan(10.51,True)
        self.assertEqual(len(self.negative()),1);self.assertRegex(self.negative()[0],r'Độ ổn định: 1[34]\d/500')
    def test_incomplete_scan_keeps_pending_log_cycle(self):
        self.w.log_failures=True
        with patch.object(engine.win,'foreground',side_effect=[7,8]):self.assertIsNone(self.w.scan(FakeMSS())[0])
        self.assertTrue(self.w.log_failures);self.assertEqual(self.negative(),[])
    def test_success_reenables_negative_logging(self):
        self.w.rules[0][1]['stable']=0;done=threading.Event();out=[];at_activation=[]
        def report(k,v):
            out.append((k,v))
            if k=='condition' and '/ Kích hoạt ' in v:at_activation.append(self.w.log_failures)
            if k=='log' and v.startswith('Hoàn thành'):done.set()
        self.w.output=report
        with patch.object(engine.mss,'mss',return_value=FakeMSS()),patch.object(engine.win,'foreground',return_value=7),patch.object(self.w,'qualifies',return_value=(True,1,1,1)),patch.object(engine.win,'key_down'),patch.object(engine.win,'key_up'):
            self.w.start();self.assertTrue(done.wait(1));self.w.stop();self.w.action_thread.join(1)
        self.assertTrue(any(k=='condition' and '/ Kích hoạt ' in v for k,v in out));self.assertEqual(at_activation,[True])
