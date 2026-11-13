# -*- coding: utf-8 -*-
"""双语界面自测：在隔离临时目录里强制英文启动，真建窗口 + 截图 + 文本校验。

不触碰真实游戏文件；临时目录里的 pyw 与设置文件用完即删。
"""
import importlib.util
import json
import os
import re
import shutil
import sys
import tempfile
import time
import ctypes

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

import tkinter as tk
from PIL import ImageGrab

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "docs", "screenshots") \
    if os.path.isdir(os.path.join(HERE, "..", "docs", "screenshots")) else HERE


def locate(name):
    """兼容开发目录与 GitHub 仓库布局。"""
    for d in (HERE, os.path.join(HERE, "..", "src"),
              os.path.join(HERE, "..", "v1.0"),
              os.path.join(HERE, "发布_v1.0"),
              os.path.join(HERE, "..", "发布_v1.0")):
        p = os.path.join(d, name)
        if os.path.isfile(p):
            return p
    raise FileNotFoundError(name)


CASES = [
    ("v2.0", locate("车皮调色台.pyw"),
     "界面预览_英文.png", "调色编辑器预览_英文.png"),
    ("v1.0", locate("车皮调色台_v1.0.pyw"),
     "v1.0_界面预览_英文.png", None),
]


def texts(w, out):
    try:
        t = w.cget("text")
        if isinstance(t, str) and t:
            out.append(t)
    except Exception:
        pass
    for c in w.winfo_children():
        texts(c, out)


def shot(win, path):
    win.attributes("-topmost", True)
    win.lift()
    win.update_idletasks()
    win.update()
    time.sleep(0.6)
    win.update()
    x, y = win.winfo_rootx(), win.winfo_rooty()
    w, h = win.winfo_width(), win.winfo_height()
    ImageGrab.grab(bbox=(x, y, x + w, y + h)).save(os.path.join(OUT, path))
    win.attributes("-topmost", False)
    print("   截图 %s (%d x %d)" % (path, w, h))


for tag, pyw, main_png, editor_png in CASES:
    tmp = tempfile.mkdtemp(prefix="rr_en_")
    try:
        local = os.path.join(tmp, "rr_en.pyw")
        shutil.copy2(pyw, local)
        cfg = os.path.join(tmp, "车皮调色台_设置.json")
        json.dump({"lang": "en"}, open(cfg, "w", encoding="utf-8"))

        name = "rr_" + tag.replace(".", "_")
        spec = importlib.util.spec_from_file_location(name, local)
        m = importlib.util.module_from_spec(spec)
        sys.modules[name] = m
        spec.loader.exec_module(m)
        m.messagebox.showinfo = lambda *a, **k: None
        m.messagebox.showerror = lambda *a, **k: print("   [error]", *a)

        assert m.LANG == "en", "%s 未按设置启动英文" % tag
        assert m.tr("选择 exe") == "Browse exe"
        assert m.tr("应用到游戏（自动备份）").startswith("Apply to Game")

        root = tk.Tk()
        app = m.App(root)
        root.update()
        assert len(app.cards) == 15
        out = []
        texts(root, out)
        joined = "\n".join(out)
        for need in ("Browse exe", "Official Fix", "Apply to Game", "Swap Slots",
                     "Rat Bikes", "Super Bikes", "Sport Bikes"):
            assert need in joined, "%s 英文界面缺少 %r" % (tag, need)
        for bad in ("选择 exe", "应用到游戏", "官方修复", "交换槽位"):
            assert bad not in joined, "%s 仍残留中文 %r" % (tag, bad)
        print("%s 英文界面文本校验: OK | 标题 = %r" % (tag, root.title()))
        shot(root, main_png)

        if editor_png:
            ed = m.ColorEditor(app, 1)
            ed.win.update()
            o2 = []
            texts(ed.win, o2)
            j2 = "\n".join(o2)
            for need in ("Live Preview", "Selected Color", "Quick Colors",
                         "Apply Color", "Pick Color"):
                assert need in j2, "英文编辑器缺少 %r" % need
            print("%s 英文调色编辑器文本校验: OK" % tag)
            shot(ed.win, editor_png)
            ed.win.destroy()

        # 语言切换（不重启进程）+ 设置持久化
        app.do_language(restart=False)
        assert m.LANG == "zh" and json.load(open(cfg, encoding="utf-8"))["lang"] == "zh"
        app.do_language(restart=False)
        assert m.LANG == "en" and json.load(open(cfg, encoding="utf-8"))["lang"] == "en"
        print("%s 语言切换与设置持久化: OK" % tag)

        root.destroy()
        del sys.modules[name]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

# selftest 也应报告当前语言
spec = importlib.util.spec_from_file_location("rr_st", locate("车皮调色台.pyw"))
m = importlib.util.module_from_spec(spec)
sys.modules["rr_st"] = m
spec.loader.exec_module(m)
tmp = tempfile.mkdtemp(prefix="rr_st_")
try:
    m.DATA_DIR = tmp
    m.SETTINGS = os.path.join(tmp, "车皮调色台_设置.json")
    m.LANG = "en"
    m.selftest()
    r = json.load(open(os.path.join(tmp, "自检结果.json"), encoding="utf-8"))
    assert r["lang"] == "en", r.get("lang")
    print("selftest 输出 lang=en: OK | 版本", r.get("version"))
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("\n=== 双语界面全部自测通过 ===")
