"""渲染服务：页面查询、各类卡片绘制与运行时图片缓存。"""
from __future__ import annotations

import base64
import hashlib
from pathlib import Path
from typing import Any
from urllib.parse import quote

from blhxwiki.models import QueryResult
from blhxwiki.paint.components import (
    generate_equip_card,
    generate_ship_equip_image,
    generate_special_equip_card,
    generate_stage_image,
)
from blhxwiki.paint.drawing import generate_ship_card
from blhxwiki.parser.wiki_parser import SEARCH_URL, build_page_url, parse_page, search_names
from blhxwiki.utils.cache import enforce_cache_limit
from blhxwiki.utils.http_utils import get as http_get, get_bytes
from blhxwiki.utils.naming import asset_key
from blhxwiki.utils.text import original_image_url, pick_direct


class Renderer:
    """把解析结果渲染成文本或图片，并管理运行时缓存。"""

    def __init__(
        self,
        *,
        assets_dir: Path,
        runtime_dir: Path,
        timeout: float,
        max_cache_mb: int,
        names,
        send,
        logger,
    ) -> None:
        self.assets_dir = assets_dir
        self.runtime_dir = runtime_dir
        self.timeout = timeout
        self.max_cache_mb = max_cache_mb
        self.names = names
        self.send = send
        self.logger = logger

    # ------------------------------------------------------------------
    # 页面查询
    # ------------------------------------------------------------------
    async def query_page(
        self,
        keyword: str,
        query_type: str,
        voice_key: str | None = None,
        stream_id: str = "",
    ) -> QueryResult:
        search_url = SEARCH_URL + quote(keyword)
        html = await http_get(search_url, timeout=self.timeout)
        if not html:
            return QueryResult(text="网络连接错误，请重试喵")

        try:
            parsed = parse_page(html, keyword, query_type, voice_key)
        except Exception as exc:  # noqa: BLE001
            return QueryResult(text=f"解析发生错误喵\n{exc}\n可以点击查看原网页：{search_url}")

        if parsed is None:
            return QueryResult(text=f"页面解析有误，暂不支持此种类页面解析~\n可以点击查看原网页：{search_url}")

        if parsed["type"] == "search":
            results = parsed["data"]["results"]
            direct = pick_direct(results, keyword)
            if direct:
                return await self.fetch_and_render(build_page_url(direct), direct, query_type, voice_key, stream_id)

            local = search_names(keyword, self.names.all)
            if local:
                result = await self.fetch_and_render(build_page_url(local[0]), local[0], query_type, voice_key, stream_id)
                if len(local) > 1:
                    extra = "还找到了以下相近词条喵\n" + "\n".join(local[1:7])
                    result.text = f"{result.text}\n{extra}".strip()
                return result
            return QueryResult(text="没有查询到结果呢~\n输入 wiki 可以查看指令列表喵")

        return await self.render(parsed, stream_id)

    async def fetch_and_render(
        self,
        url: str,
        keyword: str,
        query_type: str,
        voice_key: str | None = None,
        stream_id: str = "",
    ) -> QueryResult:
        html = await http_get(url, timeout=self.timeout)
        if not html:
            return QueryResult(text="网络连接错误，请重试喵")
        try:
            parsed = parse_page(html, keyword, query_type, voice_key)
        except Exception as exc:  # noqa: BLE001
            return QueryResult(text=f"解析发生错误喵\n{exc}\n{url}")
        if parsed is None:
            return QueryResult(text=f"页面解析有误，暂不支持此种类页面解析~\n{url}")
        return await self.render(parsed, stream_id)

    async def render(self, parsed: dict[str, Any], stream_id: str = "") -> QueryResult:
        kind, data = parsed["type"], parsed["data"]
        if kind == "ship_attr":
            return await self.ship_card(data)
        if kind == "ship_source":
            return await self.ship_source(data)
        if kind == "images":
            return await self.download_images(data.get("images", []))
        if kind == "voice":
            return await self.voice(data.get("url"), stream_id)
        if kind == "text":
            return QueryResult(text=data.get("text", ""))
        if kind == "ship_equip":
            return await self.ship_equip(data)
        if kind == "local_image":
            return QueryResult(text="立绘大图/皮肤原图需要本地资源包，当前未迁移喵")
        if kind == "equip_attr":
            return await self.equip_card(data)
        if kind == "equip_source":
            return await self.equip_source(data)
        if kind == "special_equip":
            return await self.special_equip_card(data)
        if kind == "rank":
            return await self.download_images(data.get("images", []))
        if kind == "level":
            return await self.stage(data)
        return QueryResult(text="暂不支持此页面类型喵")

    # ------------------------------------------------------------------
    # 各类渲染
    # ------------------------------------------------------------------
    async def ship_card(self, data: dict[str, Any]) -> QueryResult:
        pic_path = await self.cache_ship_art(data.get("name", ""), data.get("pic", ""))
        skills = []
        for skill in data.get("skills", []):
            skill = dict(skill)
            if str(skill.get("pic", "")).startswith("http"):
                icon = await self.cache_skill_icon(skill["pic"])
                skill["pic"] = str(icon) if icon else ""
            skills.append(skill)
        ship = {
            key: data.get(key, "")
            for key in (
                "name", "code", "type", "rarity", "camp", "time",
                "normal_from", "active_from", "file_from", "other_from",
            )
        }
        ship.update(
            {
                "pic": str(pic_path) if pic_path else "",
                "can_upgrade": data.get("can_upgrade", False),
                "attributes": data.get("attributes", {}),
                "skills": skills,
                "equip_detail": data.get("equip_detail", []),
                "assets_dir": str(self.assets_dir),
            }
        )
        image = generate_ship_card(ship)
        return QueryResult(images=[image.getvalue()])

    async def ship_source(self, data: dict[str, Any]) -> QueryResult:
        lines = [data.get("name", ""), f"{data.get('rarity', '')}{data.get('camp', '')}{data.get('type', '')}"]
        if data.get("time"):
            lines.append(f"建造时间：{data['time']}")
        sources = [
            value
            for value in (
                data.get("normal_from"), data.get("active_from"),
                data.get("file_from"), data.get("other_from"),
            )
            if value
        ]
        lines.append("获得途径：\n  " + "\n  ".join(sources) if sources else "获得途径：暂无")
        images = []
        if data.get("pic"):
            image = await get_bytes(data["pic"], timeout=self.timeout)
            if image:
                images.append(image)
        return QueryResult(text="\n".join(lines), images=images)

    async def voice(self, url: str | None, stream_id: str) -> QueryResult:
        """下载语音并按 voice 段发送；宿主不支持时回退链接。"""
        if not url:
            return QueryResult(text="该舰娘没有此语音哦~")
        audio = await get_bytes(url, timeout=self.timeout)
        if not audio:
            return QueryResult(text=f"语音下载失败：{url}")

        segment = {
            "type": "voice",
            "data": "",
            "binary_data_base64": base64.b64encode(audio).decode("ascii"),
        }
        try:
            await self.send.hybrid([segment], stream_id)
            return QueryResult()
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("语音段发送失败: %s", exc)
        return QueryResult(text=f"语音：{url}")

    async def equip_source(self, data: dict[str, Any]) -> QueryResult:
        lines = [
            data.get("name", ""),
            data.get("camp", ""),
            f"整装获取：{data.get('from', '无')}",
            f"设计图获取：{data.get('piece', '无')}",
        ]
        images = []
        if data.get("pic"):
            image = await get_bytes(data["pic"], timeout=self.timeout)
            if image:
                images.append(image)
        return QueryResult(text="\n".join(lines), images=images)

    async def equip_card(self, data: dict[str, Any]) -> QueryResult:
        data = dict(data)
        pic = await self.cache_image(data.get("pic", ""), "equip")
        data["pic"] = str(pic) if pic else ""
        image = generate_equip_card(data, assets_dir=self.assets_dir)
        return QueryResult(images=[image.getvalue()])

    async def special_equip_card(self, data: dict[str, Any]) -> QueryResult:
        data = dict(data)
        pic = await self.cache_image(data.get("pic", ""), "equip")
        data["pic"] = str(pic) if pic else ""
        image = generate_special_equip_card(data, assets_dir=self.assets_dir)
        return QueryResult(images=[image.getvalue()])

    async def ship_equip(self, data: dict[str, Any]) -> QueryResult:
        for column in data.get("equip_lists", []):
            for cell in column:
                cached = [await self.cache_image(url, "equip") for url in cell.get("pics", [])]
                cell["pics"] = [str(path) for path in cached if path]
        for special in data.get("special_equips", []):
            for icon in special.get("list", []):
                path = await self.cache_image(icon.get("url", ""), "equip")
                icon["url"] = str(path) if path else ""
        if not data.get("equip_lists"):
            return QueryResult(text="没有找到配装推荐喵")
        image = generate_ship_equip_image(data, assets_dir=self.assets_dir)
        return QueryResult(images=[image.getvalue()])

    async def stage(self, data: dict[str, Any]) -> QueryResult:
        data = dict(data)
        pic = await self.cache_image(data.get("pic", ""), "stage")
        data["pic"] = str(pic) if pic else ""
        for line in data.get("drop_lines", []):
            for item in line.get("items", []):
                path = await self.cache_image(item.get("pic", ""), "drop")
                item["pic"] = str(path) if path else ""
        image = generate_stage_image(data, assets_dir=self.assets_dir)
        return QueryResult(images=[image.getvalue()])

    async def download_images(self, urls: list[str]) -> QueryResult:
        images = []
        for url in urls[:9]:
            data = await get_bytes(url, timeout=self.timeout)
            if data:
                images.append(data)
        if not images:
            return QueryResult(text="图片下载失败喵")
        return QueryResult(images=images)

    # ------------------------------------------------------------------
    # 缓存
    # ------------------------------------------------------------------
    async def cache_image(self, url: str, subdir: str) -> Path | None:
        """远程图片下载到 runtime_dir/<subdir>；本地路径直接返回。"""
        if not url:
            return None
        if not url.startswith("http"):
            path = Path(url)
            return path if path.exists() else None
        cache_dir = self.runtime_dir / subdir
        cache_dir.mkdir(parents=True, exist_ok=True)
        path = cache_dir / f"{hashlib.md5(url.encode('utf-8')).hexdigest()}.img"
        if path.exists() and path.stat().st_size > 0:
            return path
        data = await get_bytes(original_image_url(url), timeout=self.timeout)
        if not data:
            data = await get_bytes(url, timeout=self.timeout)
        if not data:
            return None
        path.write_bytes(data)
        enforce_cache_limit(self.runtime_dir, self.max_cache_mb)
        return path

    async def cache_ship_art(self, name: str, url: str) -> Path | None:
        if not url:
            return None
        cache_dir = self.runtime_dir / "ship"
        cache_dir.mkdir(parents=True, exist_ok=True)
        suffix = ".jpg" if ".jpg" in url.lower() else ".png"
        path = cache_dir / f"{name}{suffix}"
        if path.exists() and path.stat().st_size > 0:
            return path
        data = await get_bytes(original_image_url(url), timeout=self.timeout)
        if not data:
            data = await get_bytes(url, timeout=self.timeout)
        if not data:
            return None
        path.write_bytes(data)
        enforce_cache_limit(self.runtime_dir, self.max_cache_mb)
        return path

    async def cache_skill_icon(self, url: str) -> Path | None:
        return await self.cache_image(url, "skill")

    def help_image(self, name: str) -> bytes | None:
        path = self.assets_dir / "image" / "help" / name
        return path.read_bytes() if path.exists() else None
