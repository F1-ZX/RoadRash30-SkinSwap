# -*- coding: utf-8 -*-
"""v2.0 端到端自测：真实创建 Tk 窗口 + 在临时副本上验证双文件写入。
不触碰真实游戏 exe / PALETTE.RAW。
"""
import importlib.util
import sys
import os
import json
import glob
import time
import ctypes
import shutil
import tempfile

try:                                   # 让 Win32 坐标与 ImageGrab 一致
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

import tkinter as tk

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "docs", "screenshots") \
    if os.path.isdir(os.path.join(HERE, "..", "docs", "screenshots")) else HERE


def locate(name):
    """兼容开发目录（pyw 与本脚本同级）与 GitHub 仓库（pyw 在 src/）。"""
    for d in (HERE, os.path.join(HERE, "..", "src"),
              os.path.join(HERE, "..", "v1.0")):
        p = os.path.join(d, name)
        if os.path.isfile(p):
            return p
    raise FileNotFoundError(name)


spec = importlib.util.spec_from_file_location("rr", locate("车皮调色台.pyw"))
m = importlib.util.module_from_spec(spec)
sys.modules["rr"] = m
spec.loader.exec_module(m)

# 屏蔽弹窗
m.messagebox.askyesno = lambda *a, **k: True
m.messagebox.showinfo = lambda *a, **k: None
m.messagebox.showerror = lambda *a, **k: print("  [showerror]", *a)
m.messagebox.showwarning = lambda *a, **k: None

root = tk.Tk()
app = m.App(root)
root.update()
print("窗口创建 OK, 卡片数:", len(app.cards))
imgs = [c["pic"].cget("image") for c in app.cards]
print("15 张预览图已绑定:", all(imgs))
assert len(app.cards) == 15 and all(imgs)
print("初始状态:", app.state_of(), "| 自动探测 exe:", m.DEFAULT_EXE)

assert m.DEFAULT_NAMES[0] == "450cc Banzai Sport 450"
assert m.DEFAULT_NAMES[4] == "125cc Perro Pico"
assert m.DEFAULT_NAMES[7] == "1000cc Diablo Vipera N"
assert m.DEFAULT_NAMES[14] == "600cc Stilleto Aggressore"
print("实测车名 15 项: OK")

# --- 方向切换 ---
assert app.orient == "rot180"
p180 = app.cards[0]["pic"].cget("image")
app.orient_cb.set("垂直翻转（BMP 规范）")
app.on_orient()
root.update()
assert app.orient == "flipv" and p180 != app.cards[0]["pic"].cget("image")
app.orient_cb.set("旋转 180°（游戏实测）")
app.on_orient()
root.update()
print("预览方向切换: OK")

# --- 兼容性自检窗口（含 v2 调色板段落）---
app.check_env()
root.update()
tops = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)]
assert len(tops) == 1
print("兼容性自检窗口: OK")
for t in tops:
    t.destroy()
root.update()

# --- 1.0 基础操作 ---
app.do_official()
assert m.fnv1a(m.join_luts(app.tables)) == m.FIXED_FNV
app.do_stock()
app.swap_a.set("2")
app.swap_b.set("11")
app.do_swap()
assert app.state_of() == "自定义"
app.cards[0]["cb"].set(app.scheme_labels[5])
app.on_pick(0)
print("官方修复 / 恢复原版 / 交换 / 指派: OK")

# --- 建立隔离测试环境：exe + DATA/PALETTE.RAW ---
REAL_GAME = r"D:\SteamLibrary\steamapps\common\RoadRash"
REAL_PAL = os.path.join(REAL_GAME, "DATA", "PALETTE.RAW")
src = os.path.join(HERE, "RoadRash95.修复前备份.exe")
assert m.fnv1a(m.read_region(src)) == m.STOCK_FNV
tmpdir = tempfile.mkdtemp(prefix="rr_skin_v2_")
os.makedirs(os.path.join(tmpdir, "DATA"))
tmp = os.path.join(tmpdir, "RoadRash95.exe")
tmp_pal = os.path.join(tmpdir, "DATA", "PALETTE.RAW")
shutil.copy2(src, tmp)
# 用内嵌原版调色板做基线：不依赖玩家磁盘上已应用的自定义颜色，
# 保证「空闲项分配」这条路径在任何机器上都可复现。
with open(tmp_pal, "wb") as _f:
    _f.write(m._PALETTE)
before_exe = open(tmp, "rb").read()
before_pal = open(tmp_pal, "rb").read()
app.exe = tmp
app.path_var.set(tmp)
app.reload_exe(silent=True)
assert app.palette_file == tmp_pal and app.palette_ok
assert bytes(app.palette) == before_pal
print("临时环境就绪, 调色板路径:", os.path.relpath(app.palette_file, tmpdir))

# --- 2.0 核心：专属项直接改写调色板 ---
app.do_official()
ed = m.ColorEditor(app, 1)
root.update()
excl = [(i, p, n, ow) for i, (p, n, ow) in enumerate(ed.items) if ow == [1]]
assert excl, "槽 01 应存在专属调色板项"
i, p_excl, n_px, _ = excl[0]
ed.tree.selection_set(str(i))
root.update()
lut_before = bytes(app.tables[1])
ed.apply_rgb((12, 34, 56))
assert app.tables[1] == lut_before, "专属项改色不应动 LUT"
assert m.palette_overrides(app.palette).get(str(p_excl)) == "#0c2238"
print("专属项 #%d（%d 像素）→ 直接改调色板, LUT 未动: OK" % (p_excl, n_px))

# --- 2.0 核心：共用项隔离到空闲项 ---
ed5 = m.ColorEditor(app, 5)
root.update()
common = [(i, p, n, ow) for i, (p, n, ow) in enumerate(ed5.items) if len(ow) > 1]
assert common
i5, p_common, n5, ow5 = common[0]
ed5.tree.selection_set(str(i5))
root.update()
free_before = len(app.free_items())
other_before = bytes(app.tables[ow5[0]]) if ow5[0] != 5 else bytes(app.tables[ow5[1]])
ed5.apply_rgb((255, 0, 170))
assert app.remaps and str(5) in app.remaps
assert len(app.free_items()) == free_before - 1
q = int(list(app.remaps["5"])[0])
assert m.palette_overrides(app.palette).get(str(q)) == "#ff00aa"
assert p_common not in [app.tables[5][x] for x in m._ACTIVE], "本槽不应再引用旧项"
print("共用项 #%d（%d 辆车引用）→ 隔离到空闲项 #%d, 其余车不变: OK"
      % (p_common, len(ow5), q))

# 预览确实跟着调色板变化
png_stock = m.render_png(app.tables[1], pal=bytearray(m._PALETTE))
png_now = m.render_png(app.tables[1], pal=app.palette)
assert png_stock != png_now
print("预览随自定义调色板实时变化: OK")

# --- 双文件写盘 ---
app.apply()
after_exe = open(tmp, "rb").read()
after_pal = open(tmp_pal, "rb").read()
s, e = m.TABLE_OFF, m.TABLE_OFF + m.REGION
assert before_exe[:s] == after_exe[:s] and before_exe[e:] == after_exe[e:], "表区外字节被改动!"
assert m.read_region(tmp) == m.join_luts(app.tables)
assert after_pal == bytes(app.palette) and len(after_pal) == 1024
assert after_pal != before_pal
bk_exe = glob.glob(tmp + ".调色台备份_*")
bk_pal = glob.glob(tmp_pal + ".调色台备份_*")
assert len(bk_exe) == 1 and len(bk_pal) == 1
print("写盘 OK：exe 表区外零改动、调色板 1024B 正确、双备份各 1 份")

# --- 方案 v2 保存 / 载入 ---
plan = os.path.join(tmpdir, "plan.json")
m.filedialog.asksaveasfilename = lambda *a, **k: plan
m.filedialog.askopenfilename = lambda *a, **k: plan
app.save_plan()
d = json.load(open(plan, encoding="utf-8"))
assert d["version"] == 2 and d["palette"] and d["remaps"]
snapshot_tables = [bytes(t) for t in app.tables]
snapshot_pal = bytes(app.palette)
app.do_stock()
app.palette = bytearray(m._PALETTE)
app.remaps = {}
app.load_plan()
assert [bytes(t) for t in app.tables] == snapshot_tables
assert bytes(app.palette) == snapshot_pal
print("方案 v2 保存/载入（含调色板 + remaps）: OK")

# --- 完整还原（含 LUT 重指回滚）---
app.restore_palette()
assert m.palette_overrides(app.palette) == {} and app.remaps == {}
assert q not in [app.tables[5][x] for x in range(256)], "LUT 重指未回滚"
app.apply()
assert open(tmp_pal, "rb").read() == before_pal
after2 = open(tmp, "rb").read()
assert before_exe[:s] == after2[:s] and before_exe[e:] == after2[e:]
print("还原调色板 + LUT 重指回滚 + 写盘: OK")

# 关闭编辑器窗口
for t in list(root.winfo_children()):
    if isinstance(t, tk.Toplevel):
        t.destroy()
root.update()

# --- 截图（主窗口 + 调色编辑器）---
app.exe = m.DEFAULT_EXE
app.path_var.set(m.DEFAULT_EXE)
app.reload_exe(silent=True)
root.update()
try:
    from PIL import ImageGrab
    root.attributes("-topmost", True)
    root.lift()
    root.update_idletasks()
    root.update()
    time.sleep(0.6)
    root.update()
    x, y = root.winfo_rootx(), root.winfo_rooty()
    w, h = root.winfo_width(), root.winfo_height()
    ImageGrab.grab(bbox=(x, y, x + w, y + h)).save(os.path.join(OUT, "界面预览.png"))
    root.attributes("-topmost", False)
    print("主窗口截图已保存 界面预览.png", (w, h))
except Exception as ex:
    print("截图跳过:", ex)

try:
    from PIL import ImageGrab
    edv = m.ColorEditor(app, 1)
    edv.win.attributes("-topmost", True)
    edv.win.lift()
    edv.win.update_idletasks()
    edv.win.update()
    root.update()
    time.sleep(0.6)
    edv.win.update()
    x, y = edv.win.winfo_rootx(), edv.win.winfo_rooty()
    w, h = edv.win.winfo_width(), edv.win.winfo_height()
    ImageGrab.grab(bbox=(x, y, x + w, y + h)).save(os.path.join(OUT, "调色编辑器预览.png"))
    edv.win.attributes("-topmost", False)
    print("编辑器截图已保存 调色编辑器预览.png", (w, h))
    edv.win.destroy()
except Exception as ex:
    print("编辑器截图跳过:", ex)

shutil.rmtree(tmpdir, ignore_errors=True)
app.exe = m.DEFAULT_EXE
app.path_var.set(m.DEFAULT_EXE)
app.cfg["orient"] = "rot180"
root.destroy()
print("\n=== v2.0 全部自测通过 ===")
