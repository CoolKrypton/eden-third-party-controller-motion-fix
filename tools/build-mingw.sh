#!/usr/bin/env bash
# Build Eden with MinGW GCC, tuned for the host CPU.
#
#   native preset -> -march=native -mtune=native (AVX2/FMA/BMI2 on a 9900K)
#   LTO           -> whole program optimisation on top
#
# Usage:  bash tools/build-mingw.sh [configure|build|all]
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD="${SRC}/build-mingw"
LOG="${SRC}/build-mingw.log"
MODE="${1:-all}"

MINGW=/c/msys64/mingw64/bin
# MSYS2 keeps the Qt6 uic/moc/rcc helpers here rather than in mingw64/bin.
QTBIN=/c/msys64/mingw64/share/qt6/bin

export PATH="${MINGW}:${QTBIN}:/c/msys64/usr/bin:/c/Program Files/CMake/bin:/c/Users/shore/AppData/Local/Microsoft/WinGet/Links:${PATH}"

# The bundled static Qt6 (built with GCC 16.1.0) is ABI incompatible with the
# GCC 16.2.0 in MSYS2: libstdc++ no longer exports the deprecated
# std::codecvt<char16_t/char32_t, char, mbstate_t> facets that Qt6Core was
# linked against, so every Qt tool dies with STATUS_ENTRYPOINT_NOT_FOUND
# (0xC0000139) before running. Use the MSYS2 Qt6 package instead, which is built
# with the very same toolchain.
CMAKE_ARGS=(
  -G Ninja
  -S "${SRC}" -B "${BUILD}"
  -DCMAKE_BUILD_TYPE=Release
  -DCMAKE_C_COMPILER="${MINGW}/gcc.exe"
  -DCMAKE_CXX_COMPILER="${MINGW}/g++.exe"
  -DYUZU_BUILD_PRESET=native
  -DENABLE_LTO=ON
  -DYUZU_USE_BUNDLED_QT=OFF
  # The CPM cache already holds the prebuilt mingw FFmpeg; the MSYS2 system
  # package is not installed and pulling it in would be a large download.
  -DYUZU_USE_BUNDLED_FFMPEG=ON
  -DENABLE_QT=ON
  -DENABLE_QT_TRANSLATION=ON
  -DQt6_DIR="/c/msys64/mingw64/lib/cmake/Qt6"
  -DYUZU_TESTS=OFF
  -DENABLE_WEB_SERVICE=OFF
  # NOTE: keep ENABLE_WERROR at its default (ON). Flipping it changes the
  # compile flags of every target and forces a full rebuild; the only file that
  # trips a GCC 16 warning is patched in-tree instead.
  # MSYS2 only ships vulkan-headers, which leaves the Vulkan dependency half
  # satisfied; force the bundled pair instead.
  -DVulkanHeaders_FORCE_BUNDLED=ON
)

if [[ "${MODE}" == "configure" || "${MODE}" == "all" ]]; then
  echo "=== configure ===" | tee -a "${LOG}"
  cmake "${CMAKE_ARGS[@]}" 2>&1 | tee -a "${LOG}"
fi

# CPM downloads SDL3 into .cache/, which is git-ignored, so a fresh clone would
# build pristine SDL3 and lose the motion fix. Re-apply it now that configure
# has made sure the sources are on disk.
bash "${SRC}/tools/patches/apply.sh" 2>&1 | tee -a "${LOG}"

if [[ "${MODE}" == "build" || "${MODE}" == "all" ]]; then
  echo "=== build ===" | tee -a "${LOG}"
  cmake --build "${BUILD}" --parallel "$(nproc)" 2>&1 | tee -a "${LOG}"
fi

# The MSYS2 Qt6 is a shared build, so eden.exe needs the whole runtime closure
# next to it to start without MSYS2 on PATH. CMake only copies the Qt6*.dll
# files, so walk the import tables of the exe, those DLLs and every Qt plugin
# and copy in whatever else lives in the MinGW prefix.
if [[ "${MODE}" == "build" || "${MODE}" == "all" || "${MODE}" == "package" ]]; then
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

  # MSYS2's Qt6 installs its plugins under share/qt6/plugins, so Qt6Core looks
  # for <prefix>/share/qt6/plugins and never finds the plugins/ folder CMake
  # drops next to the exe. Without this the app dies with "no Qt platform plugin
  # could be initialized".
  cat > "${BIN}/qt.conf" <<'EOF'
[Paths]
Prefix=.
Plugins=plugins
Qml2Imports=qml
EOF
  echo "wrote ${BIN}/qt.conf" | tee -a "${LOG}"
fi

echo "=== done, binaries in ${BUILD}/bin ===" | tee -a "${LOG}"
