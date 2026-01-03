import tkinter as tk
from tkinter import filedialog


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
    api_label = tk.Label(conf_frame, text='API密钥：')
    graph_json_file_label = tk.Label(conf_frame, text='图谱JSON文件路径：')
    result_json_file_label = tk.Label(conf_frame, text='任务节点JSON文件路径：')

    platform_entry = tk.Entry(conf_frame, fg='gray')
    platform_entry_placeholder = '例如：https://api.openai.com/v1'
    platform_entry.insert(0, platform_entry_placeholder)
    platform_entry.bind('<FocusIn>', lambda event: on_entry_focus_in(event, platform_entry_placeholder))
    platform_entry.bind('<FocusOut>', lambda event: on_entry_focus_out(event, platform_entry_placeholder))
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
    execute_button = tk.Button(conf_frame, text='检查并执行')

    platform_label.grid(row=0, column=0, padx=pad, pady=pad, sticky='e')
    api_label.grid(row=1, column=0, padx=pad, pady=pad, sticky='e')
    graph_json_file_label.grid(row=2, column=0, padx=pad, pady=pad, sticky='e')
    result_json_file_label.grid(row=3, column=0, padx=pad, pady=pad, sticky='e')

    graph_json_browse_button.grid(row=2, column=2, padx=pad, pady=pad)
    result_json_browse_button.grid(row=3, column=2, padx=pad, pady=pad)
    execute_button.grid(row=4, column=0, columnspan=3, padx=pad, pady=pad)

    platform_entry.grid(row=0, column=1, columnspan=2, padx=pad, pady=pad, sticky='ew')
    api_entry.grid(row=1, column=1, columnspan=2, padx=pad, pady=pad, sticky='ew')
    graph_json_file_entry.grid(row=2, column=1, padx=pad, pady=pad)
    result_json_file_entry.grid(row=3, column=1, padx=pad, pady=pad)

    
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


    window.mainloop()


if __name__ == '__main__':
    main()
