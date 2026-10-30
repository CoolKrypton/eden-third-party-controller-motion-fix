#!/usr/bin/env bash
# Two phase PGO build of Eden with MinGW GCC (native + LTO).
#
#   bash tools/build-mingw-pgo.sh gen    # phase 1: instrumented build
#   <run eden.exe, play a game for a few minutes, close it normally>
#   bash tools/build-mingw-pgo.sh use    # phase 2: rebuild using the profile
#
# Phase 1 compiles every translation unit again, so it is a full build even
# though the object cache is warm. Keep it in its own build directory so the
# already working build-mingw/bin/eden.exe stays untouched.
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD="${SRC}/build-mingw-pgo"
LOG="${SRC}/build-mingw-pgo.log"
MODE="${1:-gen}"
PROFDIR="${BUILD}/prof"

MINGW=/c/msys64/mingw64/bin
QTBIN=/c/msys64/mingw64/share/qt6/bin

export PATH="${MINGW}:${QTBIN}:/c/msys64/usr/bin:/c/Program Files/CMake/bin:/c/Users/shore/AppData/Local/Microsoft/WinGet/Links:${PATH}"

# MSYS2 rewrites TMP/TEMP/TMPDIR into POSIX form ("C:/Users/..." -> "/c/Users/...")
# when it hands the environment to a native Windows program. g++ never notices
# because with -flto it writes no temp files, but ar/ranlib always do, and after
# the rewrite they cannot use the dir and fall back to P_tmpdir:
#     Cannot create temporary file in C:\WINDOWS\: Permission denied
# Excluding them from the conversion fixes every archive/link step.
# NB: the archive steps run through cmd.exe, so prefer driving this script from
# PowerShell; bash works too as long as this exclusion is in place.
export MSYS2_ENV_CONV_EXCL="TMP;TEMP;TMPDIR"

mkdir -p "${PROFDIR}"

case "${MODE}" in
gen)
    PGO_FLAGS="-fprofile-generate -fprofile-dir=${PROFDIR}"
    LTO=OFF
    ;;
use)
    # The instrumented exe resolves the baked -fprofile-dir as a drive relative
    # "\f\..." path, so the .gcda files only land somewhere readable when
    # GCOV_PREFIX was set while running (see bin/collect profile launcher).
    # Point -fprofile-use at that redirected root, not at PROFDIR.
    GCOV_PREFIX="${GCOV_PREFIX:-C:/pgoout}"
    USEDIR="${PGO_USE_DIR:-${GCOV_PREFIX}${BUILD}/prof}"
    # -fprofile-correction keeps the build going when the instrumented run did
    # not cover every counter (multithreaded code almost never does).
    PGO_FLAGS="-fprofile-use=${USEDIR} -fprofile-correction -Wno-error=coverage-mismatch -Wno-error=coverage-invalid-line-number"
    LTO=ON
    ;;
*)
    echo "usage: $0 [gen|use]" >&2
    exit 1
    ;;
esac

CMAKE_ARGS=(
  -G Ninja
  -S "${SRC}" -B "${BUILD}"
  -DCMAKE_BUILD_TYPE=Release
  -DCMAKE_C_COMPILER="${MINGW}/gcc.exe"
  -DCMAKE_CXX_COMPILER="${MINGW}/g++.exe"
  -DYUZU_BUILD_PRESET=native
  -DENABLE_LTO="${LTO}"
  -DYUZU_USE_BUNDLED_QT=OFF
  -DYUZU_USE_BUNDLED_FFMPEG=ON
  -DENABLE_QT=ON
  -DENABLE_QT_TRANSLATION=ON
  -DQt6_DIR="/c/msys64/mingw64/lib/cmake/Qt6"
  -DYUZU_TESTS=OFF
  -DENABLE_WEB_SERVICE=OFF
  -DVulkanHeaders_FORCE_BUNDLED=ON
  -DCMAKE_C_FLAGS="${PGO_FLAGS}"
  -DCMAKE_CXX_FLAGS="${PGO_FLAGS}"
  -DCMAKE_EXE_LINKER_FLAGS="${PGO_FLAGS}"
  -DCMAKE_SHARED_LINKER_FLAGS="${PGO_FLAGS}"
)

echo "=== configure (${MODE}) ===" | tee -a "${LOG}"
cmake "${CMAKE_ARGS[@]}" 2>&1 | tee -a "${LOG}"

# CPM downloads SDL3 into .cache/, which is git-ignored, so a fresh clone would
# build pristine SDL3 and lose the motion fix. Re-apply it now that configure
# has made sure the sources are on disk.
echo "=== re-apply third party patches ===" | tee -a "${LOG}"
bash "${SRC}/tools/patches/apply.sh" 2>&1 | tee -a "${LOG}"

echo "=== build (${MODE}) ===" | tee -a "${LOG}"
cmake --build "${BUILD}" --parallel "$(nproc)" 2>&1 | tee -a "${LOG}"

# Same runtime closure fixup as tools/build-mingw.sh
echo "=== copying runtime dependencies ===" | tee -a "${LOG}"
BIN="${BUILD}/bin"
{
  ntldd "${BIN}/eden.exe"
  for f in "${BIN}"/*.dll; do ntldd "$f"; done
  while IFS= read -r f; do ntldd "$f"; done < <(find "${BIN}/plugins" -name '*.dll' 2>/dev/null)
  ntldd -R "${BIN}/eden.exe"
} 2>/dev/null \
  | grep "msys64" | sed 's/.*=> //' | sed 's/ (.*//' | sort -u > "${BUILD}/runtime-deps.txt"
while IFS= read -r dep; do
  src="$(echo "${dep}" | sed "s|C:\\\\msys64|/c/msys64|" | tr '\\' '/')"
  [[ -f "${src}" ]] && cp -n "${src}" "${BIN}/" 2>/dev/null
done < "${BUILD}/runtime-deps.txt"
echo "copied $(ls "${BIN}"/*.dll | wc -l) DLLs into ${BIN}" | tee -a "${LOG}"

cat > "${BIN}/qt.conf" <<'EOF'
[Paths]
Prefix=.
Plugins=plugins
Qml2Imports=qml
EOF

echo "=== done (${MODE}), binaries in ${BIN} ===" | tee -a "${LOG}"
