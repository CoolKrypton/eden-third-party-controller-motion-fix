#!/usr/bin/env bash
# Rebuild a self contained history out of the shallow clone.
#
# This working copy was cloned with --depth, so it stops at 26a03d2: that commit
# is a graft (see .git/shallow) whose parent objects were never downloaded.
# GitHub refuses such a pack:
#     remote: fatal: did not receive expected object b7c1ded...
#     error: remote unpack failed: index-pack failed
# `git fetch --unshallow` would fix it properly, but git.eden-emu.dev is not
# reachable from here and there is no GitHub mirror (eden-emu/eden is 404).
#
# So: turn the shallow boundary into a root commit and re-attach our two commits
# on top, preserving each commit's original tree, author and message. The result
# is a thin but complete history that GitHub can unpack, and the working tree is
# byte for byte what it is now.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

BASE=26a03d2473787abf3223b2d0e65b291eee00c1e1
MID=6526fcd
TIP=3a8a900
OUT=publish-main

commit_tree() {  # <tree> <parent-or-empty> <source-commit> <message-file>
    local tree="$1" parent="$2" src="$3" msg="$4"
    # Read each field separately; NUL separated reads are unreliable in bash.
    local an ae ad cn ce cdt
    an=$(git log -1 --format=%an "$src")
    ae=$(git log -1 --format=%ae "$src")
    ad=$(git log -1 --format=%aI "$src")
    cn=$(git log -1 --format=%cn "$src")
    ce=$(git log -1 --format=%ce "$src")
    cdt=$(git log -1 --format=%cI "$src")
    local args=()
    [[ -n "$parent" ]] && args+=(-p "$parent")
    GIT_AUTHOR_NAME="$an" GIT_AUTHOR_EMAIL="$ae" GIT_AUTHOR_DATE="$ad" \
    GIT_COMMITTER_NAME="$cn" GIT_COMMITTER_EMAIL="$ce" GIT_COMMITTER_DATE="$cdt" \
        git commit-tree "$tree" "${args[@]}" -F "$msg"
}

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "=== 1/4 根提交: 上游快照 ${BASE:0:7} ==="
git log -1 --format=%B "$BASE" > "$TMP/m1"
printf '\n[republished] Shallow clone boundary; upstream ancestors were not available.\n' >> "$TMP/m1"
C1=$(commit_tree "$(git rev-parse "${BASE}^{tree}")" "" "$BASE" "$TMP/m1")
echo "  -> ${C1:0:10}"

echo "=== 2/4 ${MID:0:7} 体感修复 ==="
git log -1 --format=%B "$MID" > "$TMP/m2"
C2=$(commit_tree "$(git rev-parse "${MID}^{tree}")" "$C1" "$MID" "$TMP/m2")
echo "  -> ${C2:0:10}"

echo "=== 3/4 ${TIP:0:7} 构建脚本与 SDL3 补丁 ==="
git log -1 --format=%B "$TIP" > "$TMP/m3"
C3=$(commit_tree "$(git rev-parse "${TIP}^{tree}")" "$C2" "$TIP" "$TMP/m3")
echo "  -> ${C3:0:10}"

echo "=== 4/4 建立分支 ${OUT} ==="
git branch -f "$OUT" "$C3"

echo
echo "=== 校验: 新分支工作树必须与当前一致 ==="
# Compare the two trees directly; `git diff --cached` cannot take two commits.
if git diff --quiet "$OUT" "$TIP"; then
    echo "  ${OUT} 与 ${TIP} 的工作树完全一致 ✓"
else
    echo "  不一致 ✗" >&2
    git diff --stat "$OUT" "$TIP" >&2
    exit 1
fi
echo
git log --oneline "$OUT"
cat <<EOF

完成。推送:
  git push -u github ${OUT}:main
EOF
