# ⚓ MaiBot 碧蓝航线 Wiki 插件 (MaiBot-blhx-wiki)

## **指挥官，wiki 数据已就位**

> **把港区百科装进群聊。**
> 舰娘档案 · 装备配装 · 关卡掉落 · 井号榜单 · 四区服监控 · 猜老婆

基于 MaiBot SDK v2 开发的碧蓝航线 Wiki 查询插件，移植自原 Mirai 平台经典插件 [blhx-wiki-mirai-plugin](https://github.com/rainlodo/blhx-wiki-mirai-plugin)。
数据实时拉取自 [碧蓝航线 biligame wiki](https://wiki.biligame.com/blhx)，由本地 Pillow 引擎动态排版绘制。除常规指令外，同时注册了 LLM Tool（`blhx_wiki_query`），支持 Agent 在会话中自主调度查询。

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB.svg)](https://www.python.org/)
[![MaiBot SDK](https://img.shields.io/badge/MaiBot%20SDK-2.x-00A1D6.svg)](https://docs.maibot.chat/plugin/)
[![Data Source](https://img.shields.io/badge/Data-Biligame%20Wiki-FB7299.svg)](https://wiki.biligame.com/blhx)

---

## 一、功能特性

- **舰娘全景档案**：基础属性卡片、打捞与建造出处、换装皮肤立绘、台词语音表、舰队科技点、配装推荐与综合评价。
- **装备与特殊兵装**：装备属性卡、整装与设计图获取途径、专属及通用特殊兵装解析。
- **关卡与掉落情报**：主线关卡地图、敌舰编队等级、BOSS 信息与掉落清单直观呈现。
- **井号系列榜单**：装备一图榜、觉醒榜、萌新榜、研发榜、打捞表等高频参考榜单。
- **四区服运行监控**：TCP Protobuf + HTTP JSON 双通道监测国服、日服、国际服、繁中服维护与在线状态。
- **科技点定向筛选**：支持按舰种与属性快速检索全港区科技点加成。
- **群聊娱乐互动**：猜老婆立绘裁剪限时抢答、萨拉托加彩蛋。
- **分词与别名系统**：内置约 690 条别名与俗称，支持自然连写（如 `wiki拉菲皮肤`）。
- **Agent Tool 支持**：注册 `blhx_wiki_query` 工具，大模型对话中可按需自主触发，图片直发群聊，不额外消耗模型 Token。

---

## 二、快速上手

### 环境需求

| 项目 | 最低要求 | 说明 |
|---|---|---|
| MaiBot 主程序 | `0.10.0+` | 宿主框架 |
| MaiBot SDK | `2.0.0+` | Python 插件 SDK 2.x |
| Python 环境 | `3.10+` | 运行环境 |
| 依赖组件 | `httpx`、`Pillow`、`beautifulsoup4`、`lxml` | 插件安装时自动解析 |

### 安装方式

- **市场一键安装**：在 MaiBot WebUI 插件市场中搜索 `碧蓝航线 wiki` 。
- **手动离线安装**：下载 Release 发布的 ZIP 压缩包，解压至 MaiBot 插件目录或在 WebUI 页面直接上传导入。

---

## 三、指令手册

> **输入小贴士**：
>
> - 所有指令以 `wiki` 开头，大小写不敏感。输入一级指令即可呼出菜单面板
> - 支持自动分词与连写，例如 `wiki拉菲`、`wiki 拉菲 皮肤`、`wiki拉菲配装` 效果相同。
> - 内置常见俗称与别名（如 `海妈` → 海伦娜、`贝爷` → 贝尔法斯特、`金坷垃` → 圣地亚哥、`花园` → 新泽西等）。

### 1. 舰娘档案

| 指令格式 | 说明 | 示例 |
|---|---|---|
| `wiki [舰娘名]` | 属性卡片（基础数值 / 技能 / 装备效率） | `wiki 拉菲` / `wiki 金坷垃` |
| `wiki [舰娘名] 出处` | 建造时间、掉落关卡与获取途径 | `wiki 企业 出处` |
| `wiki [舰娘名] 皮肤` | 换装皮肤列表与展示立绘 | `wiki 柴郡 皮肤` |
| `wiki [舰娘名] 语音` | 舰娘语音分类索引图 | `wiki 独角兽 语音` |
| `wiki [舰娘名] [语音类型]` | 试听并查看指定台词（如誓约 / 旗舰开战 / 获取台词） | `wiki 拉菲 誓约` |
| `wiki [舰娘名] 科技点` | 舰船提供的舰队科技属性 | `wiki 俾斯麦 科技点` |
| `wiki [舰娘名] 配装` | 推荐装备搭配图 | `wiki 厌战 配装` |
| `wiki [舰娘名] 评价` | Wiki 综合性能简评与攻略建议 | `wiki 埃吉尔 评价` |

### 2. 装备与兵装

| 指令格式 | 说明 | 示例 |
|---|---|---|
| `wiki [装备名]` | 装备属性卡（射程 / 弹种 / 散布等） | `wiki 533` / `wiki 四联40mm博福斯对空机炮` |
| `wiki [装备名] 出处` | 成品与设计图纸打捞出处 | `wiki 533 出处` |
| `wiki [特殊兵装名]` | 特殊兵装属性与技能强化效果 | `wiki 驭风之翼` |

### 3. 榜单与关卡

| 指令格式 | 说明 | 示例 |
|---|---|---|
| `wiki 榜单` | 查看当前支持查询的榜单清单 | `wiki 榜单` |
| `wiki [榜单名]` | 获取对应榜单完整图片 | `wiki 装备一图榜` / `wiki 觉醒榜` / `wiki 萌新榜` |
| `wiki [关卡号]` | 关卡地图、敌舰配置与掉落物 | `wiki 3-4` / `wiki 12-4` |

### 4. 工具与状态

| 指令格式 | 说明 | 示例 |
|---|---|---|
| `wiki 服务器状态 [区服]` | 区服维护与心跳监测（可选：国服 / 日服 / 国际服 / 繁中服，默认国服） | `wiki 服务器状态` / `wiki 服务器状态 日服` |
| `wiki 筛选 [舰种] [属性] [页码]` | 舰队科技加成筛选检索 | `wiki 筛选 驱逐 耐久 1` |

### 5. 群聊互动

| 指令格式 | 说明 |
|---|---|
| `wiki 猜老婆` | 随机裁切立绘局部发起竞猜 |

### 6. 管理指令（需 `admin_users` 白名单）

| 指令格式 | 说明 |
|---|---|
| `wiki 猜老婆 true/false` | 控制本群猜老婆功能开关 |
| `wiki clear` | 清空运行时图片缓存 |

---

## 四、配置说明

配置位于 `config.toml` 的 `[plugin]` 段。推荐直接在 MaiBot WebUI 插件设置页面修改，保存即热重载生效：

```toml
[plugin]
enabled = true              # 是否启用本插件
request_timeout = 10.0      # 访问 Wiki 的请求超时时间（秒）
max_cache_mb = 500          # 运行期图片缓存上限（MB），超出自动按修改时间删最旧文件
admin_users = ["12345678"]  # 管理员 QQ 白名单，仅名单内用户可执行 wiki clear 等敏感操作
enable_guess_wife = true    # 全局猜老婆功能开关
```

---

## 五、资源与缓存结构

| 目录 / 位置 | 类型 | 说明 |
|---|---|---|
| `assets/` | 静态资产 | 随插件发布的预设图标、字体、帮助说明图与默认别名表，**请勿删除** |
| `data_dir` | 持久化数据 | 存放群独立开关（`settings.json`）、名称缓存与科技点数据 |
| `runtime_dir` | 运行期缓存 | 动态下载的立绘、装备小图；受 `max_cache_mb` 控制，可随时清空 |

---

## 六、注意事项与已知说明

1. **立绘大图 / 皮肤原图**：高精度原画体积较大，依赖客户端解包资源库，目前该功能处于规划中，查询会返回提示。
2. **素材清晰度**：部分装备图标与技能小图来自 biligame wiki 原始缩略图，在绘制高清大卡片时可能存在拉伸锯齿，受限于上游图源。
3. **Wiki 页面结构**：插件基于 biligame wiki 页面实时解析，若 wiki 排版或 DOM 结构发生重大变动，可能会影响解析结果，欢迎提交 Issue 反馈。
4. **服务器状态探测**：状态检测依赖官方登录网关心跳，若探测失败通常为本地网络连通性异常或网关接口波动。

---

## 七、开源协议与致谢

- **许可协议**：本项目基于 [AGPL-3.0](LICENSE) 协议发布。
- **项目致谢**：
  - [DK09/blhx-wiki-mirai-plugin](https://github.com/DK09/blhx-wiki-mirai-plugin)：原始项目，本插件继承其架构设计、解析流程与数据模型。
  - [rainlodo/blhx-wiki-mirai-plugin](https://github.com/rainlodo/blhx-wiki-mirai-plugin)：后续维护分支（bug 修复与功能更新），本项目参照的实现来源。
  - [碧蓝航线 biligame wiki](https://wiki.biligame.com/blhx)：感谢 Wiki 攻略组与全体玩家维护的公开数据源。

---

## 八、反馈交流

- **问题与建议**：[GitHub Issues](https://github.com/senhan1337/MaiBot-blhx-wiki/issues)
- **交流 QQ 群**：`待补充`
