import threading,time,unittest
from unittest.mock import patch
import engine
from test_queue_execution import FakeMSS,action,cond

class OrderedPassTests(unittest.TestCase):
    def test_multiple_flows_and_conditions_follow_two_complete_passes(self):
        keys=['A','B','C','D','E'];locations=[('L1','C1'),('L1','C2'),('L2','C1'),('L3','C1'),('L3','C2')]
        rules=[]
        for (f,n),k in zip(locations,keys):
            c=cond(n,[action(k,1,20)]);c.update(mode='Lặp',cool=0,maximum=2,stable=0,stability_window=500);rules.append((f,c))
        rules[2][1]['actions'][0]['after_delay']=100
        out=[];downs=[];ups=[];done=threading.Event()
        def report(k,v):
            out.append((k,v))
            if k=='log' and v.startswith('Hoàn thành L3 / C2') and len(downs)>=10:done.set()
        w=engine.Engine(rules,7,False,report)
        with patch.object(engine.mss,'mss',return_value=FakeMSS()),patch.object(engine.win,'foreground',return_value=7),patch.object(w,'qualifies',return_value=(True,1,1,1)),patch.object(engine.win,'key_down',side_effect=lambda k:downs.append((k,time.monotonic()))),patch.object(engine.win,'key_up',side_effect=lambda k:ups.append((k,time.monotonic()))):
            w.start();self.assertTrue(done.wait(3));w.stop();w.action_thread.join(1)
        self.assertEqual([v for v,_ in downs],[ord(k) for k in keys]*2)
        self.assertGreaterEqual(downs[3][1]-ups[2][1],.09)
        self.assertFalse(hasattr(w,'jobs'))
        self.assertTrue(any('Hoàn thành L2 / C1; xét tiếp điều kiện kế tiếp.' in v for k,v in out if k=='log'))
        self.assertTrue(any('Hoàn thành L3 / C2; đã hết lượt, xét lại từ đầu.' in v for k,v in out if k=='log'))
    def test_skipped_early_rule_matching_during_later_chain_waits_for_next_pass(self):
        rules=[]
        for f,name,k in [('L1','A','A'),('L2','B','B'),('L3','C','C')]:
            c=cond(name,[action(k,1,20)]);c.update(stable=0,stability_window=120,maximum=1);rules.append((f,c))
        good={'A':True,'B':False,'C':True};downs=[];done=threading.Event()
        def report(k,v):
            if k=='log' and v.startswith('Hoàn thành L2'):done.set()
        def qualify(_,c):return good[c['name']],1,1,1
        def down(key):
            downs.append(key)
            if key==ord('C'):good['B']=True
        w=engine.Engine(rules,7,False,report)
        with patch.object(engine.mss,'mss',return_value=FakeMSS()),patch.object(engine.win,'foreground',return_value=7),patch.object(w,'qualifies',side_effect=qualify),patch.object(engine.win,'key_down',side_effect=down),patch.object(engine.win,'key_up'):
            w.start();self.assertTrue(done.wait(3));w.stop();w.action_thread.join(1)
        self.assertEqual(downs,[ord('A'),ord('C'),ord('B')])
    def test_focus_and_pause_reset_timers_but_preserve_order_position(self):
        rules=[('L',cond(str(i),[action(chr(65+i),1)])) for i in range(4)]
        w=engine.Engine(rules,7,False,lambda *_:None);w.pass_cursor=2;w.states[2]['since']=3;w.states[2]['window_since']=3;w.states[2]['window_phase']='search'
        with patch.object(engine.win,'foreground',return_value=8):self.assertIsNone(w.scan(FakeMSS())[0])
        self.assertEqual(w.pass_cursor,2);self.assertIsNone(w.states[2]['window_since'])
        w.pause();w.resume();self.assertEqual(w.pass_cursor,2)
        w.states[2]['window_since']=3;w.reset_stability();self.assertEqual(w.pass_cursor,2);self.assertIsNone(w.states[2]['window_since'])
    def test_later_match_disappeared_during_prior_chain_is_not_queued(self):
        rules=[('L1',cond('A',[action('A',1,50)])),('L2',cond('B',[action('B',1)]))];rules[1][1]['stability_window']=120
        good={'A':True,'B':True};downs=[];a_finished=threading.Event()
        def qualify(_,c):return good[c['name']],1,1,1
        def down(k):downs.append(k);good['B']=False
        w=engine.Engine(rules,7,False,lambda k,v:a_finished.set() if k=='log' and v.startswith('Hoàn thành L1') else None)
        with patch.object(engine.mss,'mss',return_value=FakeMSS()),patch.object(engine.win,'foreground',return_value=7),patch.object(w,'qualifies',side_effect=qualify),patch.object(engine.win,'key_down',side_effect=down),patch.object(engine.win,'key_up'):
            w.start();self.assertTrue(a_finished.wait(2));time.sleep(.35);w.stop();w.action_thread.join(1)
        self.assertEqual(downs,[ord('A')]);self.assertFalse(hasattr(w,'jobs'))
