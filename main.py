import tkinter as tk
from tkinter import filedialog
import subprocess
import os
import threading
import sys
import queue
from check_json import check_graph_json_file, check_result_json_file, check_conditional_rule_pairs
from json_to_graph_v4 import json_to_graphml
from check_json_postprocess import check_graph_for_cycles
from run_v2 import run_inference


def browse_file(target_var, entry_widget):
    # Opens the file dialog
    file_path = filedialog.askopenfilename(
        initialdir='.', 
        title='选择Json文件',
        filetypes=(('Json files', '*.json'), ('All files', '*.*'))
    )
    if file_path:
        entry_widget.config(fg='black')
        target_var.set(file_path)


def on_entry_focus_in(event, placeholder_text):
    # 'event.widget' is the specific entry box that was clicked
    entry_widget = event.widget
    if entry_widget.get() == placeholder_text:
        entry_widget.delete(0, tk.END)
        entry_widget.config(fg='black')

def on_entry_focus_out(event, placeholder_text):
    entry_widget = event.widget
    if entry_widget.get() == '':
        entry_widget.insert(0, placeholder_text)
        entry_widget.config(fg='grey')


def on_text_focus_in(event, placeholder_text):
    text_widget = event.widget
    current_content = text_widget.get('1.0', 'end-1c')
    if current_content == placeholder_text:
        text_widget.delete('1.0', 'end')
        text_widget.config(fg='black')

def on_text_focus_out(event, placeholder_text):
    text_widget = event.widget
    current_content = text_widget.get('1.0', 'end-1c')
    
    if current_content == '':
        text_widget.insert('1.0', placeholder_text)
        text_widget.config(fg='grey')

def execute_json_to_graph(graph_json_path, result_json_path, output_text, case_text, platform_entry, api_entry, model_name_entry):
    """执行检查和处理流程"""
    output_text.config(fg='black')
    output_text.delete('1.0', tk.END)
    
    # 检查图谱JSON文件路径
    if not graph_json_path or graph_json_path == '例如：C:/path/to/test.json':
        output_text.insert('1.0', '❌ 错误：请先选择图谱JSON文件\n')
        return
    
    if not os.path.exists(graph_json_path):
        output_text.insert('1.0', f'❌ 错误：文件不存在: {graph_json_path}\n')
        return
    
    # 检查结果节点JSON文件路径
    if not result_json_path or result_json_path == '例如：C:/path/to/test.json':
        output_text.insert('1.0', '❌ 错误：请先选择任务节点JSON文件\n')
        return
    
    if not os.path.exists(result_json_path):
        output_text.insert('1.0', f'❌ 错误：文件不存在: {result_json_path}\n')
        return
    
    # 获取测试用例
    facts = case_text.get('1.0', 'end-1c').strip()
    if not facts or facts == '在此处输入测试用的案例...':
        output_text.insert('1.0', '❌ 错误：请先输入测试用例\n')
        return
    
    # 获取API配置
    base_url = platform_entry.get().strip()
    if not base_url or base_url == '例如：https://api.openai.com/v1':
        output_text.insert('1.0', '❌ 错误：请先输入大模型平台网址\n')
        return
    
    api_token = api_entry.get().strip()
    if not api_token or api_token == '例如：sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx':
        output_text.insert('1.0', '❌ 错误：请先输入API密钥\n')
        return
    
    # 获取模型名称
    model_name = model_name_entry.get().strip()
    if not model_name or model_name == '例如：qwen-max':
        output_text.insert('1.0', '❌ 错误：请先输入模型名称\n')
        return
    
    # 显示开始信息
    output_text.insert('1.0', '=' * 60 + '\n')
    output_text.insert(tk.END, '开始检查和处理...\n')
    output_text.insert(tk.END, f'模型名称: {model_name}\n')
    output_text.insert(tk.END, '=' * 60 + '\n\n')

    output_queue = queue.Queue()
    worker_done = threading.Event()

    def flush_output_queue():
        while True:
            try:
                message = output_queue.get_nowait()
            except queue.Empty:
                break
            output_text.insert(tk.END, message)
            output_text.see(tk.END)

        if not worker_done.is_set() or not output_queue.empty():
            output_text.after(100, flush_output_queue)
    
    # 在后台线程中执行，避免阻塞UI
    def run_checks():
        try:
            def append_output(text):
                """实时追加输出到界面"""
                output_queue.put(text)
            
            def capture_print(*args, **kwargs):
                """捕获 print 输出并实时显示"""
                text = ' '.join(str(arg) for arg in args) + '\n'
                append_output(text)
            
            # 临时重定向 print
            import builtins
            original_print = builtins.print
            builtins.print = capture_print
            
            # Step 1: 检查 JSON 文件
            append_output("Step 1: 检查 JSON 文件合法性\n")
            append_output("-" * 60 + "\n")
            
            try:
                graph_check_passed = check_graph_json_file(graph_json_path)
                result_check_passed = check_result_json_file(result_json_path)
                
                if not graph_check_passed or not result_check_passed:
                    append_output("\n❌ Step 1 检查失败，停止执行后续步骤\n")
                    append_output("=" * 60 + "\n")
                    return  # 提前返回，不执行后续步骤
            finally:
                builtins.print = original_print
            
            append_output("\n" + "=" * 60 + "\n\n")
            
            # Step 2: 转换为图（不保存文件）
            append_output("Step 2: 转换为图\n")
            append_output("-" * 60 + "\n")
            
            builtins.print = capture_print
            try:
                # 调用 json_to_graphml，不保存文件（传入 None）
                nx_G = json_to_graphml(graph_json_path, None)
            except Exception as e:
                append_output(f"\n❌ Step 2 转换失败: {e}\n")
                append_output("停止执行后续步骤\n")
                append_output("=" * 60 + "\n")
                return  # 提前返回
            finally:
                builtins.print = original_print
            
            append_output("\n" + "=" * 60 + "\n\n")
            
            # Step 3: 检查图的环
            append_output("Step 3: 检查图的环\n")
            append_output("-" * 60 + "\n")
            
            builtins.print = capture_print
            try:
                has_cycles, cycles, cycle_nodes = check_graph_for_cycles(nx_G)
                if has_cycles:
                    append_output("\n❌ 图检查失败，存在环，停止执行后续步骤\n")
                    append_output("=" * 60 + "\n")
                    return  # 提前返回，不执行 Step 4
                else:
                    append_output("\n✅ 图检查通过，不存在环\n")
            finally:
                builtins.print = original_print
            
            append_output("\n" + "=" * 60 + "\n\n")
            
            # Step 4: 检查条件判断规则的分支完整性
            append_output("Step 4: 检查条件判断规则分支配对\n")
            append_output("-" * 60 + "\n")

            builtins.print = capture_print
            try:
                conditional_pairs_passed = check_conditional_rule_pairs(graph_json_path)
                if not conditional_pairs_passed:
                    append_output("\n❌ Step 4 检查失败，停止执行后续步骤\n")
                    append_output("=" * 60 + "\n")
                    return  # 提前返回，不执行 Step 5
            finally:
                builtins.print = original_print

            append_output("\n" + "=" * 60 + "\n\n")

            # Step 5: 执行推理（只有前面都通过才执行）
            append_output("Step 5: 执行图谱推理\n")
            append_output("-" * 60 + "\n")
            
            builtins.print = capture_print
            try:
                # 使用前端传入的模型名称
                run_inference(
                    graph=nx_G,
                    facts=facts,
                    base_url=base_url,
                    api_token=api_token,
                    model=model_name
                )
                append_output("\n✅ 推理完成！\n")
            finally:
                builtins.print = original_print
            
            append_output("\n" + "=" * 60 + "\n")
            append_output("✅ 所有步骤完成！\n")
            
        except Exception as e:
            import traceback
            error_msg = f'\n\n❌ 错误: {str(e)}\n'
            error_msg += traceback.format_exc()
            output_queue.put(error_msg)
        finally:
            worker_done.set()
    
    # 启动后台线程
    thread = threading.Thread(target=run_checks)
    thread.daemon = True
    thread.start()
    flush_output_queue()

def main():
    window = tk.Tk()
    window.title('法律规则表达测试工具')
    # window.geometry('800x600')

    pad = 10

    window.columnconfigure(0, weight=1, uniform='group1')
    window.columnconfigure(1, weight=1, uniform='group1')
    window.rowconfigure(0, weight=1)
    window.columnconfigure(1, weight=1)

    conf_frame = tk.Frame(window, borderwidth=2, relief='groove')
    conf_frame.grid(row=0, column=0, padx=pad, pady=pad, sticky='nsew')

    case_frame = tk.Frame(window, borderwidth=2, relief='groove')
    case_frame.grid(row=0, column=1, padx=pad, pady=pad, sticky='nsew')

    output_frame = tk.Frame(window, borderwidth=2, relief='groove')
    output_frame.grid(row=1, column=0, columnspan=2, padx=pad, pady=pad, sticky='ew')

    platform_label = tk.Label(conf_frame, text='大模型平台网址：')
    model_name_label = tk.Label(conf_frame, text='模型名称：')
    api_label = tk.Label(conf_frame, text='API密钥：')
    graph_json_file_label = tk.Label(conf_frame, text='图谱JSON文件路径：')
    result_json_file_label = tk.Label(conf_frame, text='任务节点JSON文件路径：')

    platform_entry = tk.Entry(conf_frame, fg='gray')
    platform_entry_placeholder = '例如：https://dashscope.aliyuncs.com/compatible-mode/v1'
    platform_entry.insert(0, platform_entry_placeholder)
    platform_entry.bind('<FocusIn>', lambda event: on_entry_focus_in(event, platform_entry_placeholder))
    platform_entry.bind('<FocusOut>', lambda event: on_entry_focus_out(event, platform_entry_placeholder))
    model_name_entry = tk.Entry(conf_frame, fg='gray')
    model_name_entry_placeholder = '例如：qwen-max'
    model_name_entry.insert(0, model_name_entry_placeholder)
    model_name_entry.bind('<FocusIn>', lambda event: on_entry_focus_in(event, model_name_entry_placeholder))
    model_name_entry.bind('<FocusOut>', lambda event: on_entry_focus_out(event, model_name_entry_placeholder))
    api_entry = tk.Entry(conf_frame, fg='gray')
    api_entry_placeholder = '例如：sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
    api_entry.insert(0, api_entry_placeholder)
    api_entry.bind('<FocusIn>', lambda event: on_entry_focus_in(event, api_entry_placeholder))
    api_entry.bind('<FocusOut>', lambda event: on_entry_focus_out(event, api_entry_placeholder))
    graph_json_path_var = tk.StringVar()
    graph_json_file_entry = tk.Entry(conf_frame, textvariable=graph_json_path_var, fg='gray')
    graph_json_file_entry_placeholder = '例如：C:/path/to/test.json'
    graph_json_file_entry.insert(0, graph_json_file_entry_placeholder)
    graph_json_file_entry.bind('<FocusIn>', lambda event: on_entry_focus_in(event, graph_json_file_entry_placeholder))
    graph_json_file_entry.bind('<FocusOut>', lambda event: on_entry_focus_out(event, graph_json_file_entry_placeholder))

    result_json_path_var = tk.StringVar()
    result_json_file_entry = tk.Entry(conf_frame, textvariable=result_json_path_var, fg='gray')
    result_json_file_entry_placeholder = '例如：C:/path/to/test.json'
    result_json_file_entry.insert(0, result_json_file_entry_placeholder)
    result_json_file_entry.bind('<FocusIn>', lambda event: on_entry_focus_in(event, result_json_file_entry_placeholder))
    result_json_file_entry.bind('<FocusOut>', lambda event: on_entry_focus_out(event, result_json_file_entry_placeholder))

    graph_json_browse_button = tk.Button(conf_frame, text='浏览...', command=lambda: browse_file(graph_json_path_var, graph_json_file_entry))
    result_json_browse_button = tk.Button(conf_frame, text='浏览...', command=lambda: browse_file(result_json_path_var, result_json_file_entry))
    
    # 创建输出文本区域（需要在execute_button之前创建）
    output_label = tk.Label(output_frame, text='执行结果：')
    output_text = tk.Text(output_frame, fg='gray')
    output_text_placeholder = '执行结果将在此处显示...'
    output_text.insert('1.0', output_text_placeholder)
    output_text.bind('<FocusIn>', lambda event: on_text_focus_in(event, output_text_placeholder))
    output_text.bind('<FocusOut>', lambda event: on_text_focus_out(event, output_text_placeholder))
    output_frame.columnconfigure(0, weight=1)
    output_frame.rowconfigure(0, weight=0)
    output_frame.rowconfigure(1, weight=1)
    output_label.grid(row=0, column=0, padx=pad, pady=pad, sticky='nw')
    output_text.grid(row=1, column=0, padx=pad, pady=pad, sticky='ew')
    
    # 修改execute_button，添加点击事件
    execute_button = tk.Button(
        conf_frame, 
        text='检查并执行',
        command=lambda: execute_json_to_graph(
            graph_json_path_var.get(), 
            result_json_path_var.get(), 
            output_text,
            case_text,
            platform_entry,
            api_entry,
            model_name_entry
        )
    )

    platform_label.grid(row=0, column=0, padx=pad, pady=pad, sticky='e')
    model_name_label.grid(row=1, column=0, padx=pad, pady=pad, sticky='e')
    api_label.grid(row=2, column=0, padx=pad, pady=pad, sticky='e')
    graph_json_file_label.grid(row=3, column=0, padx=pad, pady=pad, sticky='e')
    result_json_file_label.grid(row=4, column=0, padx=pad, pady=pad, sticky='e')

    graph_json_browse_button.grid(row=3, column=2, padx=pad, pady=pad)
    result_json_browse_button.grid(row=4, column=2, padx=pad, pady=pad)
    execute_button.grid(row=5, column=0, columnspan=3, padx=pad, pady=pad)

    platform_entry.grid(row=0, column=1, columnspan=2, padx=pad, pady=pad, sticky='ew')
    model_name_entry.grid(row=1, column=1, columnspan=2, padx=pad, pady=pad, sticky='ew')
    api_entry.grid(row=2, column=1, columnspan=2, padx=pad, pady=pad, sticky='ew')
    graph_json_file_entry.grid(row=3, column=1, padx=pad, pady=pad)
    result_json_file_entry.grid(row=4, column=1, padx=pad, pady=pad)

    
    case_label = tk.Label(case_frame, text='测试用例：')
    case_text = tk.Text(case_frame, width=1, height=1, fg='gray')
    case_text_placeholder = '在此处输入测试用的案例...'
    case_text.insert('1.0', case_text_placeholder)
    case_text.bind('<FocusIn>', lambda event: on_text_focus_in(event, case_text_placeholder))
    case_text.bind('<FocusOut>', lambda event: on_text_focus_out(event, case_text_placeholder))
    case_frame.columnconfigure(0, weight=1)
    case_frame.rowconfigure(0, weight=0)
    case_frame.rowconfigure(1, weight=1)
    case_label.grid(row=0, column=0, padx=pad, pady=pad, sticky='nw')
    case_text.grid(row=1, column=0, padx=pad, pady=pad, sticky='nswe')


    window.mainloop()


if __name__ == '__main__':
    main()
