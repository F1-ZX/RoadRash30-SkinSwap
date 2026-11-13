#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Road Rash 30th Anniversary Edition - 车皮/车手配色表修复

原理:
  30 周年版 RoadRash95.exe 的 .data 段内, 文件偏移 0x195491 处有一张
  80 组 x 32 字节 = 2560 字节的配色重映射表 (RVA 0x196A91, VA 0x596A91)。
  PC 移植时这张表的前 40 组与后 40 组整体错位, 导致 Rat Bike / Super Bike
  等车辆与车手皮肤颜色错乱。修复方式就是把前后两半 (各 1280 字节) 对调,
  与 SourceForge 上 Anakin94 发布的 RR30th_BCFIX 完全一致 (仅 1712 字节变化,
  因为两半中存在相同字节)。

  注意: 1996 年 1.0a 版的 0x0006C758 / 15 x 256 字节 LUT 不适用于本版本,
  30 周年版是重新编译的 PE, 那个地址是 .text 代码。

用法:
  python apply_bike_color_fix.py --check          仅检查状态
  python apply_bike_color_fix.py --apply          应用修复 (自动备份)
  python apply_bike_color_fix.py --apply "路径"    指定 exe 路径

Steam 校验文件或更新游戏后若 exe 被还原, 重新执行 --apply 即可。
汉化补丁 / HD 分辨率补丁不在这块区域, 修复不会破坏它们。
"""

import sys
import os
import shutil
import hashlib

DEFAULT_EXE = r"D:\SteamLibrary\steamapps\common\RoadRash\RoadRash95.exe"

TABLE_OFFSET = 0x195491
GROUP_SIZE = 32
GROUP_COUNT = 80
HALF = (GROUP_SIZE * GROUP_COUNT) // 2  # 1280
SIZE = HALF * 2                         # 2560

# 未修复 / 已修复时第一组的开头 8 字节, 用于识别状态并防止重复执行
BROKEN_HEAD = bytes.fromhex("01 50 10 52 52 b4 38 2a")
FIXED_HEAD = bytes.fromhex("01 86 8a 84 84 b4 38 2a")


def check(path):
    data = open(path, "rb").read()
    table = data[TABLE_OFFSET:TABLE_OFFSET + SIZE]
    if len(table) != SIZE:
        return "未知", "文件过短或版本不符", data
    if table.startswith(FIXED_HEAD):
        return "已修复", "", data
    if table.startswith(BROKEN_HEAD):
        return "未修复", "", data
    return "未知", "表头特征不匹配, 可能是其它版本的 exe, 已拒绝修改", data


def apply(path, do_apply=True):
    if not os.path.isfile(path):
        print("找不到文件:", path)
        return 2
    state, reason, data = check(path)
    print("目标:", path)
    print("大小:", len(data), "MD5:", hashlib.md5(data).hexdigest())
    print("状态:", state, reason)

    if state == "已修复":
        print("无需操作。重复执行不会把修复反转回去。")
        return 0
    if state != "未修复":
        print("已中止, 未写入任何内容。")
        return 1
    if not do_apply:
        return 0

    table = data[TABLE_OFFSET:TABLE_OFFSET + SIZE]
    fixed_table = table[HALF:] + table[:HALF]
    new_data = data[:TABLE_OFFSET] + fixed_table + data[TABLE_OFFSET + SIZE:]

    backup = path + ".车皮修复前备份"
    if not os.path.exists(backup):
        shutil.copy2(path, backup)
        print("已备份:", backup)
    else:
        print("备份已存在, 跳过:", backup)

    with open(path, "r+b") as fp:
        fp.seek(TABLE_OFFSET)
        fp.write(fixed_table)
        fp.flush()
        os.fsync(fp.fileno())

    result = open(path, "rb").read()
    changed = sum(1 for i in range(len(data)) if data[i] != result[i])
    assert len(result) == len(data)
    assert result[TABLE_OFFSET:TABLE_OFFSET + SIZE] == fixed_table
    assert all(data[i] == result[i] for i in range(len(data))
               if not (TABLE_OFFSET <= i < TABLE_OFFSET + SIZE))
    print("修复完成, 改写字节数:", changed)
    print("新 MD5:", hashlib.md5(result).hexdigest())
    print("改动严格限制在配色表区域:", True)
    return 0


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    mode_apply = "--apply" in sys.argv
    mode_check = "--check" in sys.argv
    if not mode_apply and not mode_check:
        print(__doc__)
        sys.exit(0)
    exe = args[0] if args else DEFAULT_EXE
    sys.exit(apply(exe, do_apply=mode_apply))
