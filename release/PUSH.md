# 推送到 GitHub — 操作说明

> **状态：已完成（2026-10-30 15:35）**
> 仓库：https://github.com/CoolKrypton/eden-third-party-controller-motion-fix
> Release：https://github.com/CoolKrypton/eden-third-party-controller-motion-fix/releases/tag/v1.0-kp40
> 以下内容保留作为复现步骤与故障记录。

## 两个坑（已解决，勿重踩）

**1. 本地是浅克隆，不能直接推**
`git rev-parse --is-shallow-repository` 为 `true`，只有 3 个提交，浅边界 `26a03d2`。
直接推会报 `remote: fatal: did not receive expected object ... / index-pack failed`
（GitHub 拿到的包引用了不存在的父对象）。`--no-thin` 无效。

`git fetch --unshallow` 才是正解，但 `git.eden-emu.dev` 连不上，且没有 GitHub 镜像
（`eden-emu/eden` 返回 404）。因此用 `release/rebuild-history.sh` 把浅边界重做成根提交，
再接上两个修复提交，得到一段自包含、GitHub 可解包的历史（工作树已校验完全一致）。
若哪天能连上上游，先 `git fetch --unshallow origin` 再推，可恢复真正的完整历史。

**2. 仓库名**
初版叫 `eden`，已重命名为 `eden-third-party-controller-motion-fix`。


本环境**无法访问 GitHub**（已验证：直连 / 系统代理 / 忽略证书三种方式全部 TLS 握手失败；
DNS 把 `github.com` 解析到保留地址 `198.18.0.29`，是典型的拦截特征；而 gitee.com 返回 200）。
所以下面这些步骤已经全部在本地准备好，你开好代理/VPN 后执行即可。

## 0. 先开代理 / VPN

确认连通性：

```bash
git ls-remote https://github.com/CoolKrypton/eden.git
# 或
curl -sS -o /dev/null -w "%{http_code}\n" https://api.github.com   # 应为 200
```

如果走 HTTP 代理（Clash / v2ray 等常见 `127.0.0.1:7890`）：

```bash
git config --global http.proxy  http://127.0.0.1:7890
git config --global https.proxy http://127.0.0.1:7890
# 用完可取消：
# git config --global --unset http.proxy && git config --global --unset https.proxy
```

## 1. 建仓库

在 https://github.com/new 创建一个**空仓库**（不要勾 README / .gitignore / LICENSE）。

- Owner: `CoolKrypton`（如果你的 GitHub 用户名不是这个，请把下面命令里的用户名改掉）
- Repository name: `eden`
- Visibility: **Public**

## 2. 推送源码（完整历史）

远端已经加好，直接推：

```bash
cd /f/MyCodes/c++/eden
git remote add github https://github.com/CoolKrypton/eden.git   # 已加过可跳过
git push -u github fix/third-party-gyro-calibration:main
```

如果你想连分支名一起保留：

```bash
git push -u github fix/third-party-gyro-calibration
```

改用 SSH（需先把公钥加到 GitHub）：

```bash
git remote set-url github git@github.com:CoolKrypton/eden.git
```

认证方式二选一：
- HTTPS：用 **Personal Access Token** 当密码（GitHub 已不支持账号密码）。
  勾选 `repo` 权限：https://github.com/settings/tokens
- SSH：`ssh-keygen -t ed25519` 后把 `~/.ssh/id_ed25519.pub` 加到
  https://github.com/settings/keys

## 3. 打 tag

```bash
git tag -a v1.0-kp40 -m "Eden fix build: motion on third party Switch controllers (BTP-KP40), MinGW native+LTO, plus PGO variant"
git push github v1.0-kp40
```

## 4. 上传 Release 资产

压缩包在 `release/` 下：

- `eden-windows-mingw-native-lto-2026-10-30.zip`
- `eden-windows-mingw-pgo-2026-10-30.zip`

网页上传：Releases → Draft a new release → 选 tag `v1.0-kp40` → 拖入两个 zip。
Release 描述直接用 `release/RELEASE_NOTES.md` 的内容。

命令行上传（需先 `gh auth login`）：

```bash
gh release create v1.0-kp40 \
  release/eden-windows-mingw-native-lto-2026-10-30.zip \
  release/eden-windows-mingw-pgo-2026-10-30.zip \
  --title "Eden — BTP-KP40 修复版 (Windows x64)" \
  --notes-file release/RELEASE_NOTES.md
```

## 一键脚本

```bash
bash release/push.sh          # 推源码 + tag（不含上传资产）
```

## 已提交内容清单

- `3a8a900` Add MinGW build tooling and preserve the SDL3 motion fix
- `6526fcd` Fix motion (gyro/accel) on third party Switch controllers with unprogrammed calibration

注意：陀螺仪修复位于 SDL3（CPM 下载到 `.cache/`，被 gitignore 忽略），
因此补丁源文件保存在 `tools/patches/sdl3/SDL_hidapi_switch.c`，
并由 `tools/patches/apply.sh` 在 CMake configure 之后自动重新套用。
全新克隆按仓库脚本构建即可完整复现本发布包。
