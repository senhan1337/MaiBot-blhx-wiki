"""MaiBot 碧蓝航线 wiki 插件入口。

插件类只负责生命周期、配置与组件注册；命令分发、渲染和具体功能分别位于
``commands``、``paint.renderer`` 与 ``features`` 子包。
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

# Runner 可能按文件路径加载 plugin.py；把 src/ 加入 sys.path 以导入 blhxwiki 包。
_PLUGIN_DIR = Path(__file__).resolve().parent
_SRC_DIR = _PLUGIN_DIR / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from maibot_sdk import (
    CONFIG_RELOAD_SCOPE_SELF,
    Command,
    Field,
    HookHandler,
    MaiBotPlugin,
    PluginConfigBase,
    Tool,
)
from maibot_sdk.types import HookMode, ToolParameterInfo, ToolParamType

from blhxwiki import commands
from blhxwiki.config.replies import Replies
from blhxwiki.config.settings import Settings
from blhxwiki.data.name_list import NameList, create_background_task
from blhxwiki.data.tech_data import TechPoints, refresh_in_background as refresh_tech
from blhxwiki.features import quiz
from blhxwiki.paint.drawing import AssetLoader
from blhxwiki.paint.renderer import Renderer
from blhxwiki.utils.http_utils import http_client
from blhxwiki.utils.server_state import close as close_server_state
from blhxwiki.utils.text import load_aliases, load_index


class PluginSectionConfig(PluginConfigBase):
    """插件基础配置（对应 config.toml 的 [plugin] 段）。"""

    __ui_label__ = "插件"

    enabled: bool = Field(default=True, description="是否启用插件")
    config_version: str = Field(default="1.0.0", description="配置版本")
    request_timeout: float = Field(default=10.0, description="访问 wiki 的超时时间（秒）")
    max_cache_mb: int = Field(default=500, description="运行时缓存上限（MB），超过后删除最旧文件")
    admin_users: list[str] = Field(default_factory=list, description="敏感命令白名单（QQ 号，可填多个），如 wiki clear；留空则无人可用")
    enable_guess_wife: bool = Field(default=True, description="是否启用猜老婆小游戏")


class BlhxWikiConfig(PluginConfigBase):
    """碧蓝航线 wiki 插件配置。"""

    plugin: PluginSectionConfig = Field(default_factory=PluginSectionConfig)


class BlhxWikiMaiBotPlugin(MaiBotPlugin):
    """碧蓝航线 wiki 查询插件。"""

    config_model = BlhxWikiConfig

    async def on_load(self) -> None:
        data_dir = Path(self.ctx.paths.data_dir)
        self.settings = Settings(data_dir)
        self.replies = Replies(data_dir)
        self.names = NameList(data_dir)
        self.tech = TechPoints(data_dir)
        self.quizzes: dict[str, quiz.Quiz] = {}
        self.assets_dir = _PLUGIN_DIR / "assets"
        self.user_aliases = load_aliases(self.assets_dir / "config" / "aliases.json")
        self.renderer = Renderer(
            assets_dir=self.assets_dir,
            runtime_dir=Path(self.ctx.paths.runtime_dir),
            timeout=self.config.plugin.request_timeout,
            max_cache_mb=self.config.plugin.max_cache_mb,
            names=self.names,
            send=self.ctx.send,
            logger=self.ctx.logger,
        )

        try:
            font = AssetLoader(self.assets_dir).font(20)
            self.ctx.logger.info("blhx_wiki 字体: %s", getattr(font, "path", type(font).__name__))
        except Exception as exc:  # noqa: BLE001
            self.ctx.logger.warning("blhx_wiki 字体加载失败: %s", exc)

        self._names_task = create_background_task(self.names, self.ctx.logger)
        self._tech_task = asyncio.create_task(refresh_tech(self.tech, self.ctx.logger))
        self.ctx.logger.info(
            "碧蓝航线 wiki MaiBot 插件已加载（assets=%s，名称缓存=%d）",
            self.assets_dir,
            len(self.names.all),
        )

    async def on_unload(self) -> None:
        for task in (self._names_task, self._tech_task):
            if task and not task.done():
                task.cancel()
        await http_client.aclose()
        await close_server_state()
        self.ctx.logger.info("碧蓝航线 wiki MaiBot 插件已卸载")

    async def on_config_update(self, scope: str, config_data: dict[str, Any], version: str) -> None:
        if scope == CONFIG_RELOAD_SCOPE_SELF:
            self.renderer.timeout = self.config.plugin.request_timeout
            self.renderer.max_cache_mb = self.config.plugin.max_cache_mb
            self.ctx.logger.info("碧蓝航线 wiki 插件配置已更新: version=%s", version)

    # ------------------------------------------------------------------
    # LLM Tool
    # ------------------------------------------------------------------
    @Tool(
        "blhx_wiki_query",
        brief_description="查询碧蓝航线 wiki 的舰船、装备、榜单、服务器状态等信息",
        detailed_description=(
            "根据关键词查询碧蓝航线 wiki 信息。keyword 可为舰船名、装备名、榜单名、服务器状态；"
            "query_type 可为 属性、出处、皮肤、大图、皮肤原图、语音、科技点、配装、评价、装备、榜单，"
            "留空表示属性。"
        ),
        parameters=[
            ToolParameterInfo(
                name="keyword",
                param_type=ToolParamType.STRING,
                description="查询关键词，例如：拉菲、533、装备一图榜、服务器状态",
                required=True,
            ),
            ToolParameterInfo(
                name="query_type",
                param_type=ToolParamType.STRING,
                description="查询类型，留空表示属性",
                required=False,
                default="",
            ),
        ],
    )
    async def query_tool(self, keyword: str, query_type: str = "", **kwargs) -> dict:
        return await commands.query_tool(self, keyword, query_type, **kwargs)

    # ------------------------------------------------------------------
    # Command / Hook
    # ------------------------------------------------------------------
    @Command("blhx_wiki", pattern=r"(?i)^wiki(?P<args>.*)$")
    async def handle_wiki_command(self, **kwargs) -> tuple:
        return await commands.handle_wiki(self, **kwargs)

    @Command("blhx_guess_wife", pattern=r"^猜老婆$")
    async def handle_guess_wife_command(self, **kwargs) -> tuple:
        return await commands.handle_guess_wife(self, **kwargs)

    @HookHandler("chat.receive.before_process", mode=HookMode.BLOCKING)
    async def handle_quiz_answer(self, **kwargs):
        return await commands.handle_quiz_answer(self, **kwargs)

    @Command(
        "blhx_reply",
        pattern=r"(?i)^/reply\s+(?P<action>set|reset|delete|list)(?:\s+(?P<command>\S+))?(?:\s+(?P<content>.+))?$",
        permission="operator",
    )
    async def handle_reply_command(self, **kwargs) -> tuple:
        return await commands.handle_reply(self, **kwargs)

    @Command(
        "blhx_config",
        pattern=r"(?i)^/wikiconfig\s+(?P<action>猜老婆|clear)(?:\s+(?P<value>true|false))?$",
        permission="operator",
    )
    async def handle_config_command(self, **kwargs) -> tuple:
        return await commands.handle_config(self, **kwargs)


# MaiBot 要求的插件工厂函数。
def create_plugin():
    return BlhxWikiMaiBotPlugin()
