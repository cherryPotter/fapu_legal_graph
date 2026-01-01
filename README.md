# fapu_legal_graph

- 输入图谱json，1.转为计算机图graphml、2.可视化图html 和 3.检查
python json_to_graph_v3.py -f demo_graph/抽象示例图谱v4.json -o 抽象示例图谱v4.graphml --html-output 抽象示例图谱v4.html

- 执行
python run.py "graph_data/djt贪污罪json图.graphml" -f "test_data/贪污罪/任某某贪污一审刑事判决书(FBM-CLI.C.559205995).html" -o "test_result/贪污罪/任某某贪污一审刑事判决书(FBM-CLI.C.559205995).json"