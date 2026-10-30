<!--
# SPDX-FileCopyrightText: Copyright 2025 Eden Emulator Project
# SPDX-License-Identifier: GPL-3.0-or-later

# SPDX-FileCopyrightText: 2018 yuzu Emulator Project
# SPDX-License-Identifier: GPL-2.0-or-later
-->
<!-- lang: en-GB -->

<h1 align="center">
  <br>
  <a href="https://git.eden-emu.dev/eden-emu/eden"><img src="./dist/qt_themes/default/icons/256x256/eden.png" alt="Eden" width="200"></a>
  <br>
  <b>Eden</b>
  <br>
</h1>

<h4 align="center"><b>Eden</b> is a free and open-source (FOSS) Switch 1 emulator started by developer Camille LaVey.
<br>
Written in C++, with builds for Windows, Linux, macOS, Android, FreeBSD and more.
</h4>

---

## 🔧 This fork — motion (gyro / accel) fix for third party Switch controllers

Upstream Eden produces **broken motion data** on third party controllers that only
emulate the outer layer of the Switch protocol — for example the **BEITONG Kunpeng 40
(BTP-KP40)** in NS mode. Their SPI calibration region is unprogrammed, so every field
reads back as `0xFFFF`: the sensitivity coefficient and the raw offset are both `-1`,
the scale divisor collapses to `0`, and every motion sample becomes `inf` / `NaN`.

**The effective fix is in SDL3, not in Eden.** `enable_procon_driver` defaults to
`false`, so controller input is read through SDL3's HIDAPI Switch driver. Both motion
paths divide by zero independently, so both are guarded:

| Path | File | Status |
| --- | --- | --- |
| SDL3 HIDAPI Switch driver (**default**) | `tools/patches/sdl3/SDL_hidapi_switch.c` | ✅ effective by default |
| Eden's own Joycon driver | `src/input_common/helpers/joycon_protocol/{calibration,poller}.cpp` | dormant unless `enable_procon_driver=true` |

Other changes needed to build with MinGW GCC at all: `externals/libusb/CMakeLists.txt`
(MSYS `configure` needs an MSYS style `--srcdir`) and `src/yuzu_cmd/yuzu.cpp`
(`WinMain` must be declared before SDL3's `SDL_main.h` under `-Werror=missing-declarations`).

### Downloads

Windows x64 builds are on the
[Releases page](https://github.com/CoolKrypton/eden-third-party-controller-motion-fix/releases):

- **standard** — `-march=native -mtune=native -O3` + LTO
- **PGO** — same, plus profile guided optimisation from real gameplay

Runtime dependencies are bundled; just unzip and run `eden.exe`. The controller must be
in **NS mode**.

### Building

```bash
bash tools/build-mingw.sh            # standard build
bash tools/build-mingw-pgo.sh gen    # PGO phase 1: instrumented
#   play a game for a few minutes, then close Eden normally
bash tools/build-mingw-pgo.sh use    # PGO phase 2: optimised
```

SDL3 is fetched by CPM into `.cache/`, which is git-ignored, so a fresh clone would get
pristine upstream sources and silently lose the motion fix. `tools/patches/apply.sh`
therefore re-applies it (idempotently) right after CMake configure; both build scripts
call it.

### Notes

- **ZL / ZR not responding** on the Kunpeng 40 is *not* a deadzone or driver problem:
  the Hall effect triggers report "fully pressed" while idle. Fix it with a **trigger
  calibration on the controller itself** — no code change can work around it.
- **Chinese UI**: build with `ENABLE_QT_TRANSLATION=ON`. If the UI stays English, check
  `Paths\language` in `%APPDATA%\eden\config\qt-config.ini`; `LoadTranslation()` writes
  back `en` whenever loading fails, which then sticks.

---

<details>
<summary>中文说明</summary>

本 fork 修复第三方 Switch 手柄（如**北通鲲鹏 40 / BTP-KP40**，NS 模式）在 Eden 上
**体感（陀螺仪 / 加速度计）失效**的问题。这类手柄只模拟了协议外层，SPI 校准区未编程，
读回全是 `0xFFFF`：灵敏度系数与原始偏移都是 `-1`，换算时除数为 0，采样全部变成
`inf` / `NaN`。

**真正生效的修复在 SDL3**，因为 `enable_procon_driver` 默认为 `false`，手柄数据走
SDL3 的 HIDAPI Switch 驱动。Eden 自研 Joycon 驱动有同源的除零 bug，也一并修了，
但默认不走该路径。

Windows x64 构建见
[Releases](https://github.com/CoolKrypton/eden-third-party-controller-motion-fix/releases)，
含标准版与 PGO 版。

**ZL / ZR 无响应**不是死区问题：霍尔线性扳机静止时被判定为按到底，需在**手柄上做扳机校准**。

</details>

<p align="center">
    </a>
    <a href="https://discord.gg/HstXbPch7X">
        <img src="https://img.shields.io/discord/1367654015269339267?color=5865F2&label=Eden&logo=discord&logoColor=white"
            alt="Discord">
    </a>
    <a href="https://stt.gg/qKgFEAbH">
        <img src="https://img.shields.io/revolt/invite/qKgFEAbH?color=d61f3a&label=Stoat"
            alt="Stoat">
    </a>
</p>

<p align="center">
  <a href="#compatibility">Compatibility</a> |
  <a href="#development">Development</a> |
  <a href="#building">Building</a> |
  <a href="#download">Download</a> |
  <a href="#support">Support</a> |
  <a href="#license">License</a>
</p>

## Compatibility

The emulator is capable of running most commercial games at full speed, provided you meet the necessary hardware requirements.

A list of supported games will be available in future. Please be patient.

Check out our [website](https://eden-emu.dev) for the latest news on exciting features, monthly progress reports, and more!

[![Packaging status](https://repology.org/badge/vertical-allrepos/eden-emulator.svg)](https://repology.org/project/eden-emulator/versions)

## Contribute

To contribute to Eden; be it financially, code, bug reports, or otherwise, see our [Contributing guidelines](./CONTRIBUTING.md).

## Documentation

We have a user manual! See our [User Handbook](./docs/user/README.md).

## Building

See the [General Build Guide](docs/Build.md)

For information on provided development tooling, see the [Tools directory](./tools)

## Download

You can download the latest releases from [our release page](https://git.eden-emu.dev/eden-emu/eden/releases).

Save us some bandwidth! We have [mirrors available](./docs/user/ThirdParty.md#mirrors) as well.

## License

Eden is licensed under the GPLv3 (or any later version). Refer to the [LICENSE.txt](https://git.eden-emu.dev/eden-emu/eden/src/branch/master/LICENSE.txt) file.

## Special thanks

Super special thanks to Cloudflare for preventing the git server from blowing up.

- Yuzu
- Ryujinx
- Sudachi
- Citron
- Torzu
- Suyu
- Ryubing

And everyone who continues or had contributed to the project! <3
