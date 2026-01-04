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
    
def check_graph_json_file(json_file):
    """检查图谱 JSON 文件"""
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
        else:
            print(f"✅ {file_name}")
            
    except json.JSONDecodeError as e:
        error_msg = f"❌ {file_name} - JSON 解析错误: {e}"
        print(error_msg)

    except Exception as e:
        error_msg = f"❌ {file_name} - 加载失败: {e}"
        print(error_msg)


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
    

