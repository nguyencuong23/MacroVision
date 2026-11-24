import threading
import unittest
from unittest.mock import patch
import engine
from test_queue_execution import FakeMSS,action,cond

class SkippedLoggingTests(unittest.TestCase):
    def make(self):
        a=cond('Điều kiện 1',[action('1',1)]);b=cond('Điều kiện 1',[action('F',1)]);c=cond('Điều kiện 1',[action('1',1)])
        for rule in (a,b,c):rule.update(stability_window=500,stable=250,maximum=10,release_stable=500)
        logs=[];w=engine.Engine([('Luồng 1',a),('Luồng 2',b),('Luồng 3',c)],7,False,lambda k,v:logs.append((k,v)))
        return w,logs
    def scan(self,w,t,vals):
        samples=iter(vals)
        with patch.object(engine.win,'foreground',return_value=7),patch.object(engine.time,'monotonic',return_value=t),patch.object(w,'qualifies',side_effect=lambda *_:next(samples)):
            return w.scan(FakeMSS())[0]
    def test_reproduces_silent_eligibility_skips_after_chain_and_prioritizes_live(self):
        w,logs=self.make();w.log_failures=True;w.states[0]['armed']=False;w.states[1]['armed']=False
        bad=(False,.65,.14,1);good=(True,.95,.6,1)
        self.assertIsNone(self.scan(w,10,[bad,bad,good]))
        out=[v for k,v in logs if k=='condition'];self.assertEqual(len(out),2)
        self.assertTrue(any('Luồng 1 / Điều kiện 1: Bỏ qua' in v and 'Một lần chưa được mở lại' in v and '0.6500/0.9000' in v for v in out))
        self.assertTrue(any('Luồng 2 / Điều kiện 1: Bỏ qua' in v and 'Một lần chưa được mở lại' in v for v in out))
        self.assertTrue(w.log_failures);self.assertEqual(self.scan(w,10.30,[bad,bad,good]),2)
        self.assertEqual(len([1 for k,v in logs if k=='condition' and ': Bỏ qua' in v]),2)
        # Selection is still driven by live eligibility, never by the logging records.
        self.assertFalse(hasattr(w,'jobs'))
    def test_all_ineligible_are_visible_once_then_logging_stops(self):
        w,logs=self.make();w.log_failures=True
        for st in w.states:st['armed']=False
        self.assertIsNone(self.scan(w,10,[(True,.95,.6,1)]*3))
        self.assertFalse(w.log_failures);self.assertEqual(sum(': Bỏ qua' in v for k,v in logs if k=='condition'),3)
        self.scan(w,10.1,[(True,.95,.6,1)]*3);self.assertEqual(sum(': Bỏ qua' in v for k,v in logs if k=='condition'),3)
    def test_cooldown_and_max_skip_reported(self):
        w,logs=self.make();w.log_failures=True;w.rules[0][1]['mode']='Lặp';w.states[0]['next']=12
        w.states[1]['count']=10;w.states[2]['armed']=False
        self.scan(w,10,[(True,.95,.6,1)]*3)
        text=' | '.join(v for k,v in logs if k=='condition')
        self.assertIn('đang nghỉ sau chuỗi',text);self.assertIn('đã đạt số lần tối đa',text);self.assertIn('Một lần chưa được mở lại',text)
    def test_lower_blocked_condition_not_logged_as_skipped_before_its_turn(self):
        w,logs=self.make();w.log_failures=True;w.states[1]['armed']=False
        vals=[(True,.95,.6,1)]*3
        self.assertIsNone(self.scan(w,10,vals));self.assertFalse(any('Bỏ qua' in v for k,v in logs if k=='condition'))
        self.assertEqual(self.scan(w,10.3,vals),0)
        self.assertFalse(any('Bỏ qua' in v for k,v in logs if k=='condition'))
    def test_no_skip_or_timeout_log_before_first_activation(self):
        w,logs=self.make()
        for st in w.states:st['armed']=False
        self.scan(w,10,[(True,.95,.6,1)]*3)
        self.assertFalse(any(k=='condition' for k,v in logs))
    def test_one_pass_mixed_skip_and_timeout_reports_every_visited_rule(self):
        w,logs=self.make();w.log_failures=True;w.states[0]['armed']=False;w.states[2]['count']=10
        bad=(False,.65,.14,1);good=(True,.95,.6,1)
        self.assertIsNone(self.scan(w,10,[bad,bad,good]));self.assertEqual(len([v for k,v in logs if k=='condition']),1)
        self.assertIsNone(self.scan(w,10.51,[bad,bad,good]))
        lines=[v for k,v in logs if k=='condition'];self.assertEqual(len(lines),3)
        self.assertIn('Luồng 1 / Điều kiện 1: Bỏ qua',lines[0]);self.assertIn('Luồng 2 / Điều kiện 1: Chưa kích hoạt',lines[1]);self.assertIn('Luồng 3 / Điều kiện 1: Bỏ qua',lines[2]);self.assertFalse(w.log_failures)
    def test_recheck_fail_is_visible_only_after_prior_activation(self):
        a=cond('Điều kiện 1',[action('1',1)]);a.update(stable=0,stability_window=500,maximum=1)
        out=[];done=threading.Event();w=engine.Engine([('Luồng 1',a)],7,False,lambda k,v:(out.append((k,v)),done.set() if k=='condition' and 'kiểm tra lại không đạt' in v else None));w.log_failures=True
        n=[0]
        def qualifies(*_):
            n[0]+=1
            return (True,.99,.7,1) if n[0]==1 else (False,.7,.3,1)
        with patch.object(engine.mss,'mss',return_value=FakeMSS()),patch.object(engine.win,'foreground',return_value=7),patch.object(w,'qualifies',side_effect=qualifies),patch.object(engine.win,'key_down') as down:
            w.start();self.assertTrue(done.wait(2));w.stop();w.action_thread.join(1);down.assert_not_called()
        self.assertTrue(any(k=='condition' and 'Bỏ qua (kiểm tra lại không đạt:' in v for k,v in out))
    def test_new_activation_clears_seen_skips(self):
        w,logs=self.make();w.rules[0][1]['stable']=0;w.logged_skips={0,1,2};done=threading.Event();seen=[]
        def output(k,v):
            if k=='condition' and '/ Kích hoạt ' in v:seen.append(set(w.logged_skips))
            if k=='log' and v.startswith('Hoàn thành'):done.set()
        w.output=output
        with patch.object(engine.mss,'mss',return_value=FakeMSS()),patch.object(engine.win,'foreground',return_value=7),patch.object(w,'qualifies',return_value=(True,1,1,1)),patch.object(engine.win,'key_down'),patch.object(engine.win,'key_up'):
            w.start();self.assertTrue(done.wait(1));w.stop();w.action_thread.join(1)
        self.assertEqual(seen,[set()])
