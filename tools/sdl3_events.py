"""Sample SDL3 gamepad sensor EVENTS (the path Eden's SDLDriver actually uses).

Prints an event-type histogram and, for sensor events, the 3 float values.
"""

import argparse
import ctypes
import math
import os
import time


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sdl3", default=r"D:\Games\eden\SDL3.dll")
    ap.add_argument("--seconds", type=float, default=4.0)
    args = ap.parse_args()

    directory = os.path.dirname(os.path.abspath(args.sdl3))
    try:
        os.add_dll_directory(directory)
    except AttributeError:
        pass
    lib = ctypes.CDLL(args.sdl3)

    def fn(name, restype, argtypes, optional=False):
        f = getattr(lib, name, None)
        if f is None:
            if optional:
                return None
            raise RuntimeError("missing " + name)
        f.restype = restype
        f.argtypes = argtypes
        return f

    SetHint = fn("SDL_SetHint", ctypes.c_bool, [ctypes.c_char_p, ctypes.c_char_p])
    Init = fn("SDL_Init", ctypes.c_bool, [ctypes.c_uint32])
    WaitEventTimeout = fn("SDL_WaitEventTimeout", ctypes.c_bool, [ctypes.c_void_p, ctypes.c_int])
    GetJoysticks = fn("SDL_GetJoysticks", ctypes.POINTER(ctypes.c_uint32), [ctypes.POINTER(ctypes.c_int)])
    OpenGamepad = fn("SDL_OpenGamepad", ctypes.c_void_p, [ctypes.c_uint32])
    IsGamepad = fn("SDL_IsGamepad", ctypes.c_bool, [ctypes.c_uint32])
    SetSensorEnabled = fn(
        "SDL_SetGamepadSensorEnabled", ctypes.c_bool, [ctypes.c_void_p, ctypes.c_int, ctypes.c_bool]
    )

    for k, v in {
        "SDL_JOYSTICK_RAWINPUT": "0",
        "SDL_JOYSTICK_HIDAPI_SWITCH": "1",
        "SDL_GAMECONTROLLER_SENSOR_FUSION": "1",
        "SDL_AUTO_UPDATE_SENSORS": "1",
        "SDL_JOYSTICK_ENHANCED_REPORTS": "1",
    }.items():
        SetHint(k.encode(), v.encode())

    if not Init(0x00000200 | 0x00001000):
        print("init failed")
        return

    count = ctypes.c_int(0)
    ids = GetJoysticks(ctypes.byref(count))
    pads = []
    for i in range(count.value):
        jid = ids[i]
        if IsGamepad(jid):
            p = OpenGamepad(jid)
            if p:
                SetSensorEnabled(p, 1, True)  # accel
                SetSensorEnabled(p, 2, True)  # gyro
                pads.append(p)
    print("gamepads opened:", len(pads))

    buf = ctypes.create_string_buffer(128)
    types = {}
    sensors = {}
    end = time.time() + args.seconds
    samples = {"accel": [], "gyro": []}
    while time.time() < end:
        if not WaitEventTimeout(buf, 100):
            continue
        etype = ctypes.c_uint32.from_buffer(buf, 0).value
        types[etype] = types.get(etype, 0) + 1
        if etype >= 0x100:  # ignore the 0x0000-0x00FF reserved range
            # sensor event layout: type u32@0, reserved u64@8, timestamp u64@16,
            # which u32@24, sensor s32@28, data float[3]@32, sensor_timestamp u64@48
            sensor = ctypes.c_int32.from_buffer(buf, 28).value
            if etype == 0x659 and types[etype] <= 2:
                print("   raw 0x659 event:", " ".join(f"{b:02x}" for b in buf.raw[:64]))
            sensors[sensor] = sensors.get(sensor, 0) + 1
            if sensor in (1, 2):
                vals = [
                    ctypes.c_float.from_buffer(buf, 32 + 4 * i).value for i in range(3)
                ]
                label = "accel" if sensor == 1 else "gyro"
                samples[label].append(vals)

    print("event type histogram:", {hex(k): v for k, v in sorted(types.items())})
    print("sensor field histogram:", sensors)
    for label, rows in samples.items():
        print(f"\n{label}: {len(rows)} events")
        for r in rows[:6]:
            finite = all(math.isfinite(v) for v in r)
            print("   ", [f"{v:.4f}" for v in r], "finite" if finite else "*** NON-FINITE ***")
        if rows:
            bad = sum(1 for r in rows if not all(math.isfinite(v) for v in r))
            print(f"    non-finite ratio: {bad}/{len(rows)}")


if __name__ == "__main__":
    main()
