"""Read the IMU calibration blocks straight out of the controller's SPI flash.

Sends subcommand 0x10 (SPI flash read) over raw hidapi and dumps the 0x21 reply,
so we can see whether the calibration SDL3/Eden read is valid or garbage.
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

# neutral rumble bytes SDL uses
NEUTRAL_RUMBLE = [0x00, 0x01, 0x40, 0x40, 0x00, 0x01, 0x40, 0x40]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sdl3", default=r"D:\Games\eden\SDL3.dll")
    ap.add_argument("--vid", default="057e")
    ap.add_argument("--pid", default="0000")
    args = ap.parse_args()

    d = os.path.dirname(os.path.abspath(args.sdl3))
    try:
        os.add_dll_directory(d)
    except AttributeError:
        pass
    lib = ctypes.CDLL(args.sdl3)

    def fn(name, restype, argtypes):
        f = getattr(lib, name)
        f.restype = restype
        f.argtypes = argtypes
        return f

    fn("SDL_hid_init", ctypes.c_int, [])()
    enum = fn("SDL_hid_enumerate", ctypes.POINTER(HidDeviceInfo), [ctypes.c_uint16, ctypes.c_uint16])
    fn("SDL_hid_free_enumeration", None, [ctypes.POINTER(HidDeviceInfo)])
    open_path = fn("SDL_hid_open_path", ctypes.c_void_p, [ctypes.c_char_p])
    write = fn("SDL_hid_write", ctypes.c_int, [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ubyte), ctypes.c_size_t])
    read_timeout = fn("SDL_hid_read_timeout", ctypes.c_int,
                      [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ubyte), ctypes.c_size_t, ctypes.c_int])

    devs = enum(int(args.vid, 16), int(args.pid, 16))
    path = devs.contents.path if devs else None
    if not path:
        print("device not found")
        return
    handle = open_path(path)
    if not handle:
        print("open failed")
        return

    def drain():
        buf = (ctypes.c_ubyte * 512)()
        for _ in range(60):
            if read_timeout(handle, buf, 512, 20) <= 0:
                break

    def spi_read(addr, length):
        drain()
        pkt = (ctypes.c_ubyte * 64)()
        pkt[0] = 0x01              # RumbleAndSubcommand
        pkt[1] = 0x00              # packet counter
        for i, b in enumerate(NEUTRAL_RUMBLE):
            pkt[2 + i] = b
        pkt[10] = 0x10             # SPIFlashRead
        pkt[11] = addr & 0xFF
        pkt[12] = (addr >> 8) & 0xFF
        pkt[13] = 0x00
        pkt[14] = 0x00
        pkt[15] = length
        n = write(handle, pkt, 64)
        if n < 0:
            return None
        buf = (ctypes.c_ubyte * 512)()
        for _ in range(80):
            got = read_timeout(handle, buf, 512, 100)
            if got > 0 and buf[0] == 0x21:
                return bytes(buf[:got])
        return None

    blocks = {
        "FACTORY IMU (0x6020, 24B)": (0x6020, 24),
        "USER IMU (0x8020, 24B)": (0x8020, 24),
        "FACTORY STICK (0x603D, 18B)": (0x603D, 18),
        "DEVICE TYPE (0x6000, 6B)": (0x6000, 6),
    }

    for label, (addr, length) in blocks.items():
        reply = spi_read(addr, length)
        print(f"\n=== {label}")
        if reply is None:
            print("   no reply (command unsupported / timed out)")
            continue
        print("   reply:", " ".join(f"{b:02x}" for b in reply[:40]))
        if len(reply) > 20 and reply[14] == 0x10:
            data = reply[20 : 20 + length]
            print("   data :", " ".join(f"{b:02x}" for b in data))
            if length == 24:
                def s16(lo, hi):
                    v = (hi << 8) | lo
                    return v - 0x10000 if v & 0x8000 else v
                raw = [s16(data[i], data[i + 1]) for i in range(0, 12, 2)]
                coeff = [s16(data[i], data[i + 1]) for i in range(12, 24, 2)]
                print(f"   accel raw   : {raw}")
                print(f"   accel coeff : {coeff}")
                print("   denominators (coeff - raw):", [c - r for c, r in zip(coeff, raw)])


if __name__ == "__main__":
    main()
