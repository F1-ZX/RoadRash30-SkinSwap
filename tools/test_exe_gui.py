# -*- coding: utf-8 -*-
"""验证发布版 EXE：真实启动 GUI、截图、优雅关闭、检查设置文件落点。"""
import ctypes
import json
import os
import subprocess
import time
from ctypes import wintypes

from PIL import ImageGrab

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "docs", "screenshots") \
    if os.path.isdir(os.path.join(HERE, "..", "docs", "screenshots")) else HERE
# 下载 Release 里的 EXE 后，可用 RR_EXE 环境变量指定其路径
_cands = [p for p in (os.environ.get("RR_EXE"),
                      os.path.join(HERE, "发布", "车皮调色台.exe"),
                      os.path.join(HERE, "..", "..", "发布", "车皮调色台.exe"))
          if p and os.path.isfile(p)]
assert _cands, "请设置 RR_EXE 指向 车皮调色台.exe"
EXE = os.path.abspath(_cands[0])
PUB = os.path.dirname(EXE)
SETTINGS = os.path.join(PUB, "车皮调色台_设置.json")
TITLE_PARTS = ("Skin Studio", "车皮调色台")   # 中文 / English 标题都认

if os.path.isfile(SETTINGS):
    os.remove(SETTINGS)

user32 = ctypes.windll.user32
try:                                   # 让 Win32 坐标与 ImageGrab 一致
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        user32.SetProcessDPIAware()
    except Exception:
        pass
CB = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)


def find_window(parts):
    found = []

    def cb(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            buf = ctypes.create_unicode_buffer(512)
            user32.GetWindowTextW(hwnd, buf, 512)
            if any(part in buf.value for part in parts):
                found.append((hwnd, buf.value))
        return True

    user32.EnumWindows(CB(cb), 0)
    return found


proc = subprocess.Popen([EXE])
hwnd = None
for _ in range(40):                       # 最多等 20 秒（onefile 需解压）
    time.sleep(0.5)
    wins = find_window(TITLE_PARTS)
    if wins:
        hwnd, title = wins[0]
        break
assert hwnd, "发布版 EXE 未弹出主窗口"
print("主窗口已出现:", hex(hwnd), title)
# 短暂置顶，避免被正在运行的游戏窗口遮挡截图
user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002)   # HWND_TOPMOST
time.sleep(1.2)

r = wintypes.RECT()
user32.GetWindowRect(hwnd, ctypes.byref(r))
box = (r.left, r.top, r.right, r.bottom)
print("窗口位置:", box, "尺寸:", box[2] - box[0], "x", box[3] - box[1])
try:                                   # 直接抓目标窗口内容，不受其它置顶窗口遮挡
    shot = ImageGrab.grab(window=hwnd)
except Exception:
    shot = ImageGrab.grab(bbox=box)
out = os.path.join(OUT, "发布版界面.png")
shot.save(out)
print("截图已保存:", out, shot.size)
user32.SetWindowPos(hwnd, -2, 0, 0, 0, 0, 0x0001 | 0x0002)   # HWND_NOTOPMOST

# 优雅关闭，触发 WM_DELETE_WINDOW → 保存设置文件
user32.PostMessageW(hwnd, 0x0010, 0, 0)   # WM_CLOSE
for _ in range(20):
    time.sleep(0.25)
    if proc.poll() is not None:
        break
if proc.poll() is None:
    subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                   capture_output=True)
print("进程退出码:", proc.poll())

assert os.path.isfile(SETTINGS), "设置文件没有写到 EXE 同目录"
cfg = json.load(open(SETTINGS, "r", encoding="utf-8"))
print("设置文件:", SETTINGS)
print("  exe    =", cfg.get("exe"))
print("  orient =", cfg.get("orient"))
print("  names[0] =", cfg.get("names", [""])[0])
assert cfg.get("orient") == "rot180"
assert cfg.get("names", [""])[0] == "450cc Banzai Sport 450"
print("\n=== 发布版 EXE 验证通过 ===")
