
# ⚓ MaiBot 碧蓝航线 Wiki 插件

**指挥官，wiki 数据已就位。**

舰娘档案、装备配装、关卡掉落、井号榜单、四区服状态——不用切浏览器，在群里一条 `wiki` 就能查完。
还附赠猜老婆小游戏，给港区日常添点乐子。

本插件基于 **MaiBot SDK v2** 与 `PluginConfigBase` 强类型配置，支持 WebUI 热重载。数据实时抓取碧蓝航线 wiki，不维护本地数据库。

[![License](https://img.shields.io/badge/license-AGPL--3.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-3776AB.svg)](https://www.python.org/)
[![MaiBot SDK](https://img.shields.io/badge/MaiBot%20SDK-2.x-00A1D6.svg)](https://docs.mai-mai.org/plugin/)

---

## 🎯 能做什么

| | 模块 | 一句话 |
| :---: | --- | --- |
| 🚢 | 舰娘档案 | 立绘、属性、技能、装备效率、建造时间、获取途径，一张卡片说清 |
| 🔫 | 装备图鉴 | 属性卡、整装/图纸获取、特殊兵装 |
| 🧩 | 配装推荐 | 六列配装图 + 特殊配装区 |
| 🗺️ | 关卡情报 | 地图、敌舰等级、BOSS、掉落表 |
| 🏆 | 井号榜单 | 装备一图榜、觉醒榜、萌新榜等 |
| 📡 | 服务器状态 | 国服 / 日服 / 国际服 / 繁中服，TCP + HTTP 双通道 |
| 📊 | 科技点筛选 | 按舰种、科技分类分页查舰队科技 |
| 🎲 | 猜老婆 | 随机裁切立绘出题，30 秒限时竞猜 |
| 🔤 | 无空格 & 别名 | `wiki拉菲皮肤` 照样懂，内置约 690 条别名 |

---

## 🧭 快速上手

> 三步进港：**放目录 → 重载 → 开聊。**

1. **安装**：把 `MaiBot-blhx-wiki` 放进 MaiBot 的 `plugins/` 下（市场安装或手动解压都行）。
2. **重载**：首次加载会自动生成 `config.toml`，默认配置直接可用。
3. **开聊**：在群里发 `wiki`，帮助菜单会以表格图的形式送到你面前。

> ⚠️ `assets/` 必须随插件一起部署。请直接解压 ZIP，**不要**用会转码中文文件名的安装方式。

**环境要求**

| 项目 | 要求 |
| --- | --- |
| MaiBot 主程序 | `0.10.0+` |
| MaiBot SDK | `2.0.0+` |
| Python | `3.10+` |
| 依赖 | `httpx`、`Pillow`、`beautifulsoup4`、`lxml`（manifest 自动安装） |

---

## 📚 指令手册

所有指令以 `wiki` 开头，大小写不敏感；支持无空格写法与别名（`金坷垃`、`海妈`、`贝爷` 等，可在 `assets/config/aliases.json` 里增删）。

### 🚢 舰娘

| 指令 | 结果 |
| --- | --- |
| `wiki 拉菲` | 属性卡片 |
| `wiki 拉菲 出处` | 获得途径 |
| `wiki 拉菲 皮肤` | 全部皮肤 |
| `wiki 拉菲 大图` | 立绘大图 |
| `wiki 拉菲 皮肤原图` | 皮肤原图 |
| `wiki 拉菲 语音` | 语音类型表（图片） |
| `wiki 拉菲 誓约` | 对应类型的语音 |
| `wiki 拉菲 科技点` | 舰队科技 |
| `wiki 拉菲 配装` | 配装推荐图 |
| `wiki 拉菲 评价` | wiki 评价 |

### 🔫 装备

| 指令 | 结果 |
| --- | --- |
| `wiki 533` | 装备属性卡 |
| `wiki 533 出处` | 整装获取、图纸获取 |

特殊兵装同样支持这两种查询。

### 🗺️ 查询类

| 指令 | 结果 |
| --- | --- |
| `wiki 榜单` | 支持的榜单列表 |
| `wiki 装备一图榜` | 榜单图片 |
| `wiki 2-1` | 关卡地图、BOSS、掉落 |
| `wiki 服务器状态` | 国服维护状态 |
| `wiki 服务器状态 日服` | 指定区服（国服/日服/国际服/繁中服） |
| `wiki 筛选 驱逐 耐久 1` | 舰队科技筛选表（舰种 / 分类 / 页码） |
| `wiki clear` | 清空图片缓存（仅限 `admin_users` 白名单） |

### 🎮 游戏

| 指令 | 结果 |
| --- | --- |
| `猜老婆` | 看图猜舰娘，30 秒超时 |
| `wiki 锉刀` | 彩蛋 |

### 🛠️ 管理（需操作员权限）

| 指令 | 结果 |
| --- | --- |
| `/reply set 指令 回复` | 新增自定义回复 |
| `/reply reset 指令 回复` | 覆盖自定义回复 |
| `/reply delete 指令` | 删除自定义回复 |
| `/reply list` | 查看回复列表 |
| `/wikiconfig 猜老婆 true/false` | 本群猜老婆开关 |
| `/wikiconfig clear` | 清空图片缓存 |

---

## 🔧 配置

配置在 `config.toml` 的 `[plugin]` 段。推荐在 WebUI 里改，保存即热重载；`config_version` 由 Runner 维护，别手碰。

| 字段 | 默认值 | 作用 |
| --- | :---: | --- |
| `enabled` | `true` | 是否启用插件 |
| `request_timeout` | `10.0` | 访问 wiki 的超时（秒） |
| `max_cache_mb` | `500` | 运行时缓存上限（MB），超出后淘汰最旧文件 |
| `admin_users` | `[]` | 敏感命令白名单（QQ 号，可填多个）；`wiki clear` 仅限名单内用户 |
| `enable_guess_wife` | `true` | 是否启用猜老婆 |

---

## 🗂️ 资源与缓存

| 位置 | 内容 | 去向 |
| --- | --- | --- |
| `assets/` | 图标、字体、头像、别名表、帮助图 | 随插件分发 |
| `data_dir` | 名称列表、科技点、群开关、自定义回复 | 自动生成 |
| `runtime_dir` | 立绘、技能图标、装备图 | 可随时清理，按需重建；猜老婆需要先查询过一些舰娘 |

缓存超过上限会自动淘汰最旧文件；也可以发 `wiki clear` 一键清空。

---

## ⚠️ 已知限制

- **清晰度**：立绘和图标来自 wiki 缩略图，放大到卡片尺寸后略糊，属于上游素材限制。
- **页面结构**：wiki 改版会导致解析失效，需要跟进选择器。
- **服务器状态**：依赖官方登录网关，网关无响应时会返回失败提示。

---

## 📜 开源协议

> 本项目以 **AGPL-3.0** 发布，见 [LICENSE](LICENSE)。

它的部分代码参考了 [mirai-blhx-wiki-plugins](https://github.com/rainlodo/blhx-wiki-mirai-plugin) ，与原项目使用相同协议；修改和分发需遵守 AGPL-3.0 条款。

## 💙 致谢

- [mirai-blhx-wiki-plugins](https://github.com/DK09/blhx-wiki-mirai-plugin)：原始功能设计与页面解析思路。
- [碧蓝航线 wiki](https://wiki.biligame.com/blhx)：全部游戏数据来源。

## 📮 反馈

- 问题与建议：[GitHub Issues](https://github.com/senhan1337/MaiBot-blhx-wiki/issues)
- 交流群：QQ 群 `待补充`

---

**愿每一次出击都有好掉落。** ⚓