#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
给定事实描述与图谱（GraphML），按照图谱的逻辑从入度为 0 的节点开始调用大模型，
逐层推理直到叶子节点。运行结束后输出所有节点的判断结果，并重点列出叶子节点。
"""

import argparse
import os
import sys
import json
import re
from pathlib import Path
from typing import Dict, Tuple, Optional, List
from openai import OpenAI
import networkx as nx
from llm_client import *

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

class NodeResponse(BaseModel):
    """
    这里定义你希望大模型返回的数据结构。
    Field 中的 description 非常重要，它相当于给模型的'微型Prompt'。
    """
    question: str = Field(description="问题")
    answer: bool = Field(description="是或否")



def extract_facts_from_html(html_path: Path) -> str:
    """从 HTML 文件中提取【判决如下】之前的案件事实部分。
    
    Args:
        html_path: HTML 文件路径
        
    Returns:
        提取的案件事实文本（纯文本，已去除 HTML 标签）
    """
    html_content = html_path.read_text(encoding='utf-8')
    
    # 使用 BeautifulSoup 解析 HTML（如果可用）
    if HAS_BS4:
        soup = BeautifulSoup(html_content, 'html.parser')
        # 获取所有文本内容
        text = soup.get_text(separator='\n', strip=True)
    else:
        # 简单的 HTML 标签去除（如果 BeautifulSoup 不可用）
        text = re.sub(r'<[^>]+>', '', html_content)
        text = re.sub(r'\s+', ' ', text)
    
    # 查找【判决如下】或类似的关键词
    markers = ['【判决如下】', '【判决如下：】', '判决如下', '判决如下：', 
                '判决如下：', '判决如下：', '判决如下：', 
                '本院认为', '本院经审理查明']
    
    # 找到第一个匹配的标记位置
    split_pos = -1
    for marker in markers:
        pos = text.find(marker)
        if pos != -1:
            split_pos = pos
            break
    
    if split_pos != -1:
        # 提取标记之前的所有文本
        facts_text = text[:split_pos].strip()
    else:
        # 如果没有找到标记，返回全部文本（可能是纯文本文件）
        facts_text = text.strip()
    
    # 清理多余的空白字符
    facts_text = re.sub(r'\n\s*\n', '\n\n', facts_text)  # 多个换行合并为两个
    facts_text = re.sub(r'[ \t]+', ' ', facts_text)  # 多个空格合并为一个
    
    return facts_text


def extract_judgement_from_html(html_path: Path) -> str:
    """从 HTML 文件中提取【判决如下】之后的判决部分。
    
    Args:
        html_path: HTML 文件路径
        
    Returns:
        提取的判决文本（纯文本，已去除 HTML 标签）
    """
    html_content = html_path.read_text(encoding='utf-8')
    
    # 使用 BeautifulSoup 解析 HTML（如果可用）
    if HAS_BS4:
        soup = BeautifulSoup(html_content, 'html.parser')
        # 获取所有文本内容
        text = soup.get_text(separator='\n', strip=True)
    else:
        # 简单的 HTML 标签去除（如果 BeautifulSoup 不可用）
        text = re.sub(r'<[^>]+>', '', html_content)
        text = re.sub(r'\s+', ' ', text)
    
    # 查找【判决如下】或类似的关键词
    markers = ['【判决如下】', '【判决如下：】', '判决如下', '判决如下：']
    
    # 找到第一个匹配的标记位置
    split_pos = -1
    marker_found = None
    for marker in markers:
        pos = text.find(marker)
        if pos != -1:
            split_pos = pos
            marker_found = marker
            break
    
    if split_pos != -1:
        # 提取标记之后的所有文本
        judgement_text = text[split_pos + len(marker_found):].strip()
    else:
        # 如果没有找到标记，返回空字符串
        judgement_text = ""
    
    # 清理多余的空白字符
    judgement_text = re.sub(r'\n\s*\n', '\n\n', judgement_text)  # 多个换行合并为两个
    judgement_text = re.sub(r'[ \t]+', ' ', judgement_text)  # 多个空格合并为一个
    
    return judgement_text


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


def create_llm_client() -> LangchainLLMClient:
    """创建用于节点评估的 LLM 客户端。
    
    该客户端可以同时用于单节点推理和批量处理。
    
    Returns:
        配置好的 LangchainLLMClient 实例
    """
    # 创建 prompt 模板，支持 {facts} 和 {question} 作为输入变量
    prompt_template = PromptTemplate(
        prompt_name="node_evaluation",
        system_prompt="你是法律推理助手。请阅读事实描述并回答问题。",
        human_template='''【事实】\n{facts}\n\n【问题】\n{question}''',
        model_config={
            "model": "qwen-max",
            "max_tokens": 4096,
            "temperature": 0.1
        },
        input_variables=["facts", "question"]
    )
    
    return LangchainLLMClient(
        prompt_template=prompt_template,
        provider="qwen",
        structured_output_schema=NodeResponse
    )


class GraphExecutor:
    def __init__(self, graph: nx.DiGraph, llm: LangchainLLMClient, facts: str):
        self.graph = graph
        self.llm = llm
        self.facts = facts
        self.results: Dict[str, bool] = {}
        self.explanations: Dict[str, str] = {}

        self.judgement_results: Dict[str, bool] = {}

    def run(self) -> Dict[str, bool]:
        """执行图谱推理：先批量处理入度为 0 的节点，然后按拓扑顺序执行到叶子节点。"""
        # 第一步：找出所有入度为 0 的节点并批量处理
        zero_indegree_nodes = [n for n in self.graph.nodes if self.graph.in_degree(n) == 0]
        
        if zero_indegree_nodes:
            print(f"\n开始逐个处理 {len(zero_indegree_nodes)} 个入度为 0 的节点...")
            
            # 逐个调用 chat 方法
            print(f"处理结果:")
            for i, node in enumerate(zero_indegree_nodes, 1):
                question = f'根据事实，判断问题【{node}】是否成立。必须回答是或否，不确定的回答否。'
                # 调用 chat 方法
                response = self.llm.chat({"facts": self.facts, "question": question})
                
                # 处理结果：NodeResponse 对象有 answer 字段（bool 类型）
                
                value = bool(response.answer)
                
                self.results[node] = value
                self.explanations[node] = "root"
                print(f"  [{i}] {response}")
        
        # 第二步：按照拓扑顺序执行，处理其他节点直到叶子节点
        print(f"\n开始按拓扑顺序执行推理...")
        order = list(nx.topological_sort(self.graph))
        for node in order:
            # 如果节点已经计算过（通过 batch 处理），跳过
            if node in self.results:
                continue
                
            preds = list(self.graph.predecessors(node))
            
            # 内部节点：根据前置节点的结果计算
            value, reason = self._evaluate_internal(node, preds)
            self.results[node] = value
            self.explanations[node] = reason
        
        return self.results

    def _evaluate_leaf(self, graph: nx.DiGraph, llm: LangchainLLMClient, judgement_text: str) -> Dict[str, Tuple[bool, str]]:
        """使用判决书文本评估图中的叶子节点。
        
        Args:
            graph: 图谱（NetworkX DiGraph）
            llm: LLM 客户端
            judgement_text: 判决书"判决如下"之后的文本
            
        Returns:
            字典，键为叶子节点名称，值为 (是否成立, 理由) 的元组
        """
        if not judgement_text:
            print("警告: 判决文本为空，无法评估叶子节点")
            return {}
        
        # 获取所有叶子节点（出度为 0 的节点）
        leaf_nodes = [n for n in graph.nodes if graph.out_degree(n) == 0]
        
        if not leaf_nodes:
            print("警告: 图中没有叶子节点")
            return {}
        
        print(f"\n开始评估 {len(leaf_nodes)} 个叶子节点...")

        # 准备批量查询
        batch_queries = [
            {
                "facts": judgement_text,
                "question": f'根据判决书内容，判断问题【{node}】是否成立。必须回答是或否，不确定的回答否。'
            }
            for node in leaf_nodes
        ]
        
        # 调用 batch 方法
        batch_results = llm.batch(batch_queries)
        
        # 处理结果
        print(f"\n叶子节点评估结果:")
        for i, (node, result) in enumerate(zip(leaf_nodes, batch_results), 1):
            # 处理结果：NodeResponse 对象有 answer 字段（bool 类型）
            value = bool(result.answer)
            self.judgement_results[node] = value
            print(f"真实判决书: [{i}] {node}: {result}")


    def _evaluate_internal(self, node: str, preds: List[str]) -> Tuple[bool, str]:
        op = normalize_operation(self.graph.nodes[node].get('operation', '与'))
        inputs = []
        for pred in preds:
            if pred not in self.results:
                raise RuntimeError(f'节点 {pred} 尚未计算，无法计算 {node}')
            inputs.append(self.results[pred])

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
            #explanation = self.explanations.get(node, '')
            lines.append(f"{node}: {value}\n")

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

    # 根据文件扩展名判断是 HTML 还是纯文本文件
    if facts_path.suffix.lower() in ['.html', '.htm']:
        facts_text = extract_facts_from_html(facts_path)
        print(f"已从 HTML 文件提取案件事实，长度: {len(facts_text)} 字符")
    else:
        facts_text = facts_path.read_text(encoding='utf-8').strip()
    
    if not facts_text:
        print("错误: 事实文件为空或未能提取到内容")
        sys.exit(1)

    try:
        G = nx.read_graphml(str(graph_path))
    except Exception as exc:
        print(f"错误: 无法读取 GraphML 文件 ({exc})")
        sys.exit(1)

    if not G.is_directed():
        G = G.to_directed()

    print(f"成功加载图：节点 {G.number_of_nodes()}，边 {G.number_of_edges()}")
    # 打印入度为 0 的节点，便于确认推理起点
    # zero_indegree_nodes = [n for n in G.nodes if G.in_degree(n) == 0]
    # print(f"入度为 0 的节点({len(zero_indegree_nodes)}): {zero_indegree_nodes}")
    
    # 创建 LLM 客户端
    llm = create_llm_client()
    

    executor = GraphExecutor(G, llm, facts_text)
    executor.run()
    report = executor.summary()

    
    compare_report = ""
    # 提取判决文本并评估叶子节点
    if facts_path.suffix.lower() in ['.html', '.htm']:
        judgement_text = extract_judgement_from_html(facts_path)
    
    if judgement_text:
        print(f"\n已提取判决文本，长度: {len(judgement_text)} 字符")
        executor._evaluate_leaf(G, llm, judgement_text)
        
        # 打印对比结果
        print(f"\n=== 叶子节点对比结果 ===")
        compare_report += "=== 叶子节点对比结果 ===\n"
        leaf_nodes = [n for n in G.nodes if G.out_degree(n) == 0]
        for node in leaf_nodes:
            graph_result = executor.results.get(node)
            judgement_result = executor.judgement_results.get(node) if node in executor.judgement_results else None
            
            if judgement_result is not None:
                match = "✓" if graph_result == judgement_result else "✗"
                compare_report += f"{match} {node}:\n"
                compare_report += f"    图谱推理: {'是' if graph_result else '否'}\n"
                compare_report += f"    判决书评估: {'是' if judgement_result else '否'}\n"
                print(f"{match} {node}:")
                print(f"    图谱推理: {'是' if graph_result else '否'}")
                print(f"    判决书评估: {'是' if judgement_result else '否'}")
            else:
                print(f"? {node}: 图谱推理={'是' if graph_result else '否'} (判决书未评估)")
                compare_report += f"? {node}: 图谱推理={'是' if graph_result else '否'} (判决书未评估)\n"
    else:
        compare_report += "警告: 未能提取判决文本，跳过叶子节点评估\n"
    
    if args.output:
        out_path = Path(args.output).expanduser()
        out_path.write_text(report+"\n"+compare_report, encoding='utf-8')
        print(f"推理结果已写入 {out_path}")
    else:
        print(report)
        print(compare_report)


if __name__ == '__main__':
    main()

