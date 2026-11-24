import unittest,threading
from unittest.mock import patch
import engine
from test_queue_execution import FakeMSS,action,cond

class ConditionLogTests(unittest.TestCase):
    def test_reports_fresh_recheck_scores_before_first_input(self):
        logs=[];done=threading.Event()
        w=engine.Engine([('Luồng 3',cond('Điều kiện 1',[action('1',1)]))],7,False,lambda k,t:(logs.append((k,t)),done.set() if k=='log' and t.startswith('Hoàn thành') else None))
        scores=iter([(True,.91234,.31,1),(True,.98765,.54321,1)])
        def qualifies(*_):return next(scores,(False,.1,.1,1))
        with patch.object(engine.mss,'mss',return_value=FakeMSS()),patch.object(engine.win,'foreground',return_value=7),patch.object(w,'qualifies',side_effect=qualifies),patch.object(engine.win,'key_down'),patch.object(engine.win,'key_up'):
            w.start();self.assertTrue(done.wait(2));w.stop();w.action_thread.join(1)
        found=[(i,s) for i,(k,s) in enumerate(logs) if k=='condition' and '/ Kích hoạt ' in s];self.assertEqual(len(found),1)
        i,text=found[0];self.assertRegex(text,r'^\d\d:\d\d:\d\d\.\d{3}: Luồng 3 / Kích hoạt Điều kiện 1 \(Độ giống: 0\.9877, Độ giống màu: 1\.0000/0\.0000, Độ sáng: 0\.5432/0\.0000\)$')
        first_action=next(i for i,(k,_) in enumerate(logs) if k=='action');self.assertLess(i,first_action)
    def test_no_activation_when_recheck_fails(self):
        logs=[];rechecked=threading.Event();n=[0]
        w=engine.Engine([('L',cond('C',[action('1',1)]))],7,False,lambda k,t:logs.append((k,t)))
        def qualifies(*_):
            n[0]+=1
            if n[0]==1:return True,.99,.6,1
            rechecked.set();return False,.4,.2,1
        with patch.object(engine.mss,'mss',return_value=FakeMSS()),patch.object(engine.win,'foreground',return_value=7),patch.object(w,'qualifies',side_effect=qualifies),patch.object(engine.win,'key_down') as down:
            w.start();self.assertTrue(rechecked.wait(2));w.stop();w.action_thread.join(1)
        self.assertFalse(any(k=='condition' and '/ Kích hoạt ' in s for k,s in logs));self.assertTrue(any('không còn đạt khi kiểm tra lại' in s for _,s in logs));down.assert_not_called()
