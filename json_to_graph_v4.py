#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JSON 文件转 GraphML 图工具
从 JSON 文件读取规则，生成 GraphML 格式的图谱
"""
import networkx as nx
import os
import json
import argparse
import re


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


def load_rules_from_json_file(json_file):
    """
    从单个 JSON 文件加载规则
    
    Args:
        json_file: JSON 文件路径
    
    Returns:
        tuple: (rules_list, case_type)
    """
    if not os.path.exists(json_file):
        raise FileNotFoundError(f"文件不存在: {json_file}")
    
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 提取案由信息
    case_type = data.get("案由", "")
    
    all_rules = []
    
    # 提取并融合"规则"数据，为每个规则添加案由信息
    if "规则" in data and isinstance(data["规则"], list):
        for rule in data["规则"]:
            rule_type = rule.get("类型", "")
            if rule_type == "逻辑运算":
                # 转换规则格式
                converted_rule = {
                    "result": rule.get("结果", ""),
                    "conditions": rule.get("条件", []),
                    "logic": convert_logic_op(rule.get("计算方式", "与")),
                    "case_type": case_type
                }
                
                # 处理"结果"可能是字符串或数组的情况
                result = converted_rule["result"]
                if isinstance(result, list):
                    for r in result:
                        rule_copy = converted_rule.copy()
                        rule_copy["result"] = r
                        all_rules.append(rule_copy)
                elif isinstance(result, str) and result:
                    all_rules.append(converted_rule)
            elif rule_type == "算术运算":
                arithmetic_rules = rule.get("算术规则", [])
                if not arithmetic_rules:
                    arithmetic_rules = rule.get("算式", [])
                
                result = rule.get("结果", "")
                if arithmetic_rules and result:
                    converted_rule = {
                        "result": result,
                        "conditions": [],
                        "logic": "ARITHMETIC",
                        "arithmetic_rules": arithmetic_rules,
                        "case_type": case_type
                    }
                    
                    if isinstance(result, list):
                        for r in result:
                            rule_copy = converted_rule.copy()
                            rule_copy["result"] = r
                            all_rules.append(rule_copy)
                    elif isinstance(result, str) and result:
                        all_rules.append(converted_rule)
            elif rule_type == "集合":
                conditions = rule.get("条件", [])
                if isinstance(conditions, str):
                    conditions = [conditions]
                elif not isinstance(conditions, list):
                    conditions = []
                
                result = rule.get("结果", "")
                logic_op = rule.get("计算方式", "")
                
                if conditions and result:
                    converted_rule = {
                        "result": result,
                        "conditions": conditions,
                        "logic": convert_logic_op(logic_op),
                        "case_type": case_type
                    }
                    
                    if isinstance(result, list):
                        for r in result:
                            rule_copy = converted_rule.copy()
                            rule_copy["result"] = r
                            all_rules.append(rule_copy)
                    elif isinstance(result, str) and result:
                        all_rules.append(converted_rule)
            elif rule_type == "条件判断":
                inputs = rule.get("输入", [])
                if isinstance(inputs, str):
                    inputs = [inputs]
                elif not isinstance(inputs, list):
                    inputs = []
                
                conditions_raw = rule.get("条件", [])
                conditions_list = []
                if isinstance(conditions_raw, list):
                    conditions_list = conditions_raw
                elif isinstance(conditions_raw, dict):
                    conditions_list = list(conditions_raw.values())
                elif isinstance(conditions_raw, str):
                    conditions_list = [conditions_raw]
                
                all_conditions = inputs + conditions_list
                calculation = rule.get("计算", {})
                result = rule.get("结果", "")
                
                if all_conditions and calculation and result:
                    converted_rule = {
                        "result": result,
                        "conditions": all_conditions,
                        "logic": "CONDITIONAL",
                        "conditional_inputs": inputs,
                        "conditional_conditions": conditions_raw,
                        "conditional_calculation": calculation,
                        "case_type": case_type
                    }
                    
                    if isinstance(result, list):
                        for r in result:
                            rule_copy = converted_rule.copy()
                            rule_copy["result"] = r
                            all_rules.append(rule_copy)
                    elif isinstance(result, str) and result:
                        all_rules.append(converted_rule)
    
    return all_rules, case_type


def extract_variables_from_expression(expr_str):
    """从表达式中提取变量名"""
    try:
        expr_normalized = expr_str.replace('≥', '>=').replace('≤', '<=').replace('≠', '!=')
        all_tokens = re.findall(r'[\u4e00-\u9fff\w]+', expr_normalized)
        number_units = {'万', '千', '百', '十', '元', '万', '千', '百', '十'}
        potential_vars = [t for t in all_tokens if not (t.replace('.', '').replace('-', '').isdigit() or t in number_units)]
        
        comparison_pattern = r'[><=!≥≤≠]+'
        parts = re.split(comparison_pattern, expr_normalized)
        
        variables = set()
        for part in parts:
            part = part.strip()
            if not part:
                continue
            
            part_clean = part.replace(' ', '').replace(',', '')
            if re.match(r'^[\d.]+[万千百十元]*$', part_clean):
                continue
            
            tokens = re.findall(r'[\u4e00-\u9fff\w]+', part)
            for token in tokens:
                is_pure_number = token.replace('.', '').replace('-', '').isdigit()
                is_unit = token in number_units
                is_number_with_unit = re.match(r'^[\d.]+[万千百十元]*$', token)
                
                if not (is_pure_number or is_unit or is_number_with_unit):
                    variables.add(token)
        
        if not variables:
            variables = set(potential_vars)
        
        return list(variables) if variables else []
    except:
        vars_found = re.findall(r'[\u4e00-\u9fff\w]+', expr_str)
        number_units = {'万', '千', '百', '十', '元'}
        filtered_vars = []
        for v in vars_found:
            is_pure_number = v.replace('.', '').replace('-', '').isdigit()
            is_unit = v in number_units
            is_number_with_unit = re.match(r'^[\d.]+[万千百十元]*$', v)
            if not (is_pure_number or is_unit or is_number_with_unit):
                filtered_vars.append(v)
        return filtered_vars


def build_graph_from_rules(rules_data):
    """
    从规则数据构建 networkx 图
    
    Args:
        rules_data: 规则列表
    
    Returns:
        networkx.DiGraph: 构建的图
    """
    nx_graph = nx.DiGraph()
    node_case_map = {}
    result_nodes = set()
    
    # 收集所有结果节点
    for rule in rules_data:
        result = rule.get("result", "")
        if result:
            if isinstance(result, str):
                result_nodes.add(result)
            elif isinstance(result, list):
                result_nodes.update(result)
    
    def add_node_safe(name, logic="", case_type=""):
        """安全添加节点到 networkx 图"""
        if not name or (isinstance(name, list) and len(name) == 0):
            return
        
        if isinstance(name, list):
            name = name[0] if name else ""
        
        if not name:
            return
        
        # 获取现有属性
        if nx_graph.has_node(name):
            existing_attrs = nx_graph.nodes[name]
            existing_case = existing_attrs.get("case_type", "") or ""
            existing_op = existing_attrs.get("operation", "") or ""
        else:
            existing_case = ""
            existing_op = ""
        
        # 合并案由信息
        if case_type:
            if name not in node_case_map:
                node_case_map[name] = set()
            node_case_map[name].add(case_type)
            
            if case_type not in existing_case:
                final_case = f"{existing_case},{case_type}" if existing_case else case_type
            else:
                final_case = existing_case
        else:
            final_case = existing_case
        
        # 合并 operation 信息
        if logic and logic not in existing_op:
            final_op = f"{existing_op},{logic}" if existing_op else logic
        else:
            final_op = existing_op if existing_op else (logic if logic else "")
        
        # 设置节点属性
        node_attrs = {
            "node_name": name,
            "type": "",
            "prompt": "",
            "operation": final_op,
            "case_type": final_case
        }
        
        nx_graph.add_node(name, **node_attrs)
    
    # 构建节点和边
    for idx, rule in enumerate(rules_data):
        result = rule.get("result", "")
        conditions = rule.get("conditions", [])
        logic = rule.get("logic", "AND")
        case_type = rule.get("case_type", "")
        arithmetic_rules = rule.get("arithmetic_rules", [])
        
        if not result:
            continue
        if logic not in ["ARITHMETIC", "CONDITIONAL"] and not conditions:
            continue
        
        if isinstance(result, list):
            if len(result) == 0:
                continue
            result = result[0]
        
        # 对于算术运算，从算术规则中提取变量名作为条件
        if logic == "ARITHMETIC" and arithmetic_rules:
            all_vars = set()
            for arith_rule in arithmetic_rules:
                vars_in_rule = re.findall(r'[\u4e00-\u9fff\w]+', arith_rule)
                all_vars.update(vars_in_rule)
            conditions = list(all_vars)
        
        # 对于条件判断，从计算规则中提取变量名作为条件
        if logic == "CONDITIONAL" and not conditions:
            conditional_calculation = rule.get("conditional_calculation", {})
            all_vars = set()
            
            def extract_vars_from_obj(obj):
                if isinstance(obj, dict):
                    for value in obj.values():
                        extract_vars_from_obj(value)
                elif isinstance(obj, str):
                    vars_in_str = re.findall(r'[\u4e00-\u9fff\w]+', obj)
                    all_vars.update(vars_in_str)
            
            extract_vars_from_obj(conditional_calculation)
            conditions = list(all_vars)
        
        # 添加结果节点
        add_node_safe(result, logic=logic, case_type=case_type)
        
        # 创建逻辑门节点（用于可视化）
        gate_id = f"PATH_{idx}"
        
        # 将逻辑门节点添加到图中
        gate_attrs = {
            "node_name": gate_id,
            "type": "gate",
            "prompt": "",
            "operation": logic,
            "case_type": case_type
        }
        nx_graph.add_node(gate_id, **gate_attrs)
        
        # 添加边：逻辑门 -> 结果
        if not nx_graph.has_edge(gate_id, result):
            nx_graph.add_edge(gate_id, result, logic=logic)
        
        # 处理条件
        for cond in conditions:
            if not cond:
                continue
            
            if cond in result_nodes:
                add_node_safe(cond, case_type=case_type)
            else:
                add_node_safe(cond, case_type=case_type)
            
            # 添加边：条件 -> 逻辑门
            if not nx_graph.has_edge(cond, gate_id):
                nx_graph.add_edge(cond, gate_id, logic=logic)
    
    # 处理比较表达式节点，建立变量关联
    comparison_ops = ['>', '<', '>=', '<=', '==', '!=', '≥', '≤', '≠']
    for node_name in list(nx_graph.nodes()):
        is_comparison = any(op in node_name for op in comparison_ops)
        
        if is_comparison:
            variables = extract_variables_from_expression(node_name)
            
            for var in variables:
                if var not in nx_graph.nodes():
                    add_node_safe(var, case_type="")
                
                if not nx_graph.has_edge(var, node_name):
                    nx_graph.add_edge(var, node_name)
    
    # 确保所有节点都有完整的属性结构
    for node in nx_graph.nodes():
        node_data = nx_graph.nodes[node]
        for attr in ["node_name", "type", "prompt", "operation", "case_type"]:
            if attr not in node_data:
                node_data[attr] = ""
    
    return nx_graph


def json_to_graphml(json_file, output_file):
    """
    将 JSON 文件转换为 GraphML 文件
    
    Args:
        json_file: 输入的 JSON 文件路径
        output_file: 输出的 GraphML 文件路径
    """
    print(f"📂 读取 JSON 文件: {os.path.basename(json_file)}")
    
    # 加载规则
    rules_data, case_type = load_rules_from_json_file(json_file)
    
    if not rules_data:
        raise ValueError("未加载到任何规则数据")
    
    print(f"📋 案由: {case_type}")
    print(f"📊 共加载 {len(rules_data)} 条规则")
    
    # 构建图
    print("\n🔨 构建图谱...")
    nx_graph = build_graph_from_rules(rules_data)
    
    # 保存 GraphML
    if output_file is not None:
        nx.write_graphml(nx_graph, output_file, encoding='utf-8')
        print(f"\n✅ GraphML 文件已保存: {os.path.abspath(output_file)}")
    
    print(f"链图统计:")
    print(f"  - 节点数: {nx_graph.number_of_nodes()}")
    print(f"  - 边数: {nx_graph.number_of_edges()}")
    
    return nx_graph


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='JSON 文件转 GraphML 图工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python json_to_graph_v4.py -f input.json -o output.graphml
        """
    )
    parser.add_argument(
        '-f', '--file',
        type=str,
        required=True,
        help='输入的 JSON 文件路径'
    )
    parser.add_argument(
        '-o', '--output',
        type=str,
        default=None,
        help='输出的 GraphML 文件名（默认: 输入文件名.graphml）'
    )
    return parser.parse_args()


def main():
    """主函数"""
    args = parse_args()
    
    json_file = args.file
    if not os.path.exists(json_file):
        print(f"❌ 文件不存在: {json_file}")
        return 1
    
    try:
        json_to_graphml(json_file, args.output)
        return 0
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    exit(main())

