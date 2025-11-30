"""
法条图谱可视化工具
从 graph_data 目录下的 JSON 文件读取法条和子图数据，
融合所有子图后生成可视化图谱
"""
from pyvis.network import Network
import networkx as nx
import matplotlib
matplotlib.use('Agg')  # 使用非交互式后端
import matplotlib.pyplot as plt
import webbrowser
import os
import json

# 确保中文能够正确显示
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Noto Sans CJK SC', 'Arial Unicode MS', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False

#图谱需要增加一下节点与法条的关联

# ==========================================
# 0. 从 graph_data 目录读取所有法条子图数据
# ==========================================
GRAPH_DATA_DIR = "graph_data"

def load_graph_data_from_json_files():
    """
    从 graph_data 目录下的所有 JSON 文件加载法条和子图数据
    返回融合后的规则数据列表，每个规则包含法条信息
    """
    graph_data_dir = os.path.join(os.path.dirname(__file__), GRAPH_DATA_DIR)
    
    if not os.path.exists(graph_data_dir):
        print(f"⚠️  目录不存在: {graph_data_dir}")
        return [], []
    
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
    
    # 存储所有规则数据（每个规则包含法条信息）
    all_rules = []
    law_info_list = []
    
    # 按文件名排序，确保顺序一致
    json_files.sort()
    
    print(f"📂 找到 {len(json_files)} 个 JSON 文件:")
    for json_file in json_files:
        print(f"  - {os.path.basename(json_file)}")
        
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 提取法条信息
            law_info = None
            if "法条" in data:
                law_info = data["法条"]
                law_info_list.append(law_info)
                law_article = law_info.get('第几条', '')
                print(f"    法条: {law_article}")
            
            # 提取并融合 graph 数据，为每个规则添加法条信息
            if "graph" in data and isinstance(data["graph"], list):
                for rule in data["graph"]:
                    # 为每个规则添加法条关联信息
                    rule_with_law = rule.copy()
                    if law_info:
                        rule_with_law["law_article"] = law_info.get('第几条', '')
                        rule_with_law["law_name"] = law_info.get('名称', '')
                    all_rules.append(rule_with_law)
                print(f"    规则数: {len(data['graph'])}")
        
        except Exception as e:
            print(f"  ⚠️  读取文件失败 {os.path.basename(json_file)}: {e}")
    
    print(f"\n✅ 共加载 {len(all_rules)} 条规则")
    return all_rules, law_info_list

# 加载并融合所有子图数据
rules_data, law_info_list = load_graph_data_from_json_files()

if not rules_data:
    print("❌ 未加载到任何规则数据，程序退出")
    exit(1)

# 显示加载的法条信息
if law_info_list:
    print("\n📋 加载的法条信息:")
    for law_info in law_info_list:
        print(f"  - {law_info.get('名称', '')} {law_info.get('第几条', '')}")
print()

# ==========================================
# 2. 初始化画布和 networkx 图
# ==========================================
# 初始化 pyvis 可视化网络
net = Network(height="800px", width="100%", bgcolor="#ffffff", font_color="black", directed=True)

# 初始化 networkx 有向图，用于保存 GraphML
nx_graph = nx.DiGraph()

# 记录节点与法条的关联
node_law_map = {}  # {node_name: set of law_articles}

# 记录已添加的节点，防止重复
added_nodes = set()
# 记录所有结果节点，用于判断节点类型
result_nodes = set(rule["result"] for rule in rules_data)

def add_node_safe(name, n_type="concept", is_result_node=False, logic="", law_article=""):
    """
    安全添加节点，避免重复
    同时添加到 pyvis 可视化图和 networkx 图
    is_result_node: 该节点是否为某个规则的结果节点
    logic: 逻辑操作符（AND/OR）
    law_article: 关联的法条
    """
    is_new_node = name not in added_nodes
    
    if is_new_node:
        # 添加到 pyvis 可视化图（仅首次添加时）
        if n_type == "result" or is_result_node:
            # 结果节点：红色，椭圆
            net.add_node(name, label=name, color="#ff4d4d", shape="ellipse", font={'size': 24, 'color': 'white'})
        else:
            # 普通条件：浅蓝色，矩形
            net.add_node(name, label=name, color="#d1d8e0", shape="box")
    
    # 处理 networkx 图的节点（无论是新节点还是已存在的节点，都需要合并属性）
    # 如果节点已存在，获取现有属性；否则使用默认值
    if nx_graph.has_node(name):
        existing_attrs = nx_graph.nodes[name]
        existing_law = existing_attrs.get("law_article", "") or ""
        existing_op = existing_attrs.get("operation", "") or ""
    else:
        existing_law = ""
        existing_op = ""
    
    # 合并法条信息（无论节点是否已存在，都需要合并）
    if law_article:
        if name not in node_law_map:
            node_law_map[name] = set()
        node_law_map[name].add(law_article)
        
        # 合并到 law_article 字符串
        if law_article not in existing_law:
            if existing_law:
                final_law = f"{existing_law},{law_article}"
            else:
                final_law = law_article
        else:
            final_law = existing_law
    else:
        final_law = existing_law
    
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
        #"type": "逻辑",
        #"prompt": "",
        "operation": final_op,
        "law_article": final_law
    }
    
    nx_graph.add_node(name, **node_attrs)
    
    if is_new_node:
        added_nodes.add(name)

# ==========================================
# 3. 构建节点与连线
# ==========================================

for idx, rule in enumerate(rules_data):
    result = rule["result"]
    conditions = rule["conditions"]
    logic = rule.get("logic", "")
    law_article = rule.get("law_article", "")
    
    # A. 确保结果节点存在
    add_node_safe(result, n_type="result", is_result_node=True, logic=logic, law_article=law_article)
    
    # B. 创建一个逻辑聚合点 (显示为 "AND" 或 "OR")
    # 为了让多条路径分开展示，我们给每个情形造一个独立的门
    gate_id = f"PATH_{idx}"
    gate_label = logic
    
    # 逻辑门节点样式（仅用于可视化）
    net.add_node(gate_id, label=gate_label, color="#fc5c65", shape="diamond", size=20, font={'size': 12})
    
    # C. 连接：逻辑门 -> 最终结果（仅用于可视化）
    net.add_edge(gate_id, result, width=2)
    
    # D. 处理条件
    for cond in conditions:
        # 判断节点类型：
        # 1. 如果该条件是某个规则的结果节点，则标记为结果节点
        # 2. 其他为普通条件
        # 注意：条件节点也应该关联到当前规则的法条信息
        if cond in result_nodes:
            add_node_safe(cond, n_type="concept", is_result_node=True, law_article=law_article)
        else:
            add_node_safe(cond, n_type="concept", law_article=law_article)
        
        # 连接：条件 -> 逻辑门（仅用于可视化）
        net.add_edge(cond, gate_id, arrows="to")
        
        # 在 networkx 图中添加边：条件 -> 结果（直接连接，不包含逻辑门）
        if not nx_graph.has_edge(cond, result):
            nx_graph.add_edge(cond, result)

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
      "nodeSpacing": 200,       
      "levelSeparation": 150,   
      "treeSpacing": 200        
    }
  },
  "edges": {
    "color": { "inherit": false, "color": "#808080" },
    "smooth": { "type": "cubicBezier", "forceDirection": "vertical", "roundness": 0.5 },
    "arrows": { "to": { "enabled": true, "scaleFactor": 1 } }
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
    for attr in ["node_name", "type", "prompt", "operation", "law_article"]:
        if attr not in node_data:
            node_data[attr] = ""

# 保存为 GraphML 格式
graphml_output = "merged_graph.graphml"
nx.write_graphml(nx_graph, graphml_output, encoding='utf-8')
print(f"\n📊 NetworkX 图统计:")
print(f"  - 节点数: {nx_graph.number_of_nodes()}")
print(f"  - 边数: {nx_graph.number_of_edges()}")
print(f"✅ GraphML 文件已保存: {os.path.abspath(graphml_output)}")

# ==========================================
# 5.1 可视化 networkx 图进行验证
# ==========================================
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

## 可视化 networkx 图
#nx_viz_output = "merged_graph_viz.png"
#visualize_networkx_graph(nx_graph, nx_viz_output, layout='spring')

# ==========================================
# 6. 生成 HTML 可视化并打开
# ==========================================
output_file = "bribe_law_graph.html"
net.write_html(output_file)

print(f"✅ 图谱已生成: {os.path.abspath(output_file)}")
print(f"\n📝 输出文件:")
print(f"  - GraphML: {os.path.abspath(graphml_output)} (用于图遍历)")
#print(f"  - PNG: {os.path.abspath(nx_viz_output)} (NetworkX 图可视化)")
print(f"  - HTML: {os.path.abspath(output_file)} (交互式可视化)")
webbrowser.open("file://" + os.path.abspath(output_file))