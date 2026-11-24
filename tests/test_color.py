import json,threading,unittest
from unittest.mock import patch
import numpy as np
import app,engine,form_model,vision
from test_queue_execution import action

class FakeImage:
    def __init__(self,image):self.image=image
    def __enter__(self):return self
    def __exit__(self,*a):pass
    def grab(self,_):return self.image

def condition():
    sample=np.full((4,4,3),(0,0,255),dtype=np.uint8)
    return dict(id='x',name='C',template=sample,mask=np.ones((4,4),dtype=np.uint8),region={'left':0,'top':0,'width':4,'height':4},sim=.9,bright=0.,color_sim=.8,stable=0,stability_window=500,release_stable=500,mode='Một lần',cool=200,maximum=1,actions=[action('1',1)])

def screen(bgr):
    arr=np.zeros((4,4,4),dtype=np.uint8);arr[:,:,:3]=bgr;arr[:,:,3]=255;return arr

class ColorTests(unittest.TestCase):
    def test_exact_rgb_and_brightness_sensitivity(self):
        c=condition();a=c['template'];mask=c['mask'];b=np.full_like(a,(0,0,155));sim,brightness,col=vision.measure(a,b,mask)
        self.assertAlmostEqual(sim,.94874,places=4);self.assertAlmostEqual(col,1-100/255,places=5)
        self.assertEqual(vision.measure(a,a,mask)[2],1.)
    def test_all_channels_and_mask(self):
        a=np.zeros((4,4,3),dtype=np.uint8);b=a.copy();mask=np.zeros((4,4),dtype=np.uint8);mask[0,0]=1
        b[1,1]=(255,255,255);self.assertEqual(vision.measure(a,b,mask)[2],1.)
        for px in ((255,0,0),(0,255,0),(0,0,255),(255,255,255)):
            b[0,0]=px;self.assertAlmostEqual(vision.measure(a,b,mask)[2],0.)
    def test_color_threshold_is_separate_and_legacy_zero_disabled(self):
        c=condition();w=engine.Engine([('L',c)],7,False,lambda *a:None)
        good,sim,bright,col=w.qualifies(FakeImage(screen((0,0,155))),c)
        self.assertFalse(good);self.assertGreater(sim,.9);self.assertLess(col,.8)
        c['color_sim']=0.;self.assertTrue(w.qualifies(FakeImage(screen((0,0,155))),c)[0])
        c['color_sim']=.6;self.assertTrue(w.qualifies(FakeImage(screen((0,0,155))),c)[0])
        c['bright']=.9;self.assertFalse(w.qualifies(FakeImage(screen((0,0,155))),c)[0])
    def test_timeout_log_includes_color_actual_and_threshold(self):
        c=condition();out=[];w=engine.Engine([('L',c)],7,False,lambda k,v:out.append((k,v)));w.log_failures=True
        with patch.object(engine.win,'foreground',return_value=7),patch.object(engine.time,'monotonic',return_value=10):w.scan(FakeImage(screen((0,0,155))))
        with patch.object(engine.win,'foreground',return_value=7),patch.object(engine.time,'monotonic',return_value=10.6):w.scan(FakeImage(screen((0,0,155))))
        line=next(v for k,v in out if k=='condition');self.assertIn('Chưa kích hoạt',line);self.assertIn('Độ giống màu: 0.6078/0.8000',line);self.assertIn('Độ giống: 0.9487/0.9000',line)
    def test_ineligible_skip_also_logs_color(self):
        c=condition();out=[];w=engine.Engine([('L',c)],7,False,lambda k,v:out.append((k,v)));w.log_failures=True;w.states[0]['armed']=False
        with patch.object(engine.win,'foreground',return_value=7):w.scan(FakeImage(screen((0,0,155))))
        line=next(v for k,v in out if k=='condition');self.assertIn('Bỏ qua',line);self.assertIn('Độ giống màu: 0.6078/0.8000',line)
    def test_recheck_rejects_changed_color_and_reports_it(self):
        c=condition();out=[];done=threading.Event();imgs=[screen((0,0,255)),screen((0,0,155))]
        class Images(FakeImage):
            def grab(self,_):return imgs.pop(0) if imgs else screen((0,0,155))
        def output(k,v):
            out.append((k,v))
            if k=='condition' and 'kiểm tra lại không đạt' in v:done.set()
        w=engine.Engine([('L',c)],7,False,output);w.log_failures=True
        with patch.object(engine.mss,'mss',return_value=Images(None)),patch.object(engine.win,'foreground',return_value=7),patch.object(engine.win,'key_down') as down:
            w.start();self.assertTrue(done.wait(2));w.stop();w.action_thread.join(1);down.assert_not_called()
        line=next(v for k,v in out if k=='condition');self.assertIn('độ giống màu dưới ngưỡng 0.8000',line);self.assertIn('Độ giống màu: 0.6078/0.8000',line)
    def test_activation_log_contains_real_color_score(self):
        c=condition();out=[];done=threading.Event()
        def output(k,v):
            out.append((k,v))
            if k=='condition' and 'Kích hoạt' in v:done.set()
        w=engine.Engine([('L',c)],7,False,output)
        with patch.object(engine.mss,'mss',return_value=FakeImage(screen((0,0,255)))),patch.object(engine.win,'foreground',return_value=7),patch.object(engine.win,'key_down'),patch.object(engine.win,'key_up'):
            w.start();self.assertTrue(done.wait(2));w.stop();w.action_thread.join(1)
        line=next(v for k,v in out if k=='condition');self.assertIn('Độ giống màu: 1.0000/0.8000',line)
    def test_old_script_default_and_new_script_persistence(self):
        c=condition();c.pop('color_sim');fs=app.deserialize(app.serialize([{'id':'f','name':'L','conditions':[c]}]))
        self.assertEqual(fs[0]['conditions'][0]['color_sim'],0.)
        fs[0]['conditions'][0]['color_sim']=.8
        self.assertEqual(app.deserialize(app.serialize(fs))[0]['conditions'][0]['color_sim'],.8)
    def test_numeric_validation(self):
        self.assertEqual(form_model.parse_field('condition','color_sim','0.83'),.83)
        for x in ('-0.1','1.1','nan','abc'):
            with self.assertRaises(ValueError):form_model.parse_field('condition','color_sim',x)
        c=condition();c['color_sim']=1.1
        with self.assertRaises(ValueError):engine.validate([{'name':'L','conditions':[c]}])
