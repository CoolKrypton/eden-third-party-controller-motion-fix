"""Diagnostic probe: check whether SDL3 can read gyro/accel from a gamepad.

It reproduces exactly the hint configuration Eden's SDLDriver constructor uses,
then reports sensor availability and live sensor samples.

Usage:
    python tools/sdl3_probe.py [--sdl3 PATH_TO_SDL3.dll] [--raw] [--seconds N]
"""

import argparse
import ctypes
import os
import sys
import time
from ctypes import wintypes

HINT_PROFILES = {
    # Exactly what Eden sets today (enable_raw_input=false, procon driver OFF so
    # SDL_HINT_JOYSTICK_HIDAPI_SWITCH=1)
    "eden-default": {
        "SDL_JOYSTICK_RAWINPUT": "0",
        "SDL_JOYSTICK_HIDAPI_JOY_CONS": "0",
        "SDL_JOYSTICK_HIDAPI_SWITCH": "1",
        "SDL_JOYSTICK_HIDAPI_SWITCH_HOME_LED": "0",
        "SDL_JOYSTICK_HIDAPI_SWITCH_PLAYER_LED": "1",
        "SDL_GAMECONTROLLER_SENSOR_FUSION": "1",
        "SDL_AUTO_UPDATE_SENSORS": "1",
        "SDL_JOYSTICK_ENHANCED_REPORTS": "1",
        "SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS": "1",
    },
    "rawinput-on": {
        "SDL_JOYSTICK_RAWINPUT": "1",
        "SDL_JOYSTICK_HIDAPI_JOY_CONS": "0",
        "SDL_JOYSTICK_HIDAPI_SWITCH": "1",
        "SDL_GAMECONTROLLER_SENSOR_FUSION": "1",
        "SDL_AUTO_UPDATE_SENSORS": "1",
        "SDL_JOYSTICK_ENHANCED_REPORTS": "1",
    },
    "no-fusion": {
        "SDL_JOYSTICK_RAWINPUT": "0",
        "SDL_JOYSTICK_HIDAPI_JOY_CONS": "0",
        "SDL_JOYSTICK_HIDAPI_SWITCH": "1",
        "SDL_GAMECONTROLLER_SENSOR_FUSION": "0",
        "SDL_AUTO_UPDATE_SENSORS": "1",
        "SDL_JOYSTICK_ENHANCED_REPORTS": "1",
    },
    "no-enhanced": {
        "SDL_JOYSTICK_RAWINPUT": "0",
        "SDL_JOYSTICK_HIDAPI_JOY_CONS": "0",
        "SDL_JOYSTICK_HIDAPI_SWITCH": "1",
        "SDL_GAMECONTROLLER_SENSOR_FUSION": "0",
        "SDL_AUTO_UPDATE_SENSORS": "1",
    },
}

SDL_INIT_JOYSTICK = 0x00000200
SDL_INIT_GAMEPAD = 0x00001000

SDL_SENSOR_ACCEL = 1
SDL_SENSOR_GYRO = 2


class SDL:
    def __init__(self, dll_path):
        directory = os.path.dirname(os.path.abspath(dll_path))
        try:
            os.add_dll_directory(directory)
        except AttributeError:
            pass
        self.lib = ctypes.CDLL(dll_path)
        self._bind()

    def _fn(self, name, restype, argtypes):
        fn = getattr(self.lib, name, None)
        if fn is None:
            return None
        fn.restype = restype
        fn.argtypes = argtypes
        return fn

    def _bind(self):
        self.SetHint = self._fn("SDL_SetHint", ctypes.c_bool, [ctypes.c_char_p, ctypes.c_char_p])
        self.Init = self._fn("SDL_Init", ctypes.c_bool, [ctypes.c_uint32])
        self.GetError = self._fn("SDL_GetError", ctypes.c_char_p, [])
        self.GetJoysticks = self._fn(
            "SDL_GetJoysticks", ctypes.POINTER(ctypes.c_uint32), [ctypes.POINTER(ctypes.c_int)]
        )
        self.OpenJoystick = self._fn("SDL_OpenJoystick", ctypes.c_void_p, [ctypes.c_uint32])
        self.OpenGamepad = self._fn("SDL_OpenGamepad", ctypes.c_void_p, [ctypes.c_uint32])
        self.IsGamepad = self._fn("SDL_IsGamepad", ctypes.c_bool, [ctypes.c_uint32])
        self.CloseJoystick = self._fn("SDL_CloseJoystick", None, [ctypes.c_void_p])
        self.CloseGamepad = self._fn("SDL_CloseGamepad", None, [ctypes.c_void_p])
        self.PumpEvents = self._fn("SDL_PumpEvents", None, [])
        self.UpdateGamepads = self._fn("SDL_UpdateGamepads", None, [])
        self.GetName = self._fn("SDL_GetJoystickName", ctypes.c_char_p, [ctypes.c_void_p])
        self.GetNameForID = self._fn("SDL_GetJoystickNameForID", ctypes.c_char_p, [ctypes.c_uint32])
        self.GetPathForID = self._fn("SDL_GetJoystickPathForID", ctypes.c_char_p, [ctypes.c_uint32])
        self.GetVendorForID = self._fn("SDL_GetJoystickVendorForID", ctypes.c_uint16, [ctypes.c_uint32])
        self.GetProductForID = self._fn(
            "SDL_GetJoystickProductForID", ctypes.c_uint16, [ctypes.c_uint32]
        )
        self.GetGamepadType = self._fn("SDL_GetGamepadType", ctypes.c_int, [ctypes.c_void_p])
        self.GamepadHasSensor = self._fn(
            "SDL_GamepadHasSensor", ctypes.c_bool, [ctypes.c_void_p, ctypes.c_int]
        )
        self.GetGamepadSensorDataRate = self._fn(
            "SDL_GetGamepadSensorDataRate", ctypes.c_float, [ctypes.c_void_p, ctypes.c_int]
        )
        self.SetGamepadSensorEnabled = self._fn(
            "SDL_SetGamepadSensorEnabled", ctypes.c_bool, [ctypes.c_void_p, ctypes.c_int, ctypes.c_bool]
        )
        self.GetGamepadSensorData = self._fn(
            "SDL_GetGamepadSensorData",
            ctypes.c_bool,
            [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_float), ctypes.c_int],
        )
        self.GetNumJoystickAxes = self._fn("SDL_GetNumJoystickAxes", ctypes.c_int, [ctypes.c_void_p])
        self.GetNumJoystickButtons = self._fn(
            "SDL_GetNumJoystickButtons", ctypes.c_int, [ctypes.c_void_p]
        )


GAMEPAD_TYPE_NAMES = {
    0: "UNKNOWN",
    1: "STANDARD",
    2: "XBOX360",
    3: "XBOXONE",
    4: "PS3",
    5: "PS4",
    6: "PS5",
    7: "NINTENDO_SWITCH_PRO",
    8: "NINTENDO_SWITCH_JOYCON_LEFT",
    9: "NINTENDO_SWITCH_JOYCON_RIGHT",
    10: "NINTENDO_SWITCH_JOYCON_PAIR",
}


def s(b):
    return b.decode("utf-8", "replace") if b else ""


def probe(profile_name, hints, seconds):
    sdl = SDL(ARGS.sdl3)
    print(f"\n{'=' * 78}\nPROFILE: {profile_name}\n{'=' * 78}")
    for k, v in hints.items():
        sdl.SetHint(k.encode(), v.encode())

    if not sdl.Init(SDL_INIT_JOYSTICK | SDL_INIT_GAMEPAD):
        print("SDL_Init failed:", s(sdl.GetError()))
        return None

    count = ctypes.c_int(0)
    ids = sdl.GetJoysticks(ctypes.byref(count))
    print(f"joysticks found: {count.value}")
    if not ids or count.value == 0:
        print("  <none>")
        return None

    results = {}
    handles = []
    for i in range(count.value):
        jid = ids[i]
        name = s(sdl.GetNameForID(jid)) if sdl.GetNameForID else "?"
        path = s(sdl.GetPathForID(jid)) if sdl.GetPathForID else "?"
        vendor = sdl.GetVendorForID(jid) if sdl.GetVendorForID else 0
        product = sdl.GetProductForID(jid) if sdl.GetProductForID else 0
        print(f"\n  [{i}] id={jid} name='{name}'")
        print(f"       vendor=0x{vendor:04X} product=0x{product:04X}")
        print(f"       path={path}")
        print(f"       is_gamepad={sdl.IsGamepad(jid)}")

        joy = sdl.OpenJoystick(jid)
        if not joy:
            print("       open joystick FAILED:", s(sdl.GetError()))
            continue
        handles.append(joy)
        pad = sdl.OpenGamepad(jid) if sdl.IsGamepad(jid) else None

        if not pad:
            print("       no gamepad handle -> sensors impossible")
            continue
        handles.append(pad)

        gtype = sdl.GetGamepadType(pad) if sdl.GetGamepadType else -1
        print(f"       gamepad_type={gtype} ({GAMEPAD_TYPE_NAMES.get(gtype, '?')})")

        info = {}
        for label, sensor in (("accel", SDL_SENSOR_ACCEL), ("gyro", SDL_SENSOR_GYRO)):
            has = sdl.GamepadHasSensor(pad, sensor)
            rate = sdl.GetGamepadSensorDataRate(pad, sensor) if sdl.GetGamepadSensorDataRate else 0
            ok = sdl.SetGamepadSensorEnabled(pad, sensor, True)
            print(
                f"       {label}: has={has} rate={rate:.1f}Hz enable_ok={ok}"
                + (f" err={s(sdl.GetError())}" if not ok else "")
            )
            info[label] = has
        results[jid] = (name, info, pad, sdl)

    if not results:
        return results

    # Live sample loop
    print(f"\n  --- sampling {seconds}s (move the controller) ---")
    buf = (ctypes.c_float * 3)()
    end = time.time() + seconds
    last = {}
    while time.time() < end:
        for jid, (name, info, pad, sdl) in results.items():
            sdl.PumpEvents()
            if sdl.UpdateGamepads:
                sdl.UpdateGamepads()
            for label, sensor in (("accel", SDL_SENSOR_ACCEL), ("gyro", SDL_SENSOR_GYRO)):
                if sdl.GetGamepadSensorData(pad, sensor, buf, 3):
                    vals = (round(buf[0], 3), round(buf[1], 3), round(buf[2], 3))
                    if vals != last.get((jid, label)):
                        last[(jid, label)] = vals
                        print(f"    {name[:28]:28s} {label}: {vals}")
        time.sleep(0.05)

    for h in handles:
        sdl.CloseJoystick(h)
    return results


def main():
    global ARGS
    ap = argparse.ArgumentParser()
    ap.add_argument("--sdl3", default=r"D:\Games\eden\SDL3.dll")
    ap.add_argument("--seconds", type=float, default=3.0)
    ap.add_argument("--profiles", default="eden-default")
    ARGS = ap.parse_args()

    print("SDL3 dll:", ARGS.sdl3)
    for name in ARGS.profiles.split(","):
        name = name.strip()
        if name not in HINT_PROFILES:
            print("unknown profile", name)
            continue
        probe(name, HINT_PROFILES[name], ARGS.seconds)


if __name__ == "__main__":
    main()
