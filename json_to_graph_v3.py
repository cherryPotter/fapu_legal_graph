"""
法条图谱可视化工具 v3
从 graph_data 目录下的 JSON 文件读取"规则"数据，
使用"案由"作为节点属性，生成可视化图谱
"""
from pyvis.network import Network
import networkx as nx
import matplotlib
matplotlib.use('Agg')  # 使用非交互式后端
import matplotlib.pyplot as plt
import webbrowser
import os
import json
import argparse

# 确保中文能够正确显示
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Noto Sans CJK SC', 'Arial Unicode MS', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False

# ==========================================
# 0. 从 graph_data 目录读取所有规则数据
# ==========================================
GRAPH_DATA_DIR = ""

def convert_logic_op(计算方式):
    """将中文逻辑操作符转换为英文"""
    if not 计算方式:
        return "AND"
    计算方式 = 计算方式.strip()
    if 计算方式 == "与":
        return "AND"
    elif 计算方式 == "或":
        return "OR"
    elif 计算方式 == "非" or 计算方式 == "否":
        return "NOT"
    elif 计算方式 == "不互斥":
        return "NON_EXCLUSIVE"
    elif 计算方式.upper() == "AND":
        return "AND"
    elif 计算方式.upper() == "OR":
        return "OR"
    elif 计算方式.upper() == "NOT":
        return "NOT"
    elif 计算方式.upper() == "NON_EXCLUSIVE":
        return "NON_EXCLUSIVE"
    else:
        return "AND"  # 默认

def load_rules_from_json_files(file_list=None):
    """
    从 graph_data 目录下的 JSON 文件加载规则数据
    返回融合后的规则数据列表，每个规则包含案由信息
    
    Args:
        file_list: 可选，指定要处理的文件名列表。如果为 None，则处理所有文件。
                   文件名可以是完整路径，或相对于 graph_data 目录的文件名。
    """
    graph_data_dir = os.path.join(os.path.dirname(__file__), GRAPH_DATA_DIR)
    
    if not os.path.exists(graph_data_dir):
        print(f"⚠️  目录不存在: {graph_data_dir}")
        return [], []
    
    # 如果指定了文件列表，只处理这些文件
    if file_list:
        json_files = []
        for file_name in file_list:
            # 如果已经是完整路径
            if os.path.isabs(file_name):
                if os.path.exists(file_name):
                    json_files.append(file_name)
                else:
                    print(f"⚠️  文件不存在: {file_name}")
            else:
                # 相对路径，尝试在 graph_data 目录下查找
                full_path = os.path.join(graph_data_dir, file_name)
                if os.path.exists(full_path):
                    json_files.append(full_path)
                else:
                    print(f"⚠️  文件不存在: {full_path}")
        
        if not json_files:
            print(f"⚠️  没有找到任何有效的 JSON 文件")
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
    
    # 存储所有规则数据（每个规则包含案由信息）
    all_rules = []
    case_types = []
    
    # 按文件名排序，确保顺序一致
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
                    # 处理"逻辑运算"和"定义"类型的规则
                    if rule_type == "逻辑运算" or rule_type == "定义":
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
                
                print(f"    规则数: {rule_count}")
        
        except Exception as e:
            print(f"  ⚠️  读取文件失败 {os.path.basename(json_file)}: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n✅ 共加载 {len(all_rules)} 条规则")
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
示例:
  # 处理所有 graph_data 目录下的 JSON 文件
  python json_to_graph_v3.py

  # 只处理指定的文件（文件名相对于 graph_data 目录）
  python json_to_graph_v3.py -f "1201醉驾量刑(按照醉驾意见新规加入不起诉规则版).json"

  # 使用完整路径指定文件
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
            # 普通条件：浅蓝色，矩形，减小字体和节点大小
            net.add_node(name, label=name, color="#d1d8e0", shape="box", font={'size': 12}, size=20)
    
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
    
    # 跳过无效规则
    if not result or not conditions:
        continue
    
    # 处理"结果"可能是字符串或数组的情况
    if isinstance(result, list):
        if len(result) == 0:
            continue
        result = result[0]  # 取第一个结果
    
    # A. 确保结果节点存在
    add_node_safe(result, n_type="result", is_result_node=True, logic=logic, case_type=case_type)
    
    # B. 创建一个逻辑聚合点 (显示为 "AND" 或 "OR" 或 "NOT" 或 "⊕")
    # 为了让多条路径分开展示，我们给每个情形造一个独立的门
    gate_id = f"PATH_{idx}"
    
    # 根据逻辑类型设置不同的标签和样式
    if logic == "NON_EXCLUSIVE":
        gate_label = "⊕"  # 使用特殊符号表示"不互斥"
        gate_color = "#95e1d3"  # 浅绿色
        gate_shape = "hexagon"  # 使用六边形区分
        gate_font_color = "black"
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
print(f"\n📊 NetworkX 图统计:")
print(f"  - 节点数: {nx_graph.number_of_nodes()}")
print(f"  - 边数: {nx_graph.number_of_edges()}")
print(f"✅ GraphML 文件已保存: {os.path.abspath(graphml_output)}")

# ==========================================
# 6. 生成 HTML 可视化并打开
# ==========================================
output_file = args.html_output
net.write_html(output_file)

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
# webbrowser.open("file://" + os.path.abspath(output_file))

