#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JSON 文件合法性检查工具
检查 raw_graph_data 目录下的所有 JSON 文件是否能够成功加载
"""
import os
import json
import sys
from json_to_graph_v4 import *
from check_json_postprocess import *


def _validate_conditional_pairs(calc_obj, file_name, rule_index, result_name, errors):
    """递归校验条件判断规则中每一层的成立/不成立分支是否成对出现。"""
    if not isinstance(calc_obj, dict):
        return

    branch_state_map = {}
    for key, value in calc_obj.items():
        condition_name = None
        branch_state = None
        if isinstance(key, str):
            if key.endswith("不成立"):
                condition_name = key[:-3]
                branch_state = "不成立"
            elif key.endswith("成立"):
                condition_name = key[:-2]
                branch_state = "成立"

        if condition_name is not None:
            branch_state_map.setdefault(condition_name, set()).add(branch_state)

        _validate_conditional_pairs(value, file_name, rule_index, result_name, errors)

    for condition_name, states in branch_state_map.items():
        if "成立" in states and "不成立" not in states:
            errors.append(
                f"❌ {file_name} - 规则 {rule_index}（结果: {result_name}）缺少配对分支: {condition_name}不成立"
            )
        elif "不成立" in states and "成立" not in states:
            errors.append(
                f"❌ {file_name} - 规则 {rule_index}（结果: {result_name}）缺少配对分支: {condition_name}成立"
            )


def check_conditional_rule_pairs(json_file):
    """检查图谱 JSON 中条件判断规则的计算分支是否成对出现。"""
    file_name = os.path.basename(json_file)
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        rules = data.get("规则", [])
        if not isinstance(rules, list):
            error_msg = f"❌ {file_name} - '规则' 的值必须是数组类型"
            print(error_msg)
            return False

        errors = []
        for rule_index, rule in enumerate(rules):
            if rule.get("类型") != "条件判断":
                continue
            calculation = rule.get("计算")
            if calculation is None:
                continue

            result_name = rule.get("结果", "<未命名结果>")
            _validate_conditional_pairs(calculation, file_name, rule_index, result_name, errors)

        if errors:
            for error in errors:
                print(error)
            return False

        print(f"✅ {file_name} - 条件判断分支配对检查通过")
        return True
    except json.JSONDecodeError as e:
        error_msg = f"❌ {file_name} - JSON 解析错误: {e}"
        print(error_msg)
        return False
    except Exception as e:
        error_msg = f"❌ {file_name} - 条件判断分支检查失败: {e}"
        print(error_msg)
        return False
    
def check_graph_json_file(json_file):
    """检查图谱 JSON 文件
    
    Returns:
        bool: 检查通过返回 True，否则返回 False
    """
    file_name = os.path.basename(json_file)
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 检查必需的 key
        required_keys = ["案由", "法律法规", "规则"]
        missing_keys = [key for key in required_keys if key not in data]
        
        if missing_keys:
            error_msg = f"❌ {file_name} - 缺少必需的 key: {', '.join(missing_keys)}"
            print(error_msg)
            return False
        else:
            print(f"✅ {file_name}")
            return True

    except Exception as e:
        error_msg = f"❌ {file_name} - 加载失败: {e}"
    print(error_msg)
    return False


def check_result_json_file(json_file):
    """检查结果节点 JSON 文件"""
    file_name = os.path.basename(json_file)
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 检查是否包含 "任务节点" key
        if "任务节点" not in data:
            error_msg = f"❌ {file_name} - 缺少必需的 key: 任务节点"
            print(error_msg)
            return False
        
        # 检查 "任务节点" 的值类型
        task_nodes = data["任务节点"]
        if not isinstance(task_nodes, list):
            error_msg = f"❌ {file_name} - '任务节点' 的值必须是数组类型"
            print(error_msg)
            return False
        
        # 检查数组是否为空
        if len(task_nodes) == 0:
            error_msg = f"❌  {file_name} - '任务节点' 数组为空"
            print(error_msg)
            return False
        
        # 检查数组元素类型
        invalid_items = []
        for i, item in enumerate(task_nodes):
            if not isinstance(item, str):
                invalid_items.append(f"索引 {i}: {type(item).__name__}")
        
        if invalid_items:
            error_msg = f"⚠️  {file_name} - '任务节点' 数组包含非字符串元素: {', '.join(invalid_items)}"
            print(error_msg)
        
        print(f"✅ {file_name} - 包含 {len(task_nodes)} 个任务节点")
        return True
            
    except json.JSONDecodeError as e:
        error_msg = f"❌ {file_name} - JSON 解析错误: {e}"
        print(error_msg)
        return False

    except Exception as e:
        error_msg = f"❌ {file_name} - 加载失败: {e}"
        print(error_msg)
        return False


def json_to_graph():
    for f in os.listdir(RAW_GRAPH_DATA_DIR):
        if f.endswith("json") == False:
            continue
        
        graph_data_des_f = f'''graph_data/{f.replace('.json', '.graphml')}'''
        cmd = f'''python json_to_graph_v3.py -f "{RAW_GRAPH_DATA_DIR}/{f}" -o "{graph_data_des_f}" --html-output "graph_html/{f.replace('.json', '.html')}"'''
        print(cmd)
        os.system(cmd)


        cmd = f'''python check_json_postprocess.py "{graph_data_des_f}"'''
        print(cmd)
        os.system(cmd)

    

if __name__ == '__main__':
    print("=" * 36)
    print("检查 JSON 文件 合法性")

    input_graph_json = "raw_graph_data/djt贪污罪json图.json"
    input_result_json = "raw_graph_data/djt贪污罪_result_node.json"


    # step1: check json file
    check_graph_json_file(input_graph_json)
    check_result_json_file(input_result_json)

    print("=" * 36)

    # step2: transfer to graph
    nx_G = json_to_graphml(input_graph_json)

    # step3: 后处理再校验一下图
    check_graph_for_cycles(nx_G)

    print("=" * 36)

    # step4: 检查条件判断规则的分支完整性
    check_conditional_rule_pairs(input_graph_json)
    
