"""Exercise actual Tk dragging, tree/model consistency and execution ordering."""
import json,os,tempfile,threading,time,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import app,engine,once_engine
from test_queue_execution import FakeMSS

@unittest.skipUnless(os.name!='nt' and os.environ.get('DISPLAY'),'Requires Xvfb/display')
class DragTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name)
        self.patches=[patch.object(app.prefs_store,'application_dir',return_value=self.base)]+[patch.object(app.win,n,return_value=False) for n in ('f6_down','f7_down','f8_down')]
        for p in self.patches:p.start()
        self.r=app.App();self.r.update()
        self.a,self.b,self.c=[app.new_action() for _ in range(3)]
        for a,k,n in [(self.a,'A',1),(self.b,'B',2),(self.c,'C',3)]:a.update(key=k,order=n,hold=10)
        self.c1,self.c2,self.c3=[app.new_condition() for _ in range(3)]
        for i,c in enumerate((self.c1,self.c2,self.c3)):
            c.update(name='C'+str(i+1),template=np.zeros((4,4,3),dtype=np.uint8),mask=np.ones((4,4),dtype=np.uint8),region={'left':0,'top':0,'width':4,'height':4},stable=0,stability_window=300,mode='Lặp',cool=200,maximum=1)
        self.c1['actions']=[self.a,self.b];self.c2['actions']=[self.c];self.c3['actions']=[app.new_action()];self.c3['actions'][0].update(key='D',hold=10)
        self.f1={'id':app.new_id(),'name':'F1','conditions':[self.c1,self.c2]};self.f2={'id':app.new_id(),'name':'F2','conditions':[self.c3]}
        self.r.flows=[self.f1,self.f2];self.r.refresh_tree(self.a['id']);self.r.dirty=False;self.r.update()
    def tearDown(self):
        try:self.r.drag_cancel();self.r.after_cancel(self.r.tick_job);self.r.cancel_pending_save();self.r.destroy()
        except Exception:pass
        for p in reversed(self.patches):p.stop()
        self.tmp.cleanup()
    def drag(self,source,target,after=True):
        t=self.r.tree;t.see(source);t.see(target);self.r.update()
        a=t.bbox(source);b=t.bbox(target);self.assertTrue(a);self.assertTrue(b)
        x=180;sy=a[1]+a[3]//2;ty=b[1]+(b[3]-3 if after else 2)
        t.event_generate('<ButtonPress-1>',x=x,y=sy);self.r.update()
        t.event_generate('<B1-Motion>',x=x,y=ty);self.r.update()
        t.event_generate('<ButtonRelease-1>',x=x,y=ty);self.r.update()
    def test_drag_flow_moves_its_whole_subtree(self):
        self.drag(self.f1['id'],self.f2['id'],True)
        self.assertEqual(self.r.flows,[self.f2,self.f1]);self.assertEqual(self.r.tree.parent(self.c1['id']),self.f1['id']);self.assertEqual(self.r.tree.parent(self.a['id']),self.c1['id']);self.assertTrue(self.r.dirty)
    def test_drag_condition_into_other_flow_preserves_descendants_and_mapping(self):
        self.drag(self.c1['id'],self.f2['id'])
        self.assertEqual([c['id'] for c in self.f1['conditions']],[self.c2['id']]);self.assertEqual([c['id'] for c in self.f2['conditions']],[self.c3['id'],self.c1['id']])
        self.assertIs(self.r.item_map[self.a['id']][1],self.f2);self.assertIs(self.r.item_map[self.a['id']][2],self.c1)
        self.assertEqual(self.r.tree.parent(self.c1['id']),self.f2['id']);self.assertEqual(self.r.tree.parent(self.a['id']),self.c1['id'])
        self.r.tree.selection_set(self.a['id']);self.r.update();self.assertIs(self.r.selected[1],self.f2)
    def test_drag_condition_before_condition_in_another_flow(self):
        self.drag(self.c2['id'],self.c3['id'],False)
        self.assertEqual([c['id'] for c in self.f2['conditions']],[self.c2['id'],self.c3['id']]);self.assertEqual(self.r.tree.parent(self.c2['id']),self.f2['id'])
    def test_drag_action_cross_conditions_preserves_order_and_configuration(self):
        old=self.b.copy();self.drag(self.b['id'],self.c3['id'])
        self.assertEqual(self.b,old);self.assertEqual([a['id'] for a in self.c3['actions']][-1],self.b['id'])
        self.assertEqual(self.r.tree.parent(self.b['id']),self.c3['id']);self.assertIs(self.r.selected[1],self.f2);self.assertIs(self.r.selected[2],self.c3)
        self.assertIn('Số thứ tự không đổi',self.r.status.get())
    def test_action_reorder_only_visual_numbers_stay_and_engine_sorts(self):
        self.drag(self.b['id'],self.a['id'],False)
        self.assertEqual([a['key'] for a in self.c1['actions']],['B','A']);self.assertEqual([a['order'] for a in self.c1['actions']],[2,1]);self.assertEqual([self.r.tree.item(i,'text')[:1] for i in self.r.tree.get_children(self.c1['id'])],['2','1'])
        self.assertEqual([a['key'] for a in sorted(self.c1['actions'],key=lambda a:a['order'])],['A','B'])
    def test_invalid_cross_type_drop_is_ignored(self):
        self.drag(self.a['id'],self.f2['id'])
        self.assertEqual(self.r.tree.parent(self.a['id']),self.c1['id']);self.assertFalse(self.r.dirty)
    def test_noop_drop_does_not_mark_dirty(self):
        self.drag(self.a['id'],self.b['id'],False)
        self.assertFalse(self.r.dirty);self.assertEqual([a['id'] for a in self.c1['actions']],[self.a['id'],self.b['id']])
    def test_drag_is_available_in_single_mode_and_roundtrips_script(self):
        self.r.script_mode_var.set('Một lần');self.r.change_script_mode();self.r.update();self.drag(self.c1['id'],self.f2['id'])
        p=self.base/'script.json'
        with patch.object(app.filedialog,'asksaveasfilename',return_value=str(p)):self.r.save_script()
        with open(p,encoding='utf8') as f:data=json.load(f)
        self.assertEqual(data['script_mode'],'Một lần');flows=app.deserialize(data)
        self.assertEqual([[c['id'] for c in f['conditions']] for f in flows],[[self.c2['id']],[self.c3['id'],self.c1['id']]])
        self.assertEqual([a['id'] for a in flows[1]['conditions'][1]['actions']],[self.a['id'],self.b['id']])
    def test_invalid_form_prevents_drag_without_losing_edit(self):
        self.r.tree.selection_set(self.c1['id']);self.r.update();self.r.vars['stable'].set('');self.r.update()
        with patch.object(app.messagebox,'showerror'):
            self.drag(self.c1['id'],self.f2['id'])
        self.assertEqual(self.r.tree.parent(self.c1['id']),self.f1['id']);self.assertEqual(self.r.vars['stable'].get(),'')
    def test_escape_cancels_drag(self):
        t=self.r.tree;bb=t.bbox(self.c1['id']);t.event_generate('<ButtonPress-1>',x=180,y=bb[1]+bb[3]//2);t.event_generate('<B1-Motion>',x=180,y=bb[1]+bb[3]+10);self.r.update()
        self.assertTrue(self.r.drag_started);self.r.drag_cancel();self.assertFalse(self.r.drag_started);self.assertIsNone(self.r.drag_scroll_job);self.assertEqual(self.r.tree.parent(self.c1['id']),self.f1['id'])
    def test_actual_execution_respects_moved_tree_for_both_modes(self):
        self.drag(self.f1['id'],self.f2['id'],True)
        self.drag(self.b['id'],self.a['id'],False)
        for mode in ('Một lần','Lặp lại'):
            events=[];done=threading.Event();msgs=[]
            rules=once_engine.validate(self.r.flows) if mode=='Một lần' else engine.validate(self.r.flows)
            def out(k,v):
                msgs.append((k,v))
                if mode=='Một lần' and k=='thread_done':done.set()
                if mode=='Lặp lại' and k=='log' and v.startswith('Hoàn thành F1 / C2'):done.set()
            w=(once_engine.OnceEngine if mode=='Một lần' else engine.Engine)(rules,7,False,out)
            with patch.object(engine.mss,'mss',return_value=FakeMSS()),patch.object(engine.win,'foreground',return_value=7),patch.object(w,'qualifies',return_value=(True,1,1,1)),patch.object(engine.win,'key_down',side_effect=lambda k:events.append(k)),patch.object(engine.win,'key_up'):
                w.start();self.assertTrue(done.wait(3));w.stop();w.action_thread.join(1)
            self.assertEqual([chr(k) for k in events],list('DABC'),mode)
    def test_same_number_preserved_in_cross_condition_move(self):
        self.b['order']=1;self.r.update_tree_item(self.b,'action')
        self.drag(self.b['id'],self.c3['id'])
        self.assertEqual(self.b['order'],1);self.assertEqual([a['order'] for a in self.c3['actions']],[1,1])
        rules=engine.validate(self.r.flows);group=[a['key'] for f,c in rules if c['id']==self.c3['id'] for a in c['actions'] if a['order']==1]
        self.assertEqual(group,['D','B'])
    def test_cross_condition_duplicate_key_validation_unchanged(self):
        self.b.update(key='D',order=1);self.r.update_tree_item(self.b,'action');self.drag(self.b['id'],self.c3['id'])
        for validate in (engine.validate,once_engine.validate):
            with self.assertRaisesRegex(ValueError,'phím trùng nhau'):validate(self.r.flows)
    def test_new_empty_flow_can_receive_condition(self):
        f3={'id':app.new_id(),'name':'F3','conditions':[]};self.r.flows.append(f3);self.r.refresh_tree(self.c1['id']);self.r.update()
        self.drag(self.c1['id'],f3['id'])
        self.assertEqual([c['id'] for c in f3['conditions']],[self.c1['id']]);self.assertEqual(self.r.tree.parent(self.c1['id']),f3['id'])
    def test_reordering_condition_inside_same_flow(self):
        self.drag(self.c2['id'],self.c1['id'],False)
        self.assertEqual([c['id'] for c in self.f1['conditions']],[self.c2['id'],self.c1['id']]);self.assertEqual(self.r.tree.get_children(self.f1['id']),(self.c2['id'],self.c1['id']))
