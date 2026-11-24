import unittest
from unittest.mock import patch
import threading
import windows_input as win

class MouseModesTests(unittest.TestCase):
    def test_current_skips_move_and_sends_click(self):
        with patch.object(win, 'ensure_windows'), patch.object(win, '_move_cursor') as move, \
             patch.object(win, 'foreground', return_value=7), patch.object(win, '_mouse') as mouse:
            mode = win.mouse_down('Chuột trái', 12, 34, 7, threading.Event(), 'Nhấn tại con trỏ hiện tại')
        move.assert_not_called(); mouse.assert_called_once_with(0x0002, 'SendInput')
        self.assertIn('không di chuyển', mode)
    def test_opted_in_position_failure_clicks_current(self):
        with patch.object(win, 'ensure_windows'), patch.object(win, '_move_cursor', side_effect=win.CursorPositionError('bị khóa')), \
             patch.object(win, 'foreground', return_value=7), patch.object(win, '_mouse') as mouse:
            result = win.mouse_down('Chuột trái', 12, 34, 7, threading.Event(), 'Tọa độ; nếu lỗi nhấn tại chỗ')
        mouse.assert_called_once_with(0x0002, 'SendInput'); self.assertIn('không đảm bảo', result)
    def test_strict_mode_position_failure_no_click(self):
        with patch.object(win, 'ensure_windows'), patch.object(win, '_move_cursor', side_effect=win.CursorPositionError('bị khóa')), \
             patch.object(win, '_mouse') as mouse:
            with self.assertRaises(win.CursorPositionError): win.mouse_down('Chuột trái', 12, 34)
        mouse.assert_not_called()
    def test_focus_loss_does_not_fallback(self):
        with patch.object(win, 'ensure_windows'), patch.object(win, '_move_cursor', side_effect=RuntimeError('mất cửa sổ')), \
             patch.object(win, '_mouse') as mouse:
            with self.assertRaises(RuntimeError): win.mouse_down('Chuột trái', 12, 34, 7, threading.Event(), 'Tọa độ; nếu lỗi nhấn tại chỗ')
        mouse.assert_not_called()
    def test_stop_after_position_failure_does_not_click(self):
        stop = threading.Event(); stop.set()
        with patch.object(win, 'ensure_windows'), patch.object(win, '_move_cursor', side_effect=win.CursorPositionError('không xác nhận')), \
             patch.object(win, '_mouse') as mouse:
            with self.assertRaises(RuntimeError): win.mouse_down('Chuột trái', 12, 34, 7, stop, 'Tọa độ; nếu lỗi nhấn tại chỗ')
        mouse.assert_not_called()

class MouseApiTests(unittest.TestCase):
    def test_mouse_event_uses_documented_function(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        fake = SimpleNamespace(mouse_event=Mock())
        with patch.object(win, 'user32', fake, create=True):
            win._mouse(0x0002, 'mouse_event')
        fake.mouse_event.assert_called_once_with(0x0002, 0, 0, 0, 0)
    def test_legacy_button_up_and_down_use_same_api(self):
        with patch.object(win, 'ensure_windows'), patch.object(win, 'foreground', return_value=7), \
             patch.object(win, '_mouse') as mouse:
            win.mouse_down('Chuột trái', 0, 0, 7, threading.Event(), 'Nhấn tại con trỏ hiện tại', 'mouse_event')
            win.mouse_up('Chuột trái', 'mouse_event')
        self.assertEqual(mouse.call_args_list[0].args, (0x0002, 'mouse_event'))
        self.assertEqual(mouse.call_args_list[1].args, (0x0004, 'mouse_event'))
    def test_invalid_api_rejected(self):
        with self.assertRaises(ValueError): win._mouse(2, 'không hợp lệ')

if __name__ == '__main__': unittest.main()
