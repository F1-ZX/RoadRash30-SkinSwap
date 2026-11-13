# -*- coding: utf-8 -*-
"""把模板里的 __DATA_*__ 占位符替换成内嵌数据，产出可单文件运行的 .pyw。"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

FIELDS = {
    "__DATA_SPRITE__": "sprite_b64",
    "__DATA_PALETTE__": "palette_b64",
    "__DATA_STOCK__": "stock_luts_b64",
    "__DATA_ACTIVE__": "active_b64",
}


def build(template, data, out):
    tpl = open(template, encoding="utf-8").read()
    d = json.load(open(data, encoding="utf-8"))
    for ph, key in FIELDS.items():
        if ph in tpl:
            assert key in d, "%s 需要 %s" % (template, key)
            tpl = tpl.replace(ph, d[key])
    assert "__DATA_" not in tpl, "仍有未替换的占位符"
    compile(tpl, out, "exec")
    open(out, "w", encoding="utf-8").write(tpl)
    print("%-42s -> %-38s  %d chars" %
          (os.path.relpath(template, HERE), os.path.relpath(out, HERE), len(tpl)))


if __name__ == "__main__":
    if os.path.isdir(os.path.join(HERE, "..", "src")):
        # GitHub 仓库布局：tools/ 与 src/、v1.0/ 平级
        s = os.path.join(HERE, "..", "src")
        v = os.path.join(HERE, "..", "v1.0")
        build(os.path.join(s, "_template.py"),
              os.path.join(s, "tool_data.json"),
              os.path.join(s, "车皮调色台.pyw"))
        build(os.path.join(v, "_template_v1.0.py"),
              os.path.join(v, "tool_data.json"),
              os.path.join(v, "车皮调色台_v1.0.pyw"))
    else:
        # 本地开发目录布局
        build(os.path.join(HERE, "_template.py"),
              os.path.join(HERE, "tool_data.json"),
              os.path.join(HERE, "车皮调色台.pyw"))
        v1 = os.path.join(HERE, "发布_v1.0")
        os.makedirs(v1, exist_ok=True)
        build(os.path.join(HERE, "v1.0_备份", "_template_v1.0_i18n.py"),
              os.path.join(HERE, "v1.0_备份", "tool_data.json"),
              os.path.join(v1, "车皮调色台_v1.0.pyw"))
