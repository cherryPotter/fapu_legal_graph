#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
给定事实描述与图谱（NetworkX 图对象），按照图谱的逻辑从入度为 0 的节点开始调用大模型，
逐层推理直到叶子节点。运行结束后输出所有节点的判断结果，并重点列出叶子节点。

使用原始 OpenAI API，不使用 LangChain。
"""

import os
import json
import re
import time
import traceback
from typing import Dict, Tuple, Optional, List, Any
from openai import OpenAI
import networkx as nx


def load_graph_from_graphml(graphml_file: str) -> nx.DiGraph:
    """
    从 GraphML 文件加载 networkx 图对象
    
    Args:
        graphml_file: GraphML 文件路径
    
    Returns:
        networkx.DiGraph: 有向图对象
    """
    if not os.path.exists(graphml_file):
        raise FileNotFoundError(f"GraphML 文件不存在: {graphml_file}")
    
    try:
        G = nx.read_graphml(graphml_file)
        if not G.is_directed():
            G = G.to_directed()
        return G
    except Exception as e:
        raise RuntimeError(f"无法读取 GraphML 文件: {e}")


def normalize_operation(operation: str) -> str:
    """将 operation 规范化为 '与'、'或'、'非'，默认返回 '与'。"""
    if not operation:
        return '与'
    ops = {op.strip() for op in operation.split(',') if op.strip()}
    if not ops:
        return '与'
    
    has_or = False
    has_and = False
    has_not = False
    
    for op in ops:
        op_upper = op.upper()
        if op == '或' or op_upper == 'OR':
            has_or = True
        if op == '与' or op_upper == 'AND':
            has_and = True
        if op == '非' or op_upper == 'NOT' or op == '!':
            has_not = True
    
    if has_not and not (has_or or has_and):
        return '非'
    if has_or and has_and:
        return '或'
    if has_or:
        return '或'
    return '与'





class GraphExecutor:
    def __init__(self, graph: nx.DiGraph, facts: str, base_url: Optional[str] = None, 
                 api_token: Optional[str] = None, model: str = "gpt-4o"):
        self.graph = graph
        self.facts = facts
        self.client = OpenAI(api_key=api_token, base_url=base_url)
        self.model = model
        self.results: Dict[str, bool] = {}
        self.explanations: Dict[str, str] = {}

    
    def call_llm_for_node(self, question_text: str):
        """
        调用 LLM 处理单个节点问题
        
        Args:
            question_text: 单个问题文本
        
        Returns:
            dict: 包含 question, answer, evidence, value_cny 的字典
        """
        system_prompt = """你是法律推理助手。请阅读事实描述并回答问题。若问题为否定表述（如以"不是""不属于""不构成"开头），回答"是"表示否定成立，回答"否"表示否定不成立。必须回答是或否，不确定的回答否。

请以 JSON 格式返回结果，格式如下：
{
  "question": "问题原文",
  "answer": true/false,
  "evidence": "支撑该回答的要点或理由原文片段",
  "value_cny": 数值或null
}"""
        
        user_prompt = f"""【事实】{self.facts}

【问题】{question_text}

question: 问题原文；answer: 是或否；evidence: 支撑该回答的要点或理由原文片段，必须填写；value_cny: 若问题涉及金额、刑期等判断、区间判断（例如"贪污数额在3万元以上不满20万元"），返回数值；否则为 null

数字与区间问题必须执行"先抽取/计算，后判断"的流程：
- 先从【事实】中抽取该问题对应的"唯一关键数值"。
- 再根据区间边界进行比较判断。
- 最后核验数字是否在区间范围内。
- 仅回答本问题即可，不用参考其他问题或定义

请返回 JSON 格式的结果。"""
        
        # 使用 OpenAI API 调用
        #print(f"=========user_prompt: {user_prompt}")
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.0,
            max_tokens=8192,  # API 限制最大值为 8192
            response_format={"type": "json_object"}  # 要求返回 JSON 格式
        )
        
        content = response.choices[0].message.content
        #print(f"=========answer: {content}")
        if not content:
            raise RuntimeError("LLM 返回内容为空")
        
        # 解析 JSON
        try:
            data = json.loads(content)
            #print(f"=========data: {data}")
            # 验证数据结构
            if "answer" not in data:
                raise RuntimeError(f"LLM 返回格式不正确，缺少 answer 字段: {data}")
            return data
        except (json.JSONDecodeError, Exception) as e:
            raise RuntimeError(f"解析 LLM 响应失败: {e}, 响应内容: {content[:200]}")


    def run(self) -> Dict[str, bool]:
        """执行图谱推理：先批量处理入度为 0 的节点，然后按拓扑顺序执行到叶子节点。"""
        # 第一步：找出所有入度为 0 的节点并批量处理
        zero_indegree_nodes = [n for n in self.graph.nodes if self.graph.in_degree(n) == 0]
        print(f"zero_indegree_nodes: {len(zero_indegree_nodes)}")
        
        for i, node in enumerate(zero_indegree_nodes):
            question_text = f"根据事实，判断问题【{node}】是否成立。必须回答是或否，不确定的回答否。"
            
            # 调用 LLM，带重试
            node_response = None
            max_retries = 3
            base_delay = 2.0
            for attempt in range(max_retries):
                try:
                    node_response = self.call_llm_for_node(question_text)
                except Exception as e:
                    if attempt < max_retries - 1:
                        wait_time = base_delay * (2 ** attempt)
                        time.sleep(wait_time)
                    else:
                        raise
            
            # 处理结果
            value = bool(node_response.get("answer", False))
            evidence = node_response.get("evidence", "")
            value_cny = node_response.get("value_cny")
            self.results[node] = value
            print(f"[{i}] node: {node}, value: {value}, evidence: {evidence}")
            self.explanations[node] = f"evidence: {evidence}, value_cny: {value_cny}"
        

        # 第二步：按照拓扑顺序执行，处理其他节点直到叶子节点
        order = list(nx.topological_sort(self.graph))
        for node in order:
            # 如果节点已经计算过（通过 LLM 处理），跳过
            if node in self.results:
                continue
                
            preds = list(self.graph.predecessors(node))
            
            # 如果没有前置节点，跳过（这种情况不应该发生，但为了安全）
            if not preds:
                continue
            
            # 内部节点：根据前置节点的结果计算
            value, reason = self._evaluate_internal(node, preds)
            # 将结果存储到 results 中，以便后续节点使用
            self.results[node] = value
            self.explanations[node] = reason
            print(f"[inference] node: {node}, value: {value}, reason: {reason}")
        
        print("=========Done=========")


    def _evaluate_internal(self, node: str, preds: List[str]) -> Tuple[bool, str]:
        """评估内部节点（非入度为0的节点）"""
        op = normalize_operation(self.graph.nodes[node].get('operation', '与'))
        pred_bool_values = []
        for pred in preds:
            if pred not in self.results:
                raise RuntimeError(f'节点 {pred} 尚未计算，无法计算 {node}')
            pred_bool_values.append(self.results[pred])

        if op == '或':
            value = any(pred_bool_values)
            details = '、'.join(f"{p}:{'是' if self.results[p] else '否'}" for p in preds)
            reason = f'''"规则"或"计算，任一条件满足即可。输入：{details}"'''
        elif op == '非':
            if not pred_bool_values:
                raise RuntimeError(f'节点 {node} 的前置为空，无法进行"非"计算')
            if len(pred_bool_values) == 1:
                value = not pred_bool_values[0]
                details = f"{preds[0]}:{'是' if pred_bool_values[0] else '否'}"
                reason = f'''规则"非"计算，对前置结果取反。输入：{details}'''
            else:
                value = not any(pred_bool_values)
                details = '、'.join(f"{p}:{'是' if self.results[p] else '否'}" for p in preds)
                reason = f'''规则"非"计算，任一前置为真则结果为假。输入：{details}'''
        else:
            value = all(pred_bool_values)
            details = '、'.join(f"{p}:{'是' if self.results[p] else '否'}" for p in preds)
            reason = f'''规则"与"计算，全部条件需满足。输入：{details}'''
        return value, reason

    def get_results(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有节点的结果
        
        Returns:
            字典，键为节点名称，值为包含 value 和 explanation 的字典
        """
        return {
            node: {
                "value": bool(self.results.get(node, False)),
                "explanation": self.explanations.get(node, "")
            }
            for node in self.graph.nodes
        }

    def get_leaf_nodes_results(self) -> Dict[str, Dict[str, Any]]:
        """
        获取叶子节点（出度为0的节点）的结果
        
        Returns:
            字典，键为叶子节点名称，值为包含 value 和 explanation 的字典
        """
        leaf_nodes = [n for n in self.graph.nodes if self.graph.out_degree(n) == 0]
        return {
            node: {
                "value": bool(self.results.get(node, False)),
                "explanation": self.explanations.get(node, "")
            }
            for node in leaf_nodes
        }


def run_inference(graph: nx.DiGraph, facts: str, base_url: Optional[str] = None, 
                  api_token: Optional[str] = None, model: str = "gpt-4o") -> Dict[str, Any]:
    
    executor = GraphExecutor(graph, facts, base_url=base_url, api_token=api_token, model=model)
    executor.run()
    
    #return {
    #    "all_nodes": executor.get_results(),
    #    "leaf_nodes": executor.get_leaf_nodes_results()
    #}


if __name__ == '__main__':

    graphml_path = "graph_data/djt贪污罪json图.graphml"
    # 加载图
    graph = load_graph_from_graphml(graphml_path)
    print(f"成功加载图：节点 {graph.number_of_nodes()}，边 {graph.number_of_edges()}")

    facts = "".join(open("note").readlines())
    
    run_inference(graph, facts, base_url=os.getenv("QWEN_API_BASE"), api_token=os.getenv("QWEN_API_KEY"), model=os.getenv("QWEN_MODEL_ID"))
    
    