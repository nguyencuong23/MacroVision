"""Documented Win32 input APIs only; no injection into another process."""
import ctypes
import os
import time
from ctypes import wintypes
import keyboard_keys

if os.name == 'nt':
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    ULONG_PTR = ctypes.c_size_t
    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [('dx', wintypes.LONG), ('dy', wintypes.LONG), ('mouseData', wintypes.DWORD), ('dwFlags', wintypes.DWORD), ('time', wintypes.DWORD), ('dwExtraInfo', ULONG_PTR)]
    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [('wVk', wintypes.WORD), ('wScan', wintypes.WORD), ('dwFlags', wintypes.DWORD), ('time', wintypes.DWORD), ('dwExtraInfo', ULONG_PTR)]
    class HARDWAREINPUT(ctypes.Structure):
        _fields_ = [('uMsg', wintypes.DWORD), ('wParamL', wintypes.WORD), ('wParamH', wintypes.WORD)]
    class _U(ctypes.Union):
        _fields_ = [('mi', MOUSEINPUT), ('ki', KEYBDINPUT), ('hi', HARDWAREINPUT)]
    class INPUT(ctypes.Structure):
        _anonymous_ = ('u',)
        _fields_ = [('type', wintypes.DWORD), ('u', _U)]
    user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int); user32.SendInput.restype = wintypes.UINT
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int); user32.GetWindowTextW.restype = ctypes.c_int
    user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
    user32.GetAsyncKeyState.argtypes = (ctypes.c_int,); user32.GetAsyncKeyState.restype = ctypes.c_short
    user32.SetCursorPos.argtypes = (ctypes.c_int, ctypes.c_int); user32.SetCursorPos.restype = wintypes.BOOL
    user32.GetCursorPos.argtypes = (ctypes.POINTER(wintypes.POINT),); user32.GetCursorPos.restype = wintypes.BOOL
    user32.GetSystemMetrics.argtypes = (ctypes.c_int,); user32.GetSystemMetrics.restype = ctypes.c_int
    user32.mouse_event.argtypes = (wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, ULONG_PTR)
    user32.mouse_event.restype = None


def ensure_windows():
    if os.name != 'nt': raise RuntimeError('Ứng dụng thao tác chỉ hỗ trợ Windows.')

def dpi_aware():
    ensure_windows()
    try:
        user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except (AttributeError, OSError):
        user32.SetProcessDPIAware()

def foreground():
    ensure_windows(); return user32.GetForegroundWindow()

def window_title(hwnd):
    ensure_windows()
    buf = ctypes.create_unicode_buffer(512); user32.GetWindowTextW(hwnd, buf, len(buf))
    return buf.value or '(không có tiêu đề)'

def describe_window(hwnd):
    """Metadata for diagnosis only; never changes the foreground window."""
    if not hwnd: return 'HWND=0, không có cửa sổ foreground'
    try:
        ensure_windows()
        pid=wintypes.DWORD();user32.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
        title=window_title(hwnd).replace('\n',' ').replace('\r',' ')
        return f'HWND={int(hwnd)}, PID={pid.value}, tiêu đề={title!r}'
    except Exception as e:
        return f'HWND={hwnd}, không đọc được thông tin: {e}'

def foreground_is_other_process(hwnd):
    pid = wintypes.DWORD(); user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return bool(hwnd and pid.value and pid.value != os.getpid())

def f6_down(): return bool(user32.GetAsyncKeyState(0x75) & 0x8000)
def f7_down(): return bool(user32.GetAsyncKeyState(0x76) & 0x8000)
def f8_down(): return bool(user32.GetAsyncKeyState(0x77) & 0x8000)

def parse_key(key):
    return keyboard_keys.parse_token(key)[1]

def parse_chord(key):
    return keyboard_keys.parse_chord(key)[1]

def _send(item):
    ctypes.set_last_error(0)
    if user32.SendInput(1, ctypes.byref(item), ctypes.sizeof(INPUT)) != 1:
        code = ctypes.get_last_error()
        raise RuntimeError(f'SendInput bị từ chối (mã Windows {code}; mã 0 không xác định nguyên nhân). Có thể do quyền hoặc ứng dụng đích.')

def _key(vk, up):
    flags=(0x0001 if vk in keyboard_keys.EXTENDED_VKS else 0) | (0x0002 if up else 0)
    _send(INPUT(type=1, ki=KEYBDINPUT(vk, 0, flags, 0, 0)))
def _mouse(flag, api='SendInput'):
    if api == 'SendInput':
        _send(INPUT(type=0, mi=MOUSEINPUT(0, 0, 0, flag, 0, 0)))
    elif api == 'mouse_event':
        # Legacy documented Windows function; returns VOID, so it cannot report
        # whether the recipient processed or even received the event.
        user32.mouse_event(flag, 0, 0, 0, 0)
    else:
        raise ValueError('API chuột không hợp lệ.')
def key_down(vk): ensure_windows(); _key(vk, False)
def key_up(vk): ensure_windows(); _key(vk, True)

def _position():
    p = wintypes.POINT()
    if not user32.GetCursorPos(ctypes.byref(p)): return None
    return p.x, p.y

class CursorPositionError(RuntimeError):
    """Cursor movement or verification failed, without changing focus state."""


def cursor_position():
    ensure_windows()
    return _position()

def _move_cursor(x, y, target=None, stop=None):
    """Use SetCursorPos; if that fails or is constrained try documented absolute SendInput.
    Verify actual cursor position before allowing a click; never click at an unknown location.
    """
    left, top, width, height = (user32.GetSystemMetrics(i) for i in (76, 77, 78, 79))
    if width < 2 or height < 2 or not (left <= x < left+width and top <= y < top+height):
        raise ValueError(f'Tọa độ ({x},{y}) nằm ngoài màn hình ảo ({left},{top},{width},{height}); cần đặt lại điểm chuột.')
    def active():
        return (stop is None or not stop.is_set()) and (target is None or foreground() == target)
    def check_position():
        for _ in range(5):
            if not active(): raise RuntimeError('Đã dừng hoặc mất cửa sổ đích khi di chuyển chuột.')
            p = _position()
            if p is not None and abs(p[0]-x) <= 2 and abs(p[1]-y) <= 2: return True
            time.sleep(.01)
        return False
    ctypes.set_last_error(0)
    direct_ok = bool(user32.SetCursorPos(x, y)); direct_error = ctypes.get_last_error()
    if direct_ok and check_position(): return 'SetCursorPos'
    if not active(): raise RuntimeError('Đã dừng hoặc mất cửa sổ đích khi di chuyển chuột.')
    # MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK
    ax = round((x-left)*65535/(width-1)); ay = round((y-top)*65535/(height-1))
    try:
        _send(INPUT(type=0, mi=MOUSEINPUT(ax, ay, 0, 0x0001|0x8000|0x4000, 0, 0)))
    except Exception as e:
        raise CursorPositionError(f'Không thể di chuyển tới ({x},{y}). SetCursorPos trả {direct_ok}, mã {direct_error}; SendInput dự phòng thất bại: {e}') from e
    if not check_position():
        raise CursorPositionError(f'Không xác nhận được con trỏ ở ({x},{y}); hiện tại {_position()}. SetCursorPos trả {direct_ok}, mã {direct_error}; đã thử SendInput dự phòng.')
    return 'SendInput di chuyển tuyệt đối'

def mouse_down(button, x, y, target=None, stop=None, mode='Đến tọa độ', api='SendInput'):
    ensure_windows()
    if button not in ('Chuột trái', 'Chuột phải'): raise ValueError('Nút chuột không hợp lệ.')
    if mode not in ('Đến tọa độ', 'Nhấn tại con trỏ hiện tại', 'Tọa độ; nếu lỗi nhấn tại chỗ'):
        raise ValueError('Chế độ vị trí chuột không hợp lệ.')
    if mode == 'Nhấn tại con trỏ hiện tại':
        method = 'nhấn tại vị trí con trỏ hiện tại; không di chuyển'
    else:
        try:
            method = _move_cursor(x, y, target, stop)
        except CursorPositionError as e:
            if mode != 'Tọa độ; nếu lỗi nhấn tại chỗ':
                raise CursorPositionError(str(e) + ' Không nhấn để tránh sai vị trí.') from e
            # Explicit opt-in; only handle a cursor-position failure, never a
            # focus loss, stop request, malformed coordinate, or mouse-button failure.
            method = f'KHÔNG đưa con trỏ tới ({x},{y}); sẽ nhấn tại vị trí hiện tại (không đảm bảo tọa độ). Chi tiết: {e}'
    if (stop is not None and stop.is_set()) or (target is not None and foreground() != target):
        raise RuntimeError('Đã dừng hoặc mất cửa sổ đích trước khi nhấn chuột.')
    _mouse(0x0002 if button == 'Chuột trái' else 0x0008, api)
    return method

def mouse_up(button, api='SendInput'): ensure_windows(); _mouse(0x0004 if button == 'Chuột trái' else 0x0010, api)
