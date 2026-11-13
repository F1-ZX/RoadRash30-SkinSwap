# -*- coding: utf-8 -*-
"""
给两个版本的 _template.py 注入中英双语界面。

做法：
  1) 在 App 里插入语言切换按钮与回调，在 selftest 里加 lang 字段；
  2) 用 tokenize 找出所有"界面可见"的中文字符串字面量，包成 tr(...)；
  3) 注入 LANG / I18N / tr / set_language / restart_app 代码。
     中文原文即字典 key —— 中文模式零开销原样返回，英文模式查表替换。

i18n_keys.json 由两个模板自动抽取、去重、排序后固化，
EN 列表与它一一对应。运行本脚本会就地更新主模板。
"""
import ast
import io
import json
import os
import re
import tokenize

HERE = os.path.dirname(os.path.abspath(__file__))
KEYS = json.load(open(os.path.join(HERE, "i18n_keys.json"), encoding="utf-8"))

# 与 i18n_keys.json 顺序严格一一对应
EN = [
    "RAT  ·  Rat Bikes",                                                    # 0
    "SUPER  ·  Super Bikes",
    "SPORT  ·  Sport Bikes",
    "Rotate 180° (in-game verified)",
    "Flip vertically (BMP spec)",
    "Raw pixels (upside down)",                                             # 5
    "Flame Red",
    "Gold Purple",
    "Sand Gold",
    "Indigo",
    "Magenta",                                                              # 10
    "Neon Green",
    "Silver White",
    "Deep Blue",
    "Wine Red",
    "Iron Grey",                                                            # 15
    "Violet",
    "Golden",
    "Teal",
    "Dark Red",
    "Purple Gold",                                                          # 20
    "PALETTE.RAW has invalid size: %d (expected 1024)",
    "Black",
    "White",
    "Light Grey",
    "Dark Grey",                                                            # 25
    "Orange Brown",
    "Red",
    "Yellow Green",
    "Green",
    "Purple",                                                               # 30
    "Blue",
    "Neutral",
    "File too short: color table region incomplete",
    "Bad table signature at offset %#x for table %d; this may not be the 30th Anniversary exe",
    "Stock %02d · %s",                                                      # 35
    "Road Rash · Skin Studio v2.0",
    "Road Rash · Skin Studio",
    "15 color remap tables  ·  Rat 0-4 / Super 5-9 / Sport 10-14  ·  ",
    "Table @ 0x195490 + global palette  ·  arbitrary RGB recoloring",
    "Browse exe",                                                           # 40
    "Reload",
    "Compatibility Check",
    "Official Fix (Rat⇄Super)",
    "Restore Stock",
    "Shuffle",                                                              # 45
    "Save Preset",
    "Load Preset",
    "Edit Bike Names",
    "Restore Palette",
    "Swap Slots",                                                           # 50
    "Swap",
    "Preview Orientation",
    "Recolor any RGB; Apply to Game writes to disk",
    "Apply to Game",
    "Slot %02d",                                                            # 55
    "Recolor",
    "File Not Found",
    "Please select RoadRash95.exe first",
    "⚠ exe not found; showing built-in stock palettes (read-only preview)",
    "Discard unsaved changes?",                                             # 60
    "You have custom colors not yet written to disk. Reloading will discard them.\nContinue?",
    "Read Failed",
    "Palette Read Failed",
    "%s\n\nUsing the built-in stock palette for preview.",
    "Stock (Rat / Super swapped)",                                          # 65
    "Official Fix (Rat⇄Super corrected)",
    "Custom Colors",
    "Palette: stock",
    "Palette: %d entries changed",
    "⚠ PALETTE.RAW not found (read-only preview)",                          # 70
    "Select RoadRash95.exe",
    "Executable",
    "All Files",
    "Road Rash · Skin Studio   Compatibility Check",
    "[ WHAT THIS TOOL CHANGES ]",                                           # 75
    "  1) 3840 bytes at file offset 0x195490 in RoadRash95.exe",
    "     (15 × 256-byte color tables); no other byte is touched.",
    "  2) 1024 bytes of DATA/PALETTE.RAW (only when custom colors exist).",
    "  Before writing: verifies all 15 table signatures, file and palette sizes.",
    "  After writing: reads both files back byte-for-byte; timestamped backups are made first.",  # 80
    "[ GLOBAL PALETTE ]",
    "  1024 bytes   MD5 %s",
    "  vs built-in stock: %s",
    "no changes",
    "%d entries changed %s",                                                # 85
    "  Pending in memory: %d entries   |   free entries left: %d",
    "  ⚠ Could not read palette: %s",
    "[ CURRENT EXE ]",
    "  Path   %s",
    "  Size  %d bytes    PE sections %d    MD5 %s",                         # 90
    "  Sections ",
    "Stock (Rat / Super swapped)",
    "Official Fix",
    "  Tables  15/15 signatures OK; FNV-1a %016X → %s",
    "  ⚠ Read failed: %s",                                                  # 95
    "[ CURRENT EXE ] No valid file selected; choose RoadRash95.exe first",
    "[ DO GAME DLLs OVERWRITE THE TABLES AT RUNTIME? ]",
    "  %-24s %7d bytes   table address refs %d",
    "  (no DLLs found)",
    "  Total refs: %d → %s",                                                # 100
    "will not overwrite the tables",
    "references found, please review",
    "[ MEASURED ON THIS MACHINE ]",
    "  exe size 1803264 bytes before the widescreen/HD patch, 1804800 after;",
    "  .data raw offset stays 0x18CA00; the 3840-byte table region is identical;",  # 105
    "  FNV-1a is 0x51D083B966BD8657 both before and after.",
    "  The localization patch edits the resource section and text, also outside the table region.",
    "  → Localization, widescreen and HD patches are independent of this tool; use any combination.",
    "[ v2.0 PALETTE PROBE (2026-11-13, this machine) ]",
    "  Temporarily wrote probe colors into PALETTE.RAW idx 2/3/4, launched the game, scanned process memory,",  # 110
    "  and found exactly `12 34 56 00 78 9A BC 00 DE F0 21 00`,",
    "  proving the file is loaded directly as a 256 x (R,G,B,0) global palette.",
    "  MultiFix hd_renderer.cpp / compose() uses the same 256xRGBA table",
    "  to convert 8-bit indices to RGB; it is the only copy in the game folder, no embedded duplicate in exe/DLL.",  # 115
    "  → Editing PALETTE.RAW does enable arbitrary RGB recolors.",
    "[ NOTES ]",
    '  · Steam "Verify integrity" or a game update restores exe/palette; re-apply afterwards.',
    "  · Reinstalling localization/HD patches may replace the exe; re-apply afterwards.",
    "  · PALETTE.RAW is shared by riders / track / UI: custom colors first rewrite",  # 120
    "    entries used only by this bike; shared entries are isolated to the closest free entry.",
    '    "Restore Palette" in the main window fully rolls back changes, including LUT redirects.',
    "  · With MultiFix FixBikeColors enabled: it only swaps when the table hash equals stock,",
    "    so custom colors are never overwritten.",
    "  · If a future mod relocates the table, signature validation fails and writing is refused (safety guard).",  # 125
    "Check status: %s",
    "PASS",
    "Not fully passed (see notes above)",
    "Close",
    "Exclusive entry #%d: rewrote the palette RGB directly, LUT untouched,",  # 130
    "%d grayscale indices (all animation frames) update together.",
    'No free palette entries left. Use "Restore Palette" to free some,',
    "or pick a color used only by this bike.",
    "Shared entry #%d (used by %d bikes): allocated free entry #%d (original %s, closest to the picked color),",
    "%d indices redirected for this slot; other bikes are unaffected.",       # 135
    "Nothing to Restore",
    "The palette already matches the built-in stock; no custom colors.",
    "This restores %d palette entries to stock and rolls back this tool's LUT redirects.\n\n",
    'Changes not yet applied will also be discarded; "Apply to Game" is what writes to disk.',
    "Restored",                                                             # 140
    "Palette and related LUT redirects are back to stock.\n",
    'Click "Apply to Game" to write it to disk.',
    "Stock (swapped)",
    "Custom",
    "   ·   %d palette entries changed",                                    # 145
    "Pending: %s   ·   %d/15 tables differ%s   ·   %d B of exe tables; PALETTE.RAW only if changed",
    "Custom / external colors",
    "Save Color Preset",
    "JSON Preset",
    "Saved",
    "Preset saved to:\n",                                                   # 150
    "Save Failed",
    "Load Color Preset",
    "Invalid Preset Format",
    "Preset %02d · Custom",
    "Load Failed",                                                          # 155
    "Edit Bike Names",
    "Names verified in-game; edit below if needed",
    "Save",
    "Not Ready",
    "Select a valid RoadRash95.exe first",                                  # 160
    "Cannot Apply",
    "You have %d custom colors but this file was not found:\n%s\n\n",
    'Check that the game folder is intact, or use "Restore Palette" to discard the color changes.',
    "Could not read palette: %s",
    "Nothing to Change",                                                    # 165
    "The exe tables and PALETTE.RAW already match the target.",
    "Will modify:",
    "    Table %#x–%#x, %d of %d bytes change",
    "    1024 bytes, %d colors changed (vs built-in stock)",
    "· Timestamped backups are created for both files before writing",      # 170
    "· Byte-for-byte readback after writing; nothing outside the table region is touched",
    "· Localization / widescreen / HD patches are unaffected",
    "Make sure the game has fully exited (files may be locked). Continue?",
    "Confirm Write",
    "PALETTE.RAW readback verification failed",                             # 175
    "exe table readback verification failed",
    "\n\nFile is locked: fully exit the game (including background processes) and retry.",
    "Write Failed",
    "%s%s\n\nRolled back automatically to the pre-write state. Backups kept:\n%s\n%s",
    "(exe unchanged)",                                                      # 180
    "(palette unchanged)",
    "Done",
    "Bike colors and palette written.\n\nBackups:\n%s\n\n",
    "Launch the game from Steam to see the changes.",
    "Neon Orange",                                                          # 185
    "Bright Yellow",
    "Mint Green",
    "Sky Blue",
    "Royal Blue",
    "Cherry Pink",                                                          # 190
    "Charcoal",
    "Recolor · Slot %02d · %s",
    "Arbitrary RGB recolor  ·  Slot %02d  %s",
    "Each row is a palette entry used by this skin. Select a row → pick a color → apply;",
    'the preview and all 15 cards refresh live. Nothing is written until "Apply to Game" in the main window.',  # 195
    "Live Preview",
    "Selected Color",
    "Colors used by this skin (sorted by pixel count)",
    "Idx",
    "Current",                                                              # 200
    "Pixels",
    "Used by",
    "Strategy",
    "Pick Color…",
    "Apply Color",                                                          # 205
    "Quick Colors",
    "Select a color to begin.",
    "Note: PALETTE.RAW is shared (riders / track / UI). Exclusive entries are rewritten directly;",
    'shared entries are isolated to the closest free entry. "Restore Palette" rolls everything back.',
    "This bike only",                                                       # 210
    "Rewrite directly",
    "%d bikes (all)",
    "Isolate & redirect",
    "%d bikes:%s%s",
    "Free palette entries: %d",                                            # 215
    "Exclusive → rewrite this palette RGB directly; LUT unchanged, shading preserved.",
    "Shared by %d bikes → allocate the closest free entry and redirect this slot's LUT; others unchanged.",
    "#%d  %s  %s  ·  %d px  ·  %s",
    "Nothing Selected",
    "Select a color in the list first.",                                    # 220
    "Recolor Failed",
    "Invalid Format",
    "Enter a 6-digit hex color, e.g. #ff3cc0.",
    "Pick a Bike Color",
    "Startup Failed",                                                       # 225
    "15 color remap tables  ·  Rat 0-4 / Super 5-9 / Sport 10-14  ·  table @ 0x195490",
    "Assign palettes; Apply to Game writes the exe",
    "  Reads and rewrites 3840 bytes at file offset 0x195490 in RoadRash95.exe",
    "  (15 × 256-byte color tables); no other byte is touched.",
    "  Before writing: verifies all 15 table signatures and the file size.",  # 230
    "  After writing: reads the table region back byte-for-byte; a timestamped backup is made first.",
    '  · Steam "Verify integrity" or a game update restores the exe; re-apply afterwards.',
    "Pending: %s   ·   %d / 15 tables differ from built-in stock   ·   writes only %#x–%#x of exe, %d bytes total",
    "The 15 tables in the current exe already match the target.",
    "Will modify %s\n\n",                                                   # 235
    "· Rewrites only table %#x–%#x (%d of %d bytes change)\n",
    "· Only the color tables change; localization / widescreen / HD patches are unaffected\n",
    "· A backup is created automatically before writing\n\n",
    "Make sure the game has fully exited. Continue?",
    "Readback verification failed; restore from the backup",                # 240
    "%s\n\nBackup:\n%s",
    "Bike colors written.\n\nBackup:\n%s\n\nLaunch the game from Steam to see the changes.",
]

assert len(EN) == len(KEYS), "EN count %d != keys %d" % (len(EN), len(KEYS))
ZH_EN = dict(zip(KEYS, EN))

# 这些是文件名 / 内部标识，翻译会改变行为，保持原样
KEEP = {
    "车皮调色台_设置.json", "车皮调色台_错误.log", "自检结果.json",
    "车皮方案.json", ".调色台备份_",
}

PATHBAR_ANCHOR = (
    '        ttk.Button(pathbar, text="兼容性自检", command=self.check_env)'
    '.pack(side="left", padx=(6, 0))\n'
)
PATHBAR_ADD = (
    '        ttk.Button(pathbar, text=("English" if LANG == "zh" else "\\u4e2d\\u6587"),\n'
    '                   width=9, command=self.do_language).pack(side="right", padx=(6, 0))\n'
)

METHOD_ANCHOR = "    def choose_exe(self):\n"
METHOD_ADD = '''    def do_language(self, restart=True):
        """切换界面语言。模块级文本在启动时构建，因此切换后重启一次。"""
        new = "en" if LANG == "zh" else "zh"
        set_language(new)
        if restart:
            if restart_app():
                os._exit(0)
            messagebox.showinfo(
                "Language", "Language saved. Restart the application to apply it.")

'''

SELFTEST_ANCHOR = '    r = {\n        "frozen":'
SELFTEST_ADD = '    r = {\n        "lang": LANG,\n        "frozen":'

I18N_HEAD = '''
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

I18N = '''

I18N_TAIL = '''

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
'''


def inject_widgets(src):
    patches = (
        (PATHBAR_ANCHOR, PATHBAR_ANCHOR + PATHBAR_ADD),   # 原行后追加按钮
        (METHOD_ANCHOR, METHOD_ADD + METHOD_ANCHOR),      # 类内插入回调方法
        (SELFTEST_ANCHOR, SELFTEST_ADD),                  # 自检结果加 lang 字段
    )
    for anchor, replacement in patches:
        assert anchor in src, "锚点缺失: %r" % anchor[:40]
        src = src.replace(anchor, replacement, 1)
    return src


def translate_strings(src):
    """把中文字符串字面量包成 tr(...)。

    关键：Python 的 "a" "b" 隐式拼接会先拼成一整个字符串再参与
    `%` 格式化。因此这里把相邻的 STRING token 视为一组，整组合并成
    一个 tr('拼接结果')，并为该结果动态补一条英文映射 —— 否则
    `("a%d" "b%s") % args` 会被改写成 `tr('a%d') + tr('b%s') % args`，
    格式化作用域就错了。
    """
    lines = src.splitlines(keepends=True)
    toks = list(tokenize.generate_tokens(io.StringIO(src).readline))
    skip = (tokenize.NL, tokenize.NEWLINE, tokenize.COMMENT,
            tokenize.INDENT, tokenize.DEDENT, tokenize.ENCODING,
            tokenize.ENDMARKER)
    meaningful = [t for t in toks if t.type not in skip]

    groups, cur = [], []
    for t in meaningful:
        if t.type == tokenize.STRING:
            cur.append(t)
        else:
            if cur:
                groups.append(cur)
                cur = []
    if cur:
        groups.append(cur)

    edits, count = [], 0
    for group in groups:
        if any(t.string.startswith(('"""', "'''"))
               or t.start[0] != t.end[0] for t in group):
            continue                       # docstring / 多行字符串：保持原样
        try:
            segs = [ast.literal_eval(t.string) for t in group]
        except Exception:
            continue
        if not all(isinstance(s, str) for s in segs):
            continue
        translatable = [s for s in segs
                        if s not in KEEP and s in ZH_EN
                        and re.search(r"[\u4e00-\u9fff]", s)]
        if not translatable:
            continue
        whole = "".join(segs)
        parts = [ZH_EN.get(s, s) for s in segs]
        en = parts[0]
        for nxt in parts[1:]:
            if en and nxt and not en[-1].isspace() and not nxt[0].isspace():
                en += " "
            en += nxt
        ZH_EN[whole] = en
        for n, t in enumerate(group):
            new = "tr(" + repr(whole) + ")" if n == 0 else ""
            edits.append((t.start[0], t.start[1], t.end[1], new))
        count += 1
    for row, c0, c1, new in sorted(edits, reverse=True):
        line = lines[row - 1]
        lines[row - 1] = line[:c0] + new + line[c1:]
    return "".join(lines), count


def polish_layout(src):
    """英文文案普遍更长：给关键控件按语言自适应宽度，避免裁切。"""
    patches = (
        ("text=tr('调色'), width=5,",
         'text=tr(\'调色\'), width=(5 if LANG == "zh" else 9),'),
        ('self.orient_cb = ttk.Combobox(tools2, width=20, state="readonly",',
         'self.orient_cb = ttk.Combobox(tools2, width=(20 if LANG == "zh" else 27), '
         'state="readonly",'),
        ('namebox = ttk.Frame(card, height=34, style="Card.TFrame")',
         'namebox = ttk.Frame(card, height=40, style="Card.TFrame")'),
    )
    for old, new in patches:
        if old in src:                       # 1.0 没有「调色」按钮
            src = src.replace(old, new, 1)
    # 底部：让主按钮先占空间，状态文字后放并允许换行，避免长英文把按钮挤出窗口
    old = ('        ttk.Label(bottom, textvariable=self.diff_var, style="Sub.TLabel")'
           '.pack(side="left")\n'
           '        ttk.Button(bottom, text=tr(\'应用到游戏（自动备份）\'), '
           'style="Go.TButton",\n'
           '                   command=self.apply).pack(side="right")\n')
    new = ('        ttk.Button(bottom, text=tr(\'应用到游戏（自动备份）\'), '
           'style="Go.TButton",\n'
           '                   command=self.apply).pack(side="right")\n'
           '        ttk.Label(bottom, textvariable=self.diff_var, style="Sub.TLabel",\n'
           '                  wraplength=(1060 if LANG == "en" else 1200))'
           '.pack(side="left")\n')
    assert old in src, "底部状态栏锚点缺失"
    return src.replace(old, new, 1)


def inject_i18n(src):
    anchor = 'LOG_PATH = os.path.join(DATA_DIR, "车皮调色台_错误.log")\n'
    assert anchor in src, "LOG_PATH 锚点缺失"
    body = json.dumps(ZH_EN, ensure_ascii=False, indent=4)
    block = I18N_HEAD + body + I18N_TAIL
    return src.replace(anchor, anchor + block, 1)


def build(src_path, dst_path):
    src = open(src_path, encoding="utf-8").read()
    assert "I18N =" not in src, "已经注入过 i18n，请勿重复运行: " + src_path
    src = inject_widgets(src)
    src, n = translate_strings(src)
    src = polish_layout(src)
    src = inject_i18n(src)
    compile(src, dst_path, "exec")          # 语法检查
    open(dst_path, "w", encoding="utf-8").write(src)
    print("%-46s -> %-40s  替换 %3d 处  输出 %d 字符"
          % (os.path.basename(src_path), os.path.basename(dst_path), n, len(src)))


if __name__ == "__main__":
    build(os.path.join(HERE, "_template.py"),
          os.path.join(HERE, "_template_i18n.py"))
    build(os.path.join(HERE, "v1.0_备份", "_template_v1.0.py"),
          os.path.join(HERE, "v1.0_备份", "_template_v1.0_i18n.py"))
