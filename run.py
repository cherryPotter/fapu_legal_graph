#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run.py
======

给定事实描述与图谱（GraphML），按照图谱的逻辑从入度为 0 的节点开始调用大模型，
逐层推理直到叶子节点。运行结束后输出所有节点的判断结果，并重点列出叶子节点。
"""

import argparse
import os
import sys
import json
from pathlib import Path
from typing import Dict, Tuple, Optional, List
from openai import OpenAI
import networkx as nx

def normalize_operation(operation: str) -> str:
    """将 operation 规范化为 '与' 或 '或'，默认返回 '与'。
    支持中英文格式：'或'/'OR' 和 '与'/'AND'
    """
    if not operation:
        return '与'
    ops = {op.strip() for op in operation.split(',') if op.strip()}
    if not ops:
        return '与'
    
    # 检查是否包含 OR（或）操作
    has_or = False
    # 检查是否包含 AND（与）操作
    has_and = False
    
    for op in ops:
        op_upper = op.upper()
        if op == '或' or op_upper == 'OR':
            has_or = True
        if op == '与' or op_upper == 'AND':
            has_and = True
    
    # 如果同时存在 OR 和 AND，优先使用 OR（任一满足即可）
    if has_or and has_and:
        return '或'
    if has_or:
        return '或'
    # 默认返回 '与'
    return '与'


class LLMClient:

    def __init__(self, model: str = "deepseek-v3.2"):
        self.model = "deepseek-v3.2",
        #self._ready = False

        self._client = OpenAI(
            base_url='https://qianfan.baidubce.com/v2',
            api_key='bce-v3/ALTAK-Anxari1XeAB7mzDSLj3Mm/bf2a97a529785f2bdd9871e38c71b3c2cbb62852'
        )

    def ask(self, facts: str, question: str) -> Tuple[bool, str]:
        
        user_content = f"【事实】\n{facts}\n\n【问题】\n{question}\n\n请以“是/否 + 理由”的形式回答。"

        try:
            response = self._client.chat.completions.create(
                model="deepseek-v3.2",
                messages=[
                    {'role': 'system', 'content': '''你是法律推理助手。请阅读事实描述并回答问题, 回复yes/no，json回复，例如{{"answer": "yes"}}'''},
                    {'role': 'user', 'content': user_content},
                ],
                temperature=0.2,
                response_format={"type": "json_object"},
            )
            answer_text = response.choices[0].message.content.strip()
            print(question, answer_text)
            
            # 直接解析JSON（使用JSON格式后响应保证是有效JSON）
            result = json.loads(answer_text)
            answer_value = result.get('answer', '').lower()
            reason = result.get('reason', '')
            
            # 转换为布尔值
            if answer_value in ('yes', '是', 'true', '1'):
                return True, reason
            elif answer_value in ('no', '否', 'false', '0'):
                return False, reason
            else:
                # 如果answer字段值无法识别，默认返回False
                print(f'警告: 无法识别answer值 "{answer_value}"，默认返回False')
                return False, reason if reason else answer_text
                    
        except json.JSONDecodeError as e:
            print(f'错误: JSON解析失败 ({e})')
            raise ValueError(f'LLM返回的JSON格式无效: {e}')
        except Exception as exc:
            print(f'错误: LLM 调用失败 ({exc})')
            raise


class GraphExecutor:
    """按照拓扑顺序执行图谱推理。"""

    def __init__(self, graph: nx.DiGraph, llm: LLMClient, facts: str):
        self.graph = graph
        self.llm = llm
        self.facts = facts
        self.results: Dict[str, bool] = {}
        self.explanations: Dict[str, str] = {}

    def run(self) -> Dict[str, bool]:
        order = list(nx.topological_sort(self.graph))
        for node in order:
            preds = list(self.graph.predecessors(node))
            if not preds:
                value, answer = self._evaluate_leaf(node)
                self.results[node] = value
                self.explanations[node] = answer
            else:
                value, reason = self._evaluate_internal(node, preds)
                self.results[node] = value
                self.explanations[node] = reason
        return self.results

    def _evaluate_leaf(self, node: str) -> Tuple[bool, str]:
        data = self.graph.nodes[node]
        prompt = data.get('prompt') or f"根据事实，判断“{node}”是否成立。"
        question = f"{prompt}\n请只回答“是”或“否”，并给出简短理由。"
        return self.llm.ask(self.facts, question)

    def _evaluate_internal(self, node: str, preds: List[str]) -> Tuple[bool, str]:
        op = normalize_operation(self.graph.nodes[node].get('operation', '与'))
        inputs = []
        for pred in preds:
            if pred not in self.results:
                raise RuntimeError(f'节点 {pred} 尚未计算，无法计算 {node}')
            inputs.append(self.results[pred])

        print("===========hhhh========op:", op)
        if op == '或':
            value = any(inputs)
            details = '、'.join(f"{p}:{'是' if self.results[p] else '否'}" for p in preds)
            reason = f"规则“或”计算，任一条件满足即可。输入：{details}"
        else:
            value = all(inputs)
            details = '、'.join(f"{p}:{'是' if self.results[p] else '否'}" for p in preds)
            reason = f"规则“与”计算，全部条件需满足。输入：{details}"
        return value, reason

    def summary(self) -> str:
        lines = []
        for node, value in self.results.items():
            explanation = self.explanations.get(node, '')
            lines.append(f"{node}: {'是' if value else '否'}\n  理由: {explanation}")

        leaves = [n for n in self.graph.nodes if self.graph.out_degree(n) == 0]
        leaf_lines = [f"  - {leaf}: {'是' if self.results.get(leaf) else '否'}"
                      for leaf in leaves if leaf in self.results]

        return (
            "=== 节点结果 ===\n" +
            "\n".join(lines) +
            "\n\n=== 叶子节点 ===\n" +
            ("\n".join(leaf_lines) if leaf_lines else "  (无)")
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='根据事实文本执行图谱推理')
    parser.add_argument('graphml', type=str, help='图谱 GraphML 文件，例如 受贿罪_correct.graphml')
    parser.add_argument('-f', '--facts-file', type=str, required=True,
                        help='包含判决书事实部分的文本文件')
    parser.add_argument('-o', '--output', type=str, default=None,
                        help='可选，将结果保存到指定文件')
    return parser.parse_args()


def main():
    args = parse_args()

    graph_path = Path(args.graphml).expanduser()
    facts_path = Path(args.facts_file).expanduser()

    if not graph_path.exists():
        print(f"错误: 找不到图谱文件 {graph_path}")
        sys.exit(1)
    if not facts_path.exists():
        print(f"错误: 找不到事实文件 {facts_path}")
        sys.exit(1)

    facts_text = facts_path.read_text(encoding='utf-8').strip()
    if not facts_text:
        print("错误: 事实文件为空")
        sys.exit(1)

    try:
        G = nx.read_graphml(str(graph_path))
    except Exception as exc:
        print(f"错误: 无法读取 GraphML 文件 ({exc})")
        sys.exit(1)

    if not G.is_directed():
        G = G.to_directed()

    print(f"成功加载图：节点 {G.number_of_nodes()}，边 {G.number_of_edges()}")

    llm = LLMClient()
    executor = GraphExecutor(G, llm, facts_text)
    executor.run()
    report = executor.summary()

    if args.output:
        out_path = Path(args.output).expanduser()
        out_path.write_text(report, encoding='utf-8')
        print(f"推理结果已写入 {out_path}")
    else:
        print(report)


if __name__ == '__main__':
    main()

