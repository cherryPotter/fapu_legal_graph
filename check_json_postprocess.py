#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GraphML 文件环检测工具
检查 GraphML 文件中是否存在环（cycle）
"""
import os
import sys
import argparse
import networkx as nx

def find_cycles(graph):
    """查找图中的所有简单环"""
    try:
        # 使用 networkx 查找所有简单环
        cycles = list(nx.simple_cycles(graph))
        return cycles
    except Exception as e:
        print(f"⚠️  查找环时出错: {e}")
        return []

def check_graphml_for_cycles(graphml_file):
    """检查 GraphML 文件中是否存在环"""
    if not os.path.exists(graphml_file):
        print(f"❌ 文件不存在: {graphml_file}")
        sys.exit(1)
    
    print(f"📂 检查文件: {os.path.basename(graphml_file)}")
    print(f"🔍 检测环（cycle）...\n")
    
    try:
        # 读取 GraphML 文件
        G = nx.read_graphml(graphml_file)
        
        # 如果不是有向图，转换为有向图
        if not G.is_directed():
            G = G.to_directed()
        
        print(f"📊 图统计: - 节点数: {G.number_of_nodes()} - 边数: {G.number_of_edges()}")
        print()
        
        # 检查是否存在环
        if nx.is_directed_acyclic_graph(G):
            print("✅ 图中不存在环（DAG - 有向无环图）")
            sys.exit(0)
        else:
            print("❌ 图中存在环！\n")
            
            # 查找所有环
            cycles = find_cycles(G)
            
            if cycles:
                print(f"📋 发现 {len(cycles)} 个环:\n")
                
                # 显示前10个环（避免输出过多）
                max_cycles_to_show = 10
                for idx, cycle in enumerate(cycles[:max_cycles_to_show], 1):
                    print(f"  环 [{idx}]: {' -> '.join(cycle)} -> {cycle[0]}")
                    print()
                
                if len(cycles) > max_cycles_to_show:
                    print(f"  ... 还有 {len(cycles) - max_cycles_to_show} 个环未显示\n")
                
                # 显示所有环的节点集合（去重）
                all_cycle_nodes = set()
                for cycle in cycles:
                    all_cycle_nodes.update(cycle)
                
                print(f"📌 涉及环的节点（共 {len(all_cycle_nodes)} 个）:")
                for node in sorted(all_cycle_nodes):
                    node_name = G.nodes[node].get('node_name', node)
                    print(f"  - {node} ({node_name})")
                
            else:
                print("⚠️  检测到环但无法列出具体路径")
            
            sys.exit(1)
            
    except nx.NetworkXError as e:
        print(f"❌ NetworkX 错误: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 读取 GraphML 文件失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='检查 GraphML 文件中是否存在环（cycle）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python check_json_pro.py graph_data/example.graphml
        """
    )
    parser.add_argument(
        'graphml_file',
        type=str,
        help='要检查的 GraphML 文件路径'
    )
    return parser.parse_args()

if __name__ == '__main__':
    args = parse_args()
    check_graphml_for_cycles(args.graphml_file)

