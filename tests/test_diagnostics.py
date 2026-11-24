import threading
import unittest
from unittest.mock import patch
import engine
from test_queue_execution import FakeMSS,action,cond

class DiagnosticTests(unittest.TestCase):
    def test_one_shot_blocker_and_priority_shown(self):
        a=cond('C1',[action('A',1)]);b=cond('C2',[action('B',1)])
        out=[];w=engine.Engine([('L3',a),('L3',b)],7,False,lambda k,v:out.append((k,v)))
        w.states[0]['armed']=False
        with patch.object(engine.win,'foreground',return_value=7),patch.object(w,'qualifies',return_value=(True,.97,.8,1)):
            self.assertEqual(w.scan(FakeMSS())[0],1)
        msg=next(v for k,v in out if 'quét trước khi chọn' in v)
        self.assertIn('chọn L3/C2',msg);self.assertIn('L3/C1:',msg);self.assertIn('Một lần chưa được mở lại',msg);self.assertIn('0.9700',msg)
    def test_actual_press_and_release_reported_with_group(self):
        out=[];done=threading.Event();w=engine.Engine([('L3',cond('C2',[action('Q',6)]))],7,False,lambda k,t:(out.append(t),done.set() if t.startswith('Hoàn thành') else None))
        with patch.object(engine.mss,'mss',return_value=FakeMSS()),patch.object(engine.win,'foreground',return_value=7),patch.object(w,'qualifies',return_value=(True,1,1,1)),patch.object(engine.win,'key_down'),patch.object(engine.win,'key_up'):
            w.start();self.assertTrue(done.wait(2));w.stop();w.action_thread.join(1)
        self.assertTrue(any('L3/C2 · nhóm 6' in x and 'NHẤN [' in x and 'phím Q' in x for x in out))
        self.assertTrue(any('L3/C2 · nhóm 6' in x and 'NHẢ [' in x and 'phím Q' in x for x in out))
        self.assertTrue(any('nhóm 6: các lần nhấn, nhả và chờ đã kết thúc' in x for x in out))
    def test_primary_log_exact_action_label_and_real_event_time(self):
        out=[];done=threading.Event();a=action('Q',6);a['repeat']=2;a['interval']=10
        w=engine.Engine([('Luồng 3',cond('Điều kiện 2',[a]))],7,False,lambda k,t:(out.append((k,t)),done.set() if k=='log' and t.startswith('Hoàn thành') else None))
        with patch.object(engine.mss,'mss',return_value=FakeMSS()),patch.object(engine.win,'foreground',return_value=7),patch.object(w,'qualifies',return_value=(True,1,1,1)),patch.object(engine.win,'key_down'),patch.object(engine.win,'key_up'):
            w.start();self.assertTrue(done.wait(2));w.stop();w.action_thread.join(1)
        events=[x for k,x in out if k=='action'];self.assertEqual(len(events),4)
        self.assertRegex(events[0],r'^\d\d:\d\d:\d\d\.\d{3}: Luồng 3 / Điều kiện 2 / Thao tác Q · số thứ tự 6 · NHẤN · lần 1/2$')
        self.assertIn('NHẢ · lần 1/2',events[1]);self.assertIn('NHẤN · lần 2/2',events[2]);self.assertIn('NHẢ · lần 2/2',events[3])
    def test_primary_log_mouse_and_emergency_release(self):
        events=[];stop=threading.Event();a=action('A',1,hold=500);a.update(type='Chuột trái',mouse_mode='Nhấn tại con trỏ hiện tại',x=0,y=0)
        def on_event(kind,act,repeat,ts):
            events.append((kind,act['type'],repeat,ts))
            if kind=='NHẤN':stop.set()
        with patch.object(engine.win,'foreground',return_value=7),patch.object(engine.win,'mouse_down',return_value='hiện tại'),patch.object(engine.win,'mouse_up'):
            self.assertFalse(engine.run_group([a],7,stop,action_event=on_event))
        self.assertEqual([x[0] for x in events],['NHẤN','NHẢ KHẨN']);self.assertEqual(events[0][1],'Chuột trái')
    def test_focus_reports_observed_handles_without_recheck(self):
        out=[];f=[7,7,8]
        with patch.object(engine.win,'foreground',side_effect=f),patch.object(engine.win,'describe_window',side_effect=lambda x:f'HWND={x}'),patch.object(engine.win,'key_down'),patch.object(engine.win,'key_up'):
            self.assertFalse(engine.run_group([action('A',1)],7,threading.Event(),out.append))
        text=' '.join(out);self.assertIn('FOCUS',text);self.assertIn('HWND=7',text);self.assertIn('HWND=8',text)
