#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
from pathlib import Path

def main():
    base_dir = Path(__file__).resolve().parent
    result_dir = base_dir / "test_result" / "贪污罪"

    files = sorted(result_dir.glob("*.json"))
    if not files:
        print(f"未找到文件: {result_dir}/*.json")
        return

    total_files = len(files)
    correct_files = 0
    wrong_list = []

    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:
            wrong_list.append((f.name, f"JSON 读取失败: {e}"))
            continue

        # 叶子节点来自判决书的部分
        leaf = data.get("leaf_nodes_from_judgement", {})
        if not leaf:
            wrong_list.append((f.name, "无 leaf_nodes_from_judgement"))
            continue

        # 找出不一致的叶子节点（value 与 from_judgement 不相等）
        bad_nodes = []
        for k, v in leaf.items():
            v_val = bool(v.get("value", False))
            j_val = bool(v.get("from_judgement", False))
            if v_val != j_val:
                bad_nodes.append(k)

        if not bad_nodes:
            correct_files += 1
        else:
            wrong_list.append((f.name, f"不一致叶子节点: {', '.join(bad_nodes)}"))

    precision = correct_files / total_files if total_files else 0.0

    print(f"总文件数: {total_files}")
    print(f"全对文件数: {correct_files}")
    print(f"正确率: {precision:.4f}")

    if wrong_list:
        print("\n有问题的文件：")
        for name, reason in wrong_list:
            print(f"- {name}: {reason}")

if __name__ == "__main__":
    main()