"""Ordered rule passes with live recognition and one serialized action executor."""
import threading
import copy
import time
import numpy as np
import mss
import vision
import windows_input as win


def validate(script):
    rules = []
    if not script: raise ValueError('Script chưa có luồng nào.')
    for flow in script:
        if not flow.get('conditions'): raise ValueError(f"Luồng {flow['name']} chưa có điều kiện.")
        for cond in flow['conditions']:
            title = f"{flow['name']} / {cond['name']}"
            if cond.get('template') is None or cond.get('mask') is None or not cond.get('region'):
                raise ValueError(title + ': cần chọn ảnh mẫu và mặt nạ.')
            if np.count_nonzero(cond['mask']) < 10: raise ValueError(title + ': mặt nạ quá nhỏ.')
            if cond['mask'].shape != cond['template'].shape[:2]: raise ValueError(title + ': mặt nạ không khớp ảnh.')
            if not 0 <= cond['sim'] <= 1 or not 0 <= cond['bright'] <= 1 or not 0 <= cond.get('color_sim',0.) <= 1: raise ValueError(title + ': ngưỡng phải trong khoảng 0–1.')
            if not 0 <= cond['stable'] <= 30000 or not 200 <= cond['cool'] <= 3600000 or (not cond.get('unlimited',False) and not 1 <= cond['maximum'] <= 10000):
                raise ValueError(title + ': ổn định 0–30000 ms, nghỉ 200–3600000 ms, tối đa 1–10000 lần.')
            window=cond.get('stability_window',max(2000,cond['stable']+500))
            if not isinstance(window,int) or not 1 <= window <= 60000:
                raise ValueError(title + ': thời gian xét ổn định tối đa phải từ 1–60000 ms.')
            if window < cond['stable']:
                raise ValueError(title + ': thời gian xét tối đa không được nhỏ hơn thời gian ổn định ít nhất.')
            if not isinstance(cond.get('release_stable', 500), int) or not 0 <= cond.get('release_stable', 500) <= 30000:
                raise ValueError(title + ': không đạt ổn định để chạy lại phải từ 0–30000 ms.')
            if not isinstance(cond.get('unlimited',False),bool) or not isinstance(cond.get('confirm_activation',False),bool):
                raise ValueError(title + ': các tích chọn phải là giá trị đúng/sai.')
            if cond['mode'] not in ('Một lần', 'Lặp'): raise ValueError(title + ': chế độ không hợp lệ.')
            if not cond['actions']: raise ValueError(title + ': chưa có thao tác.')
            groups = {}
            for a in cond['actions']:
                if not 1 <= a['order'] <= 999 or not 10 <= a['hold'] <= 5000:
                    raise ValueError(title + ': thứ tự 1–999 và thời gian giữ 10–5000 ms.')
                if not 1 <= a.get('repeat', 1) <= 100 or not 0 <= a.get('interval', 200) <= 60000:
                    raise ValueError(title + ': mỗi thao tác lặp 1–100 lần, khoảng nghỉ 0–60000 ms.')
                if not isinstance(a.get('after_delay', 0), int) or not 0 <= a.get('after_delay', 0) <= 60000:
                    raise ValueError(title + ': chờ sau thao tác phải từ 0–60000 ms.')
                if a['type'] not in ('Phím', 'Chuột trái', 'Chuột phải'): raise ValueError(title + ': loại thao tác không hợp lệ.')
                if a['type'] != 'Phím' and a.get('mouse_api', 'SendInput') not in ('SendInput', 'mouse_event'):
                    raise ValueError(title + ': API chuột không hợp lệ.')
                if a['type'] != 'Phím' and a.get('mouse_mode', 'Đến tọa độ') not in ('Đến tọa độ', 'Nhấn tại con trỏ hiện tại', 'Tọa độ; nếu lỗi nhấn tại chỗ'):
                    raise ValueError(title + ': chế độ vị trí chuột không hợp lệ.')
                if a['type'] == 'Phím':
                    win.parse_chord(a['key'])
                groups.setdefault(a['order'], []).append(a)
            if cond.get('confirm_activation',False) and len(groups[min(groups)]) != 1:
                raise ValueError(title + ': khi bật xác nhận, nhóm thao tác đầu tiên phải chỉ có một thao tác.')
            for number, group in groups.items():
                if sum(a['type'] != 'Phím' for a in group) > 1:
                    raise ValueError(f'{title}: nhóm {number} có nhiều hơn một thao tác chuột; mỗi nhóm chỉ có một con trỏ.')
                keys = [vk for a in group if a['type'] == 'Phím' for vk in win.parse_chord(a['key'])]
                if len(keys) != len(set(keys)): raise ValueError(f'{title}: nhóm {number} có phím trùng nhau.')
            rules.append((flow['name'], cond))
    return rules


def group_duration(actions):
    return max((a['hold']*a.get('repeat', 1) + a.get('interval', 200)*(a.get('repeat', 1)-1) + a.get('after_delay', 0))/1000 for a in actions)


def diagnostic_time():
    # Capture at the worker, not when Tk drains its message queue.
    now=time.time()
    return time.strftime('%H:%M:%S',time.localtime(now))+f'.{int((now%1)*1000):03d}'

def action_name(a):
    return f"phím {a['key']}" if a['type']=='Phím' else a['type']

def release_key_chord(slot):
    """Try to release every pressed key, even if one release fails."""
    failed=[];first_error=None
    for vk in reversed(slot['value']):
        try:win.key_up(vk)
        except Exception as e:
            failed.append(vk)
            if first_error is None:first_error=e
    slot['value']=list(reversed(failed))
    if first_error is not None:raise first_error


def run_group(actions, target, stop, report=lambda message: None, pause=None, action_event=lambda event, action, repeat, timestamp: None):
    """Pause prevents new presses; any ongoing hold finishes and is released.
    Resumption does not repeat completed presses; intervals are frozen while paused.
    """
    pause = pause or threading.Event()
    schedule = [{'action': a, 'remaining': a.get('repeat', 1), 'held': False,
                 'deadline': 0., 'released_at': 0., 'value': None, 'post_waiting': False} for a in actions]
    pause_started = None
    try:
        while any(slot['remaining'] or slot['held'] or slot['post_waiting'] for slot in schedule):
            if stop.is_set(): return False
            foreground=win.foreground();focused = foreground == target
            if not focused and (not pause.is_set() or any(slot['held'] for slot in schedule)):
                report(f'FOCUS [{diagnostic_time()}] mục tiêu: {win.describe_window(target)} | phía trước: {win.describe_window(foreground)}');return False
            now = time.monotonic()
            if pause.is_set() and pause_started is None: pause_started = now
            elif not pause.is_set() and pause_started is not None:
                for slot in schedule:
                    if not slot['held'] and (slot['remaining'] or slot['post_waiting']) and slot['deadline']:
                        slot['deadline'] += max(0., now - max(pause_started, slot['released_at']))
                pause_started = None
            for slot in schedule:
                if slot['held'] and now >= slot['deadline']:
                    a = slot['action']
                    if a['type'] == 'Phím': release_key_chord(slot)
                    else: win.mouse_up(a['type'], a.get('mouse_api', 'SendInput'))
                    slot['held'] = False
                    action_event('NHẢ',a,a.get('repeat',1)-slot['remaining'],diagnostic_time())
                    report(f'NHẢ [{diagnostic_time()}] {action_name(a)} · API đã gọi thành công')
                    slot['released_at'] = time.monotonic()
                    if slot['remaining']:
                        slot['deadline'] = slot['released_at'] + a.get('interval', 200)/1000
                    else:
                        slot['post_waiting'] = a.get('after_delay', 0) > 0
                        slot['deadline'] = slot['released_at'] + a.get('after_delay', 0)/1000
            if not pause.is_set():
                for slot in schedule:
                    if slot['post_waiting'] and time.monotonic() >= slot['deadline']:
                        slot['post_waiting'] = False
                for slot in schedule:
                    if stop.is_set(): return False
                    foreground=win.foreground()
                    if foreground != target:
                        report(f'FOCUS [{diagnostic_time()}] mục tiêu: {win.describe_window(target)} | phía trước: {win.describe_window(foreground)}');return False
                    if pause.is_set(): break
                    if not slot['held'] and slot['remaining'] and time.monotonic() >= slot['deadline']:
                        a = slot['action']
                        if a['type'] == 'Phím':
                            codes=win.parse_chord(a['key']);slot['value']=[];slot['held']=True
                            for key_index,code in enumerate(codes):
                                if stop.is_set():return False
                                if key_index:
                                    foreground=win.foreground()
                                    if foreground!=target:
                                        report(f'FOCUS [{diagnostic_time()}] mục tiêu: {win.describe_window(target)} | phía trước: {win.describe_window(foreground)}');return False
                                # Include the attempted key in emergency release even if SendInput fails.
                                slot['value'].append(code);win.key_down(code)
                        else:
                            method = win.mouse_down(a['type'], a['x'], a['y'], target, stop, a.get('mouse_mode', 'Đến tọa độ'), a.get('mouse_api', 'SendInput'))
                        slot['held'] = True; slot['remaining'] -= 1
                        slot['deadline'] = time.monotonic() + a['hold']/1000
                        action_event('NHẤN',a,a.get('repeat',1)-slot['remaining'],diagnostic_time())
                        report(f'NHẤN [{diagnostic_time()}] {action_name(a)} · giữ {a["hold"]} ms · lần {a.get("repeat",1)-slot["remaining"]}/{a.get("repeat",1)}')
                        if a['type'] != 'Phím' and method != 'SetCursorPos': report(f"  Chuột: {method}.")
            if pause.is_set():
                active_deadlines = [slot['deadline'] for slot in schedule if slot['held']]
                wait = min(.02, max(0., min(active_deadlines)-time.monotonic())) if active_deadlines else .05
                stop.wait(wait)
            else:
                deadlines = [slot['deadline'] for slot in schedule if slot['held'] or slot['remaining'] or slot['post_waiting']]
                if deadlines: stop.wait(min(.02, max(0, min(deadlines)-time.monotonic())))
        return True
    finally:
        for slot in reversed(schedule):
            if slot['held']:
                try:
                    if slot['action']['type'] == 'Phím': release_key_chord(slot)
                    else: win.mouse_up(slot['action']['type'], slot['action'].get('mouse_api', 'SendInput'))
                    action_event('NHẢ KHẨN',slot['action'],slot['action'].get('repeat',1)-slot['remaining'],diagnostic_time())
                    report(f'NHẢ KHẨN [{diagnostic_time()}] {action_name(slot["action"])} · API đã gọi thành công')
                except Exception as e:
                    report('  CẢNH BÁO: không xác nhận được nhả đầu vào: ' + str(e))


def wait_unpaused(stop, pause):
    while pause.is_set() and not stop.is_set(): stop.wait(.05)
    return not stop.is_set()


def wait_dry_group(actions, target, stop, pause=None):
    pause = pause or threading.Event()
    remaining = group_duration(actions)
    previous = time.monotonic()
    while remaining > 0:
        if stop.is_set(): return False
        if not pause.is_set() and win.foreground() != target: return False
        stop.wait(min(.03, max(.001, remaining)))
        now = time.monotonic()
        if not pause.is_set(): remaining -= now-previous
        previous = now
    return not stop.is_set() and (pause.is_set() or win.foreground() == target)


class Engine:
    """One worker evaluates conditions in tree order, advancing after each chain.

    Wrap after the last condition, never store condition jobs, and do not sample
    conditions while an action chain (including after-delays) is running.
    """
    def __init__(self, rules, target, dry, output):
        self.rules, self.target, self.dry, self.output = rules, target, dry, output
        self.stop_event=threading.Event();self.pause_event=threading.Event();self.pause_started=None;self.lock=threading.Lock()
        self.states=[{'since':None,'window_since':None,'window_phase':None,'last_stable_ms':0,'off_since':None,'armed':True,'next':0.,'last_finished':0.,'count':0} for _ in rules]
        self.action_thread=threading.Thread(target=self.execute,daemon=True)
        # No negative logs until an activation; one ordered pass thereafter.
        self.log_failures=False
        self.logged_skips=set()
        self.pass_cursor=0
    def start(self):self.action_thread.start()
    def stop(self):self.stop_event.set()
    def pause(self):
        with self.lock:
            if not self.pause_event.is_set():self.pause_started=time.monotonic();self.pause_event.set()
    def resume(self):
        with self.lock:
            if self.pause_event.is_set():
                now=time.monotonic()
                for state in self.states:
                    if state['next']>self.pause_started:
                        state['next']+=max(0.,now-max(self.pause_started,state['last_finished']))
                    state['since']=None;state['window_since']=None;state['window_phase']=None;state['last_stable_ms']=0;state['off_since']=None
                # Keep the ordered pass position; only restart measurement timers.
                self.pause_event.clear();self.pause_started=None
    def alive(self):return self.action_thread.is_alive()
    def qualifies(self,s,cond):
        image=np.array(s.grab(cond['region']))[:,:,:3]
        similarity,brightness,color=vision.measure(cond['template'],image,cond['mask'])
        return similarity>=cond['sim'] and brightness>=cond['bright'] and color>=cond.get('color_sim',0.),similarity,brightness,color
    def reset_stability(self):
        with self.lock:
            for state in self.states:state['since']=None;state['window_since']=None;state['window_phase']=None;state['last_stable_ms']=0;state['off_since']=None
            # Focus/pause must not silently rewind the ordered pass.
    def scan(self,s):
        """Take one ordered scan. Return the first currently eligible rule index.

        Stability is only credited between observations during scans, not through
        an unobserved running chain or pause. True samples do not enqueue work.
        """
        if self.pause_event.is_set() or win.foreground()!=self.target:
            self.reset_stability();return None, None
        observed=[];statuses=[]
        for idx,(flow_name,cond) in enumerate(self.rules):
            if self.stop_event.is_set() or self.pause_event.is_set() or win.foreground()!=self.target:
                self.reset_stability();return None,None
            good,sim,bright,color=self.qualifies(s,cond);observed.append((idx,good,time.monotonic(),sim,bright,color,diagnostic_time()))
            statuses.append(f"{flow_name}/{cond['name']}: {sim:.3f}, màu {color:.3f}, sáng {bright:.2f}, {'ĐẠT' if good else 'chưa đạt'}")
        if self.stop_event.is_set() or self.pause_event.is_set() or win.foreground()!=self.target:
            self.reset_stability();return None,None
        chosen=None; blocker=None; rearmed=[]; check_rows=[]; timeouts=[]; negative_logs=[]
        with self.lock:
            if self.pause_event.is_set():
                for state in self.states:state['since']=None;state['window_since']=None;state['window_phase']=None;state['last_stable_ms']=0;state['off_since']=None
                return None,None
            cursor=self.pass_cursor
            for idx,good,now,sim,bright,color,observed_at in observed:
                flow_name,cond=self.rules[idx];state=self.states[idx]
                window_ms=cond.get('stability_window',max(2000,cond['stable']+500))
                if not good:
                    state['since']=None
                    if not state['armed']:
                        if state['off_since'] is None:state['off_since']=now
                        if (now-state['off_since'])*1000>=cond.get('release_stable',500):
                            state['armed']=True;state['off_since']=None
                            rearmed.append((flow_name,cond['name'],cond.get('release_stable',500)))
                else:state['off_since']=None
                allowed=state['armed'] if cond['mode']=='Một lần' else now>=state['next']
                limit_reached=not cond.get('unlimited',False) and state['count']>=cond['maximum']
                available=allowed and not limit_reached
                reasons=[]
                if not good:
                    if sim<cond['sim']:reasons.append(f"độ giống dưới ngưỡng {cond['sim']:.4f}")
                    if color<cond.get('color_sim',0.):reasons.append(f"độ giống màu dưới ngưỡng {cond.get('color_sim',0.):.4f}")
                    if bright<cond['bright']:reasons.append(f"độ sáng dưới ngưỡng {cond['bright']:.4f}")
                    if not reasons:reasons.append('không đạt kiểm tra nhận diện')
                if limit_reached:reasons.append(f"đã đạt số lần tối đa {cond['maximum']}")
                if not allowed:
                    if cond['mode']=='Một lần':reasons.append(f"Một lần chưa được mở lại: cần quan sát không đạt đủ {cond.get('release_stable',500)} ms")
                    else:reasons.append(f"đang nghỉ sau chuỗi, còn khoảng {max(0,int((state['next']-now)*1000))} ms")
                is_selected=False
                if idx<cursor:
                    state['since']=None;state['window_since']=None;state['window_phase']=None;state['last_stable_ms']=0
                    reasons.append('đã bỏ qua trong lượt xét này')
                elif blocker is not None or chosen is not None:
                    state['since']=None;state['window_since']=None;state['window_phase']=None;state['last_stable_ms']=0
                    prior=blocker if blocker is not None else chosen
                    pf,pc=self.rules[prior];reasons.append(f"chờ ưu tiên {pf} / {pc['name']}")
                elif not available:
                    state['since']=None;state['window_since']=None;state['window_phase']=None;state['last_stable_ms']=0
                    # This is an immediate eligibility skip, not an expired image
                    # search; log once per post-activation pass without delaying it.
                    if self.log_failures and idx not in self.logged_skips:
                        metrics=f"Độ ổn định: chưa xét/{window_ms}, Độ giống: {sim:.4f}/{cond['sim']:.4f}, Độ giống màu: {color:.4f}/{cond.get('color_sim',0.):.4f}, Độ sáng: {bright:.4f}/{cond['bright']:.4f}"
                        negative_logs.append(f"{observed_at}: {flow_name} / {cond['name']}: Bỏ qua ({'; '.join(reasons)}; {metrics})")
                        self.logged_skips.add(idx)
                else:
                    if state['window_since'] is None:
                        state['window_since']=now;state['window_phase']='search';state['since']=None;state['last_stable_ms']=0
                    phase=state['window_phase'];started=state['window_since']
                    expired=(now-started)*1000 > window_ms
                    if expired:
                        stable_ms=state['last_stable_ms'] if phase=='stable' else 0
                        if self.log_failures:
                            metrics=f"Độ ổn định: {stable_ms}/{window_ms}, Độ giống: {sim:.4f}/{cond['sim']:.4f}, Độ giống màu: {color:.4f}/{cond.get('color_sim',0.):.4f}, Độ sáng: {bright:.4f}/{cond['bright']:.4f}"
                            negative_logs.append(f"{observed_at}: {flow_name} / {cond['name']}: Chưa kích hoạt ({metrics})")
                        reasons.append(f'hết {window_ms} ms '+('tìm hình' if phase=='search' else 'xét ổn định'))
                        timeouts.append((flow_name,cond['name'],window_ms,phase))
                        state['since']=None;state['window_since']=None;state['window_phase']=None;state['last_stable_ms']=0
                    else:
                        if phase=='search' and good:
                            state['window_phase']='stable';state['window_since']=now;state['since']=now;state['last_stable_ms']=0;phase='stable'
                        if phase=='search':reasons.append(f"đang tìm hình, tối đa {window_ms} ms")
                        elif good:
                            if state['since'] is None:state['since']=now
                            elapsed=(now-state['since'])*1000
                            state['last_stable_ms']=min(window_ms,int(max(0,elapsed)))
                            if elapsed>=cond['stable']:chosen=idx;is_selected=True
                            else:reasons.append(f"đang chờ ổn định {int(max(0,elapsed))}/{cond['stable']} ms")
                        else:
                            state['last_stable_ms']=0
                            reasons.append('đang chờ hình khớp lại trong thời gian xét')
                        if not is_selected:blocker=idx
                check_rows.append((idx,observed_at,sim,bright,color,is_selected,'; '.join(reasons)))
            if chosen is not None:self.pass_cursor=chosen
            elif blocker is not None:self.pass_cursor=blocker
            else:
                # The entire pass has completed without an activation.
                self.pass_cursor=0;self.log_failures=False
        for text in negative_logs:self.output('condition',text)
        for flow_name,condition_name,window_ms,phase in timeouts:
            self.output('log',f"CHẨN ĐOÁN [{diagnostic_time()}] {flow_name}/{condition_name}: hết {window_ms} ms {'tìm hình' if phase=='search' else 'xét ổn định'}, bỏ qua lượt này.")
        if chosen is not None:
            details=' | '.join(f"{self.rules[idx][0]}/{self.rules[idx][1]['name']}: giống {sim:.4f}, màu {color:.4f}, sáng {bright:.4f}, {reason or 'đủ điều kiện'}" for idx,_,sim,bright,color,_,reason in check_rows)
            self.output('log',f"CHẨN ĐOÁN [{diagnostic_time()}] quét trước khi chọn {self.rules[chosen][0]}/{self.rules[chosen][1]['name']}: "+details)
        for flow_name,condition_name,ms in rearmed:
            self.output('log',f'{flow_name} / {condition_name}: đã không đạt ổn định {ms} ms; sẵn sàng kích hoạt lại khi đạt.')
        return chosen,' | '.join(statuses)
    def wait_confirmation_gap(self, s, cond, flow_name, delay_ms):
        """Poll after release for a changed condition; freeze gap while paused."""
        remaining=delay_ms/1000.;last=time.monotonic()
        while not self.stop_event.is_set():
            if self.pause_event.is_set():
                if not wait_unpaused(self.stop_event,self.pause_event):return 'stopped'
                last=time.monotonic()
            foreground=win.foreground()
            if foreground!=self.target:
                self.output('log',f"FOCUS [{diagnostic_time()}] xác nhận {flow_name}/{cond['name']}: mục tiêu {win.describe_window(self.target)} | phía trước {win.describe_window(foreground)}")
                return 'stopped'
            good,similarity,brightness,color=self.qualifies(s,cond)
            if self.stop_event.is_set():return 'stopped'
            if self.pause_event.is_set():continue
            if win.foreground()!=self.target:
                self.output('log',f"FOCUS [{diagnostic_time()}] mất cửa sổ đích khi đang xác nhận {flow_name}/{cond['name']}.")
                return 'stopped'
            if not good:
                self.output('condition',f"{diagnostic_time()}: {flow_name} / {cond['name']}: Xác nhận dấu hiệu không còn đạt (Độ giống: {similarity:.4f}/{cond['sim']:.4f}, Độ giống màu: {color:.4f}/{cond.get('color_sim',0.):.4f}, Độ sáng: {brightness:.4f}/{cond['bright']:.4f})")
                return 'changed'
            now=time.monotonic();remaining-=max(0.,now-last);last=now
            if remaining<=0:return 'repeat'
            self.stop_event.wait(min(.025,remaining))
        return 'stopped'
    def wait_after_confirm(self, delay_ms, flow_name, cond):
        """Post-action delay freezes under pause and stops on focus loss/F8."""
        remaining=delay_ms/1000.;last=time.monotonic()
        while remaining>0 and not self.stop_event.is_set():
            if self.pause_event.is_set():
                if not wait_unpaused(self.stop_event,self.pause_event):return False
                last=time.monotonic()
            foreground=win.foreground()
            if foreground!=self.target:
                self.output('log',f"FOCUS [{diagnostic_time()}] chờ sau xác nhận {flow_name}/{cond['name']}: mục tiêu {win.describe_window(self.target)} | phía trước {win.describe_window(foreground)}")
                return False
            now=time.monotonic();remaining-=max(0.,now-last);last=now
            if remaining>0:self.stop_event.wait(min(.025,remaining))
        return not self.stop_event.is_set()
    def run_confirmation(self, s, cond, flow_name, order, action, action_log):
        """Repeat the first configured action until its triggering condition is false."""
        single=copy.deepcopy(action);single['repeat']=1;single['after_delay']=0;attempt=0
        self.output('condition',f"{diagnostic_time()}: {flow_name} / {cond['name']}: Bắt đầu xác nhận; lặp thao tác đầu tiên, nghỉ 150 ms sau khi nhả.")
        while not self.stop_event.is_set():
            if not wait_unpaused(self.stop_event,self.pause_event):return False
            if win.foreground()!=self.target:return False
            attempt+=1
            if self.dry:
                done=wait_dry_group([single],self.target,self.stop_event,self.pause_event)
            else:
                done=run_group([single],self.target,self.stop_event,
                    lambda msg:self.output('log',f"  [{flow_name}/{cond['name']} · nhóm {order} · xác nhận] "+msg),
                    self.pause_event,lambda event,a,repeat,ts:action_log(event,a,repeat,ts,attempt))
            if not done:return False
            result=self.wait_confirmation_gap(s,cond,flow_name,150)
            if result=='stopped':return False
            if result=='changed':
                delay=action.get('after_delay',0)
                return self.wait_after_confirm(delay,flow_name,cond)
        return False

    def execute(self):
        last_status=0.
        try:
            with mss.mss() as s:
                while not self.stop_event.is_set():
                    if not wait_unpaused(self.stop_event,self.pause_event):break
                    idx,status=self.scan(s)
                    now=time.monotonic()
                    if now-last_status>=.5:
                        self.output('status',status if status is not None else 'Tạm dừng: cửa sổ đích không ở phía trước hoặc đang tạm dừng.')
                        last_status=now
                    if idx is None:
                        self.stop_event.wait(.1);continue
                    flow_name,cond=self.rules[idx];state=self.states[idx]
                    # Fresh recheck; a condition that changed during a scan must not run.
                    if self.pause_event.is_set() or self.stop_event.is_set() or win.foreground()!=self.target:
                        self.reset_stability();continue
                    good,similarity,brightness,color=self.qualifies(s,cond)
                    if not good:
                        reasons=[]
                        if similarity < cond['sim']: reasons.append(f"độ giống dưới ngưỡng {cond['sim']:.4f}")
                        if color < cond.get('color_sim',0.): reasons.append(f"độ giống màu dưới ngưỡng {cond.get('color_sim',0.):.4f}")
                        if brightness < cond['bright']: reasons.append(f"độ sáng dưới ngưỡng {cond['bright']:.4f}")
                        if not reasons: reasons.append('không đạt kiểm tra nhận diện')
                        if self.log_failures and idx not in self.logged_skips:
                            self.output('condition',f"{diagnostic_time()}: {flow_name} / {cond['name']}: Bỏ qua (kiểm tra lại không đạt: {'; '.join(reasons)}; Độ ổn định: {state['last_stable_ms']}/{cond.get('stability_window',max(2000,cond['stable']+500))}, Độ giống: {similarity:.4f}/{cond['sim']:.4f}, Độ giống màu: {color:.4f}/{cond.get('color_sim',0.):.4f}, Độ sáng: {brightness:.4f}/{cond['bright']:.4f})")
                            self.logged_skips.add(idx)
                        self.output('log',f"CHẨN ĐOÁN [{diagnostic_time()}] bỏ chọn {flow_name}/{cond['name']}: điều kiện không còn đạt khi kiểm tra lại trước chạy.")
                        with self.lock:
                            state['since']=None;state['window_since']=None;state['window_phase']=None;state['last_stable_ms']=0;state['off_since']=None
                            if idx+1<len(self.rules):self.pass_cursor=idx+1
                            else:self.pass_cursor=0;self.log_failures=False
                        continue
                    if self.pause_event.is_set() or self.stop_event.is_set() or win.foreground()!=self.target:
                        self.reset_stability();continue
                    with self.lock:
                        if self.pause_event.is_set():continue
                        if cond['mode']=='Một lần':state['armed']=False
                    self.log_failures=True;self.logged_skips.clear()
                    self.output('condition',f"{diagnostic_time()}: {flow_name} / Kích hoạt {cond['name']} (Độ giống: {similarity:.4f}, Độ giống màu: {color:.4f}/{cond.get('color_sim',0.):.4f}, Độ sáng: {brightness:.4f})")
                    self.output('log',f"{'[THỬ] ' if self.dry else ''}Chạy {flow_name} / {cond['name']}.")
                    groups={}
                    for action in cond['actions']:groups.setdefault(action['order'],[]).append(action)
                    def action_log(event,action,repeat,timestamp,confirm_attempt=None):
                        label = action['key'] if action['type']=='Phím' else (action['type']+' · tại chỗ' if action.get('mouse_mode')=='Nhấn tại con trỏ hiện tại' else f"{action['type']} ({action['x']}, {action['y']})")
                        extra=f' · xác nhận lần {confirm_attempt}' if confirm_attempt is not None else f" · lần {repeat}/{action.get('repeat',1)}"
                        self.output('action',f"{timestamp}: {flow_name} / {cond['name']} / Thao tác {label} · số thứ tự {action['order']} · {event}{extra}")
                    finished=True
                    for order in sorted(groups):
                        if not wait_unpaused(self.stop_event,self.pause_event):
                            finished=False;break
                        foreground=win.foreground()
                        if foreground!=self.target:
                            self.output('log',f"FOCUS [{diagnostic_time()}] {flow_name}/{cond['name']} trước nhóm {order}: mục tiêu {win.describe_window(self.target)} | phía trước {win.describe_window(foreground)}")
                            finished=False;break
                        actions=groups[order]
                        self.output('log',f"  Bắt đầu nhóm {order}: " + ', '.join((a['key'] if a['type']=='Phím' else (f"{a['type']} tại con trỏ hiện tại [{a.get('mouse_api','SendInput')}]" if a.get('mouse_mode')=='Nhấn tại con trỏ hiện tại' else f"{a['type']} ({a['x']},{a['y']})")) + f" ×{a.get('repeat',1)}" + (f" · chờ sau {a.get('after_delay',0)} ms" if a.get('after_delay',0) else '') for a in actions))
                        if cond.get('confirm_activation',False) and order==min(groups):
                            finished=self.run_confirmation(s,cond,flow_name,order,actions[0],action_log)
                        elif self.dry:
                            finished=wait_dry_group(actions,self.target,self.stop_event,self.pause_event)
                            if finished:self.output('log',f"  Nhóm {order}: mô phỏng xong, không gửi đầu vào.")
                        else:
                            finished=run_group(actions,self.target,self.stop_event,lambda msg:self.output('log',f"  [{flow_name}/{cond['name']} · nhóm {order}] "+msg),self.pause_event,action_log)
                            if finished:
                                self.output('log',f"  CHẨN ĐOÁN [{diagnostic_time()}] {flow_name}/{cond['name']} nhóm {order}: các lần nhấn, nhả và chờ đã kết thúc.")
                                if any(a['type']!='Phím' and a.get('mouse_api','SendInput')=='mouse_event' for a in actions):
                                    self.output('log',f"  Nhóm {order}: đã gọi mouse_event; API này không xác nhận kết quả hay ứng dụng đích có phản ứng.")
                                else:self.output('log',f"  Nhóm {order}: Windows đã chấp nhận lệnh gửi; không xác nhận được ứng dụng đích có phản ứng.")
                        if not finished:break
                    with self.lock:
                        for st in self.states:st['since']=None;st['window_since']=None;st['window_phase']=None;st['last_stable_ms']=0;st['off_since']=None
                        # Continue after this condition; wrapping only after the last.
                        self.pass_cursor=(idx+1) % len(self.rules)
                        state['last_finished']=time.monotonic()
                        state['next']=state['last_finished']+cond['cool']/1000
                        if finished:state['count']+=1
                    if finished:
                        next_step='đã hết lượt, xét lại từ đầu' if idx+1==len(self.rules) else 'xét tiếp điều kiện kế tiếp'
                        self.output('log',f"Hoàn thành {flow_name} / {cond['name']}; {next_step}.")
                    else:
                        reason='đã yêu cầu dừng' if self.stop_event.is_set() else 'mất cửa sổ đích hoặc lỗi an toàn khác; xem dòng FOCUS nếu có'
                        self.output('log',f'  Chuỗi bị ngắt: {reason}; đã cố nhả các nút đang giữ.')
        except Exception as e:
            self.output('log','LỖI THEO DÕI/THAO TÁC: '+str(e)+' | Đã dừng để tránh nhấn sai.');self.stop_event.set()
        finally:self.output('thread_done','Theo dõi và thao tác đã dừng.')
