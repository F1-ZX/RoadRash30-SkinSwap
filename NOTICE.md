# Notice / 版权与第三方资料说明

## 1. 游戏与原始资源

**Road Rash** 及其全部原始资源（可执行文件、精灵、调色板、车辆图片、音乐、文本等）的版权归其各自权利人所有。本项目是**非官方**的互操作性 / 个人修改工具，与 Electronic Arts 或任何相关发行方、开发方均无关联，也未获得其授权或认可。

本仓库**不包含**以下文件，也请不要向本仓库提交它们：

- `RoadRash95.exe` 或任何游戏可执行文件、备份 exe
- `IMAGES/BIKES/**` 商店车辆图、游戏内截图素材
- `RR30th_BCFIX.zip` 等第三方补丁包
- `HIBOB.DAT` / `LOBOB.DAT` 精灵图集原件
- 其他项目（如 MultiFix）的完整源码副本

## 2. 仓库内的派生数据

`src/tool_data.json` 与 `v1.0/tool_data.json` 包含下列**从用户自己游戏安装中提取的最小派生数据**，用途仅限「让工具在界面里实时渲染真实车皮预览」与「识别原版配色」：

| 字段 | 大小 | 说明 |
|---|---|---|
| `sprite_b64` | 2160 B | 40×54 车手精灵的 8-bit 灰度索引矩阵（来自社区公开的 15 张预览 BMP，15 张共用同一套） |
| `palette_b64` | 1024 B | `DATA/PALETTE.RAW`，256 × (R,G,B,0) 全局调色板 |
| `stock_luts_b64` | 3840 B | exe 内 15 张原版 LUT |
| `active_b64`（仅 v2.0） | 206 B | HIBOB + LOBOB 全图集出现过的活跃像素索引 |

这些数据是**数值索引 / 颜色值**，不含游戏美术图像的像素内容。它们随工具内嵌，是为了让使用者在**已合法拥有游戏**的前提下修改自己的安装。若你是权利人并认为这些内容不合适，请通过仓库 Issue 联系，我们会及时移除。

## 3. 技术资料与致谢

本项目的逆向结论建立在以下公开资料之上，代码与文档均注明出处：

- **neparij** 在 [DxWnd / SourceForge 讨论串](https://sourceforge.net/p/dxwnd/discussion/general/thread/e080095150/) 发表的 HIBOB.DAT 灰度索引分析、15 张 256 字节 LUT 的发现、`0x0006C758`（1996 年 1.0a 版）地址，以及 15 张 `output_image_N.bmp` 预览图。本项目用这些 BMP 的调色板反推出 LUT，并与 30 周年版逐字节校验（256/256 一致）。
- **Anakin94** 的 `RR30th_BCFIX`：30 周年版专用车皮修复，本项目通过逐字节 diff 确认其修复内容正是「前后各 5 张表互换」。
- **[magoowa/RoadRash30-MultiFix](https://github.com/magoowa/RoadRash30-MultiFix)**：其 `src/hd_renderer.cpp` 注释给出 `15 tables at 0x596a90, indexed by the bike's spec number: 0-4 Rat, 5-9 Super, 10-14 Sport`，以及表区 FNV-1a 期望值 `0x51d083b966bd8657`。本项目只引用了结论与哈希常数，**未复制其源码**。
- **[Road Rash Wiki (Fandom)](https://roadrash.fandom.com/)**：PC 版 Rat Bikes 与 Super Bikes 调色板互换的记载，以及车辆 / 车手列表。
- 工具中 15 个槽位对应的具体车名由本项目维护者在游戏内实测校正。

## 4. 风险提示

工具会修改你本机的游戏文件。虽然它带自动备份与写后校验，仍建议自行保留一份游戏目录备份。作者不对因使用本工具造成的数据丢失负责 —— 详见 [LICENSE](LICENSE)。
