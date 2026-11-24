"""Stable-off rearming uses only live, contiguous observations, with no condition queue."""
import unittest
from unittest.mock import patch
import engine
import form_model
from test_queue_execution import FakeMSS, action, cond

class RearmTests(unittest.TestCase):
    def setUp(self):
        self.rule=cond('C',[action('A',1)]);self.rule.update(maximum=10,stable=0,release_stable=500)
        self.logs=[];self.w=engine.Engine([('L',self.rule)],7,False,lambda k,t:self.logs.append(t) if k=='log' else None);self.w.states[0]['armed']=False;self.s=FakeMSS()
    def scan_at(self,t,good):
        with patch.object(engine.win,'foreground',return_value=7),patch.object(engine.time,'monotonic',return_value=t),patch.object(self.w,'qualifies',return_value=(good,1 if good else 0,1,1)):
            return self.w.scan(self.s)[0]
    def test_brief_flicker_does_not_rearm(self):
        self.assertIsNone(self.scan_at(1,False));self.assertIsNone(self.scan_at(1.1,True));self.assertIsNone(self.scan_at(1.8,True))
        self.assertFalse(self.w.states[0]['armed']);self.assertEqual(self.logs,[])
    def test_sustained_off_rearms_then_new_match_can_run(self):
        self.assertIsNone(self.scan_at(1,False));self.assertIsNone(self.scan_at(1.4,False));self.assertFalse(self.w.states[0]['armed'])
        self.assertIsNone(self.scan_at(1.6,False));self.assertTrue(self.w.states[0]['armed']);self.assertEqual(len(self.logs),1)
        self.assertEqual(self.scan_at(1.7,True),0)
    def test_true_in_between_resets_off_timer(self):
        self.scan_at(1,False);self.scan_at(1.4,True);self.scan_at(1.5,False);self.scan_at(1.9,False)
        self.assertFalse(self.w.states[0]['armed']);self.scan_at(2.1,False);self.assertTrue(self.w.states[0]['armed'])
    def test_no_credit_for_non_observation_pause_focus_or_running(self):
        self.scan_at(1,False);self.w.reset_stability();self.scan_at(2,False);self.assertFalse(self.w.states[0]['armed'])
        with patch.object(engine.win,'foreground',return_value=8):self.w.scan(self.s)
        self.scan_at(3,False);self.assertFalse(self.w.states[0]['armed']);self.scan_at(3.6,False);self.assertTrue(self.w.states[0]['armed'])
    def test_zero_restores_single_observation_rearm(self):
        self.rule['release_stable']=0;self.scan_at(1,False);self.assertTrue(self.w.states[0]['armed']);self.assertEqual(self.scan_at(1.1,True),0)
    def test_validation_limits(self):
        self.assertEqual(form_model.parse_field('condition','release_stable','500'),500)
        for v in (-1,30001):
            with self.assertRaises(ValueError):form_model.parse_field('condition','release_stable',str(v))
    def test_old_script_defaults_to_500(self):
        import app
        a=app.new_condition();a.pop('release_stable');f={'id':'x','name':'L','conditions':[a]}
        self.assertEqual(app.deserialize(app.serialize([f]))[0]['conditions'][0]['release_stable'],500)
