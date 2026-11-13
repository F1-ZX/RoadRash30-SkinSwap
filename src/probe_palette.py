"""只读诊断：确认 DATA/PALETTE.RAW 是否被游戏进程真实加载。
流程：临时写入 3 个独特颜色 -> 启动游戏 -> 扫描进程内存 -> 终止 -> 原样还原。
"""
import os, sys, time, shutil, hashlib, ctypes, subprocess
from ctypes import wintypes

G = r"D:\SteamLibrary\steamapps\common\RoadRash"
EXE = os.path.join(G, "RoadRash95.exe")
PAL = os.path.join(G, "DATA", "PALETTE.RAW")
BAK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "probe_palette_backup.raw")

SIG = bytes([0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC, 0xDE, 0xF0, 0x21])
SLOTS = [2, 3, 4]

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
PROCESS_TERMINATE = 0x0001
MEM_COMMIT = 0x1000
PAGE_READABLE = (0x02, 0x04, 0x20, 0x40)  # READONLY / READWRITE / EXECUTE_READ / EXECUTE_READWRITE


class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_void_p),
                ("AllocationBase", ctypes.c_void_p),
                ("AllocationProtect", wintypes.DWORD),
                ("RegionSize", ctypes.c_size_t),
                ("State", wintypes.DWORD),
                ("Protect", wintypes.DWORD),
                ("Type", wintypes.DWORD)]


def scan(pid, needles):
    h = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    if not h:
        return None, "OpenProcess 失败 %d" % ctypes.get_last_error()
    kernel32.VirtualQueryEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p,
                                        ctypes.POINTER(MEMORY_BASIC_INFORMATION), ctypes.c_size_t]
    kernel32.ReadProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                           ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
    addr = 0
    mbi = MEMORY_BASIC_INFORMATION()
    found = {}
    total = 0
    while addr < 0x80000000:
        r = kernel32.VirtualQueryEx(h, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi))
        if not r:
            break
        size = mbi.RegionSize or 0x1000
        if (mbi.State == MEM_COMMIT and (mbi.Protect & 0xFF) in PAGE_READABLE
                and 0 < size <= 64 * 1024 * 1024):
            buf = ctypes.create_string_buffer(size)
            got = ctypes.c_size_t(0)
            if kernel32.ReadProcessMemory(h, ctypes.c_void_p(mbi.BaseAddress or addr),
                                          buf, size, ctypes.byref(got)):
                data = buf.raw[:got.value]
                total += len(data)
                for label, nd in needles.items():
                    if label in found:
                        continue
                    i = data.find(nd)
                    if i >= 0:
                        found[label] = ((mbi.BaseAddress or addr) + i,
                                        data[max(0, i - 8):i + len(nd) + 8].hex(" "))
        addr = (mbi.BaseAddress or addr) + size
    kernel32.CloseHandle(h)
    return (found, total), None


def main():
    orig = open(PAL, "rb").read()
    assert len(orig) == 1024
    with open(BAK, "wb") as f:
        f.write(orig)
    print("原 PALETTE.RAW md5:", hashlib.md5(orig).hexdigest())

    patched = bytearray(orig)
    for n, i in enumerate(SLOTS):
        patched[i * 4:i * 4 + 3] = SIG[n * 3:n * 3 + 3]
    # 内存中可能是 RGBA 原样，也可能是 3 字节 RGB 紧凑排列，或 uint32 带 alpha
    needles = {
        "RGBA 原样(3项)": bytes(patched[8:20]),
        "签名前3字节": SIG[:3],
        "签名中3字节": SIG[3:6],
        "RGBA 带FF alpha": SIG[:3] + b"\xff" + SIG[3:6] + b"\xff",
        "原始调色板 RGBA": orig[8:20],
    }
    proc = None
    try:
        with open(PAL, "wb") as f:
            f.write(patched)
        print("已临时写入 3 个探针颜色 (idx 2/3/4)")
        try:
            proc = subprocess.Popen([EXE], cwd=G, close_fds=True,
                                    creationflags=0x00000008)  # DETACHED_PROCESS
        except Exception as e:
            print("启动游戏失败:", e)
            return 2
        print("游戏 pid", proc.pid, "等待加载…")
        res = None
        for t in range(10):
            time.sleep(1.0)
            if proc.poll() is not None:
                print("游戏在 %ds 时退出，exit=%s" % (t + 1, proc.returncode))
                break
            res, err = scan(proc.pid, needles)
            if err:
                print("扫描异常:", err)
            elif res and any(k.startswith("签名") or k == "RGBA 原样(3项)" for k in res[0]):
                print("在第 %ds 命中探针颜色" % (t + 1))
                break
        if res:
            found, total = res
            print("扫描内存 %.1f MB" % (total / 1024 / 1024))
            print("命中项:")
            for k in needles:
                print("  %-20s %s" % (k, str(found.get(k, "未命中"))[:160]))
            print()
            hit = any(k in found for k in ("RGBA 原样(3项)", "签名前3字节",
                                            "RGBA 带FF alpha"))
            print("结论:", "PALETTE.RAW 已被游戏加载并生效" if hit
                  else "未在内存中发现探针颜色，需人工画面复核")
        return 0
    finally:
        if proc and proc.poll() is None:
            h = kernel32.OpenProcess(PROCESS_TERMINATE | 0x00100000, False, proc.pid)
            if h:
                kernel32.TerminateProcess(h, 0)
                kernel32.WaitForSingleObject(h, 5000)
                kernel32.CloseHandle(h)
            try:
                proc.wait(timeout=5)
            except Exception:
                pass
            print("已终止本次启动的游戏进程")
        for attempt in range(15):
            try:
                with open(PAL, "wb") as f:
                    f.write(orig)
                break
            except PermissionError:
                time.sleep(0.7)
        now = open(PAL, "rb").read()
        print("PALETTE.RAW 已还原:", now == orig,
              "md5", hashlib.md5(now).hexdigest())


if __name__ == "__main__":
    sys.exit(main())
