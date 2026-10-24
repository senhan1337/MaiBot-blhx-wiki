"""服务器状态查询：TCP protobuf + HTTP JSON 双通道，8 秒缓存。

"""
from __future__ import annotations

import asyncio
import json
import socket
import time
from dataclasses import dataclass

import httpx

MSG_REQUEST = 10018
MSG_RESPONSE = 10019
TIMEOUT = 8.0
CACHE_TTL = 8.0

REGION_NAMES = {"国服": "cn", "日服": "jp", "国际服": "en", "繁中服": "tw"}

# (kind, host, port, url)
REGIONS: dict[str, list[tuple[str, str | None, int, str | None]]] = {
    "cn": [
        ("tcp", "118.178.152.242", 80, None),
        ("http", None, 0, "http://203.107.54.122/?cmd=load_server?"),
        ("http", None, 0, "http://203.107.54.70/?cmd=load_server?"),
    ],
    "jp": [("tcp", "blhxjploginapi.azurlane.jp", 80, None)],
    "en": [("tcp", "blhxusgate.yo-star.com", 80, None)],
    "tw": [("tcp", "prod-all-login.azurlane.tw", 10080, None)],
}


@dataclass(slots=True)
class ServerState:
    name: str
    state: int
    sort: int = 0


_cache: dict[str, tuple[float, list[ServerState]]] = {}
_lock = asyncio.Lock()
_http = httpx.AsyncClient(timeout=TIMEOUT)


async def get_server_states(region: str) -> list[ServerState]:
    """查询一个区服的服务器列表；全部端点失败返回空列表。"""
    async with _lock:
        cached = _cache.get(region)
        if cached and time.monotonic() - cached[0] < CACHE_TTL:
            return cached[1]

    endpoints = REGIONS.get(region, [])
    results = await asyncio.gather(
        *(_query_endpoint(endpoint) for endpoint in endpoints), return_exceptions=True
    )
    servers: list[ServerState] = []
    for result in results:
        if isinstance(result, list):
            servers.extend(result)
    servers.sort(key=lambda item: item.sort)

    async with _lock:
        _cache[region] = (time.monotonic(), servers)
    return servers


async def _query_endpoint(endpoint: tuple[str, str | None, int, str | None]) -> list[ServerState]:
    kind, host, port, url = endpoint
    try:
        if kind == "http":
            return await _query_http(url or "")
        return await asyncio.to_thread(_query_tcp, host or "", port)
    except Exception:
        return []


async def _query_http(url: str) -> list[ServerState]:
    response = await _http.get(url)
    response.raise_for_status()
    payload = json.loads(response.text)
    return [
        ServerState(
            name=str(item.get("name", "")),
            state=int(item.get("state", 0)),
            sort=int(item.get("sort", 0)),
        )
        for item in payload
    ]


def _query_tcp(host: str, port: int) -> list[ServerState]:
    with socket.create_connection((host, port), timeout=TIMEOUT) as sock:
        sock.settimeout(TIMEOUT)
        sock.sendall(_build_packet(MSG_REQUEST, _varint_field(1, 0)))
        header = _recv_exact(sock, 2)
        remaining = (header[0] << 8) | header[1]
        rest = _recv_exact(sock, remaining)
        full = header + rest
        msg_id = (full[3] << 8) | full[4]
        if msg_id != MSG_RESPONSE:
            raise ValueError(f"unexpected msg_id {msg_id}")
        return _decode_server_list(full[7: 7 + remaining - 5])


def _recv_exact(sock: socket.socket, size: int) -> bytes:
    buffer = b""
    while len(buffer) < size:
        chunk = sock.recv(size - len(buffer))
        if not chunk:
            raise ConnectionError("connection closed")
        buffer += chunk
    return buffer


def _build_packet(msg_id: int, body: bytes) -> bytes:
    remaining = 5 + len(body)
    return bytes(
        [
            (remaining >> 8) & 0xFF,
            remaining & 0xFF,
            0,
            (msg_id >> 8) & 0xFF,
            msg_id & 0xFF,
            0,
            0,
        ]
    ) + body


def _encode_varint(value: int) -> bytes:
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def _varint_field(field: int, value: int) -> bytes:
    return _encode_varint(field << 3) + _encode_varint(value)


def _read_varint(data: bytes, offset: int) -> tuple[int, int]:
    result = 0
    shift = 0
    index = offset
    while True:
        if index >= len(data):
            raise ValueError("truncated varint")
        byte = data[index]
        result |= (byte & 0x7F) << shift
        shift += 7
        index += 1
        if not byte & 0x80:
            return result, index


def _decode_fields(data: bytes) -> dict[int, list[tuple[int, int, bytes]]]:
    fields: dict[int, list[tuple[int, int, bytes]]] = {}
    index = 0
    while index < len(data):
        tag, index = _read_varint(data, index)
        field, wire = tag >> 3, tag & 7
        if wire == 0:
            value, index = _read_varint(data, index)
            fields.setdefault(field, []).append((0, value, b""))
        elif wire == 2:
            length, index = _read_varint(data, index)
            if index + length > len(data):
                raise ValueError("truncated bytes field")
            fields.setdefault(field, []).append((2, 0, data[index: index + length]))
            index += length
        elif wire == 5:
            index += 4
        else:
            raise ValueError(f"unsupported wire type {wire}")
    return fields


def _decode_server_list(data: bytes) -> list[ServerState]:
    servers: list[ServerState] = []
    for wire_type, _, payload in _decode_fields(data).get(1, []):
        if wire_type == 2:
            servers.append(_decode_server_info(payload))
    return servers


def _decode_server_info(data: bytes) -> ServerState:
    name = ""
    state = 0
    sort = 0
    for field, entries in _decode_fields(data).items():
        for wire_type, value, payload in entries:
            if field == 4 and wire_type == 0:
                state = value
            elif field == 5 and wire_type == 2:
                name = _decode_name(payload)
            elif field == 7 and wire_type == 0:
                sort = value
    return ServerState(name=name, state=state, sort=sort)


def _decode_name(payload: bytes) -> str:
    text = payload.decode("utf-8", errors="replace")
    if "\ufffd" in text:
        return payload.decode("gbk", errors="replace")
    return text


async def close() -> None:
    await _http.aclose()
