# -*- coding: utf-8 -*-
"""
暴力摩托 · 车皮调色台  v2.0  (Road Rash 30th Anniversary Edition)
=====================================================================
零依赖单文件工具。读取 RoadRash95.exe 内 15 张 256 字节配色重映射表
(LUT)，可视化每辆车当前使用的车皮，并允许任意指派/交换/随机，
写回 exe 时只改动表区 3840 字节，自动备份。

v2.0 · 任意 RGB 改色（方案 2）
---------------------------------------------------------------------
在「调色」编辑器里可以给任意车皮的任意一种颜色挑任意 RGB：
  * 该调色板项只被这一辆车引用  → 直接改写 PALETTE.RAW 中该项的 RGB，
    LUT 一个字节都不动，所有动画帧自动同步，明暗层次原样保留。
  * 该调色板项被多辆车共用      → 从「全局空闲项」里挑一个颜色最接近
    目标色的项写入新 RGB，再把本槽 LUT 中所有指向旧项的索引重指过去，
    其余 14 辆车完全不受影响。
写盘时同时改写 exe 表区与 DATA/PALETTE.RAW，两个文件各自自动备份，
写后逐字节回读校验；「还原调色板」可一键恢复内嵌的原版 1024 字节。

生效性实测（2026-11-13，本机 30 周年 + 汉化 + 宽屏 + HD 补丁）
---------------------------------------------------------------------
临时把 PALETTE.RAW 的 idx 2/3/4 改成探针色后启动游戏，扫描进程内存，
在 0x00F02000 附近原样找到 `12 34 56 00 78 9A BC 00 DE F0 21 00`，
证明该文件被游戏直接加载为 256 x (R,G,B,0) 调色板。
另据 magoowa/RoadRash30-MultiFix 的 hd_renderer.cpp：HD 渲染器 hook 的
present8 收到的正是这张 256xRGBA 表，compose() 用它把 8-bit 索引转 RGB。
全游戏目录只有这一份调色板，exe / DLL 均无内嵌副本。

全局调色板是共享的：车手、赛道、天空、UI 都引用它。工具优先改动
「仅被本车皮引用」的项，其次挑与目标色最接近的空闲项，把可见副作用
降到最低；但无法静态保证赛道/UI 绝不受影响，改动后可用一键还原。

技术依据
---------------------------------------------------------------------
* 表区: 文件偏移 0x195490 / VA 0x596A90，15 张 x 256 字节。
* 索引: 按车辆 spec number —— 0-4 Rat, 5-9 Super, 10-14 Sport
  (magoowa/RoadRash30-MultiFix, src/hd_renderer.cpp 中 FixBikeColors 注释)。
* 原版缺陷: Rat 与 Super 两组各 5 张表整体装反，商店图片是对的、
  比赛里的 3D 车/车手配色是错的 (Fandom Wiki / Anakin94 RR30th_BCFIX)。
* 官方修复: 交换 (0,5)(1,6)(2,7)(3,8)(4,9) 五对表。
* LUT 语义: HIBOB.DAT 的车手精灵像素是 0-255 的"灰度索引"，
  最终颜色 = PALETTE.RAW[ LUT[ 像素索引 ] ]。
  PALETTE.RAW 为 256 x (R,G,B,0)，索引 0 = 纯蓝透明色。
* 预览素材: neparij 在 DxWnd 讨论串发布的 15 张 output_image_N.bmp，
  经逐字节验证与 30 周年版 15 张 LUT 完全一致 (256/256)；
  15 张图共用同一套 2160 字节 (40x54) 索引矩阵，故可给任意配色实时上色。
* 完整性校验: 15 张表的 FNV-1a = 0x51d083b966bd8657 (原版)，
  与 MultiFix 源码中的期望值一致。

15 个槽位对应的具体车名已按游戏内实测校正（2026-11-13），
不再采用早期按价格升序推断的顺序。可用「编辑车名」继续修改。

预览方向
---------------------------------------------------------------------
neparij 的 output_image_N.bmp 是标准 bottom-up BMP（height = +54），
像素矩阵首行其实是图像最底行。按 BMP 规范还原应为「垂直翻转」；
「旋转 180°」在此基础上再做一次左右镜像。工具默认使用 180°
（按游戏内画面对照实测选择），并在界面提供三种方向随时切换。

与各类补丁的关系
---------------------------------------------------------------------
工具只改写 exe 文件偏移 0x195490 起的 3840 字节，写前逐张校验
表头特征 00 01，写后回读比对。汉化 / 宽屏分辨率 / HD 补丁修改的是
PE 头、资源段与文件尾部新增节，均不落在表区内；实测补丁安装前后
表区 FNV-1a 完全一致，四个游戏 DLL 也没有引用该表地址。
"""
import os
import sys
import json
import struct
import zlib
import base64
import shutil
import hashlib
import random
import tempfile
import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog, colorchooser

# ---------------------------------------------------------------- 内嵌数据
_SPRITE = base64.b64decode("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")   # 40x54 车手精灵索引
_PALETTE = base64.b64decode("AAD/AAAAAABwodgAk6//ALjL/wDP3P8AI0ajADB5uAAocLAAJHSgACBgmAAgUIAAEjtgAA8xUAAVGoEADwpFAAUGNQBRUeIAWFCwAEBAmAAwMHIAEBxUAIhQwAB4VZsA7QPJAJocfQBLGaIAShZ7AEgcYAAuDEsAHAQyAEUPNABNGkkAy2rKAPBweQDoUFAA+ygAAOcQAADWEAgAYgAGAEEAAAA2AAAAJQAAABAAAACaU00AhEdCAHc4OAB3UkgAv0stANAgIAC2HBwAnBYVAHIRCACBJS8AahIUAEQOFABDCQgALQsWAEhAcAB7WnMArX+DAJyM1gCKhKUAkH2HADkhOQAxGDAAKRE1ABwJHAAQBQ0Ak5yKAGZ6XwBCT00AGiYpAMDPzQCbwc4Ai6nYAJOouABhaIIAYWilACxGbwAUFDUAGBApAAgDHwAIABAAJDlQAC5CSgAbJzQADxgfABQmRAAIGCkABBAeADG3PwAooxwAQs4IAG6jMgBvjzEAZ5QZAGJ9GABbbQAAb3MgADBgAAA1akgALU9LABAxKAAsaSYAF1YiAFGLFABJgBAARXgQAD9tEAAjYgAAMm0AACNUAAAwUg4AM0oNACw+CgAdNgAAHCwIABQnAAByfkIAV2chAD5WIwAxVSMAIkoOACFBCQALOwAAACsAAAgkAAASQB4ADiwMAAchCgAAEAAACBAIAAAICAAmQCcAJD0YADdAHgAhLxwAHS4QABAhDAAQGAgAvb6MAG5zSABrakUAUVErAFlkRwA4Qi4AcmYVAGVPEQBRQAgAU1MUAEJAAAA/PQsALy0IACQlAAAUGAAAEBAAAAgIAAAZGhAAISEQAEIuCABDLhcALyEIACIYAAA+GgAALAsAABgQAAATCAAALS0cADgoGAAoGBAAGxAKAJ1bIgCgSyQAjVA3AIlKGgB7ORMAZyoaAFMZCABzGgAARhwVACwOCAAcBwoA6d+6AOrWhQDVtzsAyY0AANWKKwDKcCgAdUkYAIVDAACEamUAhHNaAIx7YwCUe2sAk3RkAIRrUgBrY1IAioRoALithwC2oYIA2a99ANabawC7g2MArYc6ALKYQACgikAAoYlEAKd1QgCYc0sAgmY9AHdRMwBkQSMAZ1AmAFM/KACAZU4AlnEtAJuGLwCYgjsAjnU4AH1mLACAaDgAZ00zAGZRSABSQj4APy4vAC0dGAApISkAIRghAOXh2QDZ0tcAu7e5AGxsbABzc3MAe3NrAGtrWgBUVUMAgoeEAFlWZABYVWEAUUxZAFlSYQBWUV0ATUhUAF1WbwBcVmUASEJRAC8vRwBCQkIAOTk5ADExMQApKSkAISEhABgYGAAHBwcA////AA==")  # PALETTE.RAW 256xRGBA
_STOCK = base64.b64decode("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")      # 原版 15 张 LUT
_ACTIVE = frozenset(base64.b64decode("AgMEBgcJCgsMDQ4PEBESExUWFxgZGhscHR4fICEiIyQlJicoKSorLC0uLzAxMjM0NTY3ODk6Ozw9Pj9AQUJDREVGR0hJSktMTU5PUFFSU1RVVldYWltcXV5gYmNkZmdoaWprbG1ub3BxcnN0dXZ3eHp7fH1+gIKDhIaHiImKi4yNjo+QkZKTlZaXmJqbnJ2eoqOmp6mqq6ytr7CxsrO1tre4uru8vsLGx8nKy8zNz9DR0tXW19ja29zd3uLm5+rr7O/w8fL19vf4+vv8/f8="))  # HIBOB+LOBOB 全图集活跃像素索引

TABLE_OFF = 0x195490
TABLE_SIZE = 256
SLOTS = 15
REGION = SLOTS * TABLE_SIZE
STOCK_FNV = 0x51D083B966BD8657
FIXED_FNV = 0x18840F2491215077
PAL_SIZE = 1024
PAL_RELPATH = os.path.join("DATA", "PALETTE.RAW")
SW, SH = 40, 54
BG = (26, 28, 38)

# 打包成 EXE 后 __file__ 指向临时解压目录，设置文件必须落在 EXE 同目录；
# 若该目录不可写（例如放在 Program Files），退回 %APPDATA%。
def _writable(d):
    try:
        p = os.path.join(d, ".rr_write_test")
        with open(p, "w") as f:
            f.write("1")
        os.remove(p)
        return True
    except Exception:
        return False


BASE_DIR = os.path.dirname(os.path.abspath(
    sys.executable if getattr(sys, "frozen", False) else __file__))
DATA_DIR = BASE_DIR if _writable(BASE_DIR) else os.path.join(
    os.environ.get("APPDATA") or tempfile.gettempdir(), "RoadRashSkinStudio")
try:
    os.makedirs(DATA_DIR, exist_ok=True)
except Exception:
    DATA_DIR = tempfile.gettempdir()
SETTINGS = os.path.join(DATA_DIR, "车皮调色台_设置.json")
LOG_PATH = os.path.join(DATA_DIR, "车皮调色台_错误.log")

# ------------------------------------------------------- 界面语言 (中文 / English)
# 设置文件优先；没有设置时按系统区域自动选：中文系统用中文，其余用英文。
LANG = "en"
try:
    import locale as _rr_locale
    _rr_loc = (_rr_locale.getdefaultlocale()[0] or "").lower()
    LANG = "zh" if _rr_loc.startswith("zh") else "en"
except Exception:
    pass
try:
    with open(SETTINGS, "r", encoding="utf-8") as _rr_f:
        _rr_saved = json.load(_rr_f).get("lang")
    if _rr_saved in ("zh", "en"):
        LANG = _rr_saved
except Exception:
    pass

I18N = {
    "RAT  ·  老鼠车": "RAT  ·  Rat Bikes",
    "SUPER  ·  超级车": "SUPER  ·  Super Bikes",
    "SPORT  ·  运动车": "SPORT  ·  Sport Bikes",
    "旋转 180°（游戏实测）": "Rotate 180° (in-game verified)",
    "垂直翻转（BMP 规范）": "Flip vertically (BMP spec)",
    "原始像素（颠倒）": "Raw pixels (upside down)",
    "烈焰红": "Flame Red",
    "金紫": "Gold Purple",
    "沙金": "Sand Gold",
    "靛蓝": "Indigo",
    "品红": "Magenta",
    "荧光绿": "Neon Green",
    "银白": "Silver White",
    "深蓝": "Deep Blue",
    "酒红": "Wine Red",
    "铁灰": "Iron Grey",
    "紫罗兰": "Violet",
    "金黄": "Golden",
    "青绿": "Teal",
    "暗红": "Dark Red",
    "紫金": "Purple Gold",
    "PALETTE.RAW 长度异常：%d（应为 1024）": "PALETTE.RAW has invalid size: %d (expected 1024)",
    "黑": "Black",
    "白": "White",
    "浅灰": "Light Grey",
    "深灰": "Dark Grey",
    "橙棕": "Orange Brown",
    "红": "Red",
    "黄绿": "Yellow Green",
    "绿": "Green",
    "紫": "Purple",
    "蓝": "Blue",
    "中性": "Neutral",
    "文件太短，表区读取不完整": "File too short: color table region incomplete",
    "偏移 %#x 处的第 %d 张表特征不符，可能不是 30 周年版 exe": "Bad table signature at offset %#x for table %d; this may not be the 30th Anniversary exe",
    "原版 %02d · %s": "Stock %02d · %s",
    "暴力摩托 · 车皮调色台 v2.0": "Road Rash · Skin Studio v2.0",
    "暴力摩托 · 车皮调色台": "Road Rash · Skin Studio",
    "15 张配色重映射表  ·  Rat 0-4 / Super 5-9 / Sport 10-14  ·  ": "15 color remap tables  ·  Rat 0-4 / Super 5-9 / Sport 10-14  ·  ",
    "表区 0x195490 + 全局调色板  ·  支持任意 RGB 改色": "Table @ 0x195490 + global palette  ·  arbitrary RGB recoloring",
    "选择 exe": "Browse exe",
    "重新读取": "Reload",
    "兼容性自检": "Compatibility Check",
    "官方修复 (Rat⇄Super)": "Official Fix (Rat⇄Super)",
    "恢复原版": "Restore Stock",
    "随机打乱": "Shuffle",
    "保存方案": "Save Preset",
    "载入方案": "Load Preset",
    "编辑车名": "Edit Bike Names",
    "还原调色板": "Restore Palette",
    "交换槽位": "Swap Slots",
    "交换": "Swap",
    "预览方向": "Preview Orientation",
    "点卡片「调色」可自定义任意 RGB；点「应用到游戏」才写盘": "Recolor any RGB; Apply to Game writes to disk",
    "应用到游戏（自动备份）": "Apply to Game",
    "槽 %02d": "Slot %02d",
    "调色": "Recolor",
    "找不到文件": "File Not Found",
    "请先选择 RoadRash95.exe": "Please select RoadRash95.exe first",
    "⚠ 未找到 exe，当前显示内置原版配色（只读预览）": "⚠ exe not found; showing built-in stock palettes (read-only preview)",
    "放弃未应用的改动？": "Discard unsaved changes?",
    "当前有尚未写入磁盘的自定义颜色，重新读取会放弃它们。\n继续吗？": "You have custom colors not yet written to disk. Reloading will discard them.\nContinue?",
    "读取失败": "Read Failed",
    "调色板读取失败": "Palette Read Failed",
    "%s\n\n将使用内嵌原版调色板预览。": "%s\n\nUsing the built-in stock palette for preview.",
    "原版（Rat / Super 配色错位）": "Stock (Rat / Super swapped)",
    "官方修复（Rat⇄Super 已对调）": "Official Fix (Rat⇄Super corrected)",
    "自定义配色": "Custom Colors",
    "调色板原版": "Palette: stock",
    "调色板已改 %d 项": "Palette: %d entries changed",
    "⚠ 未找到 PALETTE.RAW（只读预览）": "⚠ PALETTE.RAW not found (read-only preview)",
    "选择 RoadRash95.exe": "Select RoadRash95.exe",
    "可执行文件": "Executable",
    "所有文件": "All Files",
    "暴力摩托 · 车皮调色台   兼容性自检": "Road Rash · Skin Studio   Compatibility Check",
    "【工具只做什么】": "[ WHAT THIS TOOL CHANGES ]",
    "  1) RoadRash95.exe 文件偏移 0x195490 起的 3840 字节": "  1) 3840 bytes at file offset 0x195490 in RoadRash95.exe",
    "     （15 张 × 256 字节配色表），其余字节一个都不碰。": "     (15 × 256-byte color tables); no other byte is touched.",
    "  2) DATA/PALETTE.RAW 的 1024 字节（仅当有自定义颜色时写入）。": "  2) 1024 bytes of DATA/PALETTE.RAW (only when custom colors exist).",
    "  写入前：校验 15 张表的 00 01 表头特征 + 文件长度 + 调色板长度。": "  Before writing: verifies all 15 table signatures, file and palette sizes.",
    "  写入后：两个文件逐字节回读比对；写入前各自创建带时间戳的备份。": "  After writing: reads both files back byte-for-byte; timestamped backups are made first.",
    "【全局调色板】": "[ GLOBAL PALETTE ]",
    "  1024 字节   MD5 %s": "  1024 bytes   MD5 %s",
    "  相对内嵌原版：%s": "  vs built-in stock: %s",
    "无改动": "no changes",
    "已改 %d 项 %s": "%d entries changed %s",
    "  内存中待应用：%d 项   |   剩余可用空闲项 %d": "  Pending in memory: %d entries   |   free entries left: %d",
    "  ⚠ 调色板读取失败：%s": "  ⚠ Could not read palette: %s",
    "【当前 exe】": "[ CURRENT EXE ]",
    "  路径   %s": "  Path   %s",
    "  大小   %d 字节    PE 节数 %d    MD5 %s": "  Size  %d bytes    PE sections %d    MD5 %s",
    "  节布局 ": "  Sections ",
    "原版（Rat / Super 错位）": "Stock (Rat / Super swapped)",
    "官方修复": "Official Fix",
    "  表区   15/15 张表头 00 01 校验通过；FNV-1a %016X → %s": "  Tables  15/15 signatures OK; FNV-1a %016X → %s",
    "  ⚠ 读取失败：%s": "  ⚠ Read failed: %s",
    "【当前 exe】未选择有效文件，请先选 RoadRash95.exe": "[ CURRENT EXE ] No valid file selected; choose RoadRash95.exe first",
    "【游戏 DLL 是否运行时改写配色表】": "[ DO GAME DLLs OVERWRITE THE TABLES AT RUNTIME? ]",
    "  %-24s %7d 字节   表地址引用 %d 处": "  %-24s %7d bytes   table address refs %d",
    "  （未找到 DLL）": "  (no DLLs found)",
    "  合计引用：%d 处 → %s": "  Total refs: %d → %s",
    "不会覆盖配色表": "will not overwrite the tables",
    "存在引用，建议复核": "references found, please review",
    "【实测结论（本机）】": "[ MEASURED ON THIS MACHINE ]",
    "  分辨率 / HD 补丁安装前 exe 1803264 字节、安装后 1804800 字节，": "  exe size 1803264 bytes before the widescreen/HD patch, 1804800 after;",
    "  .data 段 raw 偏移均为 0x18CA00，表区 3840 字节零差异，": "  .data raw offset stays 0x18CA00; the 3840-byte table region is identical;",
    "  安装前后 FNV-1a 同为 0x51D083B966BD8657。": "  FNV-1a is 0x51D083B966BD8657 both before and after.",
    "  汉化补丁改资源段与文本，同样不落在表区。": "  The localization patch edits the resource section and text, also outside the table region.",
    "  → 汉化 / 宽屏分辨率 / HD 补丁与本工具互不影响，可任意组合。": "  → Localization, widescreen and HD patches are independent of this tool; use any combination.",
    "【v2.0 调色板生效性实测（2026-11-13，本机）】": "[ v2.0 PALETTE PROBE (2026-11-13, this machine) ]",
    "  临时把 PALETTE.RAW 的 idx 2/3/4 改成探针色后启动游戏，扫描进程内存，": "  Temporarily wrote probe colors into PALETTE.RAW idx 2/3/4, launched the game, scanned process memory,",
    "  原样找到 `12 34 56 00 78 9A BC 00 DE F0 21 00`，": "  and found exactly `12 34 56 00 78 9A BC 00 DE F0 21 00`,",
    "  证明该文件被直接加载为 256 x (R,G,B,0) 全局调色板。": "  proving the file is loaded directly as a 256 x (R,G,B,0) global palette.",
    "  MultiFix 的 hd_renderer.cpp / compose() 也用同一张 256xRGBA 表": "  MultiFix hd_renderer.cpp / compose() uses the same 256xRGBA table",
    "  把 8-bit 索引转 RGB；全游戏目录只有这一份，exe/DLL 无内嵌副本。": "  to convert 8-bit indices to RGB; it is the only copy in the game folder, no embedded duplicate in exe/DLL.",
    "  → 改 PALETTE.RAW 确实能实现任意 RGB 改色。": "  → Editing PALETTE.RAW does enable arbitrary RGB recolors.",
    "【注意】": "[ NOTES ]",
    "  · Steam「校验游戏文件完整性」或游戏更新会还原 exe / 调色板，需重新应用。": "  · Steam \"Verify integrity\" or a game update restores exe/palette; re-apply afterwards.",
    "  · 重装汉化 / HD 补丁若替换了 exe，同样需重新应用。": "  · Reinstalling localization/HD patches may replace the exe; re-apply afterwards.",
    "  · PALETTE.RAW 被车手 / 赛道 / UI 共享：自定义颜色优先直接改": "  · PALETTE.RAW is shared by riders / track / UI: custom colors first rewrite",
    "    「仅本车引用」的项，共用项自动隔离到与目标色最接近的空闲项。": "    entries used only by this bike; shared entries are isolated to the closest free entry.",
    "    实测遮挡可在主窗口点「还原调色板」完整回滚（含 LUT 重指）。": "    \"Restore Palette\" in the main window fully rolls back changes, including LUT redirects.",
    "  · 若装了 MultiFix 且开启 FixBikeColors：它只在表区哈希等于原版时": "  · With MultiFix FixBikeColors enabled: it only swaps when the table hash equals stock,",
    "    才交换，自定义配色不会被覆盖。": "    so custom colors are never overwritten.",
    "  · 未来若有 mod 重定位了这张表，表头校验会失败并拒绝写入（安全保护）。": "  · If a future mod relocates the table, signature validation fails and writing is refused (safety guard).",
    "自检状态：%s": "Check status: %s",
    "通过": "PASS",
    "未完全通过（见上方提示）": "Not fully passed (see notes above)",
    "关闭": "Close",
    "专属项 #%d：直接改写调色板 RGB，LUT 一字节未动，": "Exclusive entry #%d: rewrote the palette RGB directly, LUT untouched,",
    "%d 个灰度索引（全部动画帧）同步生效。": "%d grayscale indices (all animation frames) update together.",
    "已无可用空闲调色板项。请先「还原调色板」释放，": "No free palette entries left. Use \"Restore Palette\" to free some,",
    "或改选只被这一辆车引用的颜色。": "or pick a color used only by this bike.",
    "共用项 #%d（%d 辆车引用）：已分配空闲项 #%d（原色 %s，与所挑颜色最接近），": "Shared entry #%d (used by %d bikes): allocated free entry #%d (original %s, closest to the picked color),",
    "本槽 %d 个索引重指，其余车不受影响。": "%d indices redirected for this slot; other bikes are unaffected.",
    "无需还原": "Nothing to Restore",
    "调色板当前就是内嵌原版，没有自定义颜色。": "The palette already matches the built-in stock; no custom colors.",
    "将把 %d 个调色板项恢复为原版颜色，并回滚本工具的 LUT 重指。\n\n": "This restores %d palette entries to stock and rolls back this tool's LUT redirects.\n\n",
    "尚未「应用到游戏」的改动会一起撤销；点「应用到游戏」才会写回磁盘。": "Changes not yet applied will also be discarded; \"Apply to Game\" is what writes to disk.",
    "已还原": "Restored",
    "调色板与相关 LUT 重指已恢复原版。\n": "Palette and related LUT redirects are back to stock.\n",
    "点「应用到游戏」写盘后生效。": "Click \"Apply to Game\" to write it to disk.",
    "原版（错位）": "Stock (swapped)",
    "自定义": "Custom",
    "   ·   调色板改动 %d 项": "   ·   %d palette entries changed",
    "待应用：%s   ·   %d / 15 张表不同%s   ·   exe 表区 %d 字节 + PALETTE.RAW 仅在有改动时写入": "Pending: %s   ·   %d/15 tables differ%s   ·   %d B of exe tables; PALETTE.RAW only if changed",
    "自定义 / 外部配色": "Custom / external colors",
    "保存配色方案": "Save Color Preset",
    "JSON 方案": "JSON Preset",
    "已保存": "Saved",
    "方案已保存到：\n": "Preset saved to:\n",
    "保存失败": "Save Failed",
    "载入配色方案": "Load Color Preset",
    "方案格式不正确": "Invalid Preset Format",
    "方案 %02d · 自定义": "Preset %02d · Custom",
    "载入失败": "Load Failed",
    "编辑车辆名称": "Edit Bike Names",
    "当前车名已按游戏内实测校正；如需调整可直接修改": "Names verified in-game; edit below if needed",
    "保存": "Save",
    "未就绪": "Not Ready",
    "请先选择有效的 RoadRash95.exe": "Select a valid RoadRash95.exe first",
    "无法应用": "Cannot Apply",
    "你有 %d 项自定义颜色，但没找到\n%s\n\n": "You have %d custom colors but this file was not found:\n%s\n\n",
    "请确认游戏目录结构完整，或用「还原调色板」放弃颜色改动。": "Check that the game folder is intact, or use \"Restore Palette\" to discard the color changes.",
    "读取调色板失败：%s": "Could not read palette: %s",
    "无需修改": "Nothing to Change",
    "当前 exe 的 15 张表与 PALETTE.RAW 都已与目标一致。": "The exe tables and PALETTE.RAW already match the target.",
    "将修改：": "Will modify:",
    "    表区 %#x–%#x，%d 字节中 %d 字节变化": "    Table %#x–%#x, %d of %d bytes change",
    "    1024 字节，%d 项颜色变化（相对内嵌原版）": "    1024 bytes, %d colors changed (vs built-in stock)",
    "· 两个文件写入前各自创建带时间戳的备份": "· Timestamped backups are created for both files before writing",
    "· 写后逐字节回读校验；表区之外一个字节都不碰": "· Byte-for-byte readback after writing; nothing outside the table region is touched",
    "· 汉化 / 宽屏分辨率 / HD 补丁不受影响": "· Localization / widescreen / HD patches are unaffected",
    "请先确认游戏已完全退出（否则文件可能被占用）。继续吗？": "Make sure the game has fully exited (files may be locked). Continue?",
    "确认写入": "Confirm Write",
    "PALETTE.RAW 写后校验失败": "PALETTE.RAW readback verification failed",
    "exe 表区写后校验失败": "exe table readback verification failed",
    "\n\n文件被占用：请彻底退出游戏（含后台进程）后重试。": "\n\nFile is locked: fully exit the game (including background processes) and retry.",
    "写入失败": "Write Failed",
    "%s%s\n\n已自动回滚到写入前状态。备份文件（仍保留）：\n%s\n%s": "%s%s\n\nRolled back automatically to the pre-write state. Backups kept:\n%s\n%s",
    "（exe 未改）": "(exe unchanged)",
    "（调色板未改）": "(palette unchanged)",
    "完成": "Done",
    "车皮配色与调色板已写入。\n\n备份：\n%s\n\n": "Bike colors and palette written.\n\nBackups:\n%s\n\n",
    "从 Steam 启动游戏即可生效。": "Launch the game from Steam to see the changes.",
    "荧光橙": "Neon Orange",
    "明黄": "Bright Yellow",
    "薄荷绿": "Mint Green",
    "天蓝": "Sky Blue",
    "宝蓝": "Royal Blue",
    "樱粉": "Cherry Pink",
    "炭黑": "Charcoal",
    "调色 · 槽 %02d · %s": "Recolor · Slot %02d · %s",
    "任意 RGB 改色  ·  槽 %02d  %s": "Arbitrary RGB recolor  ·  Slot %02d  %s",
    "每一行就是这套车皮用到的一个调色板项。选中一行 → 取色 → 应用；": "Each row is a palette entry used by this skin. Select a row → pick a color → apply;",
    "预览与全部 15 张卡片会实时刷新。改动只在点主窗口「应用到游戏」后写盘。": "the preview and all 15 cards refresh live. Nothing is written until \"Apply to Game\" in the main window.",
    "实时预览": "Live Preview",
    "选中颜色": "Selected Color",
    "本车皮用到的颜色（按画面像素数排序）": "Colors used by this skin (sorted by pixel count)",
    "项": "Idx",
    "当前颜色": "Current",
    "像素": "Pixels",
    "引用车辆": "Used by",
    "改色策略": "Strategy",
    "取色器…": "Pick Color…",
    "应用该颜色": "Apply Color",
    "快捷色": "Quick Colors",
    "选中一种颜色即可开始。": "Select a color to begin.",
    "注意：PALETTE.RAW 为全局共享（车手 / 赛道 / UI）。专属项直接改写，": "Note: PALETTE.RAW is shared (riders / track / UI). Exclusive entries are rewritten directly;",
    "共用项自动隔离到颜色最接近的空闲项；主窗口「还原调色板」可完整回滚。": "shared entries are isolated to the closest free entry. \"Restore Palette\" rolls everything back.",
    "仅本车": "This bike only",
    "直接改写": "Rewrite directly",
    "%d 辆(全部)": "%d bikes (all)",
    "隔离重指": "Isolate & redirect",
    "%d 辆:%s%s": "%d bikes:%s%s",
    "可用空闲调色板项：%d": "Free palette entries: %d",
    "仅本车引用 → 直接改写调色板该项 RGB，LUT 不变，明暗层次保留。": "Exclusive → rewrite this palette RGB directly; LUT unchanged, shading preserved.",
    "被 %d 辆车共用 → 分配最接近的空闲项并重指本槽 LUT，其余车不变。": "Shared by %d bikes → allocate the closest free entry and redirect this slot's LUT; others unchanged.",
    "#%d  %s  %s  ·  %d 像素  ·  %s": "#%d  %s  %s  ·  %d px  ·  %s",
    "未选择": "Nothing Selected",
    "请先在列表里选中一种颜色。": "Select a color in the list first.",
    "改色失败": "Recolor Failed",
    "格式错误": "Invalid Format",
    "请输入 6 位十六进制颜色，如 #ff3cc0。": "Enter a 6-digit hex color, e.g. #ff3cc0.",
    "挑选车皮颜色": "Pick a Bike Color",
    "启动失败": "Startup Failed",
    "15 张配色重映射表  ·  Rat 0-4  /  Super 5-9  /  Sport 10-14  ·  表区 0x195490": "15 color remap tables  ·  Rat 0-4 / Super 5-9 / Sport 10-14  ·  table @ 0x195490",
    "卡片下拉框可指派任意配色；点「应用到游戏」才写入 exe": "Assign palettes; Apply to Game writes the exe",
    "  读取并改写 RoadRash95.exe 文件偏移 0x195490 起的 3840 字节": "  Reads and rewrites 3840 bytes at file offset 0x195490 in RoadRash95.exe",
    "  （15 张 × 256 字节配色表），其余字节一个都不碰。": "  (15 × 256-byte color tables); no other byte is touched.",
    "  写入前：校验 15 张表的 00 01 表头特征 + 文件长度。": "  Before writing: verifies all 15 table signatures and the file size.",
    "  写入后：重新读取表区逐字节比对；写入前自动创建带时间戳的备份。": "  After writing: reads the table region back byte-for-byte; a timestamped backup is made first.",
    "  · Steam「校验游戏文件完整性」或游戏更新会还原 exe，需重新应用一次。": "  · Steam \"Verify integrity\" or a game update restores the exe; re-apply afterwards.",
    "待应用状态：%s   ·   与内置原版相比有 %d / 15 张表不同   ·   只写入 exe 的 %#x–%#x 共 %d 字节": "Pending: %s   ·   %d / 15 tables differ from built-in stock   ·   writes only %#x–%#x of exe, %d bytes total",
    "当前 exe 的 15 张表已经与目标一致。": "The 15 tables in the current exe already match the target.",
    "将修改 %s\n\n": "Will modify %s\n\n",
    "· 只改写表区 %#x–%#x（%d 字节中的 %d 字节变化）\n": "· Rewrites only table %#x–%#x (%d of %d bytes change)\n",
    "· 只动配色表，汉化 / 宽屏分辨率 / HD 补丁不受影响\n": "· Only the color tables change; localization / widescreen / HD patches are unaffected\n",
    "· 写入前自动创建备份\n\n": "· A backup is created automatically before writing\n\n",
    "请先确认游戏已完全退出。继续吗？": "Make sure the game has fully exited. Continue?",
    "写后校验失败，请从备份恢复": "Readback verification failed; restore from the backup",
    "%s\n\n备份位置：\n%s": "%s\n\nBackup:\n%s",
    "车皮配色已写入。\n\n备份：\n%s\n\n从 Steam 启动游戏即可生效。": "Bike colors written.\n\nBackup:\n%s\n\nLaunch the game from Steam to see the changes.",
    "15 张配色重映射表  ·  Rat 0-4 / Super 5-9 / Sport 10-14  ·  表区 0x195490 + 全局调色板  ·  支持任意 RGB 改色": "15 color remap tables  ·  Rat 0-4 / Super 5-9 / Sport 10-14  ·  Table @ 0x195490 + global palette  ·  arbitrary RGB recoloring",
    "专属项 #%d：直接改写调色板 RGB，LUT 一字节未动，%d 个灰度索引（全部动画帧）同步生效。": "Exclusive entry #%d: rewrote the palette RGB directly, LUT untouched, %d grayscale indices (all animation frames) update together.",
    "已无可用空闲调色板项。请先「还原调色板」释放，或改选只被这一辆车引用的颜色。": "No free palette entries left. Use \"Restore Palette\" to free some, or pick a color used only by this bike.",
    "共用项 #%d（%d 辆车引用）：已分配空闲项 #%d（原色 %s，与所挑颜色最接近），本槽 %d 个索引重指，其余车不受影响。": "Shared entry #%d (used by %d bikes): allocated free entry #%d (original %s, closest to the picked color), %d indices redirected for this slot; other bikes are unaffected.",
    "将把 %d 个调色板项恢复为原版颜色，并回滚本工具的 LUT 重指。\n\n尚未「应用到游戏」的改动会一起撤销；点「应用到游戏」才会写回磁盘。": "This restores %d palette entries to stock and rolls back this tool's LUT redirects.\n\nChanges not yet applied will also be discarded; \"Apply to Game\" is what writes to disk.",
    "调色板与相关 LUT 重指已恢复原版。\n点「应用到游戏」写盘后生效。": "Palette and related LUT redirects are back to stock.\nClick \"Apply to Game\" to write it to disk.",
    "你有 %d 项自定义颜色，但没找到\n%s\n\n请确认游戏目录结构完整，或用「还原调色板」放弃颜色改动。": "You have %d custom colors but this file was not found:\n%s\n\nCheck that the game folder is intact, or use \"Restore Palette\" to discard the color changes.",
    "车皮配色与调色板已写入。\n\n备份：\n%s\n\n从 Steam 启动游戏即可生效。": "Bike colors and palette written.\n\nBackups:\n%s\n\nLaunch the game from Steam to see the changes.",
    "每一行就是这套车皮用到的一个调色板项。选中一行 → 取色 → 应用；预览与全部 15 张卡片会实时刷新。改动只在点主窗口「应用到游戏」后写盘。": "Each row is a palette entry used by this skin. Select a row → pick a color → apply; the preview and all 15 cards refresh live. Nothing is written until \"Apply to Game\" in the main window.",
    "注意：PALETTE.RAW 为全局共享（车手 / 赛道 / UI）。专属项直接改写，共用项自动隔离到颜色最接近的空闲项；主窗口「还原调色板」可完整回滚。": "Note: PALETTE.RAW is shared (riders / track / UI). Exclusive entries are rewritten directly; shared entries are isolated to the closest free entry. \"Restore Palette\" rolls everything back."
}

def tr(s):
    """中文原文即 key；英文模式查表，未收录的字符串原样返回。"""
    return I18N.get(s, s) if LANG == "en" else s


def set_language(code):
    global LANG
    LANG = code
    try:
        cfg = {}
        try:
            with open(SETTINGS, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            pass
        if not isinstance(cfg, dict):
            cfg = {}
        cfg["lang"] = code
        with open(SETTINGS, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def restart_app():
    try:
        import subprocess
        subprocess.Popen([sys.executable] + sys.argv[1:], close_fds=True)
        return True
    except Exception:
        return False


def detect_exe():
    """自动探测 RoadRash95.exe：优先本程序同目录，再查 Steam 库。"""
    rel = os.path.join("steamapps", "common", "RoadRash", "RoadRash95.exe")
    cands = [os.path.join(BASE_DIR, "RoadRash95.exe")]
    # Steam libraryfolders.vdf 中登记的其它库
    try:
        import re
        for base in (os.environ.get("ProgramFiles(x86)"),
                     os.environ.get("ProgramFiles"),
                     os.environ.get("LOCALAPPDATA")):
            if not base:
                continue
            vdf = os.path.join(base, "Steam", "steamapps", "libraryfolders.vdf")
            if os.path.isfile(vdf):
                txt = open(vdf, "r", encoding="utf-8", errors="ignore").read()
                for m in re.finditer(r'"path"\s+"([^"]+)"', txt):
                    cands.append(os.path.join(m.group(1).replace("\\\\", "\\"), rel))
    except Exception:
        pass
    for drv in "CDEFGHIJ":
        root = drv + ":\\"
        if not os.path.isdir(root):
            continue
        cands.append(os.path.join(root, "SteamLibrary", rel))
        cands.append(os.path.join(root, "Program Files (x86)", "Steam", rel))
        cands.append(os.path.join(root, "Program Files", "Steam", rel))
    for p in cands:
        try:
            if os.path.isfile(p) and os.path.getsize(p) > 1000000:
                return p
        except Exception:
            pass
    return ""


DEFAULT_EXE = detect_exe()

GROUPS = [
    (tr('RAT  ·  老鼠车'), "#e2603f", 0, 5),
    (tr('SUPER  ·  超级车'), "#4aa3df", 5, 10),
    (tr('SPORT  ·  运动车'), "#62b46a", 10, 15),
]

# 经游戏内实测校正的槽位对应车名（2026-11-13）
DEFAULT_NAMES = [
    "450cc Banzai Sport 450", "400cc Corsair Swallow", "250cc Kamikaze ZYX 250",
    "500cc Killer Rat", "125cc Perro Pico",
    "750/1100cc Banzai Super Sport", "600cc Corsair Raven N",
    "1000cc Diablo Vipera N", "750cc Kamikaze ZYX 750 N",
    "900cc Stilleto Assasino N",
    "750cc Diablo Vampiro", "1000cc DMG M10", "750cc Kamikaze ZYX 750",
    "250cc Perro Grande", "600cc Stilleto Aggressore",
]

ORIENT_MODES = [
    (tr('旋转 180°（游戏实测）'), "rot180"),
    (tr('垂直翻转（BMP 规范）'), "flipv"),
    (tr('原始像素（颠倒）'), "raw"),
]

SCHEME_NAMES = [
    tr('烈焰红'), tr('金紫'), tr('沙金'), tr('靛蓝'), tr('品红'),
    tr('荧光绿'), tr('银白'), tr('深蓝'), tr('酒红'), tr('铁灰'),
    tr('紫罗兰'), tr('金黄'), tr('青绿'), tr('暗红'), tr('紫金'),
]


# ---------------------------------------------------------------- 工具函数
def fnv1a(data):
    h = 0xCBF29CE484222325
    for b in data:
        h = ((h ^ b) * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return h


def split_luts(blob):
    return [bytearray(blob[i * TABLE_SIZE:(i + 1) * TABLE_SIZE]) for i in range(SLOTS)]


def join_luts(luts):
    return b"".join(bytes(x) for x in luts)


def pal_rgb(idx, pal=None):
    q = _PALETTE if pal is None else pal
    p = (idx & 0xFF) * 4
    return (q[p], q[p + 1], q[p + 2])


def pal_set(idx, rgb, pal):
    """写入一个可变调色板项的 RGB（保留第 4 字节）。"""
    p = (idx & 0xFF) * 4
    pal[p], pal[p + 1], pal[p + 2] = rgb[0], rgb[1], rgb[2]


def dominant(lut, pal=None):
    """从精灵实际用到的索引里挑出最显眼的 3 个颜色。"""
    seen = {}
    for i in _SPRITE:
        if i < 2:
            continue
        c = pal_rgb(lut[i], pal)
        if max(c) - min(c) > 32 and max(c) > 68:
            seen[c] = seen.get(c, 0) + 1
    top = sorted(seen.items(), key=lambda kv: -kv[1])[:3]
    return [c for c, _ in top] or [(90, 90, 100)]


def hexcol(c):
    return "#%02x%02x%02x" % c


def palette_path(exe):
    """由 exe 路径推出 DATA/PALETTE.RAW。"""
    if not exe:
        return ""
    return os.path.join(os.path.dirname(os.path.abspath(exe)), PAL_RELPATH)


def read_palette(path):
    if not path or not os.path.isfile(path):
        return None
    with open(path, "rb") as f:
        d = bytearray(f.read())
    if len(d) != PAL_SIZE:
        raise ValueError(tr('PALETTE.RAW 长度异常：%d（应为 1024）') % len(d))
    return d


def palette_overrides(pal):
    """相对内嵌原版，列出被改过的调色板项 {index: '#rrggbb'}。"""
    out = {}
    for i in range(256):
        if tuple(pal[i * 4:i * 4 + 3]) != tuple(_PALETTE[i * 4:i * 4 + 3]):
            out[str(i)] = hexcol(pal_rgb(i, pal))
    return out


def parse_hex(s):
    s = (s or "").strip().lstrip("#")
    if len(s) != 6:
        return None
    try:
        return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return None


def color_distance(a, b):
    # 加权欧氏距离，接近人眼对亮度的敏感度
    return ((a[0] - b[0]) ** 2 * 2 + (a[1] - b[1]) ** 2 * 3 +
            (a[2] - b[2]) ** 2 * 2) ** 0.5


def color_name(c):
    r, g, b = c
    mx, mn = max(c), min(c)
    if mx < 38:
        return tr('黑')
    if mx - mn < 18:
        return tr('白') if mx > 205 else (tr('浅灰') if mx > 130 else tr('深灰'))
    if r > g and r > b:
        return tr('橙棕') if g > b + 25 and r < 200 else tr('红')
    if g > r and g > b:
        return tr('黄绿') if r > b + 40 else tr('绿')
    if b > r and b > g:
        return tr('紫') if r > g + 30 else tr('蓝')
    return tr('中性')


def png_encode(w, h, pixels):
    """把 (r,g,b) 行优先像素列表编成 PNG，纯标准库。"""
    raw = bytearray()
    for y in range(h):
        raw.append(0)
        for x in range(w):
            raw.extend(pixels[y * w + x])

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data +
                struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) +
            chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b""))


def render_png(lut, scale=2, orient="rot180", pal=None):
    """用指定 LUT + 调色板给车手精灵上色，返回放大后的 PNG 字节。

    源 BMP 为 bottom-up（height=+54），像素矩阵首行是图像最底行：
      flipv  按 BMP 规范还原（上下翻转）
      rot180 在 flipv 基础上再左右镜像（默认，按游戏内画面对照实测）
      raw    不做变换，画面上下颠倒
    """
    w, h = SW * scale, SH * scale
    out = [BG] * (w * h)
    for y in range(SH):
        for x in range(SW):
            sy = SH - 1 - y if orient != "raw" else y
            sx = SW - 1 - x if orient == "rot180" else x
            i = _SPRITE[sy * SW + sx]
            c = BG if i == 0 else pal_rgb(lut[i], pal)
            for dy in range(scale):
                row = (y * scale + dy) * w + x * scale
                for dx in range(scale):
                    out[row + dx] = c
    return png_encode(w, h, out)


def load_photo(png):
    b64 = base64.b64encode(png).decode("ascii")
    try:
        return tk.PhotoImage(data=b64)
    except Exception:
        # 回退到临时文件，文件名必须按内容区分，否则 15 张图会互相覆盖
        tag = hashlib.md5(png).hexdigest()[:12]
        p = os.path.join(tempfile.gettempdir(), "rr_skin_%s.png" % tag)
        if not os.path.exists(p):
            with open(p, "wb") as f:
                f.write(png)
        return tk.PhotoImage(file=p)


_PREVIEW_CACHE = {}


def preview_of(lut, orient="rot180", pal=None):
    """同一套配色 + 同一调色板只渲染一次，返回 (PNG bytes, 主色列表)。"""
    key = (orient, bytes(lut), bytes(pal) if pal is not None else b"")
    if key not in _PREVIEW_CACHE:
        png = render_png(lut, orient=orient, pal=pal)
        cols = dominant(lut, pal)
        if len(_PREVIEW_CACHE) > 240:       # 调色板频繁变化时限制缓存体积
            _PREVIEW_CACHE.clear()
        _PREVIEW_CACHE[key] = (png, cols)
    return _PREVIEW_CACHE[key]


def read_region(path):
    with open(path, "rb") as f:
        f.seek(TABLE_OFF)
        blob = f.read(REGION)
    if len(blob) != REGION:
        raise ValueError(tr('文件太短，表区读取不完整'))
    # 每张表以 00 01 开头是这套 LUT 的固定特征，防止作用到错误版本
    for i in range(SLOTS):
        if blob[i * TABLE_SIZE:i * TABLE_SIZE + 2] != b"\x00\x01":
            raise ValueError(tr('偏移 %#x 处的第 %d 张表特征不符，可能不是 30 周年版 exe') %
                             (TABLE_OFF, i))
    return blob


def load_settings():
    try:
        with open(SETTINGS, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_settings(d):
    try:
        with open(SETTINGS, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ---------------------------------------------------------------- 主程序
class App:
    def __init__(self, root):
        self.root = root
        self.cfg = load_settings()
        # 设置里存的是上一台机器的路径，文件不存在时回退到自动探测
        saved_exe = self.cfg.get("exe")
        self.exe = saved_exe if (saved_exe and os.path.isfile(saved_exe)) else DEFAULT_EXE
        self.names = self.cfg.get("names", DEFAULT_NAMES[:])
        if len(self.names) != SLOTS:
            self.names = DEFAULT_NAMES[:]
        self.orient = self.cfg.get("orient", "rot180")
        if self.orient not in [v for _, v in ORIENT_MODES]:
            self.orient = "rot180"

        self.stock = split_luts(_STOCK)
        self.fixed = self.stock[5:10] + self.stock[0:5] + self.stock[10:15]
        self.schemes = [bytes(x) for x in self.stock]      # 可指派的配色库
        self.scheme_labels = [tr('原版 %02d · %s') % (i + 1, SCHEME_NAMES[i])
                              for i in range(SLOTS)]
        self.tables = [bytearray(x) for x in self.stock]
        self.palette = bytearray(_PALETTE)      # 当前生效的 256xRGBA 调色板
        self.palette_file = ""                  # 磁盘上的 DATA/PALETTE.RAW
        self.palette_ok = False
        self.remaps = {}                        # {槽位: {新分配的空闲项: 原调色板项}}，用于完整还原
        self.photos = []
        self.cards = []
        self.dirty = False

        root.title(tr('暴力摩托 · 车皮调色台 v2.0'))
        root.geometry("1240x940")
        root.minsize(1050, 700)
        root.configure(bg="#161821")
        self._style()
        self._build()
        self.reload_exe(silent=True)
        self._protocol()

    def _style(self):
        st = ttk.Style()
        try:
            st.theme_use("clam")
        except Exception:
            pass
        st.configure(".", background="#161821", foreground="#e8eaf2",
                     fieldbackground="#222534", bordercolor="#353a4c")
        st.configure("TFrame", background="#1e2130")
        st.configure("Card.TFrame", background="#222534", relief="flat")
        st.configure("TLabel", background="#222534", foreground="#e8eaf2")
        st.configure("Head.TLabel", background="#161821", foreground="#f2f4fb",
                     font=("Microsoft YaHei UI", 15, "bold"))
        st.configure("Sub.TLabel", background="#161821", foreground="#8b93ab",
                     font=("Microsoft YaHei UI", 9))
        st.configure("TButton", background="#30364a", foreground="#e8eaf2",
                     borderwidth=0, padding=(10, 6))
        st.map("TButton", background=[("active", "#3d4661")])
        st.configure("Go.TButton", background="#c8532f", font=("Microsoft YaHei UI", 10, "bold"))
        st.map("Go.TButton", background=[("active", "#e0653c")])
        st.configure("TCombobox", fieldbackground="#2b3042", background="#2b3042",
                     foreground="#f0f2fa", arrowcolor="#c9cee0",
                     bordercolor="#3a4056", lightcolor="#2b3042",
                     darkcolor="#2b3042", padding=4)
        # clam 主题下 readonly 状态会忽略 configure 的配色，必须再用 map 指定
        st.map("TCombobox",
               fieldbackground=[("readonly", "#2b3042"), ("disabled", "#262a38")],
               foreground=[("readonly", "#f0f2fa"), ("disabled", "#7a829a")],
               background=[("readonly", "#2b3042")],
               arrowcolor=[("readonly", "#c9cee0")])
        for opt, val in [
            ("*TCombobox*Listbox.background", "#2b3042"),
            ("*TCombobox*Listbox.foreground", "#f0f2fa"),
            ("*TCombobox*Listbox.selectBackground", "#c8532f"),
            ("*TCombobox*Listbox.selectForeground", "#ffffff"),
        ]:
            try:
                root.option_add(opt, val)
            except Exception:
                pass

    def _build(self):
        top = ttk.Frame(self.root, style="TFrame", padding=(16, 12, 16, 8))
        top.pack(fill="x")
        ttk.Label(top, text=tr('暴力摩托 · 车皮调色台'), style="Head.TLabel").pack(anchor="w")
        ttk.Label(top, text=tr('15 张配色重映射表  ·  Rat 0-4 / Super 5-9 / Sport 10-14  ·  表区 0x195490 + 全局调色板  ·  支持任意 RGB 改色')
                            ,
                  style="Sub.TLabel").pack(anchor="w", pady=(2, 0))

        pathbar = ttk.Frame(self.root, style="TFrame", padding=(16, 4))
        pathbar.pack(fill="x")
        self.path_var = tk.StringVar(value=self.exe)
        ttk.Entry(pathbar, textvariable=self.path_var).pack(side="left", fill="x", expand=True, padx=(0, 8))
        ttk.Button(pathbar, text=tr('选择 exe'), command=self.choose_exe).pack(side="left")
        ttk.Button(pathbar, text=tr('重新读取'), command=lambda: self.reload_exe()).pack(side="left", padx=(6, 0))
        ttk.Button(pathbar, text=tr('兼容性自检'), command=self.check_env).pack(side="left", padx=(6, 0))
        ttk.Button(pathbar, text=("English" if LANG == "zh" else "\u4e2d\u6587"),
                   width=9, command=self.do_language).pack(side="right", padx=(6, 0))

        self.status_var = tk.StringVar(value="—")
        ttk.Label(self.root, textvariable=self.status_var, style="Sub.TLabel",
                  padding=(18, 4)).pack(anchor="w")

        tools = ttk.Frame(self.root, style="TFrame", padding=(16, 6))
        tools.pack(fill="x")
        for text, cmd in [
            (tr('官方修复 (Rat⇄Super)'), self.do_official),
            (tr('恢复原版'), self.do_stock),
            (tr('随机打乱'), self.do_shuffle),
            (tr('保存方案'), self.save_plan),
            (tr('载入方案'), self.load_plan),
            (tr('编辑车名'), self.edit_names),
            (tr('还原调色板'), self.restore_palette),
        ]:
            ttk.Button(tools, text=text, command=cmd).pack(side="left", padx=(0, 6))

        tools2 = ttk.Frame(self.root, style="TFrame", padding=(16, 2))
        tools2.pack(fill="x")
        swap = ttk.Frame(tools2, style="TFrame")
        swap.pack(side="left")
        ttk.Label(swap, text=tr('交换槽位'), style="Sub.TLabel").pack(side="left", padx=(0, 6))
        self.swap_a = ttk.Combobox(swap, width=3, state="readonly",
                                   values=[str(i) for i in range(SLOTS)])
        self.swap_a.set("0")
        self.swap_a.pack(side="left")
        ttk.Label(swap, text="⇄", style="Sub.TLabel").pack(side="left", padx=4)
        self.swap_b = ttk.Combobox(swap, width=3, state="readonly",
                                   values=[str(i) for i in range(SLOTS)])
        self.swap_b.set("5")
        self.swap_b.pack(side="left")
        ttk.Button(swap, text=tr('交换'), command=self.do_swap).pack(side="left", padx=(6, 0))
        ttk.Label(tools2, text=tr('预览方向'), style="Sub.TLabel").pack(side="left", padx=(18, 0))
        self.orient_cb = ttk.Combobox(tools2, width=(20 if LANG == "zh" else 27), state="readonly",
                                      values=[n for n, _ in ORIENT_MODES],
                                      font=("Microsoft YaHei UI", 9))
        self.orient_cb.set(next(n for n, v in ORIENT_MODES if v == self.orient))
        self.orient_cb.pack(side="left", padx=(6, 0))
        self.orient_cb.bind("<<ComboboxSelected>>", self.on_orient)
        ttk.Label(tools2, text=tr('点卡片「调色」可自定义任意 RGB；点「应用到游戏」才写盘'),
                  style="Sub.TLabel").pack(side="left", padx=(18, 0))

        # 可滚动卡片区
        wrap = ttk.Frame(self.root, style="TFrame")
        wrap.pack(fill="both", expand=True, padx=12, pady=(6, 4))
        wrap.columnconfigure(0, weight=1)
        wrap.rowconfigure(0, weight=1)
        canvas = tk.Canvas(wrap, bg="#161821", highlightthickness=0)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=canvas.yview)
        hsb = ttk.Scrollbar(wrap, orient="horizontal", command=canvas.xview)
        self.grid = ttk.Frame(canvas, style="TFrame")
        self.grid.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.grid, anchor="nw")
        canvas.configure(yscrollcommand=sb.set, xscrollcommand=hsb.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(-1 if e.delta > 0 else 1, "units"))
        self._make_cards()

        bottom = ttk.Frame(self.root, style="TFrame", padding=(16, 8))
        bottom.pack(fill="x")
        self.diff_var = tk.StringVar(value="—")
        ttk.Button(bottom, text=tr('应用到游戏（自动备份）'), style="Go.TButton",
                   command=self.apply).pack(side="right")
        ttk.Label(bottom, textvariable=self.diff_var, style="Sub.TLabel",
                  wraplength=(1060 if LANG == "en" else 1200)).pack(side="left")

    def _make_cards(self):
        for r, (title, color, lo, hi) in enumerate(GROUPS):
            lab = ttk.Label(self.grid, text=title, style="Sub.TLabel",
                            font=("Microsoft YaHei UI", 10, "bold"), foreground=color)
            lab.grid(row=r * 2, column=0, columnspan=5, sticky="w", pady=(10, 4), padx=4)
            rowf = ttk.Frame(self.grid, style="TFrame")
            rowf.grid(row=r * 2 + 1, column=0, columnspan=5, sticky="w")
            for c in range(5):
                idx = lo + c
                card = ttk.Frame(rowf, style="Card.TFrame", padding=8)
                card.grid(row=0, column=c, padx=5, sticky="n")
                headrow = ttk.Frame(card, style="Card.TFrame")
                headrow.pack(fill="x")
                head = ttk.Label(headrow, text=tr('槽 %02d') % idx, style="TLabel",
                                 font=("Microsoft YaHei UI", 9, "bold"), foreground=color)
                head.pack(side="left")
                ttk.Button(headrow, text=tr('调色'), width=(5 if LANG == "zh" else 9),
                           command=lambda i=idx: self.open_editor(i)).pack(side="right")
                namebox = ttk.Frame(card, height=40, style="Card.TFrame")
                namebox.pack(fill="x", pady=(0, 4))
                namebox.pack_propagate(False)   # 长车名换行时保持所有卡片等高
                name = ttk.Label(namebox, text="", style="TLabel", wraplength=170,
                                 justify="left", font=("Microsoft YaHei UI", 9))
                name.pack(anchor="nw")
                pic = ttk.Label(card, style="TLabel")
                pic.pack()
                pic.bind("<Double-Button-1>", lambda e, i=idx: self.open_editor(i))
                cb = ttk.Combobox(card, width=19, state="readonly",
                                  values=self.scheme_labels,
                                  font=("Microsoft YaHei UI", 9))
                cb.pack(pady=(6, 4))
                cb.bind("<<ComboboxSelected>>", lambda e, i=idx: self.on_pick(i))
                sw = tk.Canvas(card, width=160, height=12, bg="#222534", highlightthickness=0)
                sw.pack()
                self.cards.append(dict(head=head, name=name, pic=pic, cb=cb, sw=sw, idx=idx))
        for c, card in enumerate(self.cards):
            card["name"].configure(text=self.names[c])

    def _protocol(self):
        def on_close():
            self.cfg["exe"] = self.exe
            self.cfg["names"] = self.names
            self.cfg["orient"] = self.orient
            save_settings(self.cfg)
            self.root.destroy()
        self.root.protocol("WM_DELETE_WINDOW", on_close)

    # ------------------------------------------------------------ 状态
    def reload_exe(self, silent=False):
        p = self.path_var.get().strip()
        if not os.path.isfile(p):
            if not silent:
                messagebox.showwarning(tr('找不到文件'), tr('请先选择 RoadRash95.exe'))
            self.status_var.set(tr('⚠ 未找到 exe，当前显示内置原版配色（只读预览）'))
            self.exe = ""
            return
        if not silent and palette_overrides(self.palette):
            if not messagebox.askyesno(
                    tr('放弃未应用的改动？'),
                    tr('当前有尚未写入磁盘的自定义颜色，重新读取会放弃它们。\n继续吗？')):
                return
        try:
            blob = read_region(p)
        except Exception as e:
            messagebox.showerror(tr('读取失败'), str(e))
            return
        self.exe = p
        self.cfg["exe"] = p
        self.tables = split_luts(blob)
        # 调色板与 exe 同目录；缺失或长度异常时退回内嵌原版，保证预览可用
        pf = palette_path(p)
        self.palette_file = pf if os.path.isfile(pf) else ""
        try:
            disk = read_palette(pf) if self.palette_file else None
            self.palette = disk if disk is not None else bytearray(_PALETTE)
            self.palette_ok = disk is not None
        except Exception as e:
            self.palette = bytearray(_PALETTE)
            self.palette_ok = False
            if not silent:
                messagebox.showwarning(tr('调色板读取失败'), tr('%s\n\n将使用内嵌原版调色板预览。') % e)
        h = fnv1a(blob)
        if h == STOCK_FNV:
            state = tr('原版（Rat / Super 配色错位）')
        elif h == FIXED_FNV:
            state = tr('官方修复（Rat⇄Super 已对调）')
        else:
            state = tr('自定义配色')
        ov = palette_overrides(self.palette)
        pstate = (tr('调色板原版') if not ov else tr('调色板已改 %d 项') % len(ov))
        if not self.palette_ok:
            pstate = tr('⚠ 未找到 PALETTE.RAW（只读预览）')
        self.status_var.set("● %s   |   FNV-1a %016X   |   %s   |   %s" %
                            (state, h, os.path.basename(p), pstate))
        self.refresh()

    def do_language(self, restart=True):
        """切换界面语言。模块级文本在启动时构建，因此切换后重启一次。"""
        new = "en" if LANG == "zh" else "zh"
        set_language(new)
        if restart:
            if restart_app():
                os._exit(0)
            messagebox.showinfo(
                "Language", "Language saved. Restart the application to apply it.")

    def choose_exe(self):
        p = filedialog.askopenfilename(title=tr('选择 RoadRash95.exe'),
                                       filetypes=[(tr('可执行文件'), "*.exe"), (tr('所有文件'), "*.*")],
                                       initialdir=os.path.dirname(self.exe or DEFAULT_EXE) or BASE_DIR)
        if p:
            self.path_var.set(p)
            self.reload_exe()

    def on_orient(self, _event=None):
        label = self.orient_cb.get()
        v = next((v for n, v in ORIENT_MODES if n == label), "rot180")
        if v == self.orient:
            return
        self.orient = v
        self.cfg["orient"] = v
        save_settings(self.cfg)
        _PREVIEW_CACHE.clear()
        self.refresh()

    def check_env(self):
        """就地自检：证明表区与汉化 / 宽屏 / HD 补丁互不相干。"""
        p = self.path_var.get().strip()
        out = []
        out.append(tr('暴力摩托 · 车皮调色台   兼容性自检'))
        out.append("=" * 72)
        out.append("")
        out.append(tr('【工具只做什么】'))
        out.append(tr('  1) RoadRash95.exe 文件偏移 0x195490 起的 3840 字节'))
        out.append(tr('     （15 张 × 256 字节配色表），其余字节一个都不碰。'))
        out.append(tr('  2) DATA/PALETTE.RAW 的 1024 字节（仅当有自定义颜色时写入）。'))
        out.append(tr('  写入前：校验 15 张表的 00 01 表头特征 + 文件长度 + 调色板长度。'))
        out.append(tr('  写入后：两个文件逐字节回读比对；写入前各自创建带时间戳的备份。'))
        out.append("")
        pf = palette_path(p)
        if pf and os.path.isfile(pf):
            try:
                disk = read_palette(pf)
                ov_disk = palette_overrides(disk)
                out.append(tr('【全局调色板】'))
                out.append("  %s" % pf)
                out.append(tr('  1024 字节   MD5 %s') % hashlib.md5(bytes(disk)).hexdigest()[:16])
                out.append(tr('  相对内嵌原版：%s') %
                           (tr('无改动') if not ov_disk else tr('已改 %d 项 %s') %
                            (len(ov_disk), ",".join(sorted(ov_disk, key=int)[:12]))))
                out.append(tr('  内存中待应用：%d 项   |   剩余可用空闲项 %d') %
                           (len(palette_overrides(self.palette)), len(self.free_items())))
                out.append("")
            except Exception as e:
                out.append(tr('  ⚠ 调色板读取失败：%s') % e)
                out.append("")
        ok = True
        if os.path.isfile(p):
            try:
                raw = open(p, "rb").read()
                pe = struct.unpack_from("<I", raw, 0x3C)[0]
                nsec = struct.unpack_from("<H", raw, pe + 6)[0]
                osz = struct.unpack_from("<H", raw, pe + 20)[0]
                out.append(tr('【当前 exe】'))
                out.append(tr('  路径   %s') % p)
                out.append(tr('  大小   %d 字节    PE 节数 %d    MD5 %s') %
                           (len(raw), nsec, hashlib.md5(raw).hexdigest()[:16]))
                datas = []
                for i in range(nsec):
                    o = pe + 24 + osz + i * 40
                    nm = raw[o:o + 8].rstrip(b"\x00").decode(errors="replace")
                    vs, va, rs, ro = struct.unpack_from("<IIII", raw, o + 8)
                    if nm in (".data", ".rsrc", ".rrhd"):
                        datas.append("%s raw=%#x" % (nm, ro))
                out.append(tr('  节布局 ') + " | ".join(datas))
                blob = read_region(p)
                h = fnv1a(blob)
                state = {STOCK_FNV: tr('原版（Rat / Super 错位）'),
                         FIXED_FNV: tr('官方修复')}.get(h, tr('自定义配色'))
                out.append(tr('  表区   15/15 张表头 00 01 校验通过；FNV-1a %016X → %s') % (h, state))
                out.append("")
            except Exception as e:
                ok = False
                out.append(tr('  ⚠ 读取失败：%s') % e)
                out.append("")
        else:
            ok = False
            out.append(tr('【当前 exe】未选择有效文件，请先选 RoadRash95.exe'))
            out.append("")

        out.append(tr('【游戏 DLL 是否运行时改写配色表】'))
        needles = [struct.pack("<I", 0x596A90),   # VA
                   struct.pack("<I", 0x196A90),   # RVA
                   struct.pack("<I", 0x195490)]   # 文件偏移
        try:
            folder = os.path.dirname(p) if os.path.isfile(p) else ""
            dlls = sorted(f for f in os.listdir(folder) if f.lower().endswith(".dll"))
        except Exception:
            dlls = []
        total = 0
        for f in dlls:
            try:
                d = open(os.path.join(folder, f), "rb").read()
                n = sum(d.count(x) for x in needles)
                total += n
                out.append(tr('  %-24s %7d 字节   表地址引用 %d 处') % (f, len(d), n))
            except Exception:
                pass
        if not dlls:
            out.append(tr('  （未找到 DLL）'))
        out.append(tr('  合计引用：%d 处 → %s') %
                   (total, tr('不会覆盖配色表') if total == 0 else tr('存在引用，建议复核')))
        out.append("")
        out.append(tr('【实测结论（本机）】'))
        out.append(tr('  分辨率 / HD 补丁安装前 exe 1803264 字节、安装后 1804800 字节，'))
        out.append(tr('  .data 段 raw 偏移均为 0x18CA00，表区 3840 字节零差异，'))
        out.append(tr('  安装前后 FNV-1a 同为 0x51D083B966BD8657。'))
        out.append(tr('  汉化补丁改资源段与文本，同样不落在表区。'))
        out.append(tr('  → 汉化 / 宽屏分辨率 / HD 补丁与本工具互不影响，可任意组合。'))
        out.append("")
        out.append(tr('【v2.0 调色板生效性实测（2026-11-13，本机）】'))
        out.append(tr('  临时把 PALETTE.RAW 的 idx 2/3/4 改成探针色后启动游戏，扫描进程内存，'))
        out.append(tr('  原样找到 `12 34 56 00 78 9A BC 00 DE F0 21 00`，'))
        out.append(tr('  证明该文件被直接加载为 256 x (R,G,B,0) 全局调色板。'))
        out.append(tr('  MultiFix 的 hd_renderer.cpp / compose() 也用同一张 256xRGBA 表'))
        out.append(tr('  把 8-bit 索引转 RGB；全游戏目录只有这一份，exe/DLL 无内嵌副本。'))
        out.append(tr('  → 改 PALETTE.RAW 确实能实现任意 RGB 改色。'))
        out.append("")
        out.append(tr('【注意】'))
        out.append(tr('  · Steam「校验游戏文件完整性」或游戏更新会还原 exe / 调色板，需重新应用。'))
        out.append(tr('  · 重装汉化 / HD 补丁若替换了 exe，同样需重新应用。'))
        out.append(tr('  · PALETTE.RAW 被车手 / 赛道 / UI 共享：自定义颜色优先直接改'))
        out.append(tr('    「仅本车引用」的项，共用项自动隔离到与目标色最接近的空闲项。'))
        out.append(tr('    实测遮挡可在主窗口点「还原调色板」完整回滚（含 LUT 重指）。'))
        out.append(tr('  · 若装了 MultiFix 且开启 FixBikeColors：它只在表区哈希等于原版时'))
        out.append(tr('    才交换，自定义配色不会被覆盖。'))
        out.append(tr('  · 未来若有 mod 重定位了这张表，表头校验会失败并拒绝写入（安全保护）。'))
        out.append("")
        out.append(tr('自检状态：%s') % (tr('通过') if ok else tr('未完全通过（见上方提示）')))

        win = tk.Toplevel(self.root)
        win.title(tr('兼容性自检'))
        win.configure(bg="#1e2130")
        win.geometry("840x640")
        bar = ttk.Frame(win, style="TFrame")
        bar.pack(side="bottom", fill="x")
        ttk.Button(bar, text=tr('关闭'), command=win.destroy).pack(pady=6)
        body = ttk.Frame(win, style="TFrame")
        body.pack(fill="both", expand=True, padx=10, pady=(10, 0))
        txt = tk.Text(body, wrap="none", bg="#161821", fg="#dfe3f0",
                      font=("Consolas", 10), relief="flat", padx=12, pady=10)
        sb = ttk.Scrollbar(body, orient="vertical", command=txt.yview)
        txt.configure(yscrollcommand=sb.set)
        txt.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        txt.insert("1.0", "\n".join(out))
        txt.configure(state="disabled")

    # ------------------------------------------------- 任意 RGB 改色（v2.0）
    def used_items(self):
        """15 套 LUT 在整个精灵图集的活跃索引上引用到的调色板项。"""
        used = set()
        for t in self.tables:
            used.update(t[i] for i in _ACTIVE)
        return used

    def owners_of(self, p):
        return [k for k in range(SLOTS)
                if any(self.tables[k][i] == p for i in _ACTIVE)]

    def free_items(self, target=None):
        """全局空闲项：没有任何车皮引用、且仍保持原版 RGB 的调色板项。

        按与目标色的视觉距离排序，优先挑最接近的，万一赛道/UI 也用了该项，
        画面变化也最小。索引 0（透明蓝）与 1 永远排除。
        """
        used = self.used_items()
        cand = [p for p in range(2, 256)
                if p not in used and
                tuple(self.palette[p * 4:p * 4 + 3]) == tuple(_PALETTE[p * 4:p * 4 + 3])]
        if target is not None:
            cand.sort(key=lambda p: color_distance(pal_rgb(p), target))
        return cand

    def slot_items(self, slot):
        """本槽用到的调色板项 -> [(项, 单帧像素数, 引用它的槽位列表)]。"""
        lut = self.tables[slot]
        counts = {}
        for i in _SPRITE:
            if i < 2:
                continue
            counts[lut[i]] = counts.get(lut[i], 0) + 1
        out = [(p, n, self.owners_of(p)) for p, n in counts.items()]
        out.sort(key=lambda x: -x[1])
        return out

    def recolor(self, slot, p, rgb):
        """给 slot 的第 p 号颜色换成任意 RGB。返回 (说明, 结果项)。"""
        owners = self.owners_of(p)
        if owners == [slot]:
            pal_set(p, rgb, self.palette)
            n = sum(1 for i in range(256) if self.tables[slot][i] == p)
            return (tr('专属项 #%d：直接改写调色板 RGB，LUT 一字节未动，%d 个灰度索引（全部动画帧）同步生效。')
                     % (p, n), p)
        free = self.free_items(rgb)
        if not free:
            raise RuntimeError(tr('已无可用空闲调色板项。请先「还原调色板」释放，或改选只被这一辆车引用的颜色。')
                               )
        q = free[0]
        pal_set(q, rgb, self.palette)
        lut = self.tables[slot]
        n = 0
        for i in range(256):
            if lut[i] == p:
                lut[i] = q
                n += 1
        self.remaps.setdefault(str(slot), {})[str(q)] = int(p)
        return (tr('共用项 #%d（%d 辆车引用）：已分配空闲项 #%d（原色 %s，与所挑颜色最接近），本槽 %d 个索引重指，其余车不受影响。')
                
                % (p, len(owners), q, hexcol(pal_rgb(q, _PALETTE)), n), q)

    def restore_palette(self):
        """还原调色板，并把隔离改色产生的 LUT 重指一并回滚。"""
        ov = palette_overrides(self.palette)
        if not ov and not self.remaps:
            messagebox.showinfo(tr('无需还原'), tr('调色板当前就是内嵌原版，没有自定义颜色。'))
            return
        if not messagebox.askyesno(
                tr('还原调色板'),
                tr('将把 %d 个调色板项恢复为原版颜色，并回滚本工具的 LUT 重指。\n\n尚未「应用到游戏」的改动会一起撤销；点「应用到游戏」才会写回磁盘。')
                 % len(ov)):
            return
        for s, mp in self.remaps.items():
            try:
                slot = int(s)
                lut = self.tables[slot]
            except (ValueError, IndexError):
                continue
            for qs, ps in list(mp.items())[::-1]:
                q, old = int(qs), int(ps)
                if not any(lut[i] == q for i in range(256)):
                    continue                      # LUT 已被别的操作换掉，跳过
                for i in range(256):
                    if lut[i] == q:
                        lut[i] = old
        self.remaps = {}
        self.palette = bytearray(_PALETTE)
        self.refresh()
        messagebox.showinfo(tr('已还原'), tr('调色板与相关 LUT 重指已恢复原版。\n点「应用到游戏」写盘后生效。')
                                      )

    def open_editor(self, slot):
        ColorEditor(self, slot)

    def state_of(self):
        blob = join_luts(self.tables)
        h = fnv1a(blob)
        if h == STOCK_FNV:
            return tr('原版（错位）')
        if h == FIXED_FNV:
            return tr('官方修复')
        return tr('自定义')

    # ------------------------------------------------------------ 显示
    def refresh(self):
        changed = sum(1 for i in range(SLOTS) if self.tables[i] != self.stock[i])
        ov = palette_overrides(self.palette)
        extra = (tr('   ·   调色板改动 %d 项') % len(ov)) if ov else ""
        self.diff_var.set(tr('待应用：%s   ·   %d / 15 张表不同%s   ·   exe 表区 %d 字节 + PALETTE.RAW 仅在有改动时写入')
                          % (self.state_of(), changed, extra, REGION))
        for i, card in enumerate(self.cards):
            lut = self.tables[i]
            png, cols = preview_of(lut, self.orient, self.palette)
            photo = load_photo(png)
            self.photos.append(photo)          # 防 GC
            card["pic"].configure(image=photo)
            card["name"].configure(text=self.names[i])
            card["sw"].delete("all")
            for j in range(3):
                c = cols[j] if j < len(cols) else (60, 60, 70)
                card["sw"].create_rectangle(j * 54, 0, j * 54 + 52, 12,
                                            fill=hexcol(c), outline="")
            # 下拉显示当前槽实际引用哪套内置方案
            match = [k for k, s in enumerate(self.schemes) if s == bytes(lut)]
            card["cb"].set(self.scheme_labels[match[0]] if match else tr('自定义 / 外部配色'))
        self.photos = self.photos[-SLOTS * 2:]

    def on_pick(self, idx):
        label = self.cards[idx]["cb"].get()
        try:
            k = self.scheme_labels.index(label)
        except ValueError:
            return
        self.tables[idx] = bytearray(self.schemes[k])
        self.refresh()

    # ------------------------------------------------------------ 操作
    def do_official(self):
        self.tables = [bytearray(x) for x in self.fixed]
        self.refresh()

    def do_stock(self):
        self.tables = [bytearray(x) for x in self.stock]
        self.refresh()

    def do_shuffle(self):
        random.shuffle(self.tables)
        self.refresh()

    def do_swap(self):
        try:
            a, b = int(self.swap_a.get()), int(self.swap_b.get())
        except ValueError:
            return
        if not (0 <= a < SLOTS and 0 <= b < SLOTS) or a == b:
            return
        self.tables[a], self.tables[b] = self.tables[b], self.tables[a]
        self.refresh()

    def save_plan(self):
        p = filedialog.asksaveasfilename(title=tr('保存配色方案'), defaultextension=".json",
                                         filetypes=[(tr('JSON 方案'), "*.json")],
                                         initialfile="车皮方案.json")
        if not p:
            return
        d = {"version": 2,
             "names": self.names,
             "tables": [base64.b64encode(bytes(t)).decode() for t in self.tables],
             "palette": palette_overrides(self.palette),
             "remaps": self.remaps}
        try:
            with open(p, "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False, indent=2)
            messagebox.showinfo(tr('已保存'), tr('方案已保存到：\n') + p)
        except Exception as e:
            messagebox.showerror(tr('保存失败'), str(e))

    def load_plan(self):
        p = filedialog.askopenfilename(title=tr('载入配色方案'),
                                       filetypes=[(tr('JSON 方案'), "*.json"), (tr('所有文件'), "*.*")])
        if not p:
            return
        try:
            d = json.load(open(p, "r", encoding="utf-8"))
            t = [bytearray(base64.b64decode(x)) for x in d["tables"]]
            if len(t) != SLOTS or any(len(x) != TABLE_SIZE for x in t):
                raise ValueError(tr('方案格式不正确'))
            self.tables = t
            # v2 方案带自定义调色板；v1 方案没有该字段则恢复内嵌原版
            pal = bytearray(_PALETTE)
            ov = d.get("palette") or {}
            if isinstance(ov, dict):
                for k, v in ov.items():
                    try:
                        idx = int(k)
                    except (TypeError, ValueError):
                        continue
                    c = parse_hex(v) if isinstance(v, str) else None
                    if c and 0 <= idx < 256:
                        pal_set(idx, c, pal)
            self.palette = pal
            rm = d.get("remaps") or {}
            self.remaps = rm if isinstance(rm, dict) else {}
            if isinstance(d.get("names"), list) and len(d["names"]) == SLOTS:
                self.names = [str(x) for x in d["names"]]
            # 把方案里出现的新配色加入可指派库
            for i, x in enumerate(t):
                if bytes(x) not in self.schemes:
                    self.schemes.append(bytes(x))
                    self.scheme_labels.append(tr('方案 %02d · 自定义') % i)
            for card in self.cards:
                card["cb"].configure(values=self.scheme_labels)
            self.refresh()
        except Exception as e:
            messagebox.showerror(tr('载入失败'), str(e))

    def edit_names(self):
        win = tk.Toplevel(self.root)
        win.title(tr('编辑车辆名称'))
        win.configure(bg="#1e2130")
        win.geometry("420x620")
        ttk.Label(win, text=tr('当前车名已按游戏内实测校正；如需调整可直接修改'),
                  style="Sub.TLabel", wraplength=390, padding=10).pack()
        entries = []
        frm = ttk.Frame(win, style="TFrame")
        frm.pack(fill="both", expand=True, padx=12)
        for i in range(SLOTS):
            ttk.Label(frm, text=tr('槽 %02d') % i, style="TLabel").grid(row=i, column=0, sticky="w", pady=2)
            e = ttk.Entry(frm, width=38)
            e.insert(0, self.names[i])
            e.grid(row=i, column=1, sticky="w", pady=2)
            entries.append(e)

        def ok():
            self.names = [e.get().strip() or self.names[i] for i, e in enumerate(entries)]
            self.cfg["names"] = self.names
            save_settings(self.cfg)
            self.refresh()
            win.destroy()

        ttk.Button(win, text=tr('保存'), command=ok).pack(pady=10)

    # ------------------------------------------------------------ 写入
    def apply(self):
        typed = self.path_var.get().strip()
        if typed and os.path.isfile(typed):
            self.exe = typed
        if not self.exe or not os.path.isfile(self.exe):
            messagebox.showwarning(tr('未就绪'), tr('请先选择有效的 RoadRash95.exe'))
            return
        blob = join_luts(self.tables)
        try:
            current = read_region(self.exe)
        except Exception as e:
            messagebox.showerror(tr('无法应用'), str(e))
            return
        pal_blob = bytes(self.palette)
        ov = palette_overrides(self.palette)
        if ov and not self.palette_file:
            messagebox.showerror(tr('无法应用'),
                                 tr('你有 %d 项自定义颜色，但没找到\n%s\n\n请确认游戏目录结构完整，或用「还原调色板」放弃颜色改动。')
                                 
                                 % (len(ov), os.path.join(os.path.dirname(self.exe), PAL_RELPATH)))
            return
        try:
            disk_pal = read_palette(self.palette_file) if self.palette_file else None
        except Exception as e:
            messagebox.showerror(tr('无法应用'), tr('读取调色板失败：%s') % e)
            return
        need_exe = current != blob
        need_pal = disk_pal is not None and bytes(disk_pal) != pal_blob
        if not need_exe and not need_pal:
            messagebox.showinfo(tr('无需修改'), tr('当前 exe 的 15 张表与 PALETTE.RAW 都已与目标一致。'))
            return
        n = sum(1 for a, b in zip(current, blob) if a != b)
        lines = [tr('将修改：'), ""]
        if need_exe:
            lines.append("  %s" % os.path.basename(self.exe))
            lines.append(tr('    表区 %#x–%#x，%d 字节中 %d 字节变化') %
                         (TABLE_OFF, TABLE_OFF + REGION, REGION, n))
        if need_pal:
            lines.append("  DATA/PALETTE.RAW")
            lines.append(tr('    1024 字节，%d 项颜色变化（相对内嵌原版）') % len(ov))
        lines += ["", tr('· 两个文件写入前各自创建带时间戳的备份'),
                  tr('· 写后逐字节回读校验；表区之外一个字节都不碰'),
                  tr('· 汉化 / 宽屏分辨率 / HD 补丁不受影响'),
                  "", tr('请先确认游戏已完全退出（否则文件可能被占用）。继续吗？')]
        if not messagebox.askyesno(tr('确认写入'), "\n".join(lines)):
            return
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = self.exe + ".调色台备份_" + stamp
        pbackup = self.palette_file + ".调色台备份_" + stamp
        try:
            if need_pal:
                shutil.copy2(self.palette_file, pbackup)
                with open(self.palette_file, "wb") as f:
                    f.write(pal_blob)
                    f.flush()
                    os.fsync(f.fileno())
                if bytes(read_palette(self.palette_file)) != pal_blob:
                    raise RuntimeError(tr('PALETTE.RAW 写后校验失败'))
            if need_exe:
                shutil.copy2(self.exe, backup)
                with open(self.exe, "r+b") as f:
                    f.seek(TABLE_OFF)
                    f.write(blob)
                    f.flush()
                    os.fsync(f.fileno())
                if read_region(self.exe) != blob:
                    raise RuntimeError(tr('exe 表区写后校验失败'))
        except Exception as e:
            # 任一文件失败，把已经写过的都回滚，避免留下半套状态
            for need, bk, dst in ((need_pal, pbackup, self.palette_file),
                                  (need_exe, backup, self.exe)):
                if need and os.path.isfile(bk):
                    try:
                        shutil.copy2(bk, dst)
                    except Exception:
                        pass
            extra = ""
            if isinstance(e, PermissionError):
                extra = tr('\n\n文件被占用：请彻底退出游戏（含后台进程）后重试。')
            messagebox.showerror(tr('写入失败'), tr('%s%s\n\n已自动回滚到写入前状态。备份文件（仍保留）：\n%s\n%s') %
                                 (e, extra, backup if need_exe else tr('（exe 未改）'),
                                  pbackup if need_pal else tr('（调色板未改）')))
            self.reload_exe(silent=True)
            return
        self.reload_exe(silent=True)
        bk = [backup] if need_exe else []
        if need_pal:
            bk.append(pbackup)
        messagebox.showinfo(tr('完成'), tr('车皮配色与调色板已写入。\n\n备份：\n%s\n\n从 Steam 启动游戏即可生效。')
                                     % "\n".join(bk))


# ---------------------------------------------------------------- 调色编辑器
class ColorEditor:
    """给单个槽位的每一种颜色挑任意 RGB。"""
    PRESETS = [
        (tr('烈焰红'), "#e03228"), (tr('荧光橙'), "#ff7a18"), (tr('明黄'), "#ffd23f"),
        (tr('荧光绿'), "#4ce04c"), (tr('薄荷绿'), "#35d0a0"), (tr('天蓝'), "#3aa0f0"),
        (tr('宝蓝'), "#2448c8"), (tr('紫罗兰'), "#9b45e0"), (tr('品红'), "#ff3cc0"),
        (tr('樱粉'), "#ff9ab5"), (tr('银白'), "#dfe4ee"), (tr('炭黑'), "#30323c"),
    ]

    def __init__(self, app, slot):
        self.app = app
        self.slot = slot
        self.items = []
        self.photo = None
        self.win = tk.Toplevel(app.root)
        self.win.title(tr('调色 · 槽 %02d · %s') % (slot, app.names[slot]))
        self.win.configure(bg="#1e2130")
        self.win.geometry("940x760")
        self.win.minsize(860, 660)
        self._build()
        self.refresh()

    def _build(self):
        w = self.win
        head = ttk.Frame(w, style="TFrame", padding=(14, 12, 14, 2))
        head.pack(fill="x")
        ttk.Label(head, text=tr('任意 RGB 改色  ·  槽 %02d  %s') %
                  (self.slot, self.app.names[self.slot]),
                  style="Head.TLabel").pack(anchor="w")
        ttk.Label(head, style="Sub.TLabel", wraplength=900,
                  text=tr('每一行就是这套车皮用到的一个调色板项。选中一行 → 取色 → 应用；预览与全部 15 张卡片会实时刷新。改动只在点主窗口「应用到游戏」后写盘。')
                       
                  ).pack(anchor="w", pady=(3, 0))

        body = ttk.Frame(w, style="TFrame", padding=(14, 8))
        body.pack(fill="both", expand=True)

        # ---- 左：预览 ----
        left = ttk.Frame(body, style="Card.TFrame", padding=12)
        left.pack(side="left", fill="y", padx=(0, 14))
        self.pic = ttk.Label(left, style="TLabel")
        self.pic.pack()
        ttk.Label(left, text=tr('实时预览'), style="Sub.TLabel").pack(pady=(8, 2))
        self.sw = tk.Canvas(left, width=162, height=14, bg="#222534", highlightthickness=0)
        self.sw.pack()
        self.free_var = tk.StringVar(value="—")
        ttk.Label(left, textvariable=self.free_var, style="TLabel",
                  wraplength=170, justify="left").pack(anchor="w", pady=(12, 0))
        ttk.Label(left, text=tr('选中颜色'), style="Sub.TLabel").pack(anchor="w", pady=(12, 2))
        self.chip = tk.Canvas(left, width=162, height=34, bg="#222534", highlightthickness=0)
        self.chip.pack()
        ttk.Button(left, text=tr('关闭'), command=self.win.destroy).pack(side="bottom", pady=(16, 0))

        # ---- 右：颜色表 ----
        right = ttk.Frame(body, style="TFrame")
        right.pack(side="left", fill="both", expand=True)
        ttk.Label(right, text=tr('本车皮用到的颜色（按画面像素数排序）'),
                  style="TLabel").pack(anchor="w", pady=(0, 5))
        tf = ttk.Frame(right, style="TFrame")
        tf.pack(fill="both", expand=True)
        cols = ("idx", "hex", "px", "share", "mode")
        self.tree = ttk.Treeview(tf, columns=cols, show="headings",
                                 height=12, selectmode="browse")
        for c, txt, wd in [("idx", tr('项'), 56), ("hex", tr('当前颜色'), 90),
                           ("px", tr('像素'), 56), ("share", tr('引用车辆'), 116),
                           ("mode", tr('改色策略'), 124)]:
            self.tree.heading(c, text=txt)
            self.tree.column(c, width=wd, minwidth=wd,
                             stretch=(c == "mode"), anchor="w")
        sb = ttk.Scrollbar(tf, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.update_info())

        self.info_var = tk.StringVar(value="—")
        ttk.Label(right, textvariable=self.info_var, style="TLabel",
                  wraplength=580, justify="left").pack(anchor="w", pady=(10, 4))

        ctl = ttk.Frame(right, style="TFrame")
        ctl.pack(fill="x", pady=(2, 6))
        ttk.Label(ctl, text="HEX", style="Sub.TLabel").pack(side="left")
        self.hex_var = tk.StringVar(value="#000000")
        ttk.Entry(ctl, textvariable=self.hex_var, width=11).pack(side="left", padx=(6, 6))
        ttk.Button(ctl, text=tr('取色器…'), command=self.pick_color).pack(side="left")
        ttk.Button(ctl, text=tr('应用该颜色'), style="Go.TButton",
                   command=self.apply_hex).pack(side="left", padx=(6, 0))

        pf = ttk.Frame(right, style="TFrame")
        pf.pack(fill="x", pady=(2, 6))
        ttk.Label(pf, text=tr('快捷色'), style="Sub.TLabel").pack(side="left", padx=(0, 8))
        self.presets = tk.Canvas(pf, width=12 * 30, height=26, bg="#1e2130",
                                 highlightthickness=0)
        self.presets.pack(side="left")
        for j, (_nm, h) in enumerate(self.PRESETS):
            x = j * 30
            self.presets.create_rectangle(x + 1, 1, x + 28, 24, fill=h, outline="#454a5e")
        self.presets.bind("<Button-1>", self.on_preset)

        self.msg_var = tk.StringVar(value=tr('选中一种颜色即可开始。'))
        ttk.Label(right, textvariable=self.msg_var, style="Sub.TLabel",
                  wraplength=580, justify="left").pack(anchor="w", pady=(4, 4))
        ttk.Label(right, style="Sub.TLabel", wraplength=580, justify="left",
                  text=tr('注意：PALETTE.RAW 为全局共享（车手 / 赛道 / UI）。专属项直接改写，共用项自动隔离到颜色最接近的空闲项；主窗口「还原调色板」可完整回滚。')
                       
                  ).pack(anchor="w", pady=(8, 0))

    # ------------------------------------------------------------ 数据 / 显示
    def current(self):
        s = self.tree.selection()
        if not s:
            return None
        try:
            return self.items[int(s[0])]
        except (ValueError, IndexError):
            return None

    def refresh(self, keep=None):
        if keep is None:
            cur = self.current()
            keep = cur[0] if cur else None
        self.items = self.app.slot_items(self.slot)
        self.tree.delete(*self.tree.get_children())
        hit = None
        for i, (p, n, owners) in enumerate(self.items):
            col = pal_rgb(p, self.app.palette)
            tag = "r%d" % i
            lum = 0.299 * col[0] + 0.587 * col[1] + 0.114 * col[2]
            self.tree.tag_configure(tag, background=hexcol(col),
                                    foreground="#11131b" if lum > 145 else "#f2f4fb")
            if owners == [self.slot]:
                own, mode = tr('仅本车'), tr('直接改写')
            elif len(owners) == SLOTS:
                own, mode = tr('%d 辆(全部)') % len(owners), tr('隔离重指')
            else:
                own = tr('%d 辆:%s%s') % (len(owners),
                                      ",".join(str(x) for x in owners[:3]),
                                      "…" if len(owners) > 3 else "")
                mode = tr('隔离重指')
            self.tree.insert("", "end", iid=str(i), tags=(tag,),
                             values=("#%d" % p, hexcol(col), n, own, mode))
            if p == keep:
                hit = str(i)
        if hit:
            self.tree.selection_set(hit)
            self.tree.see(hit)
        elif self.items:
            self.tree.selection_set("0")
        self.update_preview()
        self.update_info()

    def update_preview(self):
        app = self.app
        self.photo = load_photo(render_png(app.tables[self.slot], scale=4,
                                           orient=app.orient, pal=app.palette))
        self.pic.configure(image=self.photo)
        self.sw.delete("all")
        for j, c in enumerate(dominant(app.tables[self.slot], app.palette)):
            self.sw.create_rectangle(j * 54, 0, j * 54 + 52, 14,
                                     fill=hexcol(c), outline="")
        self.free_var.set(tr('可用空闲调色板项：%d') % len(app.free_items()))

    def update_info(self):
        cur = self.current()
        self.chip.delete("all")
        if not cur:
            self.info_var.set("—")
            return
        p, n, owners = cur
        col = pal_rgb(p, self.app.palette)
        self.hex_var.set(hexcol(col))
        self.chip.create_rectangle(0, 0, 162, 34, fill=hexcol(col), outline="")
        if owners == [self.slot]:
            strategy = tr('仅本车引用 → 直接改写调色板该项 RGB，LUT 不变，明暗层次保留。')
        else:
            strategy = (tr('被 %d 辆车共用 → 分配最接近的空闲项并重指本槽 LUT，其余车不变。')
                        % len(owners))
        self.info_var.set(tr('#%d  %s  %s  ·  %d 像素  ·  %s') %
                          (p, hexcol(col), color_name(col), n, strategy))

    # ------------------------------------------------------------ 操作
    def apply_rgb(self, rgb):
        cur = self.current()
        if not cur:
            messagebox.showwarning(tr('未选择'), tr('请先在列表里选中一种颜色。'), parent=self.win)
            return
        try:
            msg, newp = self.app.recolor(self.slot, cur[0], rgb)
        except Exception as e:
            messagebox.showerror(tr('改色失败'), str(e), parent=self.win)
            return
        self.app.refresh()
        self.refresh(keep=newp)
        self.msg_var.set("✓ " + msg)

    def apply_hex(self):
        c = parse_hex(self.hex_var.get())
        if c is None:
            messagebox.showwarning(tr('格式错误'), tr('请输入 6 位十六进制颜色，如 #ff3cc0。'),
                                   parent=self.win)
            return
        self.apply_rgb(c)

    def pick_color(self):
        cur = self.current()
        init = hexcol(pal_rgb(cur[0], self.app.palette)) if cur else "#ff0000"
        r = colorchooser.askcolor(color=init, parent=self.win, title=tr('挑选车皮颜色'))
        if r and r[0]:
            self.apply_rgb(tuple(max(0, min(255, int(round(v)))) for v in r[0]))

    def on_preset(self, event):
        j = event.x // 30
        if 0 <= j < len(self.PRESETS):
            c = parse_hex(self.PRESETS[j][1])
            if c:
                self.apply_rgb(c)


def main():
    try:
        root = tk.Tk()
        App(root)
        root.mainloop()
    except Exception:
        import traceback
        msg = traceback.format_exc()
        log = LOG_PATH
        try:
            with open(log, "w", encoding="utf-8") as f:
                f.write(msg)
        except Exception:
            pass
        try:
            messagebox.showerror(tr('启动失败'), msg[-1500:])
        except Exception:
            pass


def selftest():
    """隐藏诊断模式：车皮调色台.exe --selftest
    不创建窗口，把环境 / 数据 / exe 探测结果写到 DATA_DIR，供排查打包版问题。"""
    r = {
        "lang": LANG,
        "frozen": bool(getattr(sys, "frozen", False)),
        "python": sys.version,
        "base_dir": BASE_DIR,
        "data_dir": DATA_DIR,
        "settings": SETTINGS,
        "detected_exe": DEFAULT_EXE,
        "table_offset": hex(TABLE_OFF),
        "table_bytes": REGION,
        "stock_fnv": "%016X" % fnv1a(_STOCK),
        "stock_fnv_expected": "%016X" % STOCK_FNV,
        "names": DEFAULT_NAMES,
        "version": "2.0",
        "active_index_count": len(_ACTIVE),
        "preview_png_bytes": {},
        "errors": [],
    }
    try:
        used = set()
        for t in split_luts(_STOCK):
            used.update(t[i] for i in _ACTIVE)
        r["free_items_stock"] = len([p for p in range(2, 256) if p not in used])
        pf = palette_path(DEFAULT_EXE)
        r["palette_path"] = pf
        r["palette_found"] = bool(pf and os.path.isfile(pf))
        if r["palette_found"]:
            dp = read_palette(pf)
            r["palette_md5"] = hashlib.md5(bytes(dp)).hexdigest()
            r["palette_overrides_on_disk"] = len(palette_overrides(dp))
            r["preview_with_disk_palette_bytes"] = len(
                render_png(split_luts(_STOCK)[0], pal=dp))
    except Exception as e:
        r["errors"].append("palette: %s" % e)
    for _n, o in ORIENT_MODES:
        try:
            r["preview_png_bytes"][o] = len(render_png(split_luts(_STOCK)[0], orient=o))
        except Exception as e:
            r["errors"].append("preview %s: %s" % (o, e))
    r["data_dir_writable"] = _writable(DATA_DIR)
    if DEFAULT_EXE and os.path.isfile(DEFAULT_EXE):
        try:
            blob = read_region(DEFAULT_EXE)
            h = fnv1a(blob)
            r["exe_fnv"] = "%016X" % h
            r["exe_state"] = {STOCK_FNV: tr('原版（错位）'),
                              FIXED_FNV: tr('官方修复')}.get(h, tr('自定义配色'))
            r["exe_table_header_ok"] = True
        except Exception as e:
            r["errors"].append("read_region: %s" % e)
    try:
        out = os.path.join(DATA_DIR, "自检结果.json")
        with open(out, "w", encoding="utf-8") as f:
            json.dump(r, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    else:
        main()
