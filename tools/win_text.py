"""Dump the window/child-window captions of a process (used to verify the UI language)."""
import ctypes
import sys
from ctypes import wintypes

u32 = ctypes.WinDLL("user32", use_last_error=True)
EnumWindows = u32.EnumWindows
EnumWindows.restype = wintypes.BOOL
EnumWindows.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
EnumChildWindows = u32.EnumChildWindows
EnumChildWindows.restype = wintypes.BOOL
EnumChildWindows.argtypes = [wintypes.HWND, ctypes.c_void_p, ctypes.c_void_p]
GetWindowTextW = u32.GetWindowTextW
GetWindowTextW.argtypes = [wintypes.HWND, ctypes.c_wchar_p, ctypes.c_int]
GetWindowTextW.restype = ctypes.c_int
GetWindowTextLengthW = u32.GetWindowTextLengthW
GetWindowTextLengthW.argtypes = [wintypes.HWND]
GetWindowTextLengthW.restype = ctypes.c_int
GetWindowThreadProcessId = u32.GetWindowThreadProcessId
GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
GetWindowThreadProcessId.restype = wintypes.DWORD
IsWindowVisible = u32.IsWindowVisible
IsWindowVisible.argtypes = [wintypes.HWND]
IsWindowVisible.restype = wintypes.BOOL

WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, ctypes.c_void_p)


def text_of(hwnd):
    n = GetWindowTextLengthW(hwnd)
    if n == 0:
        return ""
    buf = ctypes.create_unicode_buffer(n + 1)
    GetWindowTextW(hwnd, buf, n + 1)
    return buf.value


def main():
    target_pid = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    found = []

    def cb(hwnd, _):
        pid = wintypes.DWORD()
        GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == target_pid and IsWindowVisible(hwnd):
            t = text_of(hwnd)
            if t:
                found.append(t)
            kids = []

            def kcb(khwnd, _):
                kt = text_of(khwnd)
                if kt:
                    kids.append(kt)
                return True

            EnumChildWindows(hwnd, WNDENUMPROC(kcb), 0)
            found.extend(kids)
        return True

    EnumWindows(WNDENUMPROC(cb), 0)
    seen = []
    for t in found:
        if t not in seen:
            seen.append(t)
    for t in seen[:80]:
        print(t)


if __name__ == "__main__":
    main()
