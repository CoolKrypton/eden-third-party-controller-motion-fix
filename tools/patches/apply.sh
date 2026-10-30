#!/usr/bin/env bash
# Re-apply third party fixes that live inside CPM's download cache (.cache/cpm).
#
# That directory is git-ignored, so a fresh clone starts from pristine upstream
# sources and would silently lose the fixes below. CMake configure is what makes
# CPM download/verify the sources, so run this AFTER configure and BEFORE build.
#
#   bash tools/patches/apply.sh
set -uo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PATCH_DIR="${SRC}/tools/patches"

# --- SDL3 -------------------------------------------------------------------
# Third party Switch controllers that only emulate the outer layer of the
# protocol leave their SPI calibration region unprogrammed, so every field reads
# back as 0xFFFF: both the sensitivity coefficient and the raw offset are -1,
# which makes the scale divisor zero and turns every motion sample into inf or
# nan. Upstream SDL3 has no guard for it.
# Eden defaults to the SDL driver (enable_procon_driver is false), so this is
# the code path that actually feeds motion data to the emulator.
SDL3_SRC="${SRC}/.cache/cpm/sdl3/release-3.4.8/src/joystick/hidapi/SDL_hidapi_switch.c"

if [[ ! -f "${SDL3_SRC}" ]]; then
    echo "=== skip SDL3 fix: ${SDL3_SRC} not present yet (run cmake configure first) ==="
else
    if grep -q "SwitchIMUScale" "${SDL3_SRC}"; then
        echo "=== SDL3 IMU calibration fix already applied ==="
    else
        echo "=== applying SDL3 IMU calibration fix ==="
        cp "${PATCH_DIR}/sdl3/SDL_hidapi_switch.c" "${SDL3_SRC}"
    fi
fi
