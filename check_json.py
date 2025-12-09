#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JSON 文件合法性检查工具
检查 raw_graph_data 目录下的所有 JSON 文件是否能够成功加载
"""
import os
import json
import sys

RAW_GRAPH_DATA_DIR = "raw_graph_data"

def check_json_files():
    """检查 raw_graph_data 目录下的所有 JSON 文件"""
    raw_data_dir = os.path.join(os.path.dirname(__file__), RAW_GRAPH_DATA_DIR)
    
    if not os.path.exists(raw_data_dir):
        print(f"❌ 目录不存在: {raw_data_dir}")
        sys.exit(1)
    
    # 获取所有 JSON 文件
    all_files = os.listdir(raw_data_dir)
    json_files = [
        os.path.join(raw_data_dir, f) 
        for f in all_files 
        if f.endswith('.json') and os.path.isfile(os.path.join(raw_data_dir, f))
    ]
    
    if not json_files:
        print(f"⚠️  在 {raw_data_dir} 目录下未找到 JSON 文件")
        sys.exit(0)
    
    # 按文件名排序
    json_files.sort()
    
    print(f"📂 找到 {len(json_files)} 个 JSON 文件，开始检查...\n")
    
    success_count = 0
    error_count = 0
    errors = []
    
    for json_file in json_files:
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
                errors.append(error_msg)
                error_count += 1
            else:
                print(f"✅ {file_name}")
                success_count += 1
                
        except json.JSONDecodeError as e:
            error_msg = f"❌ {file_name} - JSON 解析错误: {e}"
            print(error_msg)
            errors.append(error_msg)
            error_count += 1
        except Exception as e:
            error_msg = f"❌ {file_name} - 加载失败: {e}"
            print(error_msg)
            errors.append(error_msg)
            error_count += 1
    
    # 输出总结
    print(f"\n{'='*60}")
    print(f"检查完成:")
    print(f"  ✅ 成功: {success_count} 个文件")
    print(f"  ❌ 失败: {error_count} 个文件")
    print(f"{'='*60}")
    
    if errors:
        print("\n错误详情:")
        for error in errors:
            print(f"  {error}")
        sys.exit(1)
    else:
        print("\n🎉 所有 JSON 文件检查通过！")
        sys.exit(0)

if __name__ == '__main__':
    check_json_files()


