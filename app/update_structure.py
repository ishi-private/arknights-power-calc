#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
STRUCTURE.md のツリー部分を現在のフォルダ構成で自動更新するスクリプト。
Stop hook から呼び出される。ツリー以外の説明文はそのまま保持する。
"""

import os
import re

# スクリプト自身の位置から repo ルートを特定
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))       # app/
REPO_ROOT = os.path.normpath(os.path.join(_SCRIPT_DIR, ".."))  # repo ルート
STRUCTURE_FILE = os.path.join(REPO_ROOT, "STRUCTURE.md")

# ツリーに表示しないディレクトリ名
EXCLUDE_DIRS = {".git", "__pycache__"}

# 中身を展開せず「N ファイル」とまとめるディレクトリ名
COLLAPSE_DIRS = {"images", "xlsx"}


def build_tree(root: str, prefix: str = "") -> list[str]:
    """ディレクトリツリーを文字列リストで返す（再帰）"""
    try:
        entries = sorted(os.scandir(root), key=lambda e: (not e.is_dir(), e.name.lower()))
    except PermissionError:
        return []

    entries = [e for e in entries if e.name not in EXCLUDE_DIRS]

    lines = []
    for i, entry in enumerate(entries):
        is_last = (i == len(entries) - 1)
        connector   = "└── " if is_last else "├── "
        child_prefix = "    " if is_last else "│   "

        if entry.is_dir():
            if entry.name in COLLAPSE_DIRS:
                count = sum(1 for _ in os.scandir(entry.path))
                lines.append(f"{prefix}{connector}{entry.name}/  （{count} ファイル）")
            else:
                lines.append(f"{prefix}{connector}{entry.name}/")
                lines.extend(build_tree(entry.path, prefix + child_prefix))
        else:
            lines.append(f"{prefix}{connector}{entry.name}")

    return lines


def generate_tree() -> str:
    """STRUCTURE.md に埋め込むツリー文字列を生成する"""
    root_name = os.path.basename(REPO_ROOT)
    lines = [f"{root_name}/"] + build_tree(REPO_ROOT)
    return "\n".join(lines)


def update_structure_md(new_tree: str) -> None:
    """STRUCTURE.md 内の最初のコードブロックをツリーで差し替える"""
    if not os.path.exists(STRUCTURE_FILE):
        print("[update_structure] STRUCTURE.md が見つかりません")
        return

    with open(STRUCTURE_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    # 最初の ``` ... ``` ブロックを置換
    pattern = r"```\n.*?```"
    replacement = f"```\n{new_tree}\n```"
    new_content, count = re.subn(pattern, replacement, content, count=1, flags=re.DOTALL)

    if count == 0:
        print("[update_structure] コードブロックが見つかりません")
        return

    if new_content == content:
        return  # 変更なし

    with open(STRUCTURE_FILE, "w", encoding="utf-8") as f:
        f.write(new_content)
    print("[update_structure] STRUCTURE.md を更新しました")


if __name__ == "__main__":
    update_structure_md(generate_tree())
