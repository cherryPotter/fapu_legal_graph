#!/bin/bash
# 打包 main.py 为二进制文件的脚本

echo "开始打包 main.py 为二进制文件..."

# 检查是否安装了 PyInstaller
if ! command -v pyinstaller &> /dev/null; then
    echo "错误: 未安装 PyInstaller"
    echo "请运行: pip install pyinstaller"
    exit 1
fi

# 清理之前的构建
echo "清理之前的构建文件..."
rm -rf build dist main.spec __pycache__

# 执行打包
echo "开始打包..."
pyinstaller \
    --name="法律规则表达测试工具" \
    --onefile \
    --windowed \
    --add-data="check_json.py:." \
    --add-data="json_to_graph_v4.py:." \
    --add-data="check_json_postprocess.py:." \
    --add-data="run_v2.py:." \
    --hidden-import=tkinter \
    --hidden-import=networkx \
    --hidden-import=openai \
    --hidden-import=check_json \
    --hidden-import=json_to_graph_v4 \
    --hidden-import=check_json_postprocess \
    --hidden-import=run_v2 \
    --collect-all=networkx \
    --collect-all=openai \
    main.py

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ 打包成功！"
    echo "二进制文件位置: dist/法律规则表达测试工具"
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "macOS 系统: dist/法律规则表达测试工具.app"
    elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
        echo "Windows 系统: dist/法律规则表达测试工具.exe"
    else
        echo "Linux 系统: dist/法律规则表达测试工具"
    fi
else
    echo ""
    echo "❌ 打包失败，请检查错误信息"
    exit 1
fi

