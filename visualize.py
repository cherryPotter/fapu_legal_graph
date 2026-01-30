#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GraphML 图可视化工具
从 GraphML 文件生成 HTML 可视化
"""
from pyvis.network import Network
import networkx as nx
import os
import argparse
import re
import json


def get_node_color(node_name, nx_graph, result_nodes):
    """
    根据节点属性确定颜色
    
    Args:
        node_name: 节点名称
        nx_graph: networkx 图对象
        result_nodes: 结果节点集合
    
    Returns:
        str: 颜色代码
    """
    in_degree = nx_graph.in_degree(node_name)
    node_attrs = nx_graph.nodes[node_name]
    operation = node_attrs.get("operation", "")
    is_result = operation or node_name in result_nodes
    
    if in_degree == 0:
        if is_result:
            return "#ff4d4d"  # 结果节点保持红色
        else:
            return "#d1d8e0"  # 入度为0的普通节点：灰色
    else:
        if is_result:
            return "#ff4d4d"  # 结果节点保持红色
        else:
            return "#a8e6cf"  # 入度不为0的普通节点：浅绿色


def get_gate_style(logic):
    """获取逻辑门的样式配置"""
    if logic == "NON_EXCLUSIVE":
        return {
            "label": "⊕",
            "color": "#95e1d3",
            "shape": "hexagon",
            "font_color": "black"
        }
    elif logic == "ARITHMETIC":
        return {
            "label": "ARITH",
            "color": "#9b59b6",
            "shape": "triangle",
            "font_color": "white"
        }
    elif logic == "CONDITIONAL":
        return {
            "label": "IF",
            "color": "#f39c12",
            "shape": "square",
            "font_color": "white"
        }
    elif logic == "COMPARISON":
        return {
            "label": "COMP",
            "color": "#3498db",
            "shape": "star",
            "font_color": "white"
        }
    else:
        return {
            "label": logic,
            "color": "#fc5c65",
            "shape": "diamond",
            "font_color": "white"
        }


def graphml_to_html(graphml_file, output_file):
    """
    将 GraphML 文件转换为 HTML 可视化
    
    Args:
        graphml_file: 输入的 GraphML 文件路径
        output_file: 输出的 HTML 文件路径
    """
    print(f"📂 读取 GraphML 文件: {os.path.basename(graphml_file)}")
    
    # 读取 GraphML 文件
    nx_graph = nx.read_graphml(graphml_file)
    
    if not nx_graph.is_directed():
        nx_graph = nx_graph.to_directed()
    
    print(f"📊 图统计: 节点数: {nx_graph.number_of_nodes()}, 边数: {nx_graph.number_of_edges()}")
    
    # 初始化 pyvis 可视化网络
    net = Network(height="100vh", width="100%", bgcolor="#ffffff", font_color="black", directed=True)
    
    # 收集结果节点
    result_nodes = set()
    for node_name in nx_graph.nodes():
        node_attrs = nx_graph.nodes[node_name]
        operation = node_attrs.get("operation", "")
        if operation:
            result_nodes.add(node_name)
    
    # 添加节点到可视化图
    added_nodes = set()
    virtual_gate_nodes = {}  # 存储虚拟的操作节点：{结果节点名: 操作节点名}
    
    # 第一遍：添加所有原始节点
    for node_name in nx_graph.nodes():
        node_attrs = nx_graph.nodes[node_name]
        node_type = node_attrs.get("type", "")
        operation = node_attrs.get("operation", "")
        
        # 处理普通节点
        node_color = get_node_color(node_name, nx_graph, result_nodes)
        is_result = operation or node_name in result_nodes
        
        if is_result:
            # 结果节点：只显示节点名称（操作节点会单独创建）
            net.add_node(
                node_name, 
                label=node_name, 
                color=node_color, 
                shape="ellipse", 
                font={'size': 16, 'color': 'white'}, 
                size=25
            )
            
            # 如果结果节点有 operation，创建虚拟的操作节点
            if operation:
                # 处理 operation 可能是逗号分隔的多个值的情况
                operation_list = [op.strip() for op in operation.split(',')] if operation else []
                # 检查是否有特殊操作类型
                special_ops = ["NON_EXCLUSIVE", "ARITHMETIC", "CONDITIONAL", "COMPARISON"]
                has_special_op = any(op in special_ops for op in operation_list)
                
                if has_special_op:
                    # 找到第一个特殊操作类型
                    special_op = next((op for op in operation_list if op in special_ops), None)
                    if special_op:
                        # 创建虚拟的操作节点
                        gate_node_id = f"OP_{node_name}"
                        virtual_gate_nodes[node_name] = gate_node_id
                        
                        # 获取 gate 样式
                        gate_style = get_gate_style(special_op)
                        
                        # 添加操作节点
                        net.add_node(
                            gate_node_id,
                            label=gate_style["label"],
                            color=gate_style["color"],
                            shape=gate_style["shape"],
                            size=15,
                            font={'size': 12, 'color': gate_style["font_color"]}
                        )
                        added_nodes.add(gate_node_id)
                elif any(op in ["AND", "OR", "NOT"] for op in operation_list):
                    # 标准逻辑运算，也创建操作节点
                    gate_node_id = f"OP_{node_name}"
                    virtual_gate_nodes[node_name] = gate_node_id
                    
                    # 使用默认样式
                    gate_style = get_gate_style(operation_list[0] if operation_list else "AND")
                    
                    net.add_node(
                        gate_node_id,
                        label=gate_style["label"],
                        color=gate_style["color"],
                        shape=gate_style["shape"],
                        size=15,
                        font={'size': 12, 'color': gate_style["font_color"]}
                    )
                    added_nodes.add(gate_node_id)
        else:
            # 普通节点
            net.add_node(
                node_name, 
                label=node_name, 
                color=node_color, 
                shape="box", 
                font={'size': 12}, 
                size=20
            )
        added_nodes.add(node_name)
    
    # 第二遍：添加边，处理有虚拟操作节点的情况
    for u, v in nx_graph.edges():
        if u not in added_nodes or v not in added_nodes:
            continue
        
        # 如果目标节点有虚拟操作节点，需要修改边的连接
        if v in virtual_gate_nodes:
            gate_node = virtual_gate_nodes[v]
            # 条件 -> 操作节点
            net.add_edge(u, gate_node, arrows="to", color="#808080", width=1.5)
            # 操作节点 -> 结果节点
            net.add_edge(gate_node, v, arrows="to", color="#808080", width=2)
        else:
            # 普通边
            net.add_edge(u, v, arrows="to", color="#808080", width=1.5)
    
    # 设置层次化布局
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
    
    # 生成 HTML
    print("\n🎨 生成 HTML 可视化...")
    net.write_html(output_file)
    
    # 优化 HTML 样式
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
        
        # 添加全屏样式
        style_addition = """
            html, body {
                margin: 0;
                padding: 0;
                width: 100%;
                height: 100%;
                overflow: hidden;
            }
"""
        
        if '</style>' in html_content:
            html_content = html_content.replace('</style>', style_addition + '</style>', 1)
        else:
            if '</head>' in html_content:
                html_content = html_content.replace('</head>', '<style>' + style_addition + '</style></head>', 1)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
    except Exception as e:
        print(f"⚠️  优化 HTML 样式时出错: {e}")
    
    print(f"✅ HTML 文件已生成: {os.path.abspath(output_file)}")


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='GraphML 图可视化工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python visualize.py -f input.graphml -o output.html
  python visualize.py -f input.graphml
        """
    )
    parser.add_argument(
        '-f', '--file',
        type=str,
        required=True,
        help='输入的 GraphML 文件路径'
    )
    parser.add_argument(
        '-o', '--output',
        type=str,
        default=None,
        help='输出的 HTML 文件名（默认: 输入文件名.html）'
    )
    return parser.parse_args()


def main():
    """主函数"""
    args = parse_args()
    
    graphml_file = args.file
    if not os.path.exists(graphml_file):
        print(f"❌ 文件不存在: {graphml_file}")
        return 1
    
    # 如果没有指定输出文件，使用输入文件名
    if args.output is None:
        base_name = os.path.splitext(graphml_file)[0]
        output_file = f"{base_name}.html"
    else:
        output_file = args.output
    
    try:
        graphml_to_html(graphml_file, output_file)
        return 0
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    exit(main())

