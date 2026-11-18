"""界面样式、可滚动设置区与 Windows 高 DPI 初始化。"""
import ctypes
import os
import tkinter as tk
from tkinter import ttk


def enable_high_dpi():
    # 必须在创建首个窗口之前调用；仅影响本进程，不改变系统显示设置。
    if os.name != "nt":
        return
    try:
        api = ctypes.windll.user32.SetProcessDpiAwarenessContext
        api.argtypes = [ctypes.c_void_p]
        api.restype = ctypes.c_bool
        if api(ctypes.c_void_p(-4)):
            return
    except (AttributeError, OSError):
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        pass


def apply_theme(root, scale):
    px = lambda x: max(1, round(x * scale))
    style = ttk.Style(root)
    style.theme_use("clam")
    font = ("Microsoft YaHei UI", 10)
    # 通用 *Font 会覆盖 ttk 各样式的标题字号，保持样式自身的字体层级。
    root.option_add("*TCombobox*Listbox.font", font)
    root.configure(bg="#edf2f7")
    style.configure(".", font=font, background="#edf2f7", foreground="#263449")
    style.configure("TFrame", background="#edf2f7")
    style.configure("Card.TFrame", background="white")
    style.configure("TLabel", background="white", foreground="#334155")
    style.configure("Muted.TLabel", foreground="#718096", font=("Microsoft YaHei UI", 9))
    style.configure("Section.TLabel", foreground="#172b4d", font=("Microsoft YaHei UI", 11, "bold"))
    style.configure("Header.TFrame", background="#12243a")
    style.configure("Header.TLabel", background="#12243a", foreground="#f8fafc", font=("Microsoft YaHei UI", 19, "bold"))
    style.configure("Subtitle.TLabel", background="#12243a", foreground="#b6c7dd", font=("Microsoft YaHei UI", 9))
    style.configure("TButton", background="#f1f5fa", foreground="#334155", borderwidth=0,
                    padding=(px(11), px(7)), focusthickness=1, focuscolor="#94b7ec")
    style.map("TButton", background=[("active", "#e2eaf5"), ("disabled", "#f1f5f9")],
              foreground=[("disabled", "#94a3b8")])
    style.configure("Primary.TButton", background="#2563eb", foreground="white", font=("Microsoft YaHei UI", 10, "bold"))
    style.map("Primary.TButton", background=[("active", "#1d4ed8"), ("disabled", "#a9bfe8")], foreground=[("disabled", "white")])
    style.configure("TEntry", fieldbackground="#f8fafc", bordercolor="#d9e2ef", lightcolor="#d9e2ef", darkcolor="#d9e2ef", padding=px(6))
    style.configure("TCombobox", fieldbackground="#f8fafc", background="#e9eff7", bordercolor="#d9e2ef",
                    lightcolor="#d9e2ef", darkcolor="#d9e2ef", arrowsize=px(13), padding=px(5))
    style.map("TCombobox", fieldbackground=[("readonly", "#f8fafc"), ("disabled", "#f1f5f9")],
              foreground=[("disabled", "#a0aec0")], selectbackground=[("readonly", "#e6eefc")], selectforeground=[("readonly", "#1e293b")])
    style.configure("TCheckbutton", background="white", padding=(0, px(4)))
    style.map("TCheckbutton", background=[("active", "white")])
    style.configure("TNotebook", background="white", borderwidth=0, tabmargins=0)
    style.configure("TNotebook.Tab", padding=(px(12), px(8)), background="#edf2f7", foreground="#64748b")
    style.map("TNotebook.Tab", background=[("selected", "white")], foreground=[("selected", "#2563eb")])
    style.configure("Vertical.TScrollbar", background="#d5dfed", troughcolor="#f8fafc", borderwidth=0, arrowsize=px(10))
    return px


class ScrollPanel(ttk.Frame):
    def __init__(self, parent, px):
        super().__init__(parent, style="Card.TFrame")
        self.canvas = tk.Canvas(self, highlightthickness=0, bg="white", width=1, height=1)
        scroll = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.body = ttk.Frame(self.canvas, style="Card.TFrame", padding=px(16))
        item = self.canvas.create_window((0, 0), window=self.body, anchor="nw")
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(item, width=e.width))
        self.body.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))

    def bind_scrolling(self):
        def wheel(event):
            self.canvas.yview_scroll(-int(event.delta / 120) if abs(event.delta) >= 120 else (-1 if event.delta > 0 else 1), "units")
            return "break"
        def visit(widget):
            widget.bind("<MouseWheel>", wheel)
            for child in widget.winfo_children():
                visit(child)
        visit(self)
