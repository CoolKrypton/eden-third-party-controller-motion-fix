"""Raw HID dump for the controller, using SDL3's bundled hidapi (SDL_hid_*).

Reads raw input reports and hexdumps them so we can identify the report layout
used by 3rd party "Switch mode" controllers (e.g. report id 0x81).

Usage:
    python tools/hid_dump.py [--sdl3 PATH] [--seconds 5] [--vid 057e] [--pid 2009]
"""

import argparse
import ctypes
import os
import time


class HidDeviceInfo(ctypes.Structure):
    pass


HidDeviceInfo._fields_ = [
    ("path", ctypes.c_char_p),
    ("vendor_id", ctypes.c_uint16),
    ("product_id", ctypes.c_uint16),
    ("serial_number", ctypes.c_wchar_p),
    ("release_number", ctypes.c_uint16),
    ("manufacturer_string", ctypes.c_wchar_p),
    ("product_string", ctypes.c_wchar_p),
    ("usage_page", ctypes.c_uint16),
    ("usage", ctypes.c_uint16),
    ("interface_number", ctypes.c_int),
    ("interface_class", ctypes.c_int),
    ("interface_subclass", ctypes.c_int),
    ("interface_protocol", ctypes.c_int),
    ("next", ctypes.POINTER(HidDeviceInfo)),
]


class Hid:
    def __init__(self, dll_path):
        directory = os.path.dirname(os.path.abspath(dll_path))
        try:
            os.add_dll_directory(directory)
        except AttributeError:
            pass
        self.lib = ctypes.CDLL(dll_path)

    def fn(self, name, restype, argtypes, optional=False):
        f = getattr(self.lib, name, None)
        if f is None:
            if optional:
                return None
            raise RuntimeError(f"missing export {name}")
        f.restype = restype
        f.argtypes = argtypes
        return f


def hexdump(data, width=16):
    out = []
    for off in range(0, len(data), width):
        chunk = data[off : off + width]
        hexs = " ".join(f"{b:02x}" for b in chunk)
        out.append(f"  {off:04x}  {hexs}")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sdl3", default=r"D:\Games\eden\SDL3.dll")
    ap.add_argument("--seconds", type=float, default=4.0)
    ap.add_argument("--vid", default="057e")
    ap.add_argument("--pid", default="0000")
    ap.add_argument("--reports", type=int, default=8)
    args = ap.parse_args()

    hid = Hid(args.sdl3)
    init = hid.fn("SDL_hid_init", ctypes.c_int, [])
    enum = hid.fn(
        "SDL_hid_enumerate", ctypes.POINTER(HidDeviceInfo), [ctypes.c_uint16, ctypes.c_uint16]
    )
    free_enum = hid.fn("SDL_hid_free_enumeration", None, [ctypes.POINTER(HidDeviceInfo)])
    open_path = hid.fn("SDL_hid_open_path", ctypes.c_void_p, [ctypes.c_char_p])
    read_timeout = hid.fn(
        "SDL_hid_read_timeout",
        ctypes.c_int,
        [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ubyte), ctypes.c_size_t, ctypes.c_int],
    )
    error = hid.fn("SDL_hid_error", ctypes.c_wchar_p, [ctypes.c_void_p], optional=True)
    get_error = hid.fn("SDL_GetError", ctypes.c_char_p, [], optional=True)

    print("SDL_hid_init ->", init())
    devs = enum(int(args.vid, 16), int(args.pid, 16))
    cur = devs
    entries = []
    while cur:
        d = cur.contents
        entries.append(d.path.decode() if d.path else "")
        print(
            f"  {d.vendor_id:04x}:{d.product_id:04x} usage_page={d.usage_page:#06x} "
            f"usage={d.usage:#06x} iface={d.interface_number} mf='{d.manufacturer_string}' "
            f"prod='{d.product_string}'"
        )
        print(f"    path={d.path}")
        cur = d.next
    free_enum(devs)

    if not entries:
        print("no device found")
        return

    handle = open_path(entries[0].encode())
    if not handle:
        msg = error(None) if error else ""
        msg = msg or (get_error().decode("utf-8", "replace") if get_error else "")
        print("open failed:", msg)
        return
    print("opened OK")

    buf = (ctypes.c_ubyte * 512)()
    end = time.time() + args.seconds
    seen = {}
    count = 0
    while time.time() < end and count < args.reports * 40:
        n = read_timeout(handle, buf, 512, 200)
        if n > 0:
            data = bytes(buf[:n])
            rid = data[0]
            seen[rid] = seen.get(rid, 0) + 1
            if seen[rid] <= args.reports:
                print(f"\nreport id=0x{rid:02x} len={n}")
                print(hexdump(data))
            count += 1
    print("\nreport id histogram:", {f"0x{k:02x}": v for k, v in seen.items()})


if __name__ == "__main__":
    main()
