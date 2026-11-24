import base64
import tkinter as tk
from tkinter import ttk, messagebox
import cv2
import numpy as np


def photo(bgr):
    ok, data = cv2.imencode('.png', bgr)
    if not ok:
        raise ValueError('Không thể tạo ảnh xem trước')
    return tk.PhotoImage(data=base64.b64encode(data.tobytes()))


class MaskEditor(tk.Toplevel):
    def __init__(self, parent, image, on_save, initial_mask=None):
        super().__init__(parent)
        self.title('Chỉnh mặt nạ - trắng là vùng được so sánh')
        self.image, self.on_save = image, on_save
        h, w = image.shape[:2]
        self.scale = min(3.0, 850 / w, 600 / h)
        self.dw, self.dh = max(1, int(w*self.scale)), max(1, int(h*self.scale))
        self.mask = np.zeros((h, w), dtype=np.uint8)
        self.mode = tk.StringVar(value='Tô')
        top = ttk.Frame(self); top.pack(fill='x', padx=8, pady=6)
        for text, cmd in [('Hình elip', self.ellipse), ('Chọn tất cả', self.all), ('Xóa hết', self.clear)]:
            ttk.Button(top, text=text, command=cmd).pack(side='left', padx=2)
        ttk.Radiobutton(top, text='Tô', variable=self.mode, value='Tô').pack(side='left', padx=4)
        ttk.Radiobutton(top, text='Tẩy', variable=self.mode, value='Tẩy').pack(side='left')
        ttk.Label(top, text='Cỡ cọ:').pack(side='left', padx=(8, 1))
        self.brush = tk.IntVar(value=12)
        ttk.Spinbox(top, from_=2, to=100, width=4, textvariable=self.brush).pack(side='left')
        self.canvas = tk.Canvas(self, width=self.dw, height=self.dh, cursor='crosshair', highlightthickness=0)
        self.canvas.pack(padx=8, pady=4)
        self.canvas.bind('<Button-1>', self.paint); self.canvas.bind('<B1-Motion>', self.paint)
        ttk.Label(self, text='Vùng xanh sẽ được so sánh. Tẩy nền và các phần động như số đếm ngược.').pack()
        ttk.Button(self, text='Lưu mặt nạ', command=self.save).pack(pady=8)
        if initial_mask is not None:
            self.mask = initial_mask.copy(); self.render()
        else:
            self.ellipse()
        self.transient(parent); self.grab_set()

    def ellipse(self):
        self.mask[:] = 0
        h, w = self.mask.shape
        cv2.ellipse(self.mask, (w//2, h//2), (max(1, w//2-1), max(1, h//2-1)), 0, 0, 360, 255, -1)
        self.render()
    def all(self): self.mask[:] = 255; self.render()
    def clear(self): self.mask[:] = 0; self.render()
    def paint(self, e):
        x = min(self.mask.shape[1]-1, max(0, int(e.x / self.scale)))
        y = min(self.mask.shape[0]-1, max(0, int(e.y / self.scale)))
        try: radius = max(1, int(self.brush.get() / self.scale / 2))
        except (ValueError, tk.TclError): radius = 5
        cv2.circle(self.mask, (x, y), radius, 255 if self.mode.get() == 'Tô' else 0, -1)
        self.render()
    def render(self):
        display = self.image.copy()
        sel = self.mask > 0
        display[sel] = (display[sel].astype(np.float32)*0.55 + np.array([0, 255, 0])*0.45).astype(np.uint8)
        display = cv2.resize(display, (self.dw, self.dh), interpolation=cv2.INTER_NEAREST)
        self.pic = photo(display)
        self.canvas.delete('all'); self.canvas.create_image(0, 0, image=self.pic, anchor='nw')
    def save(self):
        if np.count_nonzero(self.mask) < 10:
            messagebox.showerror('Mặt nạ', 'Hãy chọn ít nhất 10 điểm ảnh.', parent=self); return
        self.on_save(self.mask.copy()); self.destroy()

