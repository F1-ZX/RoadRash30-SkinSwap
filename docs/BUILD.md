# 从源码构建 / Build from source

> 普通玩家直接用 [Releases](https://github.com/F1-ZX/RoadRash30-SkinSwap/releases) 里的 EXE 即可，无需 Python。本文给想改代码的开发者。

## 环境

| 依赖 | 用途 | 版本（开发环境） |
|---|---|---|
| Python 3 | 运行 `.pyw`，需带 **tkinter** | 3.11（Windows） |
| PyInstaller | 打包单文件 EXE | 6.x |
| Pillow | 仅测试脚本截图 / 图标生成需要 | 10.x |

程序本体**只用标准库**：`os / sys / json / struct / zlib / base64 / shutil / hashlib / random / tempfile / datetime / tkinter`。Pillow 不是运行依赖。

## 目录

```
src/_template.py               v2.0 主模板（含 __DATA_*__ 占位符与双语字典）
src/tool_data.json             内嵌数据（精灵索引 / 调色板 / 原版 LUT / 活跃索引）
src/车皮调色台.pyw             由上面两者生成的成品，可直接运行
v1.0/_template_v1.0.py         v1.0 主模板
v1.0/tool_data.json            v1.0 内嵌数据（无 active_b64 字段）
v1.0/车皮调色台_v1.0.pyw       v1.0 成品
tools/build_pyw.py             把占位符替换成 base64 数据，生成 .pyw
tools/i18n_build.py            一次性 i18n 注入器（见下）
tools/i18n_keys.json           243 条界面中文字符串，与 i18n_build.py 的 EN 列表一一对应
tools/test_*.py                自测脚本
```

## 生成单文件 pyw

```bash
python tools/build_pyw.py
```

脚本会自动识别仓库布局（`src/` + `v1.0/`）与本地开发布局，产出两个 `.pyw`。它同时做一次 `compile()` 语法检查。

## 打包 EXE

```bash
# v2.0
pyinstaller --onefile --windowed --clean --noconfirm ^
  --name RoadRashSkinStudio --icon src/app.ico ^
  --distpath dist --workpath build --specpath build src/车皮调色台.pyw

# v1.0
pyinstaller --onefile --windowed --clean --noconfirm ^
  --name RoadRashSkinStudio10 --icon v1.0/app.ico ^
  --distpath dist --workpath build10 --specpath build v1.0/车皮调色台_v1.0.pyw
```

把产物改成中文文件名即可（可选）。`--windowed` 保证不弹控制台；`--onefile` 让对方不需要装 Python。

## 双语界面是怎么生成的

仓库里的 `src/_template.py` 与 `v1.0/_template_v1.0.py` **已经带 i18n**，日常改代码直接改它们即可。

`tools/i18n_build.py` 是**一次性注入器**，只在你从一份纯中文模板重新开始时用：

1. 用 `tokenize` 找出所有界面中文字符串字面量，包成 `tr(...)`；
2. 相邻的 `"a" "b"` 隐式拼接会**整组合并**成一个 `tr('拼接结果')` 并自动补英文映射 —— 这样 `("a%d" "b%s") % args` 的格式化作用域不会被破坏；
3. 注入 `LANG`（设置文件优先，否则按系统区域自动选）、`I18N` 字典、`tr()`、`set_language()`、`restart_app()`；
4. 在路径栏加语言切换按钮，点一下写设置并重启一次（模块级常量需按新语言重建）；
5. 给英文较长文本做控件宽度自适应。

注入器有 `assert "I18N =" not in src` 保护，**不要对已注入的模板重复运行**。若确需重跑，先用纯中文原模板覆盖目标文件。

`tools/i18n_keys.json` 共 243 条，与 `i18n_build.py` 里的 `EN` 列表严格一一对应；校验占位符顺序可用：

```bash
python -c "import ast,json,re; ..."
```

## 自测

```bash
python tools/test_gui.py          # 中文模式端到端：临时副本上验证双文件写盘 / 回滚 / 方案存读 / 截图
python tools/test_i18n_gui.py     # 强制英文启动，真窗口 + 界面文本校验 + 中英切换 + 截图
python tools/test_exe_gui.py      # 验证打包版 EXE：真实启动、截图、优雅关闭、设置落点
```

`test_exe_gui.py` 需要指定 EXE 位置（Release 下载后）：

```bash
set RR_EXE=C:\path\to\车皮调色台.exe
python tools/test_exe_gui.py
```

所有写盘测试都在**临时副本**上进行，不会触碰真实游戏 exe / `PALETTE.RAW`。截图输出到 `docs/screenshots/`（仓库布局）或脚本所在目录（开发布局）。

打包版另有一个隐藏诊断入口，不开窗口、只生成 `自检结果.json`：

```bash
车皮调色台.exe --selftest
```
