# Eden 模拟器 — 北通鲲鹏40 (BTP-KP40) 修复版 / Windows x64

基于 [eden-emu/eden](https://git.eden-emu.dev/eden-emu/eden)，用 MinGW GCC（`-march=native -mtune=native -O3`，启用 LTO）编译。

## 这个版本修了什么

1. **陀螺仪 / 体感失效**（核心修复）
   北通鲲鹏40 这类第三方手柄只模拟了 Switch 协议的外层，SPI 校准区是空白的，
   读回来全是 `0xFFFF` —— 灵敏度系数和原始偏移都是 `-1`，导致换算时的除数为 0，
   每一个运动采样都变成 `inf` / `NaN`，模拟器收到的是垃圾数据。
   修复位置在 **SDL3 的 HIDAPI Switch 驱动**（`SDL_hidapi_switch.c`），
   因为 Eden 的 `enable_procon_driver` 默认是 `false`，手柄数据实际走 SDL 路径。
   为退化轴增加兜底缩放后，陀螺仪与加速度计恢复正常。

2. **ZL / ZR 无响应**
   排查结论：不是死区问题，也不是驱动问题。手柄的霍尔线性扳机在静止状态下被
   固件判定为“按到底”（SDL3 读到 `32767`），软件侧无法修正。
   **解决办法：在手柄上做一次扳机校准**（手柄侧的硬件校准），校准后 SDL3 能读到
   `0 → 32767` 的连续模拟量，ZL / ZR 即恢复正常。

3. **UI 不是中文**
   编译时开启了 `ENABLE_QT_TRANSLATION=ON` 以生成并嵌入 `zh_CN.qm`。
   另外：`Main_window::LoadTranslation()` 加载失败时会把配置写成 `en`，
   导致之后即使有语言包也一直走英文。若遇到英文界面，请检查
   `%APPDATA%\eden\config\qt-config.ini` 里的 `Paths\language` 是否为 `zh_CN`。

## 两个版本怎么选

| | 标准版 | PGO 版 |
|---|---|---|
| 文件 | `eden-windows-mingw-native-lto-*.zip` | `eden-windows-mingw-pgo-*.zip` |
| LTO | 是 | 是 |
| PGO | 否 | 是（用实际游玩采集的 profile 优化） |
| exe 体积 | 34.4 MB | 26.7 MB |

PGO 优化的是**代码路径**而不是具体游戏。Eden 的 dynarmic（CPU JIT）、
着色器重编译器、纹理解码是所有游戏共享的热路径，所以：

- **CPU 瓶颈的游戏**：预期 **5~15%** 帧率提升
- **GPU 瓶颈的游戏**：基本无变化

建议两版都试，用同一款游戏、同一场景对比帧率和帧时间稳定性。
如果差别不明显，说明瓶颈在 GPU，用标准版即可。

## 运行方式

解压后直接双击 `eden.exe`。目录下已包含全部运行时依赖（37 个 DLL）和
Qt 插件（`plugins/`）+ `qt.conf`，无需安装 MSYS2 或 Qt。

手柄需设为 **NS 模式**。

## 故障排查

- 提示 “no Qt platform plugin could be initialized”：确认 `qt.conf` 和
  `plugins/` 与 `eden.exe` 在同一目录，且解压时目录结构未被破坏。
- 想确认手柄数据是否正常：仓库 `tools/` 下有 `hid_dump.c`、`sdl3_bindings.c`
  两个诊断工具，可以打印原始 HID 报文和 SDL3 的轴值。

## 源码

仓库里 `tools/patches/sdl3/SDL_hidapi_switch.c` 是打过补丁的 SDL3 源文件。
因为 SDL3 由 CPM 下载到 `.cache/`（被 gitignore 忽略），全新克隆会拿到纯净版，
所以 `tools/patches/apply.sh` 会在 CMake configure 之后自动重新套用该补丁，
两个构建脚本都已经调用了它。直接按仓库里的脚本构建即可复现本发布包。
