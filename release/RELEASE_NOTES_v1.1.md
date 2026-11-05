## Eden — 多核 TLS 修复版 (v1.1-kp40) · Windows x64

在 v1.0-kp40 的基础上修复了**多核心模式下必现的硬卡死**。构建为 **MinGW GCC + PGO + LTO**
（profile 用 Dragon Quest VII Reimagined 实机采样采集），运行时依赖已全部打包，解压即用。

### 本版修复

**多核模式下游戏启动后卡死（核心修复）**

现象：开启「多核心 CPU 模拟」时，部分游戏启动后 8~40 秒内画面冻结、窗口无响应，
日志末尾是 dynarmic 的 `assert !is_executing`，紧随其后是 `FastmemCallback: unreachable`
和 `reg_alloc` 的一连串断言。

根因：客机纤程（guest fiber）会在**另一个宿主线程**上恢复执行，而 kernel 的
`tls_data` 是一个 `static inline thread_local`，在 `KernelCore::Impl` 里到处被直接访问。
开启 LTO 后，编译器可以把 TLS 地址提到热路径之外缓存起来，于是纤程迁移后仍然沿用旧地址，
**某个核读到了别的核的 TLS 块**，解析出错误的 KThread，重入了一个已经在运行的 JIT。

修复：把所有 `tls_data` 访问收敛到一个**非内联**访问器上，每次调用都重新解析 TLS 地址：

```cpp
[[gnu::noinline, gnu::noipa]]
static ThreadLocalData& GetTlsData() { return tls_data; }
```

`noipa` 在 GCC 上是必需的——否则 LTO 会把访问器重新内联回去，问题原样复现。
这也解释了为什么插桩版（`-fprofile-generate`，`LTO=OFF`）从来不会卡死：
没有跨 TU 内联，TLS 地址就不会被提前缓存。

上游对应修复见 PR #4497（2026-09-30）。

### 继承自 v1.0-kp40

- 第三方 Switch 手柄（如北通鲲鹏40）陀螺仪 / 体感失效修复
- 第三方手柄十字键映射修正（SDL 数据库里这类手柄十字键是 hat，不是 button）

### 安装

1. 解压到任意目录；
2. 双击 `eden.exe`，配置目录与存档沿用 `%APPDATA%\eden`；
3. 需要系统固件与 `prod.keys`（放在 `%APPDATA%\eden\keys\`）。

### 构建环境

- MSYS2 MinGW64 GCC 16.2.0 + Ninja + CMake
- `-O3 -march=native -mtune=native` + `-fprofile-use` + `-flto=8`
- Qt 6.12.0（动态链接，DLL 已随包提供）
