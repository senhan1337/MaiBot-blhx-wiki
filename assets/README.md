# 插件资源

插件固定资源，约 32M，随插件一起分发。

| 路径 | 内容 |
|---|---|
| `fonts/SourceHanSans.ttf` | 绘制字体 |
| `config/active_pool.json` | 活动卡池配置 |
| `config/aliases.json` | 别名表（别名 → 正式名称，可自行增删） |
| `config/head_index.json` | 头像文件名索引（hex → 中文名，用于猜老婆选项） |
| `image/help/` | 帮助菜单与语音类型表格图 |
| `image/emoji/` | 彩蛋图 |
| `image/icon/head/` | 舰娘头像（大建、猜老婆） |
| `image/icon/rarity/` | 稀有度卡片背景 |
| `image/icon/camp/` | 阵营图标 |
| `image/icon/ship/` | 舰种图标、属性图标、绘制背景 |
| `image/icon/equip/` | 装备等级/T 序号/适用舰种图标 |

文件名编码：中文名资源统一转成 UTF-8 hex（如 `拉菲.png` → `e68b89e88f9.png`），避免跨平台部署时文件名乱码；代码用同样的规则查找，中文名反查通过 `config/head_index.json`。

立绘、技能图标、装备图不在此目录，运行时从 wiki 按需下载到 `runtime_dir` 缓存，可随时清理。

代码通过 `Path(__file__).parent / "assets"` 读取本目录，随插件分发即可，无需额外配置。
