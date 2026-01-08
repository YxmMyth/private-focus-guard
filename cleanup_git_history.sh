#!/bin/bash
# Git 历史清理脚本 - 移除敏感信息
# 警告：这会重写 git 历史，如果已经推送到远程需要 force push

echo "⚠️  警告：此操作将重写 git 历史"
echo "建议先备份：git clone . ../backup"
echo ""

# 使用 git filter-branch 删除敏感文件
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch WEEK2_PROGRESS.md RECOVERY_CHECKLIST.md" \
  --prune-empty --tag-name-filter cat -- --all

# 清理备份和引用
rm -rf .git/refs/original/
git reflog expire --expire=now --all
git gc --prune=now --aggressive

echo "✅ Git 历史已清理"
echo "如果已推送到 GitHub，需要运行：git push origin --force --all"
