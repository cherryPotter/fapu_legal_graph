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
from itertools import count
from typing import Dict, Tuple, Optional, List, Any
from openai import OpenAI
import networkx as nx


# ========== 计算器工具定义 (用于大模型 Tool Use) ==========
CALCULATOR_TOOL = {
    "type": "function",
    "function": {
        "name": "calculate",
        "description": "执行算术运算表达式。支持 +、-、*、/、括号。表达式中的变量应已替换为具体数值。",
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "算术表达式，例如 '70000.0 * 0.8' 或 '(150000 + 30000) * 0.15'。只能包含数字、小数点、运算符和括号。"
                }
            },
            "required": ["expression"]
        }
    }
}


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


def evaluate_arithmetic_expression(expr: str, variable_values: Dict[str, Any]) -> float:
    """
    计算算术表达式
    
    Args:
        expr: 算术表达式字符串，如 "变量1+变量2*3"
        variable_values: 变量名到值的映射
    
    Returns:
        计算结果（浮点数）
    """
    def _coerce_numeric(value: Any, var_name: Optional[str] = None) -> float:
        """将数值或数值字符串转换为数值。"""
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            return float(value.strip())
        raise RuntimeError(
            f"变量 {var_name} 的值无法转换为数字: {value}"
            if var_name
            else f"值无法转换为数字: {value}"
        )

    # 将百分数字面量预处理为 Python 可计算的小数
    expr_normalized = re.sub(
        r'(\d+(?:\.\d+)?)\s*%',
        lambda match: str(float(match.group(1)) / 100.0),
        expr
    )

    # 替换中文运算符和比较符
    expr_normalized = expr_normalized.replace('≥', '>=').replace('≤', '<=').replace('≠', '!=')

    # 基于已知变量名分词，兼容 "变量24"、")12" 这类隐式乘法写法。
    # 优先匹配变量名（按长度降序），这样以数字开头的变量名（如"2008年..."）能被完整识别
    sorted_var_names = sorted(variable_values.keys(), key=len, reverse=True)
    tokens = []
    i = 0
    while i < len(expr_normalized):
        ch = expr_normalized[i]

        if ch.isspace():
            i += 1
            continue

        # 优先尝试匹配变量名（包括以数字开头的变量名如"2008年1月1日之后工作年限_数值"）
        matched_var = None
        for var_name in sorted_var_names:
            if expr_normalized.startswith(var_name, i):
                matched_var = var_name
                break
        if matched_var is not None:
            tokens.append(str(_coerce_numeric(variable_values[matched_var], matched_var)))
            i += len(matched_var)
            continue

        # 再尝试匹配数字字面量
        number_match = re.match(r'(?:\d+(?:\.\d+)?|\.\d+)', expr_normalized[i:])
        if number_match:
            tokens.append(number_match.group(0))
            i += len(number_match.group(0))
            continue

        # 支持整除运算符 //
        if expr_normalized[i:i+2] == '//':
            tokens.append('//')
            i += 2
            continue

        if ch in '+-*/()':
            tokens.append(ch)
            i += 1
            continue

        raise RuntimeError(f"算术表达式包含无法解析的片段: {expr_normalized[i:i+20]}")

    expr_parts = []
    prev_token = None
    for token in tokens:
        if prev_token is not None:
            prev_is_operand = prev_token == ')' or re.fullmatch(r'(?:\d+(?:\.\d+)?|\.\d+)', prev_token)
            curr_is_operand = token == '(' or re.fullmatch(r'(?:\d+(?:\.\d+)?|\.\d+)', token)
            if prev_is_operand and curr_is_operand:
                expr_parts.append('*')
        expr_parts.append(token)
        prev_token = token

    expr_eval = ''.join(expr_parts)
    
    # 安全地计算表达式
    try:
        # 使用 eval 计算表达式（注意：在生产环境中应该使用更安全的方法）
        result = eval(expr_eval, {"__builtins__": {}}, {})
        return float(result)
    except Exception as e:
        raise RuntimeError(f"计算算术表达式失败: {expr}, 错误: {e}")


def normalize_operation(operation: str) -> str:
    """将 operation 规范化为 '与'、'或'、'非'、'ARITHMETIC'、'CONDITIONAL'、'COMPARISON'，默认返回 '与'。"""
    if not operation:
        return '与'
    
    # 检查是否是特殊操作类型
    op_upper = operation.upper()
    if op_upper in ['ARITHMETIC', 'CONDITIONAL', 'COMPARISON']:
        return op_upper
    
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
        self.results: Dict[str, Any] = {}  # 支持布尔值和数值
        self.explanations: Dict[str, str] = {}

    
    def call_llm_for_node(self, question_text: str, node_type="逻辑"):
        """
        调用 LLM 处理单个节点问题
        
        Args:
            question_text: 单个问题文本
            node_type: 节点类型（"逻辑"或"数值"）
        
        Returns:
            dict: 包含 question, answer, evidence, value_cny 的字典
        """
        # 根据节点类型调整 system_prompt
        if node_type == "数值":
            system_prompt = """你是法律推理助手。请阅读事实描述并回答问题。如果问题要求返回数值（如金额、刑期、数量等），请从事实中提取或计算该数值。

请以 JSON 格式返回结果，格式如下：
{
  "question": "问题原文",
  "answer": 数值（如金额、刑期、数量等），不含单位,
  "evidence": "支撑该回答的要点或理由原文片段",
  "value_cny": 具体数字（如金额、刑期、数量等），不含单位
}

value_cny 字段必须填写具体的 JSON number 数值，不能是字符串、百分号、布尔值或 null！！！"""
            
            user_prompt = f"""【事实】{self.facts}

【问题】{question_text}

question: 问题原文；answer: 数值；evidence: 支撑该回答的要点或理由原文片段，必须填写；value_cny: 必须返回具体的 JSON number 数值（如金额、刑期、数量等），不能为 null，不能带单位，不能写成字符串

数字与区间问题必须执行"先抽取/计算，后判断"的流程：
- 先从【事实】中抽取该问题对应的"唯一关键数值"。
- 再根据区间边界进行比较判断。
- 最后核验数字是否在区间范围内。
- 若问题是责任比例类数值，请直接返回 0 到 1 之间的小数，例如 0.7、0.5、0.07，不要返回 70 或 70%。
- 仅回答本问题即可，不用参考其他问题或定义

请返回 JSON 格式的结果。"""
        else:
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
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.0,
            max_tokens=4096,  # API 限制最大值为 8192
            response_format={"type": "json_object"}  # 要求返回 JSON 格式
        )
        
        content = response.choices[0].message.content
        content_json = self.extract_outer_json(content)
        content=self.clean_json_markdown_chars(content_json)

        #print(f"response:   {response.choices[0].message.content}\t\t after content: {content}")
        if not content:
            raise RuntimeError("LLM 返回内容为空")
        
        # 解析 JSON
        try:
            data = json.loads(content)
            # 验证数据结构
            if "answer" not in data:
                raise RuntimeError(f"LLM 返回格式不正确，缺少 answer 字段: {data}")
            return data
        except (json.JSONDecodeError, Exception) as e:
            raise RuntimeError(f"解析 LLM 响应失败: {e}, 响应内容: {content[:200]}")


    def _is_pure_number(self, node_name: str) -> bool:
        """检查节点名称是否是纯数字"""
        try:
            # 尝试转换为浮点数
            float(str(node_name).strip())
            return True
        except (ValueError, AttributeError, TypeError):
            return False
    
    def _parse_numeric_value(self, node_name: str) -> float:
        """将节点名称解析为数字值"""
        try:
            return float(str(node_name).strip())
        except (ValueError, AttributeError, TypeError):
            return None

    def _is_ratio_node(self, node_name: str) -> bool:
        return node_name in {"主要责任比例", "次要责任比例", "撞行人增加的责任比例"} or "责任比例" in node_name

    def _coerce_numeric_value(self, value: Any, *, node_name: Optional[str] = None, default: float = 0.0) -> float:
        """将模型返回值或中间结果转换为数值；责任比例节点统一为 0~1。"""
        numeric_value = self._parse_optional_numeric_value(value, node_name=node_name)
        if numeric_value is None:
            return default

        if node_name and self._is_ratio_node(node_name) and numeric_value > 1.0 and numeric_value <= 100.0:
            return numeric_value / 100.0
        return numeric_value

    def _parse_optional_numeric_value(self, value: Any, *, node_name: Optional[str] = None) -> Optional[float]:
        if value is None or isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            numeric_value = float(value)
        elif isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            try:
                if text.endswith("%"):
                    numeric_value = float(text[:-1].strip()) / 100.0
                else:
                    numeric_value = float(text)
            except ValueError:
                return None
        else:
            return None

        if node_name and self._is_ratio_node(node_name) and numeric_value > 1.0 and numeric_value <= 100.0:
            return numeric_value / 100.0
        return numeric_value

    def _extract_numeric_from_evidence(self, evidence: str, *, node_name: Optional[str] = None) -> float:
        if not evidence:
            return 0.0

        mg_match = re.search(r'(\d+(?:\.\d+)?)\s*mg/100ml', evidence, re.IGNORECASE)
        if mg_match:
            return self._coerce_numeric_value(mg_match.group(1), node_name=node_name)

        percent_match = re.search(r'(\d+(?:\.\d+)?)\s*%', evidence)
        if percent_match:
            return self._coerce_numeric_value(percent_match.group(0), node_name=node_name)

        number_match = re.search(r'(\d+(?:\.\d+)?)', evidence)
        if number_match:
            return self._coerce_numeric_value(number_match.group(1), node_name=node_name)

        return 0.0

    def run(self) -> Dict[str, bool]:
        """执行图谱推理：先批量处理入度为 0 的节点，然后按拓扑顺序执行到叶子节点。"""
        # 第一步：找出所有入度为 0 的节点并批量处理
        zero_indegree_nodes = [n for n in self.graph.nodes if self.graph.in_degree(n) == 0]
        print(f"zero_indegree_nodes: {len(zero_indegree_nodes)}")
        
        for i, node in enumerate(zero_indegree_nodes):
            # 检查是否是纯数字节点
            if self._is_pure_number(node):
                # 直接使用数字值，不调用 LLM
                numeric_value = self._parse_numeric_value(node)
                self.results[node] = numeric_value
                self.explanations[node] = f"常量数值: {numeric_value}"
                print(f"[{i}] node: {node}, value: {numeric_value} (常量数值)")
                continue
            
            # 获取节点属性
            node_attrs = self.graph.nodes[node]
            node_type = node_attrs.get("type", "逻辑")  # 默认是"逻辑"
            node_prompt = node_attrs.get("prompt", "")  # 获取用户定义的提示词
            
            # 构建问题文本：如果有用户定义的 prompt，就用它；否则根据节点类型使用默认提示词
            if node_prompt:
                question_text = f"{node_prompt}\n\n节点名称：{node}，节点类型应该是{node_type}"
            else:
                # 根据节点类型使用不同的默认提示词
                if node_type == "数值":
                    question_text = f"根据输入的事实，回答【{node}】的具体数值是多少。"
                else:
                    question_text = f"根据事实，判断问题【{node}】是否成立。必须回答是或否，不确定的回答否。"
            
            # 调用 LLM，带重试
            node_response = None
            max_retries = 3
            base_delay = 2.0
            for attempt in range(max_retries):
                try:
                    node_response = self.call_llm_for_node(question_text, node_type=node_type)
                    break
                except Exception as e:
                    if attempt < max_retries - 1:
                        wait_time = base_delay * (2 ** attempt)
                        time.sleep(wait_time)
                    else:
                        raise
            
            # 处理结果：根据节点类型决定返回数值还是布尔值
            answer = node_response.get("answer", False)
            evidence = node_response.get("evidence", "")
            value_cny = node_response.get("value_cny")
            
            
            # 判断节点类型：纯数字、定义为"数值"类型、或逻辑类型
            is_numeric_type = (node_type == "数值")
            
            if is_numeric_type:
                parsed_value = self._parse_optional_numeric_value(value_cny, node_name=node)
                if parsed_value is None:
                    extracted_value = self._extract_numeric_from_evidence(evidence, node_name=node)
                    normalized_value = extracted_value
                else:
                    normalized_value = parsed_value
                self.results[node] = normalized_value
                print(f"[{i}] node: {node}, value: {normalized_value} (数值), evidence: {evidence}")
                self.explanations[node] = f"evidence: {evidence}, value: {normalized_value}"
            else:
                # 逻辑类型：返回布尔值
                self.results[node] = bool(answer)
                print(f"[{i}] node: {node}, value: {bool(answer)}, evidence: {evidence}")
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
            
            # 统一处理所有节点：根据 operation 类型和节点属性判断
            value, reason = self._evaluate_internal(node, preds)
            
            # 将结果存储到 results 中，以便后续节点使用
            self.results[node] = value
            self.explanations[node] = reason
            print(f"[inference] node: {node}, value: {value}, reason: {reason}")
        
        print("=========Done=========")


    def _evaluate_internal(self, node: str, preds: List[str]) -> Tuple[Any, str]:
        """评估内部节点（统一处理所有节点类型）"""
        node_attrs = self.graph.nodes[node]
        op = normalize_operation(node_attrs.get('operation', '与'))
        
        # 获取前置节点的值
        pred_values = {}
        for pred in preds:
            if pred not in self.results:
                raise RuntimeError(f'节点 {pred} 尚未计算，无法计算 {node}')
            pred_values[pred] = self.results[pred]
        
        # 检查是否是逻辑门节点（有特殊属性）
        has_conditional_calc = node_attrs.get('conditional_calculation')
        has_arithmetic_rules = node_attrs.get('arithmetic_rules')
        has_comparison_op = node_attrs.get('comparison_op')
        
        # 处理 CONDITIONAL（条件判断）
        if op == 'CONDITIONAL':
            if has_conditional_calc:
                # 结果节点直接执行条件判断
                return self._evaluate_conditional(node, pred_values, node_attrs)
            else:
                # 如果没有条件判断规则，按标准逻辑运算处理（默认"与"）
                pred_bool_values = [bool(v) for v in pred_values.values()]
                value = all(pred_bool_values)
                details = '、'.join(f"{p}:{'是' if bool(self.results[p]) else '否'}" for p in preds)
                reason = f'''规则"与"计算，全部条件需满足。输入：{details}'''
                return value, reason
        
        # 处理 ARITHMETIC（算术运算）
        elif op == 'ARITHMETIC':
            if has_arithmetic_rules:
                # 结果节点直接执行算术运算
                return self._evaluate_arithmetic(node, pred_values, node_attrs)
            else:
                # 如果没有算术规则，按标准逻辑运算处理（默认"与"）
                pred_bool_values = [bool(v) for v in pred_values.values()]
                value = all(pred_bool_values)
                details = '、'.join(f"{p}:{'是' if bool(self.results[p]) else '否'}" for p in preds)
                reason = f'''规则"与"计算，全部条件需满足。输入：{details}'''
                return value, reason
        
        # 处理 COMPARISON（比较运算）
        elif op == 'COMPARISON':
            if has_comparison_op:
                # 结果节点直接执行比较运算
                return self._evaluate_comparison(node, pred_values, node_attrs)
            else:
                # 如果没有比较运算符，按标准逻辑运算处理（默认"与"）
                pred_bool_values = [bool(v) for v in pred_values.values()]
                value = all(pred_bool_values)
                details = '、'.join(f"{p}:{'是' if bool(self.results[p]) else '否'}" for p in preds)
                reason = f'''规则"与"计算，全部条件需满足。输入：{details}'''
                return value, reason
        
        # 处理标准逻辑运算（与/或/非）
        else:
            pred_bool_values = [bool(v) for v in pred_values.values()]
            if op == '或':
                value = any(pred_bool_values)
                details = '、'.join(f"{p}:{'是' if bool(self.results[p]) else '否'}" for p in preds)
                reason = f'''规则"或"计算，任一条件满足即可。输入：{details}'''
            elif op == '非':
                if not pred_bool_values:
                    raise RuntimeError(f'节点 {node} 的前置为空，无法进行"非"计算')
                if len(pred_bool_values) == 1:
                    value = not pred_bool_values[0]
                    details = f"{preds[0]}:{'是' if bool(self.results[preds[0]]) else '否'}"
                    reason = f'''规则"非"计算，对前置结果取反。输入：{details}'''
                else:
                    value = not any(pred_bool_values)
                    details = '、'.join(f"{p}:{'是' if bool(self.results[p]) else '否'}" for p in preds)
                    reason = f'''规则"非"计算，任一前置为真则结果为假。输入：{details}'''
            else:  # 与
                value = all(pred_bool_values)
                details = '、'.join(f"{p}:{'是' if bool(self.results[p]) else '否'}" for p in preds)
                reason = f'''规则"与"计算，全部条件需满足。输入：{details}'''
            return value, reason
    
    def _parse_condition_key(self, key: str) -> Tuple[Optional[str], bool]:
        """
        解析条件键名，提取条件名称和状态
        
        Args:
            key: 条件键名，如 "一级条件成立"、"二级条件不成立"
        
        Returns:
            tuple: (条件名称, 是否成立)，如 ("一级条件", True) 或 ("二级条件", False)
        """
        # 注意：必须先检查 "不成立"（更长的后缀），再检查 "成立"，否则会误匹配
        if key.endswith("不成立"):
            condition_name = key[:-3]  # 去掉"不成立"
            return condition_name, False
        elif key.endswith("成立"):
            condition_name = key[:-2]  # 去掉"成立"
            return condition_name, True
        else:
            # 无法解析
            return None, False
    
    def _evaluate_conditional(self, gate_node: str, pred_values: Dict[str, Any], node_attrs: Dict) -> Tuple[Any, str]:
        """评估条件判断规则（支持任意嵌套）"""
        # 读取条件判断的计算规则
        conditional_calculation_str = node_attrs.get('conditional_calculation', '{}')
        conditional_inputs_str = node_attrs.get('conditional_inputs', '[]')
        conditional_conditions_str = node_attrs.get('conditional_conditions', '{}')
        
        try:
            conditional_calculation = json.loads(conditional_calculation_str)
            conditional_inputs = json.loads(conditional_inputs_str)
            conditional_conditions = json.loads(conditional_conditions_str)
        except:
            raise RuntimeError(f'节点 {gate_node} 的条件判断规则格式错误')
        
        # 递归函数：根据条件组合选择计算表达式
        def resolve_conditional_value(calc_dict, conditions_dict):
            """
            递归解析条件判断结构
            
            Args:
                calc_dict: 计算规则字典，如 {"一级条件成立": {...}, "一级条件不成立": [...]}
                conditions_dict: 条件名称字典，如 {"一级条件": "条件A", "二级条件": "条件B"}
            
            Returns:
                计算表达式（字符串、数字、列表）或嵌套字典
            """
            if not isinstance(calc_dict, dict):
                # 如果不是字典，直接返回（可能是字符串、数字或列表）
                return calc_dict
            
            # 遍历字典的每个键值对
            for key, value in calc_dict.items():
                # 解析键名，提取条件名称和状态（成立/不成立）
                condition_name, is_positive = self._parse_condition_key(key)
                
                if condition_name is None:
                    # 无法解析的键，跳过
                    continue
                
                # 获取实际的条件节点名称
                actual_condition = conditions_dict.get(condition_name, "")
                if not actual_condition:
                    continue
                
                # 检查条件是否成立
                condition_result = bool(self.results.get(actual_condition, False))
                
                # 判断是否匹配当前分支
                if (is_positive and condition_result) or (not is_positive and not condition_result):
                    # 匹配当前分支
                    if isinstance(value, dict):
                        # 继续递归处理嵌套结构
                        nested_result = resolve_conditional_value(value, conditions_dict)
                        if nested_result is not None:
                            return nested_result
                    elif isinstance(value, (str, list, int, float)):
                        # 找到最终的计算表达式
                        return value
                    else:
                        # 其他类型，直接返回
                        return value
            
            # 如果没有找到匹配的分支，返回 None
            return None
        
        # 执行递归解析
        calc_expr = resolve_conditional_value(conditional_calculation, conditional_conditions)
        
        if calc_expr is None:
            raise RuntimeError(f'节点 {gate_node} 无法找到匹配的计算表达式')
        
        # 如果是列表，取第一个
        if isinstance(calc_expr, list):
            calc_expr = calc_expr[0] if calc_expr else "0"
        
        # 如果是数字，直接返回
        if isinstance(calc_expr, (int, float)):
            normalized_value = self._coerce_numeric_value(calc_expr, node_name=gate_node)
            reason = f"条件判断：根据条件组合选择数值 {normalized_value}"
            return normalized_value, reason
        
        # 执行计算表达式（字符串）
        try:
            # 获取输入变量的值
            variable_values = {}
            for input_var in conditional_inputs:
                if input_var in self.results:
                    variable_values[input_var] = self._coerce_numeric_value(self.results[input_var], node_name=input_var)
            
            # 计算表达式
            result = evaluate_arithmetic_expression(str(calc_expr), variable_values)
            result = self._coerce_numeric_value(result, node_name=gate_node)
            reason = f"条件判断：根据条件组合选择表达式 '{calc_expr}'，计算结果: {result}"
            return result, reason
        except Exception as e:
            raise RuntimeError(f'节点 {gate_node} 执行计算表达式失败: {calc_expr}, 错误: {e}')
    
    def _evaluate_arithmetic(self, gate_node: str, pred_values: Dict[str, Any], node_attrs: Dict) -> Tuple[Any, str]:
        """评估算术运算规则 - 使用大模型 Tool Use 调用计算器"""
        arithmetic_rules_str = node_attrs.get('arithmetic_rules', '[]')
        try:
            arithmetic_rules = json.loads(arithmetic_rules_str)
        except:
            raise RuntimeError(f'节点 {gate_node} 的算术规则格式错误')
        
        if not arithmetic_rules or len(arithmetic_rules) == 0:
            raise RuntimeError(f'节点 {gate_node} 没有算术规则')
        
        # 使用第一个算术规则
        expr = arithmetic_rules[0]
        
        # 检测表达式类型：如果包含比较运算符，应该使用比较运算处理
        comparison_ops = ['>=', '<=', '==', '!=', '>', '<']
        has_comparison = any(op in expr for op in comparison_ops)
        
        if has_comparison:
            # 这是一个比较表达式，重定向到比较运算处理
            # 尝试提取比较运算符
            comparison_op = None
            for op in comparison_ops:
                if op in expr:
                    comparison_op = op
                    break
            if comparison_op:
                # 临时设置 comparison_op 属性
                temp_attrs = dict(node_attrs)
                temp_attrs['comparison_op'] = comparison_op
                return self._evaluate_comparison_expression(gate_node, expr, pred_values, temp_attrs)
        
        # 获取变量值（确保为数值类型）
        variable_values = {}
        for var_name, var_value in pred_values.items():
            variable_values[var_name] = self._coerce_numeric_value(var_value, node_name=var_name)
        
        # 尝试使用 Tool Use 方式调用大模型计算
        try:
            return self._evaluate_arithmetic_with_tool(gate_node, expr, variable_values)
        except Exception as tool_error:
            # Tool use 失败，回退到本地计算
            print(f"[WARN] Tool use 计算失败，回退到本地计算: {tool_error}")
            try:
                result = evaluate_arithmetic_expression(expr, variable_values)
                result = self._coerce_numeric_value(result, node_name=gate_node)
                reason = f"算术运算(本地)：执行表达式 '{expr}'，计算结果: {result}"
                return result, reason
            except Exception as local_error:
                raise RuntimeError(f'节点 {gate_node} 执行算术表达式失败: {expr}, tool错误: {tool_error}, 本地错误: {local_error}')
    
    def _evaluate_arithmetic_with_tool(self, gate_node: str, expr: str, variable_values: Dict[str, float]) -> Tuple[float, str]:
        """使用大模型 Tool Use 执行算术运算，失败时回退到本地计算"""
        # 准备变量说明
        var_descriptions = [f"- {name}: {value}" for name, value in variable_values.items()]
        
        system_prompt = """你是一个精确的计算器助手。
你的任务是将给定的算术表达式中的变量替换为具体数值，然后调用 calculate 工具进行计算。

规则：
1. 直接将变量名替换为对应的数值
2. 保持运算符和括号不变
3. 不要自己计算结果，必须调用 calculate 工具
4. 表达式可以包含：数字、小数点、+、-、*、/、//（整除）和括号

支持的运算符：
- + 加法
- - 减法  
- * 乘法
- / 除法（浮点除）
- // 整除（向下取整）

示例：
变量：threshold = 70000.0, factor = 0.8
表达式：threshold * 0.8
你应该调用：calculate(expression="70000.0 * 0.8")

示例2：
变量：years = 3.18, one = 1
表达式：years // one
你应该调用：calculate(expression="3.18 // 1")"""

        user_prompt = f"""请计算以下表达式：

变量值：
{chr(10).join(var_descriptions)}

原始表达式：{expr}

请调用 calculate 工具，将变量替换为数值后传入。"""

        try:
            # 调用大模型（启用 tool use）
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                tools=[CALCULATOR_TOOL],
                tool_choice={"type": "function", "function": {"name": "calculate"}},
                temperature=0.0
            )
            
            message = response.choices[0].message
            
            # 处理 tool call
            if message.tool_calls and len(message.tool_calls) > 0:
                tool_call = message.tool_calls[0]
                if tool_call.function.name == "calculate":
                    args = json.loads(tool_call.function.arguments)
                    expression_to_calc = args["expression"]
                    
                    # 本地安全计算（二次验证）
                    result = self._safe_eval(expression_to_calc)
                    
                    return result, f"算术运算(Tool)：表达式 '{expr}' → '{expression_to_calc}'，结果: {result}"
            
            # 如果没有 tool call，尝试从返回内容中解析
            if message.content:
                # 尝试提取计算结果
                extracted_result = self._extract_number_from_text(message.content)
                if extracted_result is not None:
                    return extracted_result, f"算术运算(文本)：表达式 '{expr}'，结果: {extracted_result}"
        
        except Exception as e:
            # API 调用失败，会在外层捕获
            raise RuntimeError(f"Tool use 调用失败: {e}")
        
        raise RuntimeError("大模型未返回有效的 tool call 或计算结果")
    
    def _extract_number_from_text(self, text: str) -> Optional[float]:
        """从文本中提取数字（支持普通数字和科学计数法）"""
        if not text:
            return None
        
        # 尝试匹配 JSON 中的 result 或 value 字段
        try:
            # 尝试提取 JSON
            json_match = re.search(r'\{[^}]+\}', text)
            if json_match:
                data = json.loads(json_match.group(0))
                for key in ['result', 'value', 'answer', 'calculation']:
                    if key in data and isinstance(data[key], (int, float)):
                        return float(data[key])
        except:
            pass
        
        # 尝试匹配数字（包括科学计数法）
        # 匹配模式：整数.小数 或 科学计数法
        patterns = [
            r'-?\d+\.?\d*(?:[eE][+-]?\d+)?',  # 科学计数法
            r'-?\d+\.\d+',  # 小数
            r'-?\d+',  # 整数
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                try:
                    return float(match)
                except ValueError:
                    continue
        
        return None
    
    def _evaluate_comparison_expression(self, gate_node: str, expr: str, pred_values: Dict[str, Any], node_attrs: Dict) -> Tuple[bool, str]:
        """使用大模型 Tool 执行比较运算
        
        将整个比较表达式（如 "a >= b * 3"）交给大模型 Tool 计算
        """
        # 准备变量说明
        var_descriptions = [f"- {name}: {value}" for name, value in pred_values.items()]
        
        system_prompt = """你是一个精确的比较运算助手。
你的任务是将给定的比较表达式中的变量替换为具体数值，然后调用 calculate 工具进行计算。

规则：
1. 直接将变量名替换为对应的数值
2. 保持比较运算符（>=, <=, >, <, ==, !=）不变
3. 如果操作数包含算术运算（如 b * 3 或 a // 1），保持运算结构
4. 不要自己计算结果，必须调用 calculate 工具
5. 表达式可以包含：数字、小数点、+、-、*、/、//（整除）、括号和比较运算符

支持的运算符：
- + 加法, - 减法, * 乘法, / 除法（浮点除）, // 整除（向下取整）
- >=, <=, >, <, ==, != 比较运算

示例1：
变量：a = 9500.0, b = 3000.0, 3 = 3.0
表达式：a >= b * 3
你应该调用：calculate(expression="9500.0 >= 3000.0 * 3")

示例2：
变量：years = 3.18, one = 1
表达式：(years // one) >= 3
你应该调用：calculate(expression="3.18 // 1 >= 3")

示例3：
变量：x = 100.0, y = 50.0
表达式：x > y
你应该调用：calculate(expression="100.0 > 50.0")"""

        user_prompt = f"""请计算以下比较表达式：

变量值：
{chr(10).join(var_descriptions)}

原始表达式：{expr}

请调用 calculate 工具，将变量替换为数值后传入。
注意：如果表达式右侧有算术运算（如 "b * 3"），请确保替换后保持运算结构。"""

        try:
            # 调用大模型（启用 tool use）
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                tools=[CALCULATOR_TOOL],
                tool_choice={"type": "function", "function": {"name": "calculate"}},
                temperature=0.0
            )
            
            message = response.choices[0].message
            
            # 处理 tool call
            if message.tool_calls and len(message.tool_calls) > 0:
                tool_call = message.tool_calls[0]
                if tool_call.function.name == "calculate":
                    args = json.loads(tool_call.function.arguments)
                    expression_to_calc = args["expression"]
                    
                    # 本地安全计算（支持比较运算）
                    result = self._safe_eval_comparison(expression_to_calc)
                    
                    return result, f"比较运算(Tool)：表达式 '{expr}' → '{expression_to_calc}'，结果: {result}"
            
            # 如果没有 tool call，回退到本地处理
            print(f"[WARN] 比较运算 Tool use 未返回 tool call，回退到本地处理")
            return self._evaluate_comparison_local(gate_node, expr, pred_values, node_attrs)
        
        except Exception as e:
            # API 调用失败，回退到本地处理
            print(f"[WARN] 比较运算 Tool use 失败，回退到本地处理: {e}")
            return self._evaluate_comparison_local(gate_node, expr, pred_values, node_attrs)
    
    def _safe_eval_comparison(self, expression: str) -> bool:
        """安全地计算比较表达式"""
        if not expression or not isinstance(expression, str):
            raise ValueError(f"表达式无效: {expression}")
        
        # 清理表达式
        cleaned = expression.strip()
        
        # 允许的数字、运算符、括号和比较符
        allowed_chars = set("0123456789.+-*/() >=<!")
        
        # 检查每个字符
        invalid_chars = [c for c in cleaned if c not in allowed_chars]
        if invalid_chars:
            raise ValueError(f"表达式包含非法字符: {invalid_chars}, 表达式: {cleaned}")
        
        # 安全检查通过，执行计算
        try:
            result = eval(cleaned, {"__builtins__": {}}, {})
            return bool(result)
        except Exception as e:
            raise RuntimeError(f"计算失败: {cleaned}, 错误: {e}")
    
    def _evaluate_comparison_local(self, gate_node: str, expr: str, pred_values: Dict[str, Any], node_attrs: Dict) -> Tuple[bool, str]:
        """本地执行比较运算（作为 Tool use 的 fallback）"""
        # 提取比较运算符
        comparison_ops = ['>=', '<=', '==', '!=', '>', '<']
        comparison_op = None
        for op in comparison_ops:
            if op in expr:
                comparison_op = op
                break
        
        if not comparison_op:
            raise RuntimeError(f'表达式中未找到比较运算符: {expr}')
        
        parts = expr.split(comparison_op)
        if len(parts) != 2:
            raise RuntimeError(f'比较表达式格式错误: {expr}')
        
        left_expr = parts[0].strip()
        right_expr = parts[1].strip()
        
        # 获取左右操作数的值（支持简单算术）
        left_val = self._get_operand_value_with_arithmetic(left_expr, pred_values)
        right_val = self._get_operand_value_with_arithmetic(right_expr, pred_values)
        
        # 执行比较
        if comparison_op == '>=':
            result = left_val >= right_val
        elif comparison_op == '<=':
            result = left_val <= right_val
        elif comparison_op == '>':
            result = left_val > right_val
        elif comparison_op == '<':
            result = left_val < right_val
        elif comparison_op in ('==', '='):
            result = left_val == right_val
        elif comparison_op == '!=':
            result = left_val != right_val
        else:
            raise RuntimeError(f'未知的比较运算符: {comparison_op}')
        
        return result, f"比较运算(本地)：{left_expr} ({left_val}) {comparison_op} {right_expr} ({right_val})，结果: {result}"
    
    def _get_operand_value_with_arithmetic(self, operand_expr: str, pred_values: Dict[str, Any]) -> float:
        """获取操作数的值，支持简单算术运算"""
        # 1. 如果是纯数字，直接返回
        try:
            return float(operand_expr)
        except ValueError:
            pass
        
        # 2. 如果是变量名，直接查找
        if operand_expr in pred_values:
            return self._coerce_numeric_value(pred_values[operand_expr], node_name=operand_expr)
        
        # 3. 包含算术运算，尝试替换变量后计算
        # 按长度排序变量名，避免短名干扰长名
        temp_expr = operand_expr
        for var_name in sorted(pred_values.keys(), key=len, reverse=True):
            if var_name in temp_expr:
                value = self._coerce_numeric_value(pred_values[var_name], node_name=var_name)
                temp_expr = temp_expr.replace(var_name, str(value))
        
        # 4. 尝试计算替换后的表达式
        try:
            result = eval(temp_expr, {"__builtins__": {}}, {})
            return float(result)
        except Exception as e:
            raise RuntimeError(f'无法计算操作数 "{operand_expr}"，替换后: "{temp_expr}"，错误: {e}')
    
    def _safe_eval(self, expression: str) -> float:
        """安全地计算算术表达式（支持 + - * / // 和括号）"""
        if not expression or not isinstance(expression, str):
            raise ValueError(f"表达式无效: {expression}")
        
        # 清理表达式
        cleaned = expression.strip()
        
        # 允许的数字、运算符、括号和空格
        # 单独处理 //（整除），所以需要允许 /
        allowed_chars = set("0123456789.+-*/() ")
        
        # 检查每个字符
        invalid_chars = [c for c in cleaned if c not in allowed_chars]
        if invalid_chars:
            raise ValueError(f"表达式包含非法字符: {invalid_chars}, 表达式: {cleaned}")
        
        # 安全检查通过，执行计算
        try:
            result = eval(cleaned, {"__builtins__": {}}, {})
            return float(result)
        except Exception as e:
            raise RuntimeError(f"计算失败: {cleaned}, 错误: {e}")
    
    def _evaluate_comparison(self, gate_node: str, pred_values: Dict[str, Any], node_attrs: Dict) -> Tuple[bool, str]:
        """评估比较运算规则"""
        def _coerce_numeric(value: Any) -> float:
            return self._coerce_numeric_value(value)

        comparison_op = node_attrs.get('comparison_op', '>=')
        
        # 比较运算应该有两个前置节点：变量和阈值
        if len(pred_values) != 2:
            raise RuntimeError(f'节点 {gate_node} 的比较运算应该有两个前置节点（变量和阈值），实际有 {len(pred_values)} 个')
        
        # 获取变量和阈值
        pred_nodes = list(pred_values.keys())
        left_node = pred_nodes[0]
        right_node = pred_nodes[1]
        
        left_value = pred_values[left_node]
        right_value = pred_values[right_node]
        
        # 如果阈值是字符串且是纯数字，转换为数字
        if isinstance(right_value, str):
            if self._is_pure_number(right_value):
                right_value = self._parse_numeric_value(right_value)
        
        # 如果变量值是字符串且是纯数字，转换为数字
        if isinstance(left_value, str):
            if self._is_pure_number(left_value):
                left_value = self._parse_numeric_value(left_value)
        
        # 执行比较运算
        try:
            left_num = self._coerce_numeric_value(left_value, node_name=left_node)
            right_num = self._coerce_numeric_value(right_value, node_name=right_node)
            
            if comparison_op == '>=':
                result = left_num >= right_num
            elif comparison_op == '<=':
                result = left_num <= right_num
            elif comparison_op == '>':
                result = left_num > right_num
            elif comparison_op == '<':
                result = left_num < right_num
            elif comparison_op == '==':
                result = left_num == right_num
            elif comparison_op == '=':
                result = left_num == right_num
            elif comparison_op == '!=':
                result = left_num != right_num
            else:
                raise RuntimeError(f'不支持的比较运算符: {comparison_op}')
            
            reason = f"比较运算：{left_node}({left_value}) {comparison_op} {right_node}({right_value}) = {result}"
            return result, reason
        except (ValueError, TypeError) as e:
            raise RuntimeError(f'节点 {gate_node} 执行比较运算失败: {left_value} {comparison_op} {right_value}, 错误: {e}')
    

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

    def extract_outer_json(self,text):
        """
        从文本中提取最外层的JSON结构（保留{}）
        :param text: 包含JSON的混合文本
        :return: 提取到的最外层JSON字符串，无则返回None
        """
        first_brace = text.find("{")
        if first_brace == -1:
            return None

        brace_count = 0
        end_index = -1
        for i in range(first_brace, len(text)):
            char = text[i]
            if char == "{":
                brace_count += 1
            elif char == "}":
                brace_count -= 1
                if brace_count == 0:
                    end_index = i
                    break

        if end_index == -1:
            return None
        return text[first_brace:end_index + 1]

    def clean_json_markdown_chars(self,json_str):
        """
        清理JSON字符串中的Markdown标识和干扰字符，保留合法JSON结构
        :param json_str: 待清理的JSON字符串
        :return: 清理后的合法JSON字符串（若无法修复则返回None）
        """
        if not json_str:
            return None

        # 修复正则语法错误，修正星号匹配规则
        markdown_patterns = [
            # 1. 代码块符号（`或 ```）
            (r"`+", ""),
            # 2. Markdown标题（# 及空格）
            (r"#{1,6}\s*", ""),
            # 3. 引用符号（> 及空格）
            (r">\s*", ""),
            # 4. 删除线（~~）
            (r"~~", ""),
            # 5. 列表符号（-/*/+ 开头的符号，避免误删JSON中的-数字）
            (r"(?<=\s)[-*+]\s*", ""),
            # 6. 分隔线（---/***）
            (r"-{3,}|[*]{3,}", ""),
            # 7. 链接格式 [文本](链接) → 保留文本
            (r"\[(.*?)\]\(.*?\)", r"\1"),
            # 8. 多余的星号（*）→ 修复正则语法错误：^\*+ 而非 ^\\*+
            (r"(?<=\s)\*+(?=\s)|^\*+|\*+$", ""),
            # 9. 表格竖线（|）（避免误删JSON中的|，仅匹配单独的|）
            (r"(?<=\s)\|(?=\s)", ""),
            # 10. 多余的空格/换行（JSON允许空格，但过多会影响解析）
            (r"\s+", " "),
        ]

        # 逐一遍历清理规则
        cleaned_str = json_str
        for pattern, replacement in markdown_patterns:
            cleaned_str = re.sub(pattern, replacement, cleaned_str)

        # 最后清理首尾多余字符
        cleaned_str = cleaned_str.strip()

        # 验证清理后的JSON是否合法，不合法则返回None
        try:
            json.loads(cleaned_str)
            return cleaned_str
        except json.JSONDecodeError:
            # 若仍不合法，可尝试进一步清理（如移除所有非JSON核心字符）
            # 保留JSON核心字符：{}[]:" ,0-9a-zA-Z_\u4e00-\u9fa5（中文）
            final_cleaned = re.sub(r'[^\{\}\[\]:",\s0-9a-zA-Z_\u4e00-\u9fa5]', '', cleaned_str)
            try:
                json.loads(final_cleaned)
                return final_cleaned
            except json.JSONDecodeError:
                return None


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
    #facts=open('fact.txt').readlines()
    
    run_inference(graph, facts, base_url=os.getenv("QWEN_API_BASE"), api_token=os.getenv("QWEN_API_KEY"), model=os.getenv("QWEN_MODEL_ID"))
    # run_inference(graph, facts, base_url="https://dashscope.aliyuncs.com/compatible-mode/v1", api_token="sk-fb0b02a253b74b2eb658565a322f0817",
    #               model="qwen-max")
    
