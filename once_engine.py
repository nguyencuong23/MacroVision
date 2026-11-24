"""Independent one-pass script runner. Old repeating Engine is left untouched."""
import copy
import time
import mss
import engine
import windows_input as win


def validate(flows):
    """Validate a copy with loop-only condition settings disabled.

    Group by tree position, never by display name (flow names need not be unique).
    Original settings are not modified or saved over.
    """
    snapshot=copy.deepcopy(flows)
    for flow in snapshot:
        for c in flow.get('conditions',[]):
            c.update(mode='Lặp',cool=200,maximum=1,unlimited=False,release_stable=0,stability_window=60000)
    rules=engine.validate(snapshot)
    groups=[];pos=0
    for flow in snapshot:
        n=len(flow['conditions']);groups.append(rules[pos:pos+n]);pos+=n
    return groups


class OnceEngine(engine.Engine):
    def __init__(self,flow_rules,target,dry,output):
        self.flow_rules=flow_rules
        super().__init__([r for flow in flow_rules for r in flow],target,dry,output)
        self.log_failures=False

    def evaluate(self,s,flow_name,cond):
        """Wait indefinitely for a continuously stable match, until stop."""
        since=None;last_status=0
        while not self.stop_event.is_set():
            if self.pause_event.is_set():
                if not engine.wait_unpaused(self.stop_event,self.pause_event):return 'stop',None
                since=None
            if win.foreground()!=self.target:
                since=None
                self.output('status','Tạm dừng: cửa sổ đích không ở phía trước hoặc đang tạm dừng.')
                self.stop_event.wait(.1);continue
            good,sim,bright,color=self.qualifies(s,cond);now=time.monotonic()
            if self.stop_event.is_set():return 'stop',None
            if self.pause_event.is_set() or win.foreground()!=self.target:
                since=None;continue
            if now-last_status>=.5:
                self.output('status',f"{flow_name}/{cond['name']}: {sim:.3f}, màu {color:.3f}, sáng {bright:.2f}, {'ĐẠT' if good else 'chưa đạt'}");last_status=now
            if not good:since=None
            else:
                if since is None:since=now
                if (now-since)*1000>=cond['stable']:
                    if self.pause_event.is_set() or self.stop_event.is_set() or win.foreground()!=self.target:
                        since=None;continue
                    good,sim,bright,color=self.qualifies(s,cond)
                    if self.stop_event.is_set():return 'stop',None
                    if self.pause_event.is_set() or win.foreground()!=self.target:
                        since=None;continue
                    if not good:
                        if self.log_failures:self.output('condition',f"{engine.diagnostic_time()}: {flow_name} / {cond['name']}: Kiểm tra lại không đạt — tiếp tục chờ (Độ giống: {sim:.4f}/{cond['sim']:.4f}, Độ giống màu: {color:.4f}/{cond.get('color_sim',0.):.4f}, Độ sáng: {bright:.4f}/{cond['bright']:.4f})")
                        self.log_failures=False;since=None
                    else:return 'ready',(sim,bright,color)
            self.stop_event.wait(.1)
        return 'stop',None

    def execute(self):
        try:
            with mss.mss() as s:
                for flow_index,flow in enumerate(self.flow_rules):
                    flow_name=flow[0][0]
                    for _,cond in flow:
                        while not self.stop_event.is_set():
                            result,values=self.evaluate(s,flow_name,cond)
                            if result=='stop':return
                            similarity,brightness,color=values
                            self.log_failures=True
                            self.output('condition',f"{engine.diagnostic_time()}: {flow_name} / Kích hoạt {cond['name']} (Độ giống: {similarity:.4f}, Độ giống màu: {color:.4f}/{cond.get('color_sim',0.):.4f}, Độ sáng: {brightness:.4f})")
                            self.output('log',f"Chạy {flow_name} / {cond['name']}.")
                            finished=self.run_chain(s,flow_name,cond)
                            if not finished:
                                self.output('log','Chuỗi bị ngắt: dừng mode Một lần để tránh chạy lại các thao tác đã thực hiện.')
                                return
                            self.output('log',f"Hoàn thành {flow_name} / {cond['name']}; tiếp tục xét script.")
                            break
                        if self.stop_event.is_set():return
                    step="chuyển luồng tiếp theo" if flow_index+1<len(self.flow_rules) else "đã đến luồng cuối"
                    self.output('condition',f"{engine.diagnostic_time()}: {flow_name}: đã hoàn thành tất cả điều kiện, {step}.")
            if not self.stop_event.is_set():
                self.output('condition',f'{engine.diagnostic_time()}: Mode Một lần: đã hoàn thành tất cả luồng; script dừng.')
                self.output('status','Mode Một lần: đã hoàn thành tất cả luồng.')
        except Exception as e:
            self.output('log','LỖI THEO DÕI/THAO TÁC: '+str(e)+' | Đã dừng để tránh nhấn sai.');self.stop_event.set()
        finally:self.output('thread_done','Theo dõi và thao tác đã dừng.')

    def run_chain(self,s,flow_name,cond):
        groups={}
        for action in cond['actions']:groups.setdefault(action['order'],[]).append(action)
        def action_log(event,action,repeat,timestamp,confirm_attempt=None):
            label = action['key'] if action['type']=='Phím' else (action['type']+' · tại chỗ' if action.get('mouse_mode')=='Nhấn tại con trỏ hiện tại' else f"{action['type']} ({action['x']}, {action['y']})")
            extra=f' · xác nhận lần {confirm_attempt}' if confirm_attempt is not None else f" · lần {repeat}/{action.get('repeat',1)}"
            self.output('action',f"{timestamp}: {flow_name} / {cond['name']} / Thao tác {label} · số thứ tự {action['order']} · {event}{extra}")
        finished=True
        for order in sorted(groups):
            if not engine.wait_unpaused(self.stop_event,self.pause_event):
                finished=False;break
            foreground=win.foreground()
            if foreground!=self.target:
                self.output('log',f"FOCUS [{engine.diagnostic_time()}] {flow_name}/{cond['name']} · trước nhóm {order}: mục tiêu {win.describe_window(self.target)} | phía trước {win.describe_window(foreground)}")
                finished=False;break
            actions=groups[order]
            self.output('log',f"  Bắt đầu nhóm {order}: " + ', '.join((a['key'] if a['type']=='Phím' else (f"{a['type']} tại con trỏ hiện tại [{a.get('mouse_api','SendInput')}]" if a.get('mouse_mode')=='Nhấn tại con trỏ hiện tại' else f"{a['type']} ({a['x']},{a['y']})")) + f" ×{a.get('repeat',1)}" + (f" · chờ sau {a.get('after_delay',0)} ms" if a.get('after_delay',0) else '') for a in actions))
            if cond.get('confirm_activation',False) and order==min(groups):
                finished=self.run_confirmation(s,cond,flow_name,order,actions[0],action_log)
            elif self.dry:
                finished=engine.wait_dry_group(actions,self.target,self.stop_event,self.pause_event)
                if finished:self.output('log',f"  Nhóm {order}: mô phỏng xong, không gửi đầu vào.")
            else:
                finished=engine.run_group(actions,self.target,self.stop_event,lambda msg:self.output('log',f"  [{flow_name}/{cond['name']} · nhóm {order}] "+msg),self.pause_event,action_log)
                if finished:
                    self.output('log',f"  CHẨN ĐOÁN [{engine.diagnostic_time()}] {flow_name}/{cond['name']} nhóm {order}: các lần nhấn, nhả và chờ đã kết thúc.")
                    if any(a['type']!='Phím' and a.get('mouse_api','SendInput')=='mouse_event' for a in actions):
                        self.output('log',f"  Nhóm {order}: đã gọi mouse_event; API này không xác nhận kết quả hay ứng dụng đích có phản ứng.")
                    else:self.output('log',f"  Nhóm {order}: Windows đã chấp nhận lệnh gửi; không xác nhận được ứng dụng đích có phản ứng.")
            if not finished:break
        return finished
