#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pyvis.network import Network
import networkx as nx
import matplotlib
matplotlib.use('Agg')  # 使用非交互式后端
import matplotlib.pyplot as plt
import webbrowser
import os
import json
import argparse
import re
import ast

# 确保中文能够正确显示
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Noto Sans CJK SC', 'Arial Unicode MS', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False

# ==========================================
# 0. 从 graph_data 目录读取所有规则数据
# ==========================================
GRAPH_DATA_DIR = ""

def convert_logic_op(logic_op):
    """将中文逻辑操作符转换为英文"""
    if not logic_op:
        return "AND"
    logic_op = logic_op.strip()
    if logic_op == "与":
        return "AND"
    elif logic_op == "或":
        return "OR"
    elif logic_op == "非" or logic_op == "否":
        return "NOT"
    elif logic_op == "不互斥":
        return "NON_EXCLUSIVE"
    elif logic_op.upper() == "AND":
        return "AND"
    elif logic_op.upper() == "OR":
        return "OR"
    elif logic_op.upper() == "NOT":
        return "NOT"
    elif logic_op.upper() == "NON_EXCLUSIVE":
        return "NON_EXCLUSIVE"
    else:
        return "AND"  # 默认

def load_rules_from_json_files(file_list=None):
    graph_data_dir = os.path.join(os.path.dirname(__file__), GRAPH_DATA_DIR)
    
    if not os.path.exists(graph_data_dir):
        print(f"目录不存在: {graph_data_dir}")
        return [], []
    

    if file_list:
        json_files = []
        for file_name in file_list:
            if os.path.isabs(file_name):
                if os.path.exists(file_name):
                    json_files.append(file_name)
                else:
                    print(f"文件不存在: {file_name}")
            else:
                full_path = os.path.join(graph_data_dir, file_name)
                if os.path.exists(full_path):
                    json_files.append(full_path)
                else:
                    print(f"文件不存在: {full_path}")
        
        if not json_files:
            print(f"没有找到任何有效的 JSON 文件")
            return [], []
    else:
        # 获取所有 JSON 文件
        all_files = os.listdir(graph_data_dir)
        json_files = [
            os.path.join(graph_data_dir, f) 
            for f in all_files 
            if f.endswith('.json') and os.path.isfile(os.path.join(graph_data_dir, f))
        ]
        
        if not json_files:
            print(f"⚠️  在 {graph_data_dir} 目录下未找到 JSON 文件")
            return [], []
    

    all_rules = []
    case_types = []
    

    json_files.sort()
    
    print(f"📂 找到 {len(json_files)} 个 JSON 文件:")
    for json_file in json_files:
        print(f"  - {os.path.basename(json_file)}")
        
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 提取案由信息
            case_type = data.get("案由", "")
            if case_type:
                case_types.append(case_type)
                print(f"    案由: {case_type}")
            
            # 提取并融合"规则"数据，为每个规则添加案由信息
            if "规则" in data and isinstance(data["规则"], list):
                rule_count = 0
                for rule in data["规则"]:
                    rule_type = rule.get("类型", "")
                    if rule_type == "逻辑运算":
                        # 转换规则格式
                        converted_rule = {
                            "result": rule.get("结果", ""),
                            "conditions": rule.get("条件", []),
                            "logic": convert_logic_op(rule.get("计算方式", "与")),
                            "case_type": case_type  # 使用案由
                        }
                        
                        # 处理"结果"可能是字符串或数组的情况
                        result = converted_rule["result"]
                        if isinstance(result, list):
                            # 如果结果是数组，为每个结果创建一个规则
                            for r in result:
                                rule_copy = converted_rule.copy()
                                rule_copy["result"] = r
                                all_rules.append(rule_copy)
                                rule_count += 1
                        elif isinstance(result, str) and result:
                            all_rules.append(converted_rule)
                            rule_count += 1
                    elif rule_type == "算术运算":
                        # 处理算术运算类型
                        arithmetic_rules = rule.get("算术规则", [])
                        if not arithmetic_rules:
                            # 兼容旧格式：使用"算式"字段
                            arithmetic_rules = rule.get("算式", [])
                        
                        result = rule.get("结果", "")
                        if arithmetic_rules and result:
                            # 转换规则格式
                            converted_rule = {
                                "result": result,
                                "conditions": [],
                                "logic": "ARITHMETIC",
                                "arithmetic_rules": arithmetic_rules,
                                "case_type": case_type
                            }
                            
                            # 处理"结果"可能是字符串或数组的情况
                            if isinstance(result, list):
                                for r in result:
                                    rule_copy = converted_rule.copy()
                                    rule_copy["result"] = r
                                    all_rules.append(rule_copy)
                                    rule_count += 1
                            elif isinstance(result, str) and result:
                                all_rules.append(converted_rule)
                                rule_count += 1
                    elif rule_type == "集合":
                        conditions = rule.get("条件", [])
                        if isinstance(conditions, str):
                            conditions = [conditions]
                        elif not isinstance(conditions, list):
                            conditions = []
                        
                        result = rule.get("结果", "")
                        logic_op = rule.get("计算方式", "")
                        
                        if conditions and result:
                            # 转换规则格式
                            converted_rule = {
                                "result": result,
                                "conditions": conditions,
                                "logic": convert_logic_op(logic_op),
                                "case_type": case_type
                            }
                            
                            # 处理"结果"可能是字符串或数组的情况
                            if isinstance(result, list):
                                # 如果结果是数组，为每个结果创建一个规则
                                for r in result:
                                    rule_copy = converted_rule.copy()
                                    rule_copy["result"] = r
                                    all_rules.append(rule_copy)
                                    rule_count += 1
                            elif isinstance(result, str) and result:
                                all_rules.append(converted_rule)
                                rule_count += 1
                    elif rule_type == "条件判断":
                        # 处理条件判断类型
                        inputs = rule.get("输入", [])
                        if isinstance(inputs, str):
                            inputs = [inputs]
                        elif not isinstance(inputs, list):
                            inputs = []
                        
                        conditions_raw = rule.get("条件", [])
                        # 条件可能是数组或对象
                        conditions_list = []
                        if isinstance(conditions_raw, list):
                            conditions_list = conditions_raw
                        elif isinstance(conditions_raw, dict):
                            # 如果是对象，提取所有值
                            conditions_list = list(conditions_raw.values())
                        elif isinstance(conditions_raw, str):
                            conditions_list = [conditions_raw]
                        
                        # 合并输入和条件作为条件列表
                        all_conditions = inputs + conditions_list
                        
                        calculation = rule.get("计算", {})
                        result = rule.get("结果", "")
                        
                        if all_conditions and calculation and result:
                            # 转换规则格式
                            converted_rule = {
                                "result": result,
                                "conditions": all_conditions,
                                "logic": "CONDITIONAL",
                                "conditional_inputs": inputs,
                                "conditional_conditions": conditions_raw,
                                "conditional_calculation": calculation,
                                "case_type": case_type
                            }
                            
                            # 处理"结果"可能是字符串或数组的情况
                            if isinstance(result, list):
                                # 如果结果是数组，为每个结果创建一个规则
                                for r in result:
                                    rule_copy = converted_rule.copy()
                                    rule_copy["result"] = r
                                    all_rules.append(rule_copy)
                                    rule_count += 1
                            elif isinstance(result, str) and result:
                                all_rules.append(converted_rule)
                                rule_count += 1
                
                print(f"    规则数: {rule_count}")
        
        except Exception as e:
            print(f"  ⚠️  读取文件失败 {os.path.basename(json_file)}: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n 共加载 {len(all_rules)} 条规则")
    return all_rules, case_types

# ==========================================
# 1. 解析命令行参数
# ==========================================
def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='法条图谱可视化工具 v3 - 从"规则"字段生成图谱，使用"案由"作为节点属性',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
  python json_to_graph_v3.py

  python json_to_graph_v3.py -f "1201醉驾量刑(按照醉驾意见新规加入不起诉规则版).json"

  python json_to_graph_v3.py -f graph_data/1201醉驾量刑(按照醉驾意见新规加入不起诉规则版).json
        """
    )
    parser.add_argument(
        '-f', '--files',
        nargs='+',
        default=None,
        help='指定要处理的 JSON 文件列表（相对于 graph_data 目录的文件名或完整路径）'
    )
    parser.add_argument(
        '-o', '--output',
        type=str,
        default='merged_graph_v3.graphml',
        help='输出的 GraphML 文件名（默认: merged_graph_v3.graphml）'
    )
    parser.add_argument(
        '--html-output',
        type=str,
        default='merged_graph_v3.html',
        help='输出的 HTML 文件名（默认: merged_graph_v3.html）'
    )
    return parser.parse_args()

# ==========================================
# 主程序入口
# ==========================================
# 解析命令行参数
args = parse_args()

# 加载并融合所有规则数据
rules_data, case_types = load_rules_from_json_files(args.files)

if not rules_data:
    print("❌ 未加载到任何规则数据，程序退出")
    exit(1)

# 显示加载的案由信息
if case_types:
    print("\n📋 加载的案由信息:")
    for case_type in case_types:
        print(f"  - {case_type}")
print()

# ==========================================
# 2. 初始化画布和 networkx 图
# ==========================================
# 初始化 pyvis 可视化网络
net = Network(height="100vh", width="100%", bgcolor="#ffffff", font_color="black", directed=True)

# 初始化 networkx 有向图，用于保存 GraphML
nx_graph = nx.DiGraph()

# 记录节点与案由的关联
node_case_map = {}  # {node_name: set of case_types}

# 记录已添加的节点，防止重复
added_nodes = set()
# 记录所有结果节点，用于判断节点类型
result_nodes = set()
for rule in rules_data:
    result = rule.get("result", "")
    if result:
        if isinstance(result, str):
            result_nodes.add(result)
        elif isinstance(result, list):
            result_nodes.update(result)

def add_node_safe(name, n_type="concept", is_result_node=False, logic="", case_type=""):
    """
    安全添加节点，避免重复
    同时添加到 pyvis 可视化图和 networkx 图
    is_result_node: 该节点是否为某个规则的结果节点
    logic: 逻辑操作符（AND/OR/NOT）
    case_type: 关联的案由
    """
    if not name or (isinstance(name, list) and len(name) == 0):
        return
    
    # 如果 name 是列表，取第一个元素
    if isinstance(name, list):
        name = name[0] if name else ""
    
    if not name:
        return
    
    is_new_node = name not in added_nodes
    
    if is_new_node:
        # 添加到 pyvis 可视化图（仅首次添加时）
        if n_type == "result" or is_result_node:
            # 结果节点：红色，椭圆，减小字体和节点大小
            net.add_node(name, label=name, color="#ff4d4d", shape="ellipse", font={'size': 16, 'color': 'white'}, size=25)
        else:
            # 普通条件：默认浅绿色，矩形，减小字体和节点大小（最后会根据入度更新颜色）
            net.add_node(name, label=name, color="#a8e6cf", shape="box", font={'size': 12}, size=20)
    
    # 处理 networkx 图的节点（无论是新节点还是已存在的节点，都需要合并属性）
    # 如果节点已存在，获取现有属性；否则使用默认值
    if nx_graph.has_node(name):
        existing_attrs = nx_graph.nodes[name]
        existing_case = existing_attrs.get("case_type", "") or ""
        existing_op = existing_attrs.get("operation", "") or ""
    else:
        existing_case = ""
        existing_op = ""
    
    # 合并案由信息（无论节点是否已存在，都需要合并）
    if case_type:
        if name not in node_case_map:
            node_case_map[name] = set()
        node_case_map[name].add(case_type)
        
        # 合并到 case_type 字符串
        if case_type not in existing_case:
            if existing_case:
                final_case = f"{existing_case},{case_type}"
            else:
                final_case = case_type
        else:
            final_case = existing_case
    else:
        final_case = existing_case
    
    # 合并 operation 信息
    if logic and logic not in existing_op:
        if existing_op:
            final_op = f"{existing_op},{logic}"
        else:
            final_op = logic
    else:
        final_op = existing_op if existing_op else (logic if logic else "")
    
    # 设置节点属性（更新或新增）
    node_attrs = {
        "node_name": name,
        "type": "",
        "prompt": "",
        "operation": final_op,
        "case_type": final_case  # 使用案由而不是法条
    }
    
    nx_graph.add_node(name, **node_attrs)
    
    if is_new_node:
        added_nodes.add(name)

# ==========================================
# 3. 构建节点与连线
# ==========================================

for idx, rule in enumerate(rules_data):
    result = rule.get("result", "")
    conditions = rule.get("conditions", [])
    logic = rule.get("logic", "AND")
    case_type = rule.get("case_type", "")
    arithmetic_rules = rule.get("arithmetic_rules", [])
    
    # 跳过无效规则（算术运算和条件判断允许conditions为空）
    if not result:
        continue
    if logic not in ["ARITHMETIC", "CONDITIONAL"] and not conditions:
        continue
    
    # 处理"结果"可能是字符串或数组的情况
    if isinstance(result, list):
        if len(result) == 0:
            continue
        result = result[0]  # 取第一个结果
    
    # 对于算术运算，从算术规则中提取变量名作为条件
    if logic == "ARITHMETIC" and arithmetic_rules:
        # 从算术表达式中提取变量名（中文字符、字母、数字、下划线的组合）
        all_vars = set()
        for arith_rule in arithmetic_rules:
            # 匹配变量名：中文字符、字母、数字、下划线的组合
            vars_in_rule = re.findall(r'[\u4e00-\u9fff\w]+', arith_rule)
            all_vars.update(vars_in_rule)
        conditions = list(all_vars)
    
    # 对于条件判断，从计算规则中提取变量名作为条件（如果conditions为空）
    if logic == "CONDITIONAL" and not conditions:
        conditional_calculation = rule.get("conditional_calculation", {})
        all_vars = set()
        
        def extract_vars_from_obj(obj):
            """递归提取对象中的所有变量名"""
            if isinstance(obj, dict):
                for value in obj.values():
                    extract_vars_from_obj(value)
            elif isinstance(obj, str):
                # 从字符串中提取变量名
                vars_in_str = re.findall(r'[\u4e00-\u9fff\w]+', obj)
                all_vars.update(vars_in_str)
        
        extract_vars_from_obj(conditional_calculation)
        conditions = list(all_vars)
    
    # A. 确保结果节点存在
    add_node_safe(result, n_type="result", is_result_node=True, logic=logic, case_type=case_type)
    
    # B. 创建一个逻辑聚合点 (显示为 "AND" 或 "OR" 或 "NOT" 或 "⊕" 或 "ARITH")
    # 为了让多条路径分开展示，我们给每个情形造一个独立的门
    gate_id = f"PATH_{idx}"
    
    # 根据逻辑类型设置不同的标签和样式
    if logic == "NON_EXCLUSIVE":
        gate_label = "⊕"  # 使用特殊符号表示"不互斥"
        gate_color = "#95e1d3"  # 浅绿色
        gate_shape = "hexagon"  # 使用六边形区分
        gate_font_color = "black"
    elif logic == "ARITHMETIC":
        gate_label = "ARITH"  # 算术运算
        gate_color = "#9b59b6"  # 紫色
        gate_shape = "triangle"  # 三角形
        gate_font_color = "white"
    elif logic == "CONDITIONAL":
        gate_label = "IF"  # 条件判断
        gate_color = "#f39c12"  # 橙色
        gate_shape = "square"  # 方形
        gate_font_color = "white"
    else:
        # AND、OR、NOT 保持原来的样式（红色菱形）
        gate_label = logic
        gate_color = "#fc5c65"  # 红色
        gate_shape = "diamond"  # 菱形
        gate_font_color = "white"
    
    # 逻辑门节点样式（仅用于可视化），减小大小
    net.add_node(gate_id, label=gate_label, color=gate_color, shape=gate_shape, size=15, font={'size': 12, 'color': gate_font_color})
    
    # C. 连接：逻辑门 -> 最终结果（仅用于可视化）
    net.add_edge(gate_id, result, width=2)
    
    # D. 处理条件
    for cond in conditions:
        if not cond:
            continue
        
        # 判断节点类型：
        # 1. 如果该条件是某个规则的结果节点，则标记为结果节点
        # 2. 其他为普通条件
        # 注意：条件节点也应该关联到当前规则的案由信息
        if cond in result_nodes:
            add_node_safe(cond, n_type="concept", is_result_node=True, case_type=case_type)
        else:
            add_node_safe(cond, n_type="concept", case_type=case_type)
        
        # 连接：条件 -> 逻辑门（仅用于可视化）
        net.add_edge(cond, gate_id, arrows="to")
        
        # 在 networkx 图中添加边：条件 -> 结果（直接连接，不包含逻辑门）
        if not nx_graph.has_edge(cond, result):
            nx_graph.add_edge(cond, result)

# ==========================================
# 3.5. 处理比较表达式节点，建立变量关联
# ==========================================
def extract_variables_from_expression(expr_str):
    """
    从表达式中提取变量名，使用AST解析和eval验证
    返回变量名列表
    """
    try:
        # 将中文比较运算符替换为Python运算符
        expr_normalized = expr_str.replace('≥', '>=').replace('≤', '<=').replace('≠', '!=')
        
        # 先提取所有可能的变量名（中文字符、字母、数字、下划线的组合）
        all_tokens = re.findall(r'[\u4e00-\u9fff\w]+', expr_normalized)
        
        # 过滤掉纯数字和数字单位（如"万"、"千"等）
        number_units = {'万', '千', '百', '十', '元', '万', '千', '百', '十'}
        potential_vars = [t for t in all_tokens if not (t.replace('.', '').replace('-', '').isdigit() or t in number_units)]
        
        # 识别比较运算符位置，分割表达式获取变量部分
        comparison_pattern = r'[><=!≥≤≠]+'
        parts = re.split(comparison_pattern, expr_normalized)
        
        variables = set()
        for part in parts:
            part = part.strip()
            if not part:
                continue
            
            # 检查整个部分是否是纯数字或数字+单位的组合（如"3万"、"100万"）
            # 如果是，跳过这个部分
            part_clean = part.replace(' ', '').replace(',', '')
            if re.match(r'^[\d.]+[万千百十元]*$', part_clean):
                continue
            
            # 提取该部分的变量名（排除数字和单位）
            tokens = re.findall(r'[\u4e00-\u9fff\w]+', part)
            for token in tokens:
                # 排除纯数字、单位、以及数字开头的token（如"3万"会被分割，但"3"会被过滤）
                is_pure_number = token.replace('.', '').replace('-', '').isdigit()
                is_unit = token in number_units
                # 检查是否是数字+单位的组合（如"3万"、"100万"）
                is_number_with_unit = re.match(r'^[\d.]+[万千百十元]*$', token)
                
                if not (is_pure_number or is_unit or is_number_with_unit):
                    variables.add(token)
        
        # 如果没有找到变量，使用potential_vars作为后备
        if not variables:
            variables = set(potential_vars)
        
        # 使用eval验证：构建context字典
        if variables:
            context = build_context_for_eval(list(variables))
            # 尝试构建测试表达式验证变量名
            try:
                test_expr = expr_normalized
                for var in variables:
                    # 将变量替换为占位值（用于验证语法）
                    test_expr = re.sub(r'\b' + re.escape(var) + r'\b', '0', test_expr)
                # 验证表达式语法（不实际执行）
                ast.parse(test_expr, mode='eval')
            except:
                # 如果验证失败，仍然返回提取的变量
                pass
        
        return list(variables) if variables else []
    except:
        # 如果全部失败，使用正则表达式作为后备
        vars_found = re.findall(r'[\u4e00-\u9fff\w]+', expr_str)
        number_units = {'万', '千', '百', '十', '元'}
        # 更严格的过滤：排除纯数字、单位、以及数字+单位的组合
        filtered_vars = []
        for v in vars_found:
            is_pure_number = v.replace('.', '').replace('-', '').isdigit()
            is_unit = v in number_units
            is_number_with_unit = re.match(r'^[\d.]+[万千百十元]*$', v)
            if not (is_pure_number or is_unit or is_number_with_unit):
                filtered_vars.append(v)
        return filtered_vars

def build_context_for_eval(variables):
    """
    为eval构建context字典，将变量名映射到占位值
    这样可以验证表达式语法，而不实际执行
    """
    context = {}
    for var in variables:
        # 使用一个占位值，确保eval可以验证语法
        context[var] = 0
    return context

# 处理所有节点，识别比较表达式并建立关联
comparison_ops = ['>', '<', '>=', '<=', '==', '!=', '≥', '≤', '≠']
for node_name in list(nx_graph.nodes()):
    # 检查节点名是否包含比较运算符
    is_comparison = any(op in node_name for op in comparison_ops)
    
    if is_comparison:
        # 提取变量名
        variables = extract_variables_from_expression(node_name)
        
        # 为每个变量建立到表达式的边
        for var in variables:
            # 确保变量节点存在
            if var not in nx_graph.nodes():
                add_node_safe(var, n_type="concept", case_type="")
            
            # 建立变量 -> 表达式的边
            if not nx_graph.has_edge(var, node_name):
                nx_graph.add_edge(var, node_name)
                # 在可视化图中也添加边
                if var in added_nodes and node_name in added_nodes:
                    net.add_edge(var, node_name, arrows="to", color="#3498db", width=1.5)

# ==========================================
# 3.6. 更新节点颜色：只有入度为0的节点才显示为灰色
# ==========================================
# 遍历所有节点，根据入度更新颜色
# 直接修改pyvis Network的nodes列表中的节点数据
for node_name in list(nx_graph.nodes()):
    in_degree = nx_graph.in_degree(node_name)
    
    # 检查节点是否在可视化图中（排除逻辑门节点）
    if node_name in added_nodes and not node_name.startswith("PATH_"):
        # 获取节点在networkx图中的信息，判断是否是结果节点
        node_attrs = nx_graph.nodes[node_name]
        operation = node_attrs.get("operation", "")
        is_result = operation or node_name in result_nodes
        
        # 根据入度确定颜色
        if in_degree == 0:
            if is_result:
                # 结果节点保持红色
                node_color = "#ff4d4d"
            else:
                # 入度为0的普通节点：灰色（浅蓝色）
                node_color = "#d1d8e0"
        else:
            if is_result:
                # 结果节点保持红色
                node_color = "#ff4d4d"
            else:
                # 如果入度不为0且不是结果节点，使用浅绿色
                node_color = "#a8e6cf"
        
        # 直接修改节点的颜色属性
        # pyvis的Network对象内部使用nodes列表存储节点数据
        try:
            # 遍历nodes列表，找到对应的节点并更新颜色
            nodes_list = list(net.nodes)
            for i, node in enumerate(nodes_list):
                # pyvis节点可能使用'id'或'label'作为标识
                node_id = node.get('id') or node.get('label')
                if node_id == node_name:
                    # 直接修改节点字典的颜色
                    node['color'] = node_color
                    # 更新nodes列表
                    net.nodes[i] = node
                    break
        except Exception as e:
            # 如果更新失败，尝试其他方法
            try:
                # 尝试通过节点的内部数据结构更新
                if hasattr(net, 'nodes') and isinstance(net.nodes, list):
                    for node in net.nodes:
                        if isinstance(node, dict):
                            node_id = node.get('id') or node.get('label')
                            if node_id == node_name:
                                node['color'] = node_color
                                break
            except:
                pass

# ==========================================
# 4. 设置层次化布局 (Hierarchical Layout)
# ==========================================
options = """
var options = {
  "layout": {
    "hierarchical": {
      "enabled": true,
      "direction": "UD",        
      "sortMethod": "directed", 
      "nodeSpacing": 60,       
      "levelSeparation": 90,   
      "treeSpacing": 10,
      "blockShifting": true,
      "edgeMinimization": true,
      "parentCentralization": true,
      "shakeTowards": "leaves"
    }
  },
  "edges": {
    "color": { "inherit": false, "color": "#808080" },
    "smooth": { "type": "cubicBezier", "forceDirection": "vertical", "roundness": 0.2 },
    "arrows": { "to": { "enabled": true, "scaleFactor": 0.8 } },
    "width": 1.5
  },
  "physics": { "enabled": false } 
}
"""
net.set_options(options)

# ==========================================
# 5. 保存 networkx 图为 GraphML 格式
# ==========================================
# 确保所有节点都有完整的属性结构
for node in nx_graph.nodes():
    node_data = nx_graph.nodes[node]
    # 确保所有必需的属性都存在
    for attr in ["node_name", "type", "prompt", "operation", "case_type"]:
        if attr not in node_data:
            node_data[attr] = ""

# 保存为 GraphML 格式
graphml_output = args.output
nx.write_graphml(nx_graph, graphml_output, encoding='utf-8')
print(f"\n图统计:")
print(f"  - 节点数: {nx_graph.number_of_nodes()}")
print(f"  - 边数: {nx_graph.number_of_edges()}")
print(f"  - GraphML文件已保存: {os.path.abspath(graphml_output)}")

# ==========================================
# 6. 生成 HTML 可视化并打开
# ==========================================
output_file = args.html_output

for node_name in list(nx_graph.nodes()):
    in_degree = nx_graph.in_degree(node_name)
    
    if node_name in added_nodes and not node_name.startswith("PATH_"):
        node_attrs = nx_graph.nodes[node_name]
        operation = node_attrs.get("operation", "")
        is_result = operation or node_name in result_nodes
        
        # 根据入度确定颜色
        if in_degree == 0:
            if is_result:
                node_color = "#ff4d4d"
            else:
                node_color = "#d1d8e0"
        else:
            if is_result:
                # 结果节点保持红色
                node_color = "#ff4d4d"
            else:
                # 如果入度不为0且不是结果节点，使用浅绿色
                node_color = "#a8e6cf"
        
        try:
            for node in net.nodes:
                if isinstance(node, dict):
                    node_id = node.get('id') or node.get('label')
                    if node_id == node_name:
                        node['color'] = node_color
                        break
        except:
            pass

net.write_html(output_file)

# 在write_html之后，通过修改HTML来更新节点颜色（作为备用方案）
try:
    with open(output_file, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    # 为每个节点根据入度更新颜色
    for node_name in list(nx_graph.nodes()):
        in_degree = nx_graph.in_degree(node_name)
        
        # 检查节点是否在可视化图中（排除逻辑门节点）
        if node_name in added_nodes and not node_name.startswith("PATH_"):
            # 获取节点在networkx图中的信息，判断是否是结果节点
            node_attrs = nx_graph.nodes[node_name]
            operation = node_attrs.get("operation", "")
            is_result = operation or node_name in result_nodes
            
            # 根据入度确定颜色
            if in_degree == 0:
                if is_result:
                    # 结果节点保持红色
                    node_color = "#ff4d4d"
                else:
                    # 入度为0的普通节点：灰色（浅蓝色）
                    node_color = "#d1d8e0"
            else:
                if is_result:
                    # 结果节点保持红色
                    node_color = "#ff4d4d"
                else:
                    # 如果入度不为0且不是结果节点，使用浅绿色
                    node_color = "#a8e6cf"
            
            # 在HTML中查找并替换节点颜色
            # pyvis生成的HTML中，节点数据在JavaScript的nodes数组中
            import json
            escaped_name = json.dumps(node_name)
            
            # 使用正则表达式匹配并替换节点颜色
            # 匹配模式：{"id": "节点名", ..., "color": "旧颜色", ...}
            # 需要处理可能的转义字符
            pattern = rf'("id":\s*{re.escape(escaped_name)}[^}}]*"color":\s*")[^"]*(")'
            replacement = rf'\1{node_color}\2'
            html_content = re.sub(pattern, replacement, html_content)
    
    # 写回修改后的HTML
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
except Exception as e:
    pass

# 优化 HTML 样式，使其铺满浏览器窗口
try:
    with open(output_file, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    # 替换固定的高度为 100vh
    html_content = html_content.replace('height: 800px', 'height: 100vh')
    html_content = html_content.replace('height:800px', 'height:100vh')
    
    # 修改 #mynetwork 样式，使其铺满全屏
    html_content = html_content.replace('position: relative;', 'position: absolute;')
    html_content = html_content.replace('float: left;', '')
    html_content = html_content.replace('border: 1px solid lightgray;', 'border: none;')
    
    # 在 head 标签的 style 部分添加全屏样式
    style_addition = """
            html, body {
                margin: 0;
                padding: 0;
                width: 100%;
                height: 100%;
                overflow: hidden;
            }
"""
    
    # 找到 </style> 标签并在之前插入新样式
    if '</style>' in html_content:
        html_content = html_content.replace('</style>', style_addition + '</style>', 1)
    else:
        # 如果没有 style 标签，在 head 中添加
        if '</head>' in html_content:
            html_content = html_content.replace('</head>', '<style>' + style_addition + '</style></head>', 1)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
except Exception as e:
    print(f"⚠️  优化 HTML 样式时出错: {e}")

print(f"✅ 图谱已生成: {os.path.abspath(output_file)}")
print(f"\n📝 输出文件:")
print(f"  - GraphML: {os.path.abspath(graphml_output)} (用于图遍历)")
print(f"  - HTML: {os.path.abspath(output_file)} (交互式可视化)")
