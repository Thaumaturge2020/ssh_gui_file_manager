import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import paramiko
import os
import stat
import datetime
import threading
from typing import List, Dict, Optional
import queue
import traceback

# 兼容不同版本的 Paramiko 主机密钥策略
try:
    # 尝试导入 AutoAddHostKeyPolicy(新版本)
    AutoAddHostKeyPolicy = paramiko.AutoAddHostKeyPolicy
except AttributeError:
    try:
        # 尝试从 client 模块导入(某些版本)
        from paramiko.client import AutoAddPolicy as AutoAddHostKeyPolicy
    except ImportError:
        # 如果都不存在,创建自定义策略
        class AutoAddHostKeyPolicy(paramiko.MissingHostKeyPolicy):
            def missing_host_key(self, client, hostname, key):
                # 自动接受所有主机密钥
                pass


class SSHFileManagerGUI:
    """SSH远程文件管理器GUI类"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("SSH远程资源管理器")
        
        # 启用高DPI支持
        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
        except:
            pass
        
        # 设置高分辨率窗口
        self.root.geometry("1400x900")
        self.root.minsize(1000, 700)
        
        # 优化字体渲染
        self.root.option_add('*TkDefaultFont', 'Arial 10')
        self.root.option_add('*Font', 'Arial 10')
        
        # SSH连接相关
        self.ssh_client = None
        self.sftp_client = None
        self.current_path = "/"
        self.connected = False
        
        # GUI组件
        self.setup_gui()
        self.setup_styles()
        
        # 消息队列用于线程间通信
        self.message_queue = queue.Queue()
        self.root.after(100, self.process_queue)
    
    def setup_styles(self):
        """设置GUI样式"""
        style = ttk.Style()
        
        # 配置现代化主题
        available_themes = style.theme_names()
        if 'clam' in available_themes:
            style.theme_use('clam')
        elif 'vista' in available_themes:
            style.theme_use('vista')
        
        # 自定义高清样式
        style.configure('Title.TLabel', font=('Arial', 14, 'bold'))
        style.configure('Status.TLabel', font=('Arial', 10))
        style.configure('Treeview.Heading', font=('Arial', 11, 'bold'))
        style.configure('Treeview', font=('Arial', 10), rowheight=25)
        
        # 按钮样式
        style.configure('TButton', font=('Arial', 10), padding=(10, 6))
        style.configure('Toolbutton.TButton', font=('Arial', 9), padding=(8, 4))
        
        # 输入框样式
        style.configure('TEntry', font=('Arial', 10), fieldbackground='white')
        style.configure('Path.TEntry', font=('Consolas', 10), fieldbackground='#f8f9fa')
        
        # LabelFrame样式
        style.configure('TLabelframe.Label', font=('Arial', 11, 'bold'))
        style.configure('TLabelframe', padding=10)
        
        # 优化颜色方案
        style.configure('TFrame', background='#f5f5f5')
        style.configure('TLabel', background='#f5f5f5', font=('Arial', 10))
        
        # 高亮样式
        style.map('Treeview', 
                 background=[('selected', '#0078d4')],
                 foreground=[('selected', 'white')])
        
        style.configure('Success.TLabel', foreground='#28a745', font=('Arial', 10, 'bold'))
        style.configure('Error.TLabel', foreground='#dc3545', font=('Arial', 10, 'bold'))
        style.configure('Warning.TLabel', foreground='#ffc107', font=('Arial', 10, 'bold'))
    
    def setup_gui(self):
        """设置GUI界面"""
        # 主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 配置网格权重
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(2, weight=1)
        
        # 连接区域
        self.setup_connection_frame(main_frame)
        
        # 工具栏
        self.setup_toolbar(main_frame)
        
        # 文件浏览区域
        self.setup_file_browser(main_frame)
        
        # 状态栏
        self.setup_status_bar(main_frame)
        
        # 终端区域
        self.setup_terminal_frame(main_frame)
    
    def setup_connection_frame(self, parent):
        """设置连接区域"""
        conn_frame = ttk.LabelFrame(parent, text="SSH连接配置", padding="15")
        conn_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 15))
        conn_frame.columnconfigure(1, weight=1)
        conn_frame.columnconfigure(3, weight=1)
        conn_frame.columnconfigure(5, weight=1)
        
        # 第一行:基本连接信息
        row = 0
        # 服务器地址
        ttk.Label(conn_frame, text="服务器地址:", font=('Arial', 10, 'bold')).grid(row=row, column=0, padx=(0, 8), pady=5, sticky=tk.W)
        self.hostname_var = tk.StringVar(value="localhost")
        hostname_entry = ttk.Entry(conn_frame, textvariable=self.hostname_var, width=25, font=('Arial', 10))
        hostname_entry.grid(row=row, column=1, padx=(0, 15), pady=5, sticky=(tk.W, tk.E))
        
        # 用户名
        ttk.Label(conn_frame, text="用户名:", font=('Arial', 10, 'bold')).grid(row=row, column=2, padx=(0, 8), pady=5, sticky=tk.W)
        self.username_var = tk.StringVar()
        username_entry = ttk.Entry(conn_frame, textvariable=self.username_var, width=20, font=('Arial', 10))
        username_entry.grid(row=row, column=3, padx=(0, 15), pady=5, sticky=(tk.W, tk.E))
        
        # 端口
        ttk.Label(conn_frame, text="端口:", font=('Arial', 10, 'bold')).grid(row=row, column=4, padx=(0, 8), pady=5, sticky=tk.W)
        self.port_var = tk.StringVar(value="22")
        port_entry = ttk.Entry(conn_frame, textvariable=self.port_var, width=10, font=('Arial', 10))
        port_entry.grid(row=row, column=5, padx=(0, 15), pady=5)
        
        # 连接按钮
        button_frame = ttk.Frame(conn_frame)
        button_frame.grid(row=row, column=6, rowspan=2, padx=(10, 0), pady=5, sticky=(tk.N, tk.S))
        
        self.connect_btn = ttk.Button(button_frame, text="连接", command=self.connect_ssh, 
                                    style='TButton', width=12)
        self.connect_btn.pack(pady=(0, 8))
        
        self.disconnect_btn = ttk.Button(button_frame, text="断开", command=self.disconnect_ssh, 
                                       state="disabled", style='TButton', width=12)
        self.disconnect_btn.pack()
        
        # 第二行:认证设置
        row = 1
        auth_label_frame = ttk.Frame(conn_frame)
        auth_label_frame.grid(row=row, column=0, columnspan=6, sticky=(tk.W, tk.E), pady=(10, 5))
        
        ttk.Label(auth_label_frame, text="认证方式:", font=('Arial', 10, 'bold')).pack(side=tk.LEFT)
        
        self.auth_var = tk.StringVar(value="password")
        auth_frame = ttk.Frame(auth_label_frame)
        auth_frame.pack(side=tk.LEFT, padx=(10, 0))
        
        ttk.Radiobutton(auth_frame, text="密码认证", variable=self.auth_var, value="password", 
                       style='TRadiobutton').pack(side=tk.LEFT, padx=(0, 20))
        ttk.Radiobutton(auth_frame, text="密钥认证", variable=self.auth_var, value="key", 
                       style='TRadiobutton').pack(side=tk.LEFT, padx=(0, 20))
        
        # 密钥文件选择
        key_frame = ttk.Frame(auth_label_frame)
        key_frame.pack(side=tk.LEFT, padx=(20, 0))
        
        self.key_file_var = tk.StringVar()
        ttk.Button(key_frame, text="选择密钥", command=self.select_key_file, 
                  style='Toolbutton.TButton').pack(side=tk.LEFT, padx=(0, 10))
        key_label = ttk.Label(key_frame, textvariable=self.key_file_var, foreground="#666666", 
                             font=('Arial', 9, 'italic'))
        key_label.pack(side=tk.LEFT)
    
    def setup_toolbar(self, parent):
        """设置工具栏"""
        toolbar_frame = ttk.LabelFrame(parent, text="导航与操作", padding="12")
        toolbar_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 15))
        toolbar_frame.columnconfigure(1, weight=1)
        
        # 第一行:路径导航
        path_label = ttk.Label(toolbar_frame, text="当前路径:", font=('Arial', 10, 'bold'))
        path_label.grid(row=0, column=0, padx=(0, 10), pady=(0, 8), sticky=tk.W)
        
        self.path_var = tk.StringVar(value="/")
        path_entry = ttk.Entry(toolbar_frame, textvariable=self.path_var, 
                              font=('Consolas', 11), style='Path.TEntry')
        path_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 15), pady=(0, 8))
        path_entry.bind('<Return>', self.navigate_to_path)
        
        nav_btn = ttk.Button(toolbar_frame, text="转到", command=self.navigate_to_path,
                           style='Toolbutton.TButton')
        nav_btn.grid(row=0, column=2, padx=(0, 0), pady=(0, 8))
        
        # 第二行:操作按钮
        btn_frame = ttk.Frame(toolbar_frame)
        btn_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(5, 0))
        
        # 左侧按钮组
        left_btn_frame = ttk.Frame(btn_frame)
        left_btn_frame.pack(side=tk.LEFT)
        
        self.refresh_btn = ttk.Button(left_btn_frame, text="刷新", command=self.refresh_directory, 
                                    state="disabled", style='Toolbutton.TButton')
        self.refresh_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.upload_btn = ttk.Button(left_btn_frame, text="上传文件", command=self.upload_file, 
                                   state="disabled", style='Toolbutton.TButton')
        self.upload_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.mkdir_btn = ttk.Button(left_btn_frame, text="新建目录", command=self.create_directory, 
                                  state="disabled", style='Toolbutton.TButton')
        self.mkdir_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # 右侧按钮组
        right_btn_frame = ttk.Frame(btn_frame)
        right_btn_frame.pack(side=tk.RIGHT)
        
        self.terminal_btn = ttk.Button(right_btn_frame, text="终端", command=self.toggle_terminal,
                                     style='Toolbutton.TButton')
        self.terminal_btn.pack(side=tk.RIGHT)
    
    def setup_file_browser(self, parent):
        """设置文件浏览器"""
        # 创建Panedwindow用于分割文件浏览器和终端
        self.paned_window = ttk.PanedWindow(parent, orient=tk.VERTICAL)
        self.paned_window.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 文件浏览框架
        browser_frame = ttk.LabelFrame(self.paned_window, text="远程文件浏览器", padding="10")
        
        # 创建高清Treeview
        self.tree = ttk.Treeview(browser_frame, columns=('size', 'type', 'permissions', 'modified'), 
                               show='tree headings', style='Treeview')
        
        # 设置列标题
        self.tree.heading('#0', text='文件名称')
        self.tree.heading('size', text='大小')
        self.tree.heading('type', text='类型')
        self.tree.heading('permissions', text='权限')
        self.tree.heading('modified', text='修改时间')
        
        # 优化列宽设置
        self.tree.column('#0', width=400, minwidth=250)
        self.tree.column('size', width=120, minwidth=100)
        self.tree.column('type', width=100, minwidth=80)
        self.tree.column('permissions', width=120, minwidth=100)
        self.tree.column('modified', width=180, minwidth=150)
        
        # 高清滚动条
        tree_scrolly = ttk.Scrollbar(browser_frame, orient=tk.VERTICAL, command=self.tree.yview)
        tree_scrollx = ttk.Scrollbar(browser_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=tree_scrolly.set, xscrollcommand=tree_scrollx.set)
        
        # 网格布局
        self.tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 2), pady=(0, 2))
        tree_scrolly.grid(row=0, column=1, sticky=(tk.N, tk.S))
        tree_scrollx.grid(row=1, column=0, sticky=(tk.W, tk.E))
        
        browser_frame.columnconfigure(0, weight=1)
        browser_frame.rowconfigure(0, weight=1)
        
        # 绑定事件
        self.tree.bind('<Double-1>', self.on_item_double_click)
        self.tree.bind('<Button-3>', self.show_context_menu)  # 右键菜单
        
        # 添加到PanedWindow
        self.paned_window.add(browser_frame, weight=3)
        
        # 上下文菜单
        self.setup_context_menu()
    
    def setup_context_menu(self):
        """设置右键上下文菜单"""
        self.context_menu = tk.Menu(self.root, tearoff=0, font=('Arial', 10))
        self.context_menu.add_command(label="下载", command=self.download_selected)
        self.context_menu.add_command(label="删除", command=self.delete_selected)
        self.context_menu.add_command(label="重命名", command=self.rename_selected)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="属性", command=self.show_properties)
    
    def setup_terminal_frame(self, parent):
        """设置终端区域"""
        self.terminal_frame = ttk.LabelFrame(self.paned_window, text="远程终端", padding="10")
        
        # 终端输出区域
        terminal_text_frame = ttk.Frame(self.terminal_frame)
        terminal_text_frame.pack(fill=tk.BOTH, expand=True)
        
        # 高清终端文本框
        self.terminal_text = tk.Text(terminal_text_frame, height=12, font=('Consolas', 11), 
                                   bg='#1e1e1e', fg='#d4d4d4', insertbackground='#d4d4d4',
                                   selectbackground='#264f78', relief='flat', borderwidth=0)
        
        # 高清滚动条
        terminal_scroll = ttk.Scrollbar(terminal_text_frame, orient=tk.VERTICAL, command=self.terminal_text.yview)
        self.terminal_text.configure(yscrollcommand=terminal_scroll.set)
        
        self.terminal_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 2))
        terminal_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 命令输入区域
        cmd_frame = ttk.Frame(self.terminal_frame)
        cmd_frame.pack(fill=tk.X, pady=(10, 0))
        
        prompt_label = ttk.Label(cmd_frame, text="$", font=('Consolas', 11, 'bold'), foreground='#0078d4')
        prompt_label.pack(side=tk.LEFT, padx=(0, 8))
        
        self.cmd_var = tk.StringVar()
        cmd_entry = ttk.Entry(cmd_frame, textvariable=self.cmd_var, font=('Consolas', 11))
        cmd_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        cmd_entry.bind('<Return>', self.execute_command)
        
        exec_btn = ttk.Button(cmd_frame, text="执行", command=self.execute_command,
                            style='Toolbutton.TButton')
        exec_btn.pack(side=tk.RIGHT)
        
        # 默认隐藏终端
        self.terminal_visible = False
    
    def setup_status_bar(self, parent):
        """设置状态栏"""
        self.status_frame = ttk.Frame(parent, style='TFrame')
        self.status_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(15, 0))
        self.status_frame.columnconfigure(0, weight=1)
        
        # 状态信息框架
        status_info_frame = ttk.Frame(self.status_frame)
        status_info_frame.grid(row=0, column=0, sticky=(tk.W, tk.E))
        status_info_frame.columnconfigure(1, weight=1)
        
        # 状态图标和文本
        self.status_icon_var = tk.StringVar(value="o")
        status_icon_label = ttk.Label(status_info_frame, textvariable=self.status_icon_var, 
                                    font=('Arial', 12))
        status_icon_label.grid(row=0, column=0, padx=(0, 8))
        
        self.status_var = tk.StringVar(value="未连接")
        self.status_label = ttk.Label(status_info_frame, textvariable=self.status_var, 
                                    style='Status.TLabel')
        self.status_label.grid(row=0, column=1, sticky=tk.W)
        
        # 进度条和时间
        progress_frame = ttk.Frame(self.status_frame)
        progress_frame.grid(row=0, column=1, sticky=tk.E, padx=(10, 0))
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, 
                                          length=200, style='TProgressbar')
        self.progress_bar.pack(side=tk.LEFT, padx=(0, 10))
        self.progress_bar.pack_forget()  # 默认隐藏
        
        # 时间显示
        self.time_var = tk.StringVar()
        time_label = ttk.Label(progress_frame, textvariable=self.time_var, 
                             font=('Arial', 9), foreground='#666666')
        time_label.pack(side=tk.LEFT)
        
        # 启动时间更新
        self.update_time()
    
    def update_time(self):
        """更新时间显示"""
        current_time = datetime.datetime.now().strftime("%H:%M:%S")
        self.time_var.set(current_time)
        self.root.after(1000, self.update_time)
    
    def set_status(self, message, status_type="info"):
        """设置状态栏信息"""
        # 设置状态图标
        icons = {
            "info": "i",
            "success": "v", 
            "error": "x",
            "warning": "!",
            "connecting": "~"
        }
        
        self.status_icon_var.set(icons.get(status_type, "i"))
        self.status_var.set(message)
        
        # 设置状态标签样式
        if status_type == "success":
            self.status_label.configure(style='Success.TLabel')
        elif status_type == "error":
            self.status_label.configure(style='Error.TLabel')
        elif status_type == "warning":
            self.status_label.configure(style='Warning.TLabel')
        else:
            self.status_label.configure(style='Status.TLabel')
        
        self.root.update_idletasks()
    
    def select_key_file(self):
        """选择SSH密钥文件"""
        filename = filedialog.askopenfilename(
            title="选择SSH私钥文件",
            filetypes=[("所有文件", "*.*"), ("私钥文件", "*.pem"), ("私钥文件", "*.key")]
        )
        if filename:
            self.key_file_var.set(os.path.basename(filename))
            self.selected_key_file = filename
        else:
            self.selected_key_file = None
    
    def connect_ssh(self):
        """连接SSH服务器"""
        if self.connected:
            messagebox.showwarning("警告", "已经连接到服务器!\n\n如需连接其他服务器,请先断开当前连接.")
            return
        
        hostname = self.hostname_var.get().strip()
        username = self.username_var.get().strip()
        port_str = self.port_var.get().strip()
        
        if not hostname or not username:
            messagebox.showerror("输入错误", "请填写完整的服务器地址和用户名!")
            return
        
        try:
            port = int(port_str)
            if port <= 0 or port > 65535:
                raise ValueError("端口号超出有效范围")
        except ValueError:
            messagebox.showerror("端口错误", "端口号必须是1-65535之间的整数!")
            return
        
        # 检查密钥文件
        if self.auth_var.get() == "key":
            if not hasattr(self, 'selected_key_file') or not self.selected_key_file:
                messagebox.showerror("密钥错误", "请选择SSH私钥文件!")
                return
            if not os.path.exists(self.selected_key_file):
                messagebox.showerror("文件不存在", f"密钥文件不存在:\n{self.selected_key_file}")
                return
        
        # 在单独线程中连接
        self.set_status("正在连接服务器...", "connecting")
        self.connect_btn.config(state="disabled")
        
        thread = threading.Thread(target=self._connect_thread, args=(hostname, username, port))
        thread.daemon = True
        thread.start()
    
    def _connect_thread(self, hostname, username, port):
        """连接线程"""
        try:
            self.message_queue.put(("status", "正在建立SSH连接..."))
            
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(AutoAddHostKeyPolicy())
            
            # 获取认证信息
            if self.auth_var.get() == "key" and hasattr(self, 'selected_key_file'):
                # 密钥认证
                self.message_queue.put(("status", "使用密钥文件认证..."))
                private_key = paramiko.RSAKey.from_private_key_file(self.selected_key_file)
                self.ssh_client.connect(hostname, port=port, username=username, pkey=private_key, timeout=10)
            else:
                # 密码认证
                password = simpledialog.askstring("密码认证", 
                                                f"请输入 {username}@{hostname} 的密码:", 
                                                show='*')
                if not password:
                    self.message_queue.put(("error", "连接已取消"))
                    return
                
                self.message_queue.put(("status", "使用密码认证..."))
                self.ssh_client.connect(hostname, port=port, username=username, password=password, timeout=10)
            
            # 创建SFTP客户端
            self.message_queue.put(("status", "正在建立SFTP连接..."))
            self.sftp_client = self.ssh_client.open_sftp()
            self.current_path = self.sftp_client.getcwd() or "/"
            self.connected = True
            
            self.message_queue.put(("success", f"成功连接到 {username}@{hostname}:{port}"))
            self.message_queue.put(("refresh", None))
            
        except paramiko.AuthenticationException:
            self.message_queue.put(("error", "认证失败:用户名、密码或密钥错误"))
        except paramiko.SSHException as e:
            self.message_queue.put(("error", f"SSH连接错误:{str(e)}"))
        except Exception as e:
            self.message_queue.put(("error", f"连接失败:{str(e)}"))
    
    def disconnect_ssh(self):
        """断开SSH连接"""
        if self.sftp_client:
            self.sftp_client.close()
        if self.ssh_client:
            self.ssh_client.close()
        
        self.connected = False
        self.ssh_client = None
        self.sftp_client = None
        
        # 更新GUI状态
        self.connect_btn.config(state="normal")
        self.disconnect_btn.config(state="disabled")
        self.refresh_btn.config(state="disabled")
        self.upload_btn.config(state="disabled")
        self.mkdir_btn.config(state="disabled")
        
        # 清空文件列表
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # 重置路径
        self.path_var.set("/")
        
        self.set_status("已断开连接", "warning")
    
    def refresh_directory(self):
        """刷新目录"""
        if not self.connected:
            return
        
        thread = threading.Thread(target=self._refresh_thread)
        thread.daemon = True
        thread.start()
    
    def _refresh_thread(self):
        """刷新目录线程"""
        try:
            files = []
            for item in self.sftp_client.listdir_attr(self.current_path):
                file_info = {
                    'name': item.filename,
                    'size': item.st_size if item.st_size else 0,
                    'type': 'directory' if stat.S_ISDIR(item.st_mode) else 'file',
                    'permissions': stat.filemode(item.st_mode),
                    'modified': datetime.datetime.fromtimestamp(item.st_mtime).strftime('%Y-%m-%d %H:%M:%S') if item.st_mtime else 'Unknown'
                }
                files.append(file_info)
            
            # 排序:目录在前,然后按名称排序
            files.sort(key=lambda x: (x['type'] == 'file', x['name'].lower()))
            
            self.message_queue.put(("update_tree", files))
            
        except Exception as e:
            self.message_queue.put(("error", f"刷新目录失败: {str(e)}"))
    
    def update_file_tree(self, files):
        """更新文件树"""
        # 清空现有项目
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # 添加返回上级目录项
        if self.current_path != "/":
            self.tree.insert("", tk.END, text="[..] 返回上级目录", 
                           values=("", "directory", "", ""), tags=("parent",))
        
        # 添加文件和目录
        for file_info in files:
            # 根据文件类型选择图标
            if file_info['type'] == 'directory':
                icon = "[DIR]"
                size_text = "<目录>"
                type_display = "目录"
            else:
                # 根据文件扩展名选择标识
                name = file_info['name'].lower()
                if name.endswith(('.txt', '.log', '.md', '.readme')):
                    icon = "[TXT]"
                elif name.endswith(('.py', '.js', '.html', '.css', '.java', '.cpp', '.c')):
                    icon = "[CODE]"
                elif name.endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg')):
                    icon = "[IMG]"
                elif name.endswith(('.zip', '.tar', '.gz', '.rar', '.7z')):
                    icon = "[ARC]"
                elif name.endswith(('.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx')):
                    icon = "[DOC]"
                elif name.endswith(('.mp3', '.wav', '.flac', '.aac')):
                    icon = "[AUD]"
                elif name.endswith(('.mp4', '.avi', '.mkv', '.mov', '.wmv')):
                    icon = "[VID]"
                else:
                    icon = "[FILE]"
                
                size_text = self._format_size(file_info['size'])
                type_display = "文件"
            
            # 插入到树视图
            item_id = self.tree.insert("", tk.END, 
                           text=f"{icon} {file_info['name']}", 
                           values=(size_text, type_display, 
                                 file_info['permissions'], file_info['modified']),
                           tags=(file_info['type'],))
        
        # 配置标签样式
        self.tree.tag_configure('directory', foreground='#0078d4', font=('Arial', 10, 'bold'))
        self.tree.tag_configure('file', foreground='#333333')
        self.tree.tag_configure('parent', foreground='#666666', font=('Arial', 10, 'italic'))
        
        # 更新路径显示
        self.path_var.set(self.current_path)
        
        # 更新状态
        if files:
            dir_count = len([f for f in files if f['type'] == 'directory'])
            file_count = len([f for f in files if f['type'] == 'file'])
            status_msg = f"已连接 - {dir_count} 个目录, {file_count} 个文件"
        else:
            status_msg = "已连接 - 目录为空"
        
        self.set_status(status_msg, "success")
    
    def on_item_double_click(self, event):
        """双击项目事件"""
        if not self.connected:
            return
        
        selection = self.tree.selection()
        if not selection:
            return
        
        item = self.tree.item(selection[0])
        item_text = item['text']
        
        if "返回上级目录" in item_text:
            # 返回上级目录
            self.change_directory("..")
        elif item_text.startswith("[DIR]"):
            # 是目录,进入目录
            folder_name = item_text[6:].strip()  # 去掉[DIR] 前缀
            self.change_directory(folder_name)
        elif any(prefix in item_text for prefix in ["[FILE]", "[TXT]", "[CODE]", "[IMG]", "[ARC]", "[DOC]", "[AUD]", "[VID]"]):
            # 是文件,询问是否下载
            file_name = item_text.split("] ", 1)[1] if "] " in item_text else item_text[7:].strip()
            result = messagebox.askyesno("下载文件", 
                                       f"是否下载文件 '{file_name}' 到本地?\n\n"
                                       f"提示:您也可以右键点击文件选择下载位置")
            if result:
                local_path = filedialog.asksaveasfilename(
                    title="保存文件到...",
                    initialname=file_name,
                    defaultextension=os.path.splitext(file_name)[1]
                )
                if local_path:
                    self.download_file(file_name, local_path)
    
    def change_directory(self, path):
        """切换目录"""
        thread = threading.Thread(target=self._change_directory_thread, args=(path,))
        thread.daemon = True
        thread.start()
    
    def _change_directory_thread(self, path):
        """切换目录线程"""
        try:
            if path == "..":
                new_path = os.path.dirname(self.current_path.rstrip('/'))
                if not new_path:
                    new_path = "/"
            elif path.startswith('/'):
                new_path = path
            else:
                new_path = os.path.join(self.current_path, path).replace('\\', '/')
            
            # 测试目录是否存在
            self.sftp_client.listdir(new_path)
            self.current_path = new_path
            
            self.message_queue.put(("refresh", None))
            
        except Exception as e:
            self.message_queue.put(("error", f"切换目录失败: {str(e)}"))
    
    def navigate_to_path(self, event=None):
        """导航到指定路径"""
        path = self.path_var.get().strip()
        if path and self.connected:
            self.change_directory(path)
    
    def upload_file(self):
        """上传文件"""
        if not self.connected:
            return
        
        local_path = filedialog.askopenfilename(title="选择要上传的文件")
        if local_path:
            remote_name = os.path.basename(local_path)
            remote_path = os.path.join(self.current_path, remote_name).replace('\\', '/')
            
            thread = threading.Thread(target=self._upload_thread, args=(local_path, remote_path))
            thread.daemon = True
            thread.start()
    
    def _upload_thread(self, local_path, remote_path):
        """上传文件线程"""
        try:
            self.message_queue.put(("status", f"正在上传: {os.path.basename(local_path)}"))
            self.sftp_client.put(local_path, remote_path)
            self.message_queue.put(("success", f"上传完成: {os.path.basename(local_path)}"))
            self.message_queue.put(("refresh", None))
        except Exception as e:
            self.message_queue.put(("error", f"上传失败: {str(e)}"))
    
    def download_file(self, remote_name, local_path):
        """下载文件"""
        remote_path = os.path.join(self.current_path, remote_name).replace('\\', '/')
        
        thread = threading.Thread(target=self._download_thread, args=(remote_path, local_path))
        thread.daemon = True
        thread.start()
    
    def _download_thread(self, remote_path, local_path):
        """下载文件线程"""
        try:
            self.message_queue.put(("status", f"正在下载: {os.path.basename(remote_path)}"))
            self.sftp_client.get(remote_path, local_path)
            self.message_queue.put(("success", f"下载完成: {os.path.basename(local_path)}"))
        except Exception as e:
            self.message_queue.put(("error", f"下载失败: {str(e)}"))
    
    def create_directory(self):
        """创建新目录"""
        if not self.connected:
            return
        
        dir_name = simpledialog.askstring("新建目录", "请输入目录名称:")
        if dir_name:
            thread = threading.Thread(target=self._mkdir_thread, args=(dir_name,))
            thread.daemon = True
            thread.start()
    
    def _mkdir_thread(self, dir_name):
        """创建目录线程"""
        try:
            remote_path = os.path.join(self.current_path, dir_name).replace('\\', '/')
            self.sftp_client.mkdir(remote_path)
            self.message_queue.put(("success", f"创建目录成功: {dir_name}"))
            self.message_queue.put(("refresh", None))
        except Exception as e:
            self.message_queue.put(("error", f"创建目录失败: {str(e)}"))
    
    def show_context_menu(self, event):
        """显示右键菜单"""
        if not self.connected:
            return
        
        # 选择右键点击的项目
        item = self.tree.identify('item', event.x, event.y)
        if item:
            self.tree.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)
    
    def download_selected(self):
        """下载选中的文件"""
        selection = self.tree.selection()
        if not selection:
            return
        
        item = self.tree.item(selection[0])
        item_text = item['text']
        
        if not item_text.startswith("[DIR]") and "返回上级目录" not in item_text:
            file_name = item_text.split("] ", 1)[1] if "] " in item_text else item_text.strip()
            local_path = filedialog.asksaveasfilename(
                title="保存文件",
                initialname=file_name
            )
            if local_path:
                self.download_file(file_name, local_path)
    
    def delete_selected(self):
        """删除选中的项目"""
        selection = self.tree.selection()
        if not selection:
            return
        
        item = self.tree.item(selection[0])
        item_text = item['text']
        
        if "返回上级目录" in item_text:
            return
            
        item_name = item_text.split("] ", 1)[1] if "] " in item_text else item_text.strip()
        
        result = messagebox.askyesno("确认删除", f"确定要删除 '{item_name}' 吗?")
        if result:
            thread = threading.Thread(target=self._delete_thread, args=(item_name, item_text.startswith("[DIR]")))
            thread.daemon = True
            thread.start()
    
    def _delete_thread(self, item_name, is_directory):
        """删除文件/目录线程"""
        try:
            remote_path = os.path.join(self.current_path, item_name).replace('\\', '/')
            if is_directory:
                self.sftp_client.rmdir(remote_path)
                self.message_queue.put(("success", f"删除目录成功: {item_name}"))
            else:
                self.sftp_client.remove(remote_path)
                self.message_queue.put(("success", f"删除文件成功: {item_name}"))
            
            self.message_queue.put(("refresh", None))
        except Exception as e:
            self.message_queue.put(("error", f"删除失败: {str(e)}"))
    
    def rename_selected(self):
        """重命名选中的项目"""
        selection = self.tree.selection()
        if not selection:
            return
        
        item = self.tree.item(selection[0])
        item_text = item['text']
        old_name = item_text.split("] ", 1)[1] if "] " in item_text else item_text.strip()
        
        if "返回上级目录" in item_text:
            return
        
        new_name = simpledialog.askstring("重命名", f"新名称:", initialvalue=old_name)
        if new_name and new_name != old_name:
            thread = threading.Thread(target=self._rename_thread, args=(old_name, new_name))
            thread.daemon = True
            thread.start()
    
    def _rename_thread(self, old_name, new_name):
        """重命名文件/目录线程"""
        try:
            old_path = os.path.join(self.current_path, old_name).replace('\\', '/')
            new_path = os.path.join(self.current_path, new_name).replace('\\', '/')
            
            # 使用SSH命令执行重命名(SFTP没有直接的重命名方法)
            stdin, stdout, stderr = self.ssh_client.exec_command(f'mv "{old_path}" "{new_path}"')
            exit_code = stdout.channel.recv_exit_status()
            
            if exit_code == 0:
                self.message_queue.put(("success", f"重命名成功: {old_name} -> {new_name}"))
                self.message_queue.put(("refresh", None))
            else:
                error_msg = stderr.read().decode('utf-8').strip()
                self.message_queue.put(("error", f"重命名失败: {error_msg}"))
                
        except Exception as e:
            self.message_queue.put(("error", f"重命名失败: {str(e)}"))
    
    def show_properties(self):
        """显示选中项目的属性"""
        selection = self.tree.selection()
        if not selection:
            return
        
        item = self.tree.item(selection[0])
        item_text = item['text']
        item_name = item_text.split("] ", 1)[1] if "] " in item_text else item_text.strip()
        
        if "返回上级目录" in item_text:
            return
        
        thread = threading.Thread(target=self._show_properties_thread, args=(item_name,))
        thread.daemon = True
        thread.start()
    
    def _show_properties_thread(self, item_name):
        """显示属性线程"""
        try:
            remote_path = os.path.join(self.current_path, item_name).replace('\\', '/')
            file_attr = self.sftp_client.stat(remote_path)
            
            info = {
                'name': item_name,
                'path': remote_path,
                'size': file_attr.st_size if file_attr.st_size else 0,
                'type': 'Directory' if stat.S_ISDIR(file_attr.st_mode) else 'File',
                'permissions': stat.filemode(file_attr.st_mode),
                'modified': datetime.datetime.fromtimestamp(file_attr.st_mtime).strftime('%Y-%m-%d %H:%M:%S') if file_attr.st_mtime else 'Unknown',
                'accessed': datetime.datetime.fromtimestamp(file_attr.st_atime).strftime('%Y-%m-%d %H:%M:%S') if file_attr.st_atime else 'Unknown'
            }
            
            self.message_queue.put(("show_properties", info))
            
        except Exception as e:
            self.message_queue.put(("error", f"获取属性失败: {str(e)}"))
    
    def show_properties_dialog(self, info):
        """显示属性对话框"""
        dialog = tk.Toplevel(self.root)
        dialog.title(f"属性 - {info['name']}")
        dialog.geometry("500x400")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 居中显示
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (500 // 2)
        y = (dialog.winfo_screenheight() // 2) - (400 // 2)
        dialog.geometry(f"500x400+{x}+{y}")
        
        # 主框架
        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 标题
        title_frame = ttk.Frame(main_frame)
        title_frame.pack(fill=tk.X, pady=(0, 20))
        
        # 文件图标
        file_icon = "[DIR]" if info['type'] == 'Directory' else "[FILE]"
        ttk.Label(title_frame, text=file_icon, font=('Arial', 18)).pack(side=tk.LEFT, padx=(0, 15))
        
        title_info_frame = ttk.Frame(title_frame)
        title_info_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        ttk.Label(title_info_frame, text=info['name'], font=('Arial', 14, 'bold')).pack(anchor=tk.W)
        ttk.Label(title_info_frame, text=info['type'], font=('Arial', 10), foreground='#666666').pack(anchor=tk.W)
        
        # 分隔线
        separator = ttk.Separator(main_frame, orient='horizontal')
        separator.pack(fill=tk.X, pady=(0, 20))
        
        # 属性信息
        props_frame = ttk.Frame(main_frame)
        props_frame.pack(fill=tk.BOTH, expand=True)
        
        properties = [
            ("完整路径:", info['path']),
            ("文件大小:", self._format_size(info['size']) if info['type'] == 'File' else '-'),
            ("访问权限:", info['permissions']),
            ("修改时间:", info['modified']),
            ("访问时间:", info['accessed'])
        ]
        
        for i, (label, value) in enumerate(properties):
            prop_frame = ttk.Frame(props_frame)
            prop_frame.pack(fill=tk.X, pady=5)
            
            ttk.Label(prop_frame, text=label, font=('Arial', 10, 'bold'), width=15).pack(side=tk.LEFT, anchor=tk.W)
            
            # 使用可选择的标签显示值
            value_label = tk.Label(prop_frame, text=value, font=('Consolas', 10), 
                                 bg='white', relief='sunken', borderwidth=1, anchor=tk.W, 
                                 padx=8, pady=4)
            value_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 0))
        
        # 按钮框架
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(30, 0))
        
        ttk.Button(btn_frame, text="确定", command=dialog.destroy, 
                  style='TButton').pack(side=tk.RIGHT)
    
    def toggle_terminal(self):
        """切换终端显示/隐藏"""
        if self.terminal_visible:
            self.paned_window.remove(self.terminal_frame)
            self.terminal_visible = False
            self.terminal_btn.config(text="显示终端")
        else:
            self.paned_window.add(self.terminal_frame, weight=1)
            self.terminal_visible = True
            self.terminal_btn.config(text="隐藏终端")
            
            # 如果是第一次打开终端,显示欢迎信息
            if self.terminal_text.get("1.0", tk.END).strip() == "":
                welcome_msg = """欢迎使用SSH远程终端!

提示:
  - 输入Linux命令并按回车执行
  - 支持所有标准shell命令
  - 彩色输出让结果更清晰

-------------------------------------------

"""
                self.terminal_text.insert(tk.END, welcome_msg, "welcome")
                self.terminal_text.tag_config("welcome", foreground="#81c784", font=('Consolas', 10))
    
    def execute_command(self, event=None):
        """执行远程命令"""
        if not self.connected:
            return
        
        command = self.cmd_var.get().strip()
        if not command:
            return
        
        self.cmd_var.set("")  # 清空输入框
        
        # 在终端显示命令
        self.terminal_text.insert(tk.END, f"$ {command}\n", "command")
        self.terminal_text.see(tk.END)
        
        thread = threading.Thread(target=self._execute_command_thread, args=(command,))
        thread.daemon = True
        thread.start()
    
    def _execute_command_thread(self, command):
        """执行命令线程"""
        try:
            stdin, stdout, stderr = self.ssh_client.exec_command(command)
            stdout_data = stdout.read().decode('utf-8', errors='ignore')
            stderr_data = stderr.read().decode('utf-8', errors='ignore')
            exit_code = stdout.channel.recv_exit_status()
            
            result = {
                'command': command,
                'stdout': stdout_data,
                'stderr': stderr_data,
                'exit_code': exit_code
            }
            
            self.message_queue.put(("command_result", result))
            
        except Exception as e:
            self.message_queue.put(("error", f"执行命令失败: {str(e)}"))
    
    def display_command_result(self, result):
        """在终端显示命令结果"""
        if not self.terminal_visible:
            self.toggle_terminal()
        
        # 显示命令提示符和命令
        self.terminal_text.insert(tk.END, f"[{datetime.datetime.now().strftime('%H:%M:%S')}] ", "timestamp")
        self.terminal_text.insert(tk.END, f"$ {result['command']}\n", "command")
        
        # 显示输出
        if result['stdout']:
            self.terminal_text.insert(tk.END, result['stdout'], "output")
            if not result['stdout'].endswith('\n'):
                self.terminal_text.insert(tk.END, "\n")
        
        # 显示错误
        if result['stderr']:
            self.terminal_text.insert(tk.END, "错误输出:\n", "error_header")
            self.terminal_text.insert(tk.END, result['stderr'], "error")
            if not result['stderr'].endswith('\n'):
                self.terminal_text.insert(tk.END, "\n")
        
        # 显示退出码
        if result['exit_code'] == 0:
            self.terminal_text.insert(tk.END, f"[执行成功, 退出码: {result['exit_code']}]\n\n", "success_info")
        else:
            self.terminal_text.insert(tk.END, f"[执行失败, 退出码: {result['exit_code']}]\n\n", "error_info")
        
        # 配置终端文本标签样式
        self.terminal_text.tag_config("timestamp", foreground="#888888", font=('Consolas', 10))
        self.terminal_text.tag_config("command", foreground="#ffeb3b", font=('Consolas', 11, 'bold'))
        self.terminal_text.tag_config("output", foreground="#e8e8e8", font=('Consolas', 10))
        self.terminal_text.tag_config("error_header", foreground="#f44336", font=('Consolas', 10, 'bold'))
        self.terminal_text.tag_config("error", foreground="#ffcdd2", font=('Consolas', 10))
        self.terminal_text.tag_config("success_info", foreground="#4caf50", font=('Consolas', 10, 'bold'))
        self.terminal_text.tag_config("error_info", foreground="#f44336", font=('Consolas', 10, 'bold'))
        
        self.terminal_text.see(tk.END)
    
    def process_queue(self):
        """处理消息队列"""
        try:
            while True:
                message_type, data = self.message_queue.get_nowait()
                
                if message_type == "success":
                    self.set_status(data, "success")
                    if "连接" in data:
                        # 连接成功时不显示弹窗,只在状态栏显示
                        pass
                    else:
                        messagebox.showinfo("操作成功", data)
                    
                elif message_type == "error":
                    self.set_status(data, "error")
                    messagebox.showerror("操作失败", data)
                    self.connect_btn.config(state="normal")
                    
                elif message_type == "status":
                    self.set_status(data, "info")
                    
                elif message_type == "refresh":
                    self.refresh_directory()
                    
                elif message_type == "update_tree":
                    self.update_file_tree(data)
                    # 启用按钮
                    self.disconnect_btn.config(state="normal")
                    self.refresh_btn.config(state="normal")
                    self.upload_btn.config(state="normal")
                    self.mkdir_btn.config(state="normal")
                    
                elif message_type == "show_properties":
                    self.show_properties_dialog(data)
                    
                elif message_type == "command_result":
                    self.display_command_result(data)
                    
                elif message_type == "system_info":
                    messagebox.showinfo("系统信息", data)
                    
        except queue.Empty:
            pass
        
        # 继续处理队列
        self.root.after(100, self.process_queue)
    
    @staticmethod
    def _format_size(size_bytes):
        """格式化文件大小"""
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB", "TB"]
        import math
        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return f"{s} {size_names[i]}"
    
    def on_closing(self):
        """程序关闭时的清理工作"""
        if self.connected:
            self.disconnect_ssh()
        self.root.destroy()
    
    def setup_menu(self):
        """设置菜单栏"""
        menubar = tk.Menu(self.root, font=('Arial', 10))
        self.root.config(menu=menubar)
        
        # 文件菜单
        file_menu = tk.Menu(menubar, tearoff=0, font=('Arial', 10))
        menubar.add_cascade(label="文件", menu=file_menu)
        file_menu.add_command(label="连接服务器", command=self.connect_ssh, accelerator="Ctrl+N")
        file_menu.add_command(label="断开连接", command=self.disconnect_ssh, accelerator="Ctrl+D")
        file_menu.add_separator()
        file_menu.add_command(label="上传文件", command=self.upload_file, accelerator="Ctrl+U")
        file_menu.add_command(label="新建目录", command=self.create_directory, accelerator="Ctrl+M")
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self.on_closing, accelerator="Ctrl+Q")
        
        # 查看菜单
        view_menu = tk.Menu(menubar, tearoff=0, font=('Arial', 10))
        menubar.add_cascade(label="查看", menu=view_menu)
        view_menu.add_command(label="刷新", command=self.refresh_directory, accelerator="F5")
        view_menu.add_command(label="切换终端", command=self.toggle_terminal, accelerator="Ctrl+T")
        
        # 工具菜单
        tools_menu = tk.Menu(menubar, tearoff=0, font=('Arial', 10))
        menubar.add_cascade(label="工具", menu=tools_menu)
        tools_menu.add_command(label="清理终端", command=self.clear_terminal)
        tools_menu.add_command(label="系统信息", command=self.show_system_info)
        
        # 帮助菜单
        help_menu = tk.Menu(menubar, tearoff=0, font=('Arial', 10))
        menubar.add_cascade(label="帮助", menu=help_menu)
        help_menu.add_command(label="快捷键", command=self.show_shortcuts)
        help_menu.add_command(label="关于", command=self.show_about)
        
        # 绑定快捷键
        self.root.bind('<Control-n>', lambda e: self.connect_ssh())
        self.root.bind('<Control-d>', lambda e: self.disconnect_ssh())
        self.root.bind('<Control-u>', lambda e: self.upload_file())
        self.root.bind('<Control-m>', lambda e: self.create_directory())
        self.root.bind('<Control-t>', lambda e: self.toggle_terminal())
        self.root.bind('<Control-q>', lambda e: self.on_closing())
        self.root.bind('<F5>', lambda e: self.refresh_directory())
    
    def clear_terminal(self):
        """清理终端"""
        if hasattr(self, 'terminal_text'):
            self.terminal_text.delete('1.0', tk.END)
            self.set_status("终端已清理", "info")
    
    def show_system_info(self):
        """显示远程系统信息"""
        if not self.connected:
            messagebox.showwarning("警告", "请先连接到SSH服务器")
            return
        
        # 在单独线程中获取系统信息
        thread = threading.Thread(target=self._get_system_info_thread)
        thread.daemon = True
        thread.start()
    
    def _get_system_info_thread(self):
        """获取系统信息线程"""
        try:
            commands = [
                ("系统信息", "uname -a"),
                ("磁盘使用", "df -h"),
                ("内存信息", "free -h"),
                ("CPU信息", "cat /proc/cpuinfo | grep 'model name' | head -1"),
                ("系统负载", "uptime")
            ]
            
            info_text = "远程系统信息\n" + "="*50 + "\n\n"
            
            for title, cmd in commands:
                stdin, stdout, stderr = self.ssh_client.exec_command(cmd)
                output = stdout.read().decode('utf-8', errors='ignore').strip()
                if output:
                    info_text += f"{title}:\n{output}\n\n"
            
            self.message_queue.put(("system_info", info_text))
            
        except Exception as e:
            self.message_queue.put(("error", f"获取系统信息失败: {str(e)}"))
    
    def show_shortcuts(self):
        """显示快捷键帮助"""
        shortcuts_text = """快捷键列表

连接操作:
  Ctrl + N    连接服务器
  Ctrl + D    断开连接

文件操作:
  Ctrl + U    上传文件
  Ctrl + M    新建目录
  F5          刷新目录

界面操作:
  Ctrl + T    切换终端显示
  Ctrl + Q    退出程序

鼠标操作:
  双击目录    进入目录
  双击文件    下载文件
  右键点击    显示上下文菜单

使用技巧:
  - 在路径栏直接输入路径并按回车
  - 终端支持所有Linux命令
  - 支持批量文件操作"""
        
        messagebox.showinfo("快捷键帮助", shortcuts_text)
    
    def show_about(self):
        """显示关于对话框"""
        about_text = """SSH远程资源管理器 v2.0

基于Python Paramiko库开发的高清可视化SSH文件管理工具

主要特性:
- 安全的SSH连接(密码/密钥认证)
- 直观的高清文件浏览界面
- 便捷的文件上传/下载
- 集成的远程终端
- 现代化的用户界面
- 多线程操作,响应迅速
- 丰富的快捷键支持

技术栈:
- Python 3.x
- Paramiko (SSH客户端)
- tkinter (GUI框架)
- 多线程架构

开发目标:
让SSH文件管理变得简单、直观、高效!

Copyright 2024 - 专为提升远程开发体验而设计"""
        
        messagebox.showinfo("关于程序", about_text)
    
    def run(self):
        """运行GUI程序"""
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 添加菜单栏
        self.setup_menu()
        
        # 设置窗口图标(如果有的话)
        try:
            # 可以在这里设置自定义图标
            pass
        except:
            pass
        
        # 显示欢迎信息
        self.set_status("欢迎使用SSH远程资源管理器!请连接到服务器开始使用", "info")
        
        # 启动主循环
        self.root.mainloop()


def main():
    """主程序入口"""
    try:
        # 设置控制台编码
        import sys
        if sys.platform.startswith('win'):
            try:
                import locale
                locale.setlocale(locale.LC_ALL, 'zh_CN.UTF-8')
            except:
                pass
        
        print("启动SSH远程资源管理器...")
        
        # 检查 Paramiko 是否安装
        try:
            import paramiko
            print(f"Paramiko 版本: {getattr(paramiko, '__version__', '未知')}")
        except ImportError:
            print("错误: 未安装 Paramiko 库")
            print("请运行: pip install paramiko")
            return
        
        # 创建并运行GUI应用
        app = SSHFileManagerGUI()
        app.run()
        
    except Exception as e:
        print(f"程序启动失败: {str(e)}")
        traceback.print_exc()
        messagebox.showerror("启动错误", f"程序启动失败:\n\n{str(e)}\n\n请检查Python环境和依赖库安装情况.")


if __name__ == "__main__":
    main()#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SSH远程资源管理器 - GUI版本
基于Paramiko和tkinter的可视化远程文件管理工具
"""