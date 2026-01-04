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


def ensure_connected(graph):
    """检查弱连通性，不连通则报错退出"""
    if nx.is_directed(graph):
        connected = nx.is_weakly_connected(graph)
        components = list(nx.weakly_connected_components(graph)) if not connected else []
    else:
        connected = nx.is_connected(graph)
        components = list(nx.connected_components(graph)) if not connected else []

    if connected:
        print("✅ 图是连通的（弱连通）")
        return True
    else:
        print(f"❌ 图不连通，共 {len(components)} 个连通分量（弱连通）")
        return False


def check_graph_for_cycles(graph):
    """
    检查 networkx 图对象中是否存在环
    
    Args:
        graph: networkx 图对象（DiGraph 或 Graph）
    
    Returns:
        tuple: (has_cycles: bool, cycles: list, cycle_nodes: set)
            - has_cycles: 是否存在环
            - cycles: 环的列表
            - cycle_nodes: 涉及环的节点集合
    """
    print(f"🔍 检测环（cycle）...\n")
    
    try:
        # 确保是有向图
        G = graph
        if not G.is_directed():
            G = G.to_directed()
        
        print(f"📊 图统计: - 节点数: {G.number_of_nodes()} - 边数: {G.number_of_edges()}")
        print()
        
        # 检查连通性
        is_connected = ensure_connected(G)
        
        # 检查是否存在环
        if nx.is_directed_acyclic_graph(G):
            print("✅ 图中不存在环（DAG - 有向无环图）")
            return False, [], set()
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
                
                return True, cycles, all_cycle_nodes
            else:
                print("⚠️  检测到环但无法列出具体路径")
                return True, [], set()
                
    except nx.NetworkXError as e:
        print(f"❌ NetworkX 错误: {e}")
        raise
    except Exception as e:
        print(f"❌ 检查图时出错: {e}")
        import traceback
        traceback.print_exc()
        raise


def check_graphml_for_cycles(graphml_file):
    """检查 GraphML 文件中是否存在环"""
    if not os.path.exists(graphml_file):
        print(f"❌ 文件不存在: {graphml_file}")
        sys.exit(1)
    
    try:
        # 读取 GraphML 文件
        G = nx.read_graphml(graphml_file)
        
        print(f"📂 检查文件: {os.path.basename(graphml_file)}")
        
        # 使用新的检查函数
        has_cycles, cycles, cycle_nodes = check_graph_for_cycles(G)
        
        # 根据检查结果退出
        if has_cycles:
            sys.exit(1)
        else:
            sys.exit(0)
            
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

