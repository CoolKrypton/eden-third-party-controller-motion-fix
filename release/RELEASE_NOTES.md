## Eden — 北通鲲鹏40 (BTP-KP40) 修复版 · Windows x64

基于 [eden-emu/eden](https://git.eden-emu.dev/eden-emu/eden)，MinGW GCC 编译
（`-march=native -mtune=native -O3`，启用 LTO）。运行时依赖已全部打包，解压即用。

### 修复内容

**1. 陀螺仪 / 体感失效（核心修复）**

北通鲲鹏40 这类第三方手柄只模拟了 Switch 协议的外层，SPI 校准区是空白的，
读回来全是 `0xFFFF` —— 灵敏度系数和原始偏移都是 `-1`，换算时除数为 0，
每个运动采样都变成 `inf` / `NaN`，模拟器收到的是垃圾数据。

修复位置在 **SDL3 的 HIDAPI Switch 驱动**（`SDL_hidapi_switch.c`），
因为 Eden 的 `enable_procon_driver` 默认是 `false`，手柄数据实际走 SDL 路径。
为退化轴增加兜底缩放后，陀螺仪与加速度计恢复正常。

**2. ZL / ZR 无响应**

排查结论：不是死区问题。抓包显示手柄的霍尔线性扳机在静止状态下被判定为
“按到底”（SDL3 恒定读到 `32767`），软件侧无法修正。
**解决办法：在手柄上做一次扳机校准**，校准后 SDL3 能读到 `0 → 32767`
的连续模拟量，ZL / ZR 即恢复正常。

**3. UI 不是中文**

编译时开启了 `ENABLE_QT_TRANSLATION=ON`。另外
`MainWindow::LoadTranslation()` 加载失败时会把配置写成 `en`，
导致之后即使有语言包也一直走英文 —— 如遇英文界面，检查
`%APPDATA%\eden\config\qt-config.ini` 里 `Paths\language` 是否为 `zh_CN`。

### 两个资产怎么选

| | 标准版 | PGO 版 |
|---|---|---|
| 文件 | `eden-windows-mingw-native-lto-2026-10-30.zip` | `eden-windows-mingw-pgo-2026-10-30.zip` |
| LTO | 是 | 是 |
| PGO | 否 | 是（实际游玩采集的 profile） |
| exe 体积 | 32.8 MB | 25.4 MB |

PGO 优化的是**代码路径**而非具体游戏。Eden 的 dynarmic（CPU JIT）、
着色器重编译器、纹理解码是所有游戏共享的热路径，因此：

- **CPU 瓶颈的游戏**：预期 **5~15%** 帧率提升
- **GPU 瓶颈的游戏**：基本无变化

建议同游戏同场景实测对比。差别不明显说明瓶颈在 GPU，用标准版即可。

### 使用

解压后双击 `eden.exe`。手柄需设为 **NS 模式**。
无需安装 MSYS2 或 Qt，`plugins/` 与 `qt.conf` 已在包内。

### 从源码复现

陀螺仪修复位于 SDL3（CPM 下载到 `.cache/`，被 gitignore 忽略），因此：

- 补丁源文件保存在 `tools/patches/sdl3/SDL_hidapi_switch.c`
- `tools/patches/apply.sh` 在 CMake configure 之后自动重新套用（幂等）
- `tools/build-mingw.sh` 与 `tools/build-mingw-pgo.sh` 均已调用它

```bash
bash tools/build-mingw.sh            # 标准版
bash tools/build-mingw-pgo.sh gen    # PGO 第一阶段（插桩）
#  跑游戏采集 profile，正常关闭
bash tools/build-mingw-pgo.sh use    # PGO 第二阶段（优化）
```

### 提交

- `3a8a900` Add MinGW build tooling and preserve the SDL3 motion fix
- `6526fcd` Fix motion (gyro/accel) on third party Switch controllers with unprogrammed calibration
