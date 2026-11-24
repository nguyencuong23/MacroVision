import sys
import types
import unittest
from unittest.mock import patch
import threading
import numpy as np

# The tests of validation and input scheduling don't need screen capture.
try:
    import mss
except ImportError:
    sys.modules['mss'] = types.ModuleType('mss')
import engine


def rule(actions):
    return [{'name': 'A', 'conditions': [{'name': 'B', 'template': np.zeros((5,5,3), dtype=np.uint8),
        'mask': np.ones((5,5), dtype=np.uint8)*255, 'region': {'left':0,'top':0,'width':5,'height':5},
        'sim':.96,'bright':0.,'stable':250,'mode':'Một lần','cool':2000,'maximum':10,'actions':actions}]}]

def act(kind='Phím', key='A', order=1, hold=20):
    return {'type':kind,'key':key,'order':order,'hold':hold,'x':10,'y':20}

class EngineTest(unittest.TestCase):
    def test_duplicate_mouse_same_group_rejected(self):
        with self.assertRaisesRegex(ValueError,'nhiều hơn một'):
            engine.validate(rule([act('Chuột trái'),act('Chuột phải')]))
    def test_duplicate_key_rejected(self):
        with self.assertRaisesRegex(ValueError,'phím trùng'):
            engine.validate(rule([act(key='A'),act(key='a')]))
    def test_mouse_and_key_down_before_release(self):
        events=[]
        with patch.object(engine.win,'foreground',return_value=7), \
             patch.object(engine.win,'key_down',side_effect=lambda x:events.append(('down-key',x))), \
             patch.object(engine.win,'key_up',side_effect=lambda x:events.append(('up-key',x))), \
             patch.object(engine.win,'mouse_down',side_effect=lambda *x:events.append(('down-mouse',x))), \
             patch.object(engine.win,'mouse_up',side_effect=lambda *x:events.append(('up-mouse',x))):
            self.assertTrue(engine.run_group([act(),act('Chuột trái')],7,threading.Event()))
        self.assertEqual([e[0] for e in events],['down-key','down-mouse','up-key','up-mouse'])
    def test_focus_loss_releases_key(self):
        events=[]
        with patch.object(engine.win,'foreground',side_effect=[7,7,8]), \
             patch.object(engine.win,'key_down',side_effect=lambda x:events.append('down')), \
             patch.object(engine.win,'key_up',side_effect=lambda x:events.append('up')):
            self.assertFalse(engine.run_group([act()],7,threading.Event()))
        self.assertEqual(events,['down','up'])

class ApiSchedulingTests(unittest.TestCase):
    def test_legacy_backend_forwarded_on_down_and_up(self):
        a=act('Chuột trái',hold=10); a['mouse_api']='mouse_event'
        with patch.object(engine.win,'foreground',return_value=7), \
             patch.object(engine.win,'mouse_down',return_value='SetCursorPos') as down, \
             patch.object(engine.win,'mouse_up') as up:
            self.assertTrue(engine.run_group([a],7,threading.Event()))
        self.assertEqual(down.call_args.args[-1], 'mouse_event')
        self.assertEqual(up.call_args.args, ('Chuột trái','mouse_event'))

if __name__=='__main__': unittest.main()

class RepeatTests(unittest.TestCase):
    def test_repeats_and_interval(self):
        events=[]
        a=act(key='A', hold=10); a.update(repeat=3, interval=10)
        with patch.object(engine.win,'foreground',return_value=7), \
             patch.object(engine.win,'key_down',side_effect=lambda x:events.append('down')), \
             patch.object(engine.win,'key_up',side_effect=lambda x:events.append('up')):
            self.assertTrue(engine.run_group([a],7,threading.Event()))
        self.assertEqual(events,['down','up','down','up','down','up'])
        self.assertAlmostEqual(engine.group_duration([a]), .05)
    def test_repeat_limit(self):
        a=act(); a.update(repeat=101, interval=0)
        with self.assertRaisesRegex(ValueError, 'lặp'):
            engine.validate(rule([a]))
    def test_stop_releases_key(self):
        stop = threading.Event(); events=[]
        def down(_): events.append('down'); stop.set()
        with patch.object(engine.win,'foreground',return_value=7), \
             patch.object(engine.win,'key_down',side_effect=down), \
             patch.object(engine.win,'key_up',side_effect=lambda x:events.append('up')):
            self.assertFalse(engine.run_group([act(hold=100)],7,stop))
        self.assertEqual(events,['down','up'])
    def test_input_failure_releases_other_held_key(self):
        events=[]
        with patch.object(engine.win,'foreground',return_value=7), \
             patch.object(engine.win,'key_down',side_effect=lambda x:events.append('down')), \
             patch.object(engine.win,'key_up',side_effect=lambda x:events.append('up')), \
             patch.object(engine.win,'mouse_down',side_effect=RuntimeError('no cursor')):
            with self.assertRaises(RuntimeError):
                engine.run_group([act(),act('Chuột trái')],7,threading.Event())
        self.assertEqual(events,['down','up'])
