#!/usr/bin/env bash
# Push the source tree and the release tag to GitHub.
#
# The machine this repo was prepared on cannot reach GitHub (TLS handshake fails
# on every route; DNS resolves github.com to the reserved address 198.18.0.29).
# Enable a VPN / proxy first, then run this.
#
#   bash release/push.sh
#
# Uploading the release assets is a separate step, see release/PUSH.md
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

REMOTE_NAME="${REMOTE_NAME:-github}"
REMOTE_URL="${REMOTE_URL:-https://github.com/CoolKrypton/eden-third-party-controller-motion-fix.git}"
BRANCH="${BRANCH:-publish-main}"
TARGET="${TARGET:-main}"
TAG="${TAG:-v1.0-kp40}"

echo "=== 0/4 连通性检查 ==="
if ! git ls-remote "${REMOTE_URL}" >/dev/null 2>&1; then
    echo "无法访问 ${REMOTE_URL}" >&2
    echo "请先开启 VPN / 代理。若走 HTTP 代理:" >&2
    echo "  git config --global http.proxy  http://127.0.0.1:7890" >&2
    echo "  git config --global https.proxy http://127.0.0.1:7890" >&2
    exit 1
fi
echo "  GitHub 可达"

echo "=== 1/4 远端 ==="
if git remote get-url "${REMOTE_NAME}" >/dev/null 2>&1; then
    git remote set-url "${REMOTE_NAME}" "${REMOTE_URL}"
    echo "  已更新 ${REMOTE_NAME} -> ${REMOTE_URL}"
else
    git remote add "${REMOTE_NAME}" "${REMOTE_URL}"
    echo "  已添加 ${REMOTE_NAME} -> ${REMOTE_URL}"
fi

echo "=== 2/4 推送源码(完整历史) ==="
git push -u "${REMOTE_NAME}" "${BRANCH}:${TARGET}"

echo "=== 3/4 推送分支本身 ==="
git push "${REMOTE_NAME}" "${BRANCH}"

echo "=== 4/4 打 tag ==="
if git rev-parse "${TAG}" >/dev/null 2>&1; then
    echo "  tag ${TAG} 已存在, 跳过创建"
else
    git tag -a "${TAG}" -m "Eden fix build: motion on third party Switch controllers (BTP-KP40), MinGW native+LTO, plus a PGO variant"
    echo "  已创建 ${TAG}"
fi
git push "${REMOTE_NAME}" "${TAG}"

cat <<EOF

完成。源码与 tag 已推送。

下一步: 上传 Release 资产(需 gh auth login, 或直接在网页拖入)
  gh release create ${TAG} \\
    release/eden-windows-mingw-native-lto-2026-10-30.zip \\
    release/eden-windows-mingw-pgo-2026-10-30.zip \\
    --title "Eden — BTP-KP40 修复版 (Windows x64)" \\
    --notes-file release/RELEASE_NOTES.md
EOF
