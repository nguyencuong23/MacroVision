"""Linux Xvfb UI tests, with all writes isolated in a temporary directory."""
import json
import os
import tempfile
import unittest
from unittest.mock import patch

@unittest.skipUnless(os.name != 'nt' and os.environ.get('DISPLAY'), 'Requires Xvfb/display')
class UITests(unittest.TestCase):
    def setUp(self):
        import app
        self.app=app;self.tmp=tempfile.TemporaryDirectory();self.base=__import__('pathlib').Path(self.tmp.name)
        self.base_patch=patch.object(app.prefs_store,'application_dir',return_value=self.base);self.base_patch.start()
        self.hotkeys=[patch.object(app.win,n,return_value=False) for n in ('f6_down','f7_down','f8_down')]
        for p in self.hotkeys:p.start()
        self.root=app.App();self.update()
    def tearDown(self):
        try:self.root.after_cancel(self.root.tick_job);self.root.cancel_pending_save();self.root.destroy()
        except Exception:pass
        for p in self.hotkeys:p.stop()
        self.base_patch.stop();self.tmp.cleanup()
    def update(self): self.root.update_idletasks();self.root.update()
    def restart(self):
        self.root.after_cancel(self.root.tick_job);self.root.cancel_pending_save();self.root.destroy();self.root=self.app.App();self.update()
    def add_action(self):
        self.root.add_flow();self.update();self.root.add_condition();self.update();self.root.add_action();self.update()
    def test_primary_action_log_and_optional_diagnostics(self):
        r=self.root;r.after_cancel(r.tick_job)
        r.messages.put(('condition','19:22:18.000: Luồng 3 / Kích hoạt Điều kiện 2 (Độ giống: 0.9500, Độ sáng: 0.5000)'))
        r.messages.put(('action','19:22:18.790: Luồng 3 / Điều kiện 2 / Thao tác Q · số thứ tự 6 · NHẤN · lần 1/1'))
        r.messages.put(('log','CHẨN ĐOÁN mẫu ẩn'));r.messages.put(('log','LỖI thử nghiệm'))
        r.tick();r.after_cancel(r.tick_job);text=r.logbox.get('1.0','end')
        self.assertIn('19:22:18.000: Luồng 3 / Kích hoạt Điều kiện 2 (Độ giống: 0.9500, Độ sáng: 0.5000)',text)
        self.assertIn('19:22:18.790: Luồng 3 / Điều kiện 2 / Thao tác Q',text);self.assertNotIn('mẫu ẩn',text);self.assertIn('LỖI thử nghiệm',text)
        r.detailed_log.set(True);r.messages.put(('log','CHẨN ĐOÁN mẫu hiện'));r.tick();r.after_cancel(r.tick_job)
        self.assertIn('mẫu hiện',r.logbox.get('1.0','end'))
    def test_defaults_autosave_restore_without_script(self):
        self.add_action();r=self.root
        r.vars['type'].set('Chuột trái');r.vars['mouse_mode'].set('Nhấn tại con trỏ hiện tại');r.vars['hold'].set('500');self.update()
        r.after(750,r.quit);r.mainloop()
        with open(self.base/'settings.json',encoding='utf8') as f:d=json.load(f)
        self.assertEqual(d['preferences']['action']['hold'],500);self.assertNotIn('flows',d)
        self.restart();r=self.root;self.assertEqual(r.flows,[])
        self.add_action();self.assertEqual(r.selected[3]['hold'],500);self.assertEqual(r.selected[3]['type'],'Chuột trái')
    def test_rearm_field_edit_and_new_condition_default(self):
        r=self.root;r.add_flow();self.update();r.add_condition();self.update()
        self.assertEqual(r.vars['release_stable'].get(),'500');r.vars['release_stable'].set('800');self.update()
        self.assertEqual(r.selected[2]['release_stable'],800);r.add_condition();self.update()
        self.assertEqual(r.selected[2]['release_stable'],800);r.after(750,r.quit);r.mainloop();self.restart()
        self.assertEqual(self.root.preferences['condition']['release_stable'],800)
    def test_window_field_autosaves_preferences(self):
        r=self.root;r.add_flow();self.update();r.add_condition();self.update()
        self.assertEqual(r.vars['stability_window'].get(),'2000');r.vars['stability_window'].set('3500');self.update()
        self.assertEqual(r.selected[2]['stability_window'],3500);r.add_condition();self.update()
        self.assertEqual(r.selected[2]['stability_window'],3500)
        r.after(750,r.quit);r.mainloop();self.restart();self.assertEqual(self.root.preferences['condition']['stability_window'],3500)
    def test_color_field_autosaves_preferences(self):
        r=self.root;r.add_flow();self.update();r.add_condition();self.update()
        self.assertEqual(r.vars['color_sim'].get(),'0.0');r.vars['color_sim'].set('0.85');self.update()
        self.assertEqual(r.selected[2]['color_sim'],.85);r.add_condition();self.update();self.assertEqual(r.selected[2]['color_sim'],.85)
        r.after(750,r.quit);r.mainloop();self.restart();self.assertEqual(self.root.preferences['condition']['color_sim'],.85)
    def test_after_delay_is_saved_and_restored_as_default(self):
        self.add_action();r=self.root;r.vars['after_delay'].set('1200');self.update()
        self.assertEqual(r.selected[3]['after_delay'],1200);r.after(750,r.quit);r.mainloop()
        self.restart();self.add_action();self.assertEqual(self.root.selected[3]['after_delay'],1200)
    def test_older_script_defaults_after_delay_to_zero(self):
        a=self.app.new_action();a.pop('after_delay');c=self.app.new_condition();c['actions']=[a]
        f={'id':'flow','name':'L','conditions':[c]};loaded=self.app.deserialize(self.app.serialize([f]))
        self.assertEqual(loaded[0]['conditions'][0]['actions'][0]['after_delay'],0)
    def test_settings_are_kept_beside_app_and_script_is_separate(self):
        r=self.root;self.add_action();r.vars['hold'].set('750');self.update();r.after(750,r.quit);r.mainloop()
        self.assertTrue((self.base/'settings.json').exists());self.assertFalse((self.base/'MacroVision-defaults.json').exists())
        self.restart();self.assertEqual(self.root.preferences['action']['hold'],750);self.assertEqual(self.root.flows,[])
        self.assertEqual(self.root.preference_store.path,self.base/'settings.json')
    def test_script_only_saved_by_button_not_auto_saved(self):
        r=self.root;r.add_flow();self.update();p=self.base/'script.json'
        with patch.object(self.app.filedialog,'asksaveasfilename',return_value=str(p)):r.save_script()
        with open(p,encoding='utf8') as f:before=json.load(f)
        self.assertNotIn('preferences',before);r.vars['name'].set('chỉnh mới');self.update();r.after(750,r.quit);r.mainloop()
        with open(p,encoding='utf8') as f:self.assertEqual(json.load(f),before)
        self.assertTrue(r.dirty)
    def test_open_does_not_change_defaults_or_overwrite_script(self):
        p=self.base/'old.json';original={'version':1,'flows':[], 'preferences':{'condition':{'stable':999}}}
        with open(p,'w',encoding='utf8') as f:json.dump(original,f)
        with patch.object(self.app.filedialog,'askopenfilename',return_value=str(p)),patch.object(self.app.messagebox,'askyesno') as ask:
            self.root.load_script();self.update();ask.assert_not_called()
        self.assertNotIn('stable',self.root.preferences['condition']);self.root.add_flow();self.update()
        with open(p,encoding='utf8') as f:self.assertEqual(json.load(f),original)
    def test_no_run_mode_and_startup_prompt(self):
        self.assertFalse(hasattr(self.root,'dry'));self.assertNotIn('thử',self.root.start_button.cget('text').lower())
    def test_invalid_field_blocks_switch_and_preserves_value(self):
        self.root.add_flow();self.update();self.root.add_condition();self.update();r=self.root
        flow=r.selected[1]['id'];cond=r.selected[2]['id'];r.vars['stable'].set('');self.update()
        with patch.object(self.app.messagebox,'showerror'):r.tree.selection_set(flow);self.update()
        self.assertEqual(r.selected[2]['id'],cond);self.assertEqual(r.selected[2]['stable'],250)
    def test_reserved_preferences_cannot_be_overwritten_as_script(self):
        r=self.root;r.add_flow();self.update();path=str(self.base/'settings.json')
        with patch.object(self.app.filedialog,'asksaveasfilename',return_value=path),patch.object(self.app.messagebox,'showerror') as err:r.save_script();err.assert_called_once()
        self.assertFalse(os.path.exists(path))
    def test_priority_hotkeys_edge_trigger(self):
        r=self.root
        with patch.object(self.app.win,'f6_down',return_value=True),patch.object(self.app.win,'f7_down',return_value=False),patch.object(self.app.win,'f8_down',return_value=False),patch.object(r,'start') as start:
            r.after_cancel(r.tick_job);r.tick();r.after_cancel(r.tick_job);r.tick();self.assertEqual(start.call_count,1)


    def test_new_checkboxes_save_defaults_and_restore(self):
        r=self.root;r.add_flow();self.update();r.add_condition();self.update()
        c=r.selected[2];self.assertFalse(c['unlimited']);self.assertFalse(c['confirm_activation'])
        r.vars['maximum'].set('7');r.vars['unlimited'].set(True);r.vars['confirm_activation'].set(True);self.update()
        self.assertTrue(c['unlimited']);self.assertTrue(c['confirm_activation']);self.assertEqual(c['maximum'],7)
        self.assertIn('disabled',r.field_widgets['maximum'][1].state())
        r.after(750,r.quit);r.mainloop();self.restart()
        r=self.root;r.add_flow();self.update();r.add_condition();self.update()
        self.assertTrue(r.selected[2]['unlimited']);self.assertTrue(r.selected[2]['confirm_activation']);self.assertEqual(r.selected[2]['maximum'],7)
        r.vars['unlimited'].set(False);self.update();self.assertNotIn('disabled',r.field_widgets['maximum'][1].state())

    def test_start_is_immediate_and_refuses_app_window(self):
        r=self.root
        with patch.object(self.app.engine,'validate',return_value=['rule']),patch.object(self.app.win,'foreground',return_value=11),patch.object(self.app.win,'foreground_is_other_process',return_value=False):
            r.start();self.assertFalse(r.pending);self.assertIn('nhấn F6',r.status.get());self.assertIsNone(r.engine)
        class FakeEngine:
            def __init__(self,rules,hwnd,dry,report):self.rules=rules;self.target=hwnd;self.started=False
            def start(self):self.started=True
            def alive(self):return False
        with patch.object(self.app.engine,'validate',return_value=['rule']),patch.object(self.app.engine,'Engine',FakeEngine),patch.object(self.app.win,'foreground',return_value=22),patch.object(self.app.win,'foreground_is_other_process',return_value=True),patch.object(self.app.win,'window_title',return_value='target'):
            r.start();self.assertTrue(r.engine.started);self.assertEqual(r.engine.target,22);self.assertFalse(r.pending)

    def test_global_mode_hides_loop_fields_and_restores_values(self):
        r=self.root;r.add_flow();self.update();r.add_condition();self.update()
        c=r.selected[2];r.vars['release_stable'].set('888');r.vars['mode'].set('Lặp');r.vars['cool'].set('1234');r.vars['maximum'].set('8');r.vars['unlimited'].set(True);self.update()
        keys=('release_stable','mode','cool','maximum','unlimited')
        before={k:c[k] for k in keys}
        r.script_mode_var.set('Một lần');r.change_script_mode();self.update()
        self.assertEqual(r.script_mode,'Một lần');self.assertFalse(any(k in r.vars for k in keys));self.assertIn('confirm_activation',r.vars)
        self.assertEqual({k:c[k] for k in keys},before)
        r.script_mode_var.set('Lặp lại');r.change_script_mode();self.update()
        self.assertTrue(all(k in r.vars for k in keys));self.assertEqual({k:c[k] for k in keys},before);self.assertIn('disabled',r.field_widgets['maximum'][1].state())
    def test_global_mode_saves_loads_and_old_script_defaults_loop(self):
        r=self.root;r.add_flow();self.update();r.add_condition();self.update();r.script_mode_var.set('Một lần');r.change_script_mode()
        path=self.base/'one.json'
        with patch.object(self.app.filedialog,'asksaveasfilename',return_value=str(path)):r.save_script()
        with open(path,encoding='utf8') as f:data=json.load(f)
        self.assertEqual(data['script_mode'],'Một lần');self.assertIn('mode',data['flows'][0]['conditions'][0])
        r.new_script();self.assertEqual(r.script_mode,'Lặp lại')
        with patch.object(self.app.filedialog,'askopenfilename',return_value=str(path)):r.load_script()
        self.assertEqual(r.script_mode,'Một lần');self.assertEqual(r.script_mode_var.get(),'Một lần')
        data.pop('script_mode');old=self.base/'old-mode.json'
        with open(old,'w',encoding='utf8') as f:json.dump(data,f)
        with patch.object(self.app.filedialog,'askopenfilename',return_value=str(old)):r.load_script()
        self.assertEqual(r.script_mode,'Lặp lại')
    def test_mode_switch_with_invalid_field_does_not_lose_edit(self):
        r=self.root;r.add_flow();self.update();r.add_condition();self.update();r.vars['stable'].set('')
        r.script_mode_var.set('Một lần')
        with patch.object(self.app.messagebox,'showerror'):r.change_script_mode()
        self.assertEqual(r.script_mode,'Lặp lại');self.assertEqual(r.script_mode_var.get(),'Lặp lại');self.assertEqual(r.vars['stable'].get(),'')
    def test_single_mode_start_uses_separate_engine(self):
        r=self.root;r.script_mode_var.set('Một lần');r.change_script_mode()
        class FakeEngine:
            def __init__(self,rules,hwnd,dry,report):self.rules=rules;self.target=hwnd;self.started=False
            def start(self):self.started=True
            def alive(self):return False
        with patch.object(self.app.once_engine,'validate',return_value=[['one']]) as v,patch.object(self.app.engine,'validate') as old,patch.object(self.app.once_engine,'OnceEngine',FakeEngine),patch.object(self.app.win,'foreground',return_value=22),patch.object(self.app.win,'foreground_is_other_process',return_value=True),patch.object(self.app.win,'window_title',return_value='target'):
            r.start();self.assertTrue(r.engine.started);self.assertEqual(r.engine.rules,[['one']]);v.assert_called_once();old.assert_not_called()

    def test_confirm_checkbox_does_not_overlap_fields_in_both_modes(self):
        import tkinter.ttk as ttk
        r=self.root;r.add_flow();self.update();r.add_condition();self.update()
        for mode in ('Một lần','Lặp lại'):
            r.script_mode_var.set(mode);r.change_script_mode();self.update()
            last='stable' if mode=='Một lần' else 'maximum'
            label,entry=r.field_widgets[last];form=label.master
            widgets=[w for w in form.winfo_children() if isinstance(w,ttk.Checkbutton) and w.cget('text')=='Xác nhận đã kích hoạt']
            self.assertEqual(len(widgets),1,mode);check=widgets[0]
            self.assertGreater(check.winfo_y(),label.winfo_y()+label.winfo_height()-1,mode)
            self.assertGreater(check.winfo_y(),entry.winfo_y()+entry.winfo_height()-1,mode)
            self.assertEqual('stability_window' in r.vars,mode=='Lặp lại')
            r.vars['confirm_activation'].set(True);self.assertTrue(r.selected[2]['confirm_activation'])
    def test_search_window_hidden_in_once_but_preserved_in_script(self):
        r=self.root;r.add_flow();self.update();r.add_condition();self.update();r.vars['stability_window'].set('3456');self.update()
        r.script_mode_var.set('Một lần');r.change_script_mode();self.update()
        self.assertNotIn('stability_window',r.vars);self.assertIn('stable',r.vars)
        self.assertEqual(r.selected[2]['stability_window'],3456)
        payload=r.script_payload();self.assertEqual(payload['flows'][0]['conditions'][0]['stability_window'],3456)
        r.script_mode_var.set('Lặp lại');r.change_script_mode();self.update()
        self.assertEqual(r.vars['stability_window'].get(),'3456')

if __name__=='__main__':unittest.main()
