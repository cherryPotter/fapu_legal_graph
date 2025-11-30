#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图工具函数
用于打印和保存 GraphML 图中的所有节点和边信息
"""
import networkx as nx
import os
from pathlib import Path
from typing import Optional

def visualize_networkx_graph(G, output_path, layout='spring'):
    """
    可视化 networkx 图
    """
    print(f"\n🎨 正在生成 NetworkX 图可视化...")
    
    # 选择布局
    if layout == 'spring':
        pos = nx.spring_layout(G, k=0.5, iterations=50, seed=42)
    elif layout == 'kamada_kawai':
        pos0 = nx.spring_layout(G, k=0.8, seed=42)
        pos = nx.kamada_kawai_layout(G, pos=pos0)
    elif layout == 'hierarchical':
        # 尝试使用层次化布局
        try:
            pos = nx.nx_agraph.graphviz_layout(G, prog='dot')
        except:
            # 如果没有 graphviz，使用 spring layout
            pos = nx.spring_layout(G, k=0.5, iterations=50, seed=42)
    else:
        pos = nx.spring_layout(G, k=0.5, iterations=50, seed=42)
    
    # 创建图形
    plt.figure(figsize=(20, 14))
    
    # 根据节点类型设置不同的颜色
    node_colors = []
    for node in G.nodes():
        # 判断节点类型：如果 operation 不为空，说明是结果节点
        op = G.nodes[node].get("operation", "")
        if op:
            node_colors.append('#ff4d4d')  # 红色：结果节点
        else:
            node_colors.append('#4C89C6')  # 蓝色：条件节点
    
    # 绘制边
    nx.draw_networkx_edges(
        G, pos, 
        alpha=0.3, 
        width=0.8, 
        arrows=True, 
        arrowstyle='-|>', 
        arrowsize=15,
        edge_color='#808080'
    )
    
    # 绘制节点
    nx.draw_networkx_nodes(
        G, pos,
        node_size=1000,
        node_color=node_colors,
        alpha=0.9,
        linewidths=1.5,
        edgecolors='#1c3d5a'
    )
    
    # 显示节点标签
    labels = {node: node for node in G.nodes()}
    nx.draw_networkx_labels(
        G, pos, 
        labels,
        font_size=8,
        font_weight='bold'
    )
    
    plt.axis('off')
    plt.title('NetworkX 图可视化验证', fontsize=16, pad=20)
    plt.tight_layout()
    
    # 保存图片
    plt.savefig(output_path, dpi=200, bbox_inches='tight')
    print(f"✅ NetworkX 图可视化已保存: {os.path.abspath(output_path)}")
    plt.close()


def print_graph_nodes_and_edges(graphml_path: str, output_file: Optional[str] = None):
    """
    打印 GraphML 文件中的所有节点和边信息
    
    Args:
        graphml_path: GraphML 文件路径
        output_file: 可选，输出文件路径。如果不提供，则只打印到控制台
    
    Returns:
        None
    """
    # 检查文件是否存在
    graphml_file = Path(graphml_path)
    if not graphml_file.exists():
        raise FileNotFoundError(f'找不到文件: {graphml_path}')
    
    # 读取 GraphML 文件
    print(f'📖 正在读取图文件: {graphml_path}')
    G = nx.read_graphml(graphml_path)
    print(f'✅ 图加载成功: 节点数={G.number_of_nodes()}, 边数={G.number_of_edges()}\n')
    
    # 决定输出目标
    if output_file:
        f = open(output_file, 'w', encoding='utf-8')
        print(f'📝 正在保存到文件: {output_file}')
    else:
        import sys
        f = sys.stdout
    
    try:
        # 写入标题
        f.write("=" * 80 + "\n")
        f.write(f"图文件: {graphml_path}\n")
        f.write("=" * 80 + "\n\n")
        
        # 1. 基本统计信息
        f.write("【基本统计信息】\n")
        f.write("-" * 80 + "\n")
        f.write(f"节点总数: {G.number_of_nodes()}\n")
        f.write(f"边总数: {G.number_of_edges()}\n")
        f.write(f"是否为有向图: {isinstance(G, nx.DiGraph)}\n")
        f.write("\n")
        
        # 2. 所有节点列表
        f.write("【所有节点列表】\n")
        f.write("-" * 80 + "\n")
        
        # 获取所有节点，按名称排序
        all_nodes = sorted(G.nodes(data=True), key=lambda x: x[0])
        
        for idx, (node_name, node_data) in enumerate(all_nodes, 1):
            f.write(f"\n{idx:3d}. 节点: {node_name}\n")
            
            # 显示节点属性
            if node_data:
                attrs = []
                if node_data.get('node_name'):
                    attrs.append(f"node_name: {node_data['node_name']}")
                if node_data.get('type'):
                    attrs.append(f"type: {node_data['type']}")
                if node_data.get('op_type'):
                    attrs.append(f"op_type: {node_data['op_type']}")
                if node_data.get('operation'):
                    attrs.append(f"operation: {node_data['operation']}")
                if node_data.get('law_article'):
                    attrs.append(f"law_article: {node_data['law_article']}")
                if node_data.get('prompt'):
                    attrs.append(f"prompt: {node_data['prompt']}")
                
                if attrs:
                    f.write("     属性: " + ", ".join(attrs) + "\n")
            
            # 显示度信息
            if isinstance(G, nx.DiGraph):
                in_degree = G.in_degree(node_name)
                out_degree = G.out_degree(node_name)
                f.write(f"     入度: {in_degree}, 出度: {out_degree}\n")
            else:
                degree = G.degree(node_name)
                f.write(f"     度: {degree}\n")
            
            # 显示前驱和后继节点（如果有向图）
            if isinstance(G, nx.DiGraph):
                predecessors = list(G.predecessors(node_name))
                successors = list(G.successors(node_name))
                if predecessors:
                    f.write(f"     前驱节点: {', '.join(sorted(predecessors))}\n")
                if successors:
                    f.write(f"     后继节点: {', '.join(sorted(successors))}\n")
        
        # 3. 所有边列表
        f.write("\n\n【所有边列表】\n")
        f.write("-" * 80 + "\n")
        
        # 获取所有边，按源节点和目标节点排序
        all_edges = sorted(G.edges(data=True), key=lambda x: (x[0], x[1]))
        
        if isinstance(G, nx.DiGraph):
            for idx, (source, target, edge_data) in enumerate(all_edges, 1):
                f.write(f"{idx:3d}. {source} -> {target}\n")
                if edge_data:
                    attrs = [f"{k}: {v}" for k, v in edge_data.items() if v]
                    if attrs:
                        f.write(f"     属性: {', '.join(attrs)}\n")
        else:
            for idx, (source, target, edge_data) in enumerate(all_edges, 1):
                f.write(f"{idx:3d}. {source} - {target}\n")
                if edge_data:
                    attrs = [f"{k}: {v}" for k, v in edge_data.items() if v]
                    if attrs:
                        f.write(f"     属性: {', '.join(attrs)}\n")
        
        # 4. 按结果节点分组的边（适用于有向图）
        if isinstance(G, nx.DiGraph):
            f.write("\n\n【按结果节点分组的边】\n")
            f.write("-" * 80 + "\n")
            
            # 按目标节点分组
            edges_by_target = {}
            for source, target in G.edges():
                if target not in edges_by_target:
                    edges_by_target[target] = []
                edges_by_target[target].append(source)
            
            # 按目标节点排序
            for target in sorted(edges_by_target.keys()):
                sources = sorted(edges_by_target[target])
                target_data = G.nodes[target]
                
                f.write(f"\n结果节点: {target}\n")
                if target_data:
                    if target_data.get('operation'):
                        f.write(f"  操作: {target_data['operation']}\n")
                    if target_data.get('law_article'):
                        f.write(f"  法条: {target_data['law_article']}\n")
                f.write(f"  条件节点 ({len(sources)} 个):\n")
                for i, source in enumerate(sources, 1):
                    f.write(f"    {i:2d}. {source}\n")
        
        # 5. 节点统计（按类型分组）
        f.write("\n\n【节点统计（按类型分组）】\n")
        f.write("-" * 80 + "\n")
        
        nodes_by_type = {}
        for node, data in G.nodes(data=True):
            node_type = data.get('type', '未知')
            if node_type not in nodes_by_type:
                nodes_by_type[node_type] = []
            nodes_by_type[node_type].append(node)
        
        for node_type in sorted(nodes_by_type.keys()):
            nodes = sorted(nodes_by_type[node_type])
            f.write(f"{node_type}: {len(nodes)} 个节点\n")
            for node in nodes:
                f.write(f"  - {node}\n")
        
        f.write("\n" + "=" * 80 + "\n")
        f.write("输出完成\n")
        f.write("=" * 80 + "\n")
        
    finally:
        if output_file:
            f.close()
            print(f'✅ 已保存到文件: {os.path.abspath(output_file)}')
        else:
            print("\n✅ 输出完成")


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("用法: python utils.py <graphml文件路径> [输出文件路径]")
        print("示例: python utils.py merged_graph.graphml graph_details.txt")
        sys.exit(1)
    
    graphml_path = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        print_graph_nodes_and_edges(graphml_path, output_file)
    except Exception as e:
        print(f"❌ 错误: {e}")
        sys.exit(1)

