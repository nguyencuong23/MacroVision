import copy,threading,time,unittest
from unittest.mock import patch
import numpy as np
import engine,once_engine
from test_queue_execution import FakeMSS,action,cond

def c(name,key):
    c=cond(name,[action(key,1,15)]);c.update(stable=0,stability_window=110,color_sim=0.,unlimited=True,confirm_activation=False)
    return c

def run(groups,qualify,on_down=None):
    events=[];messages=[];done=threading.Event()
    def out(k,v):
        messages.append((k,v))
        if k=='thread_done':done.set()
    w=once_engine.OnceEngine(groups,7,False,out)
    def press(k):
        events.append(('down',k))
        if on_down:on_down(k)
    with patch.object(engine.mss,'mss',return_value=FakeMSS()),patch.object(once_engine.mss,'mss',return_value=FakeMSS()),patch.object(engine.win,'foreground',return_value=7),patch.object(w,'qualifies',side_effect=qualify),patch.object(engine.win,'key_down',side_effect=press),patch.object(engine.win,'key_up',side_effect=lambda k:events.append(('up',k))):
        w.start();assert done.wait(5), 'worker timed out';w.action_thread.join(1)
    return events,messages,w

class OnceTests(unittest.TestCase):
    def test_each_flow_all_conditions_in_order_then_automatically_stops(self):
        groups=[[('F1',c('C1','A')),('F1',c('C2','B'))],[('F2',c('C1','C'))],[('F3',c('C1','D')),('F3',c('C2','E'))]]
        events,msg,w=run(groups,lambda *_:(True,1,1,1))
        self.assertEqual([k for event,k in events if event=='down'],list(map(ord,'ABCDE')))
        self.assertFalse(w.alive());self.assertTrue(any('đã hoàn thành tất cả luồng' in v for k,v in msg))
    def test_waits_current_condition_then_executes_every_condition_once(self):
        a,b,d=c('A','A'),c('B','B'),c('D','D');seen=[];count=[0]
        def qual(s,x):
            seen.append(x['name'])
            if x['name']=='A':count[0]+=1
            return (x['name']!='A' or count[0]>=4,1,1,1)
        events,msg,w=run([[('F1',a),('F1',b)],[('F2',d)]],qual)
        self.assertEqual([chr(k) for e,k in events if e=='down'],['A','B','D'])
        self.assertGreaterEqual(count[0],5);self.assertTrue(all(n=='A' for n in seen[:seen.index('B')]))
    def test_later_ready_condition_does_not_run_while_first_never_ready(self):
        a,b=c('A','A'),c('B','B');seen=[];events=[];w=once_engine.OnceEngine([[('F',a),('F',b)]],7,False,lambda *_:None)
        def qual(_,x):seen.append(x['name']);return (x['name']=='B',1,1,1)
        with patch.object(once_engine.mss,'mss',return_value=FakeMSS()),patch.object(engine.win,'foreground',return_value=7),patch.object(w,'qualifies',side_effect=qual),patch.object(engine.win,'key_down',side_effect=lambda k:events.append(k)),patch.object(engine.win,'key_up'):
            w.start();time.sleep(.55);self.assertTrue(w.alive());w.stop();w.action_thread.join(1)
        self.assertFalse(events);self.assertTrue(seen);self.assertEqual(set(seen),{'A'})
    def test_same_named_flows_still_distinct(self):
        events,_,_=run([[('L',c('A','A'))],[('L',c('B','B'))]],lambda *_:(True,1,1,1))
        self.assertEqual([chr(k) for e,k in events if e=='down'],['A','B'])
    def test_configuration_is_copied_and_loop_settings_ignored_for_validation(self):
        x=c('A','A');x.update(region={'left':0,'top':0,'width':4,'height':4},template=np.zeros((4,4,3),np.uint8),mask=np.ones((4,4),np.uint8),mode='bad',maximum=-44,cool=-3,release_stable=-2)
        flows=[{'name':'L','conditions':[x]}];groups=once_engine.validate(flows)
        self.assertEqual(x['maximum'],-44);self.assertEqual(x['mode'],'bad');self.assertEqual(groups[0][0][1]['maximum'],1)
        with self.assertRaises(ValueError):engine.validate(flows)
    def test_pause_and_stop_during_unmatched_search(self):
        x=c('A','A');w=once_engine.OnceEngine([[('L',x)]],7,False,lambda *_:None);calls=[]
        with patch.object(once_engine.mss,'mss',return_value=FakeMSS()),patch.object(engine.win,'foreground',return_value=7),patch.object(w,'qualifies',side_effect=lambda *_:(calls.append(1) or False,0,0,0)):
            w.start();time.sleep(.12);w.pause();time.sleep(.15);count=len(calls);time.sleep(.15);self.assertEqual(len(calls),count);w.stop();w.action_thread.join(1)
        self.assertFalse(w.alive())
    def test_f8_interrupt_during_hold_never_moves_to_next_flow(self):
        entered=threading.Event();events=[];w=once_engine.OnceEngine([[('L1',c('A','A'))],[('L2',c('B','B'))]],7,False,lambda *_:None)
        w.flow_rules[0][0][1]['actions'][0]['hold']=500
        with patch.object(once_engine.mss,'mss',return_value=FakeMSS()),patch.object(engine.win,'foreground',return_value=7),patch.object(w,'qualifies',return_value=(True,1,1,1)),patch.object(engine.win,'key_down',side_effect=lambda k:(events.append(('down',k)),entered.set())),patch.object(engine.win,'key_up',side_effect=lambda k:events.append(('up',k))):
            w.start();self.assertTrue(entered.wait(2));w.stop();w.action_thread.join(1)
        self.assertEqual(events,[('down',65),('up',65)])
    def test_focus_loss_during_hold_stops_one_time_script(self):
        state=[7];events=[];ended=threading.Event();a=c('A','A');a['actions'][0]['hold']=300
        w=once_engine.OnceEngine([[('L1',a)],[('L2',c('B','B'))]],7,False,lambda k,v:ended.set() if k=='thread_done' else None)
        def down(k):events.append(('down',k));state[0]=8
        with patch.object(once_engine.mss,'mss',return_value=FakeMSS()),patch.object(engine.win,'foreground',side_effect=lambda:state[0]),patch.object(engine.win,'describe_window',side_effect=lambda x:str(x)),patch.object(w,'qualifies',return_value=(True,1,1,1)),patch.object(engine.win,'key_down',side_effect=down),patch.object(engine.win,'key_up',side_effect=lambda k:events.append(('up',k))):
            w.start();self.assertTrue(ended.wait(2));w.action_thread.join(1)
        self.assertEqual(events,[('down',65),('up',65)])
    def test_confirmation_keeps_pressing_first_before_second(self):
        a=c('A','A');a['confirm_activation']=True;a['actions'].append(action('B',2,15));pressed=[]
        def qual(s,cond):return (len(pressed)<2,1,1,1)
        events,msg,w=run([[('L',a)]],qual,lambda k:pressed.append(k))
        self.assertEqual([chr(k) for e,k in events if e=='down'],['A','A','B'])
    def test_post_delay_completes_before_next_flow(self):
        a=c('A','A');a['actions'][0]['after_delay']=150;times={}
        def on_down(k):times[k]=time.monotonic()
        events,_,_=run([[('L1',a)],[('L2',c('B','B'))]],lambda *_:(True,1,1,1),on_down)
        self.assertGreaterEqual(times[66]-times[65],.15)
    def test_stable_duration_is_observed_before_press(self):
        a=c('A','A');a.update(stable=150,stability_window=400);samples=[];times=[]
        def qual(*_):samples.append(time.monotonic());return True,1,1,1
        run([[('L',a)]],qual,lambda k:times.append(time.monotonic()))
        self.assertGreaterEqual(times[0]-samples[0],.14);self.assertGreaterEqual(len(samples),3)
    def test_failed_recheck_retries_same_condition_before_next(self):
        a,b=c('A','A'),c('B','B');n=[0]
        def qual(_,x):
            if x['name']=='A':
                n[0]+=1;return n[0]!=2,1,1,1
            return True,1,1,1
        ev,_,_=run([[('L',a),('L',b)]],qual)
        self.assertEqual([chr(k) for e,k in ev if e=='down'],['A','B']);self.assertGreaterEqual(n[0],4)
    def test_later_condition_is_checked_fresh_and_waited_not_queued(self):
        a,b=c('A','A'),c('B','B');a['actions'][0]['hold']=70;good=[True];done=threading.Event();events=[]
        w=once_engine.OnceEngine([[('L1',a),('L1',b)]],7,False,lambda k,v:done.set() if k=='thread_done' else None)
        def down(k):events.append(k);good[0]=False
        def qual(_,x):return (x['name']=='A' or good[0],1,1,1)
        with patch.object(once_engine.mss,'mss',return_value=FakeMSS()),patch.object(engine.win,'foreground',return_value=7),patch.object(w,'qualifies',side_effect=qual),patch.object(engine.win,'key_down',side_effect=down),patch.object(engine.win,'key_up'):
            w.start();time.sleep(.5);self.assertFalse(done.is_set());self.assertEqual(events,[65]);good[0]=True
            self.assertTrue(done.wait(2));w.action_thread.join(1)
        self.assertEqual(events,[65,66])
    def test_flow_waits_for_all_conditions_and_does_not_replay_completed(self):
        a,b,d=c('A','A'),c('B','B'),c('D','D');enabled=threading.Event();reached_b=threading.Event();done=threading.Event();pressed=[]
        def qual(_,x):
            if x['name']=='B':reached_b.set();return enabled.is_set(),1,1,1
            return True,1,1,1
        w=once_engine.OnceEngine([[('F1',a),('F1',b)],[('F2',d)]],7,False,lambda k,v:done.set() if k=='thread_done' else None)
        with patch.object(once_engine.mss,'mss',return_value=FakeMSS()),patch.object(engine.win,'foreground',return_value=7),patch.object(w,'qualifies',side_effect=qual),patch.object(engine.win,'key_down',side_effect=lambda k:pressed.append(k)),patch.object(engine.win,'key_up'):
            w.start();self.assertTrue(reached_b.wait(2));time.sleep(.45);self.assertEqual(pressed,[65]);self.assertFalse(done.is_set())
            w.pause();time.sleep(.15);enabled.set();time.sleep(.2);self.assertEqual(pressed,[65])
            w.resume();self.assertTrue(done.wait(3));w.action_thread.join(1)
        self.assertEqual(pressed,[65,66,68])
    def test_all_conditions_must_complete_even_when_later_flow_is_ready(self):
        a,b,d=c('A','A'),c('B','B'),c('D','D');pressed=[];waiting=threading.Event();messages=[]
        def qual(_,x):
            if x['name']=='B':waiting.set();return False,0,0,0
            return True,1,1,1
        w=once_engine.OnceEngine([[('F1',a),('F1',b)],[('F2',d)]],7,False,lambda k,v:messages.append((k,v)))
        with patch.object(once_engine.mss,'mss',return_value=FakeMSS()),patch.object(engine.win,'foreground',return_value=7),patch.object(w,'qualifies',side_effect=qual),patch.object(engine.win,'key_down',side_effect=lambda k:pressed.append(k)),patch.object(engine.win,'key_up'):
            w.start();self.assertTrue(waiting.wait(2));time.sleep(.3);w.stop();w.action_thread.join(1)
        self.assertEqual(pressed,[65]);self.assertFalse(any('đã hoàn thành tất cả luồng' in m for _,m in messages))
    def test_hidden_search_window_never_causes_stable_timer_reset(self):
        a=c('A','A');a.update(stable=260,stability_window=100);samples=[];pressed=[]
        ev,_,_=run([[('L',a)]],lambda *_:(samples.append(time.monotonic()) or True,1,1,1),lambda k:pressed.append(time.monotonic()))
        self.assertEqual([k for e,k in ev if e=='down'],[65]);self.assertGreaterEqual(pressed[0]-samples[0],.26)
    def test_search_waits_unlimited_and_keeps_later_condition_blocked(self):
        a,b=c('A','A'),c('B','B');a['stability_window']=50;ready=threading.Event();observed=threading.Event();done=threading.Event();samples=[];pressed=[]
        def qual(_,x):
            samples.append(x['name']);observed.set()
            return (ready.is_set() if x['name']=='A' else True,1,1,1)
        w=once_engine.OnceEngine([[('L',a),('L',b)]],7,False,lambda k,v:done.set() if k=='thread_done' else None)
        with patch.object(once_engine.mss,'mss',return_value=FakeMSS()),patch.object(engine.win,'foreground',return_value=7),patch.object(w,'qualifies',side_effect=qual),patch.object(engine.win,'key_down',side_effect=lambda k:pressed.append(k)),patch.object(engine.win,'key_up'):
            w.start();self.assertTrue(observed.wait(1));time.sleep(.6);self.assertFalse(done.is_set());self.assertEqual(set(samples),{'A'});self.assertEqual(pressed,[])
            ready.set();self.assertTrue(done.wait(2));w.action_thread.join(1)
        self.assertEqual(pressed,[65,66])
    def test_unstable_sample_resets_stability_timer(self):
        a=c('A','A');a.update(stable=240,stability_window=100);calls=[];pressed=[]
        def qual(*_):
            calls.append(time.monotonic());return len(calls)!=3,1,1,1
        run([[('L',a)]],qual,lambda k:pressed.append(time.monotonic()))
        self.assertGreaterEqual(len(calls),7);self.assertGreaterEqual(pressed[0]-calls[3],.23)
    def test_once_validation_ignores_saved_window_but_repeat_mode_does_not(self):
        x=c('A','A');x.update(region={'left':0,'top':0,'width':4,'height':4},template=np.zeros((4,4,3),np.uint8),mask=np.ones((4,4),np.uint8),stable=500,stability_window=100)
        flows=[{'name':'L','conditions':[x]}]
        once_engine.validate(flows);self.assertEqual(x['stability_window'],100)
        with self.assertRaisesRegex(ValueError,'không được nhỏ hơn'):engine.validate(flows)
