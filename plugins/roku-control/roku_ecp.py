"""Small, dependency-free Roku External Control Protocol client."""

from __future__ import annotations

from dataclasses import dataclass
import http.client
import ipaddress
import re
import socket
import time
from typing import Iterable
from urllib.parse import quote, urlparse
import xml.etree.ElementTree as ET


SSDP_ADDRESS = ("239.255.255.250", 1900)
SSDP_REQUEST = (
    b"M-SEARCH * HTTP/1.1\r\n"
    b"Host: 239.255.255.250:1900\r\n"
    b'Man: "ssdp:discover"\r\n'
    b"ST: roku:ecp\r\n"
    b"MX: 2\r\n"
    b"\r\n"
)

REMOTE_KEYS = {
    "home": "Home",
    "rev": "Rev",
    "fwd": "Fwd",
    "play": "Play",
    "select": "Select",
    "left": "Left",
    "right": "Right",
    "down": "Down",
    "up": "Up",
    "back": "Back",
    "instantreplay": "InstantReplay",
    "info": "Info",
    "backspace": "Backspace",
    "search": "Search",
    "enter": "Enter",
    "findremote": "FindRemote",
    "volumedown": "VolumeDown",
    "volumemute": "VolumeMute",
    "volumeup": "VolumeUp",
    "channelup": "ChannelUp",
    "channeldown": "ChannelDown",
    "inputtuner": "InputTuner",
    "inputhdmi1": "InputHDMI1",
    "inputhdmi2": "InputHDMI2",
    "inputhdmi3": "InputHDMI3",
    "inputhdmi4": "InputHDMI4",
    "inputav1": "InputAV1",
}


class RokuError(RuntimeError):
    """Base error for discovery, transport, and Roku response failures."""


class RokuHTTPError(RokuError):
    def __init__(self, status: int, reason: str, path: str):
        super().__init__(f"Roku returned HTTP {status} {reason} for {path}")
        self.status = status
        self.reason = reason
        self.path = path


@dataclass(frozen=True)
class DiscoveredRoku:
    host: str
    port: int
    location: str
    usn: str

    def as_dict(self) -> dict[str, object]:
        return {
            "host": self.host,
            "port": self.port,
            "location": self.location,
            "usn": self.usn,
        }


def _local_ipv4(value: str) -> str:
    try:
        address = ipaddress.ip_address(value)
    except ValueError as exc:
        raise RokuError(f"target must be a literal local IP address, got {value!r}") from exc
    if address.version != 4:
        raise RokuError("this POC supports IPv4 Roku targets only")
    if not (address.is_private or address.is_link_local):
        raise RokuError(f"refusing non-local Roku target {address}")
    return str(address)


def _parse_ssdp_response(payload: bytes) -> dict[str, str]:
    text = payload.decode("iso-8859-1", errors="replace")
    lines = text.splitlines()
    if not lines or " 200 " not in f" {lines[0]} ":
        return {}
    headers: dict[str, str] = {}
    for line in lines[1:]:
        name, separator, value = line.partition(":")
        if separator:
            headers[name.strip().lower()] = value.strip()
    return headers


def discover(timeout: float = 2.5) -> list[DiscoveredRoku]:
    """Discover Roku ECP services on the current LAN using SSDP."""
    if timeout <= 0 or timeout > 30:
        raise RokuError("discovery timeout must be between 0 and 30 seconds")

    found: dict[str, DiscoveredRoku] = {}
    deadline = time.monotonic() + timeout
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    try:
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        sock.sendto(SSDP_REQUEST, SSDP_ADDRESS)
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            sock.settimeout(remaining)
            try:
                payload, _sender = sock.recvfrom(65535)
            except socket.timeout:
                break
            headers = _parse_ssdp_response(payload)
            if headers.get("st", "").lower() != "roku:ecp":
                continue
            location = headers.get("location", "")
            parsed = urlparse(location)
            if parsed.scheme != "http" or not parsed.hostname:
                continue
            try:
                host = _local_ipv4(parsed.hostname)
                port = parsed.port or 8060
            except (RokuError, ValueError):
                continue
            if not 1 <= port <= 65535:
                continue
            usn = headers.get("usn", "")
            identity = usn or f"{host}:{port}"
            found[identity] = DiscoveredRoku(host, port, location, usn)
    except OSError as exc:
        raise RokuError(f"SSDP discovery failed: {exc}") from exc
    finally:
        sock.close()
    return sorted(found.values(), key=lambda item: (item.host, item.port, item.usn))


def _xml_root(payload: bytes, operation: str) -> ET.Element:
    try:
        return ET.fromstring(payload)
    except ET.ParseError as exc:
        raise RokuError(f"invalid XML from Roku for {operation}: {exc}") from exc


def _element_value(element: ET.Element) -> object:
    children = list(element)
    if not children:
        return (element.text or "").strip()
    result: dict[str, object] = {}
    for child in children:
        value = _element_value(child)
        existing = result.get(child.tag)
        if existing is None:
            result[child.tag] = value
        elif isinstance(existing, list):
            existing.append(value)
        else:
            result[child.tag] = [existing, value]
    if element.attrib:
        result["@attributes"] = dict(element.attrib)
    return result


def _canonical_key(key: str, *, allow_power_off: bool = False) -> str:
    normalized = re.sub(r"[\s_-]+", "", key).lower()
    if allow_power_off and normalized == "poweroff":
        return "PowerOff"
    try:
        return REMOTE_KEYS[normalized]
    except KeyError as exc:
        choices = ", ".join(REMOTE_KEYS.values())
        raise RokuError(f"unsupported key {key!r}; supported keys: {choices}") from exc


class RokuClient:
    def __init__(self, host: str, port: int = 8060, timeout: float = 3.0):
        self.host = _local_ipv4(host)
        if not 1 <= port <= 65535:
            raise RokuError("port must be between 1 and 65535")
        if timeout <= 0 or timeout > 30:
            raise RokuError("request timeout must be between 0 and 30 seconds")
        self.port = port
        self.timeout = timeout

    def _request(self, method: str, path: str) -> bytes:
        connection = http.client.HTTPConnection(self.host, self.port, timeout=self.timeout)
        try:
            connection.request(method, path, body=b"" if method == "POST" else None)
            response = connection.getresponse()
            payload = response.read(2 * 1024 * 1024 + 1)
            if len(payload) > 2 * 1024 * 1024:
                raise RokuError(f"Roku response too large for {path}")
            if not 200 <= response.status < 300:
                raise RokuHTTPError(response.status, response.reason, path)
            return payload
        except (OSError, http.client.HTTPException) as exc:
            raise RokuError(f"request to {self.host}:{self.port} failed: {exc}") from exc
        finally:
            connection.close()

    def _query(self, path: str) -> ET.Element:
        return _xml_root(self._request("GET", path), path)

    def device_info(self) -> dict[str, object]:
        root = self._query("/query/device-info")
        value = _element_value(root)
        return value if isinstance(value, dict) else {"value": value}

    def media_player(self) -> dict[str, object]:
        root = self._query("/query/media-player")
        value = _element_value(root)
        result = value if isinstance(value, dict) else {"value": value}
        if root.attrib:
            result["@attributes"] = dict(root.attrib)
        return result

    def active_app(self) -> dict[str, object]:
        root = self._query("/query/active-app")
        app = root.find("app")
        if app is None:
            return {}
        return {"id": app.get("id", ""), "name": (app.text or "").strip()}

    def apps(self) -> list[dict[str, object]]:
        root = self._query("/query/apps")
        return [
            {"id": app.get("id", ""), "name": (app.text or "").strip(), **app.attrib}
            for app in root.findall("app")
        ]

    def keypress(self, key: str) -> str:
        canonical = _canonical_key(key)
        self._request("POST", f"/keypress/{canonical}")
        return canonical

    def hold(self, key: str, seconds: float) -> str:
        canonical = _canonical_key(key)
        if seconds <= 0 or seconds > 10:
            raise RokuError("hold duration must be between 0 and 10 seconds")
        self._request("POST", f"/keydown/{canonical}")
        try:
            time.sleep(seconds)
        finally:
            self._request("POST", f"/keyup/{canonical}")
        return canonical

    def type_text(self, text: str) -> int:
        if not text:
            raise RokuError("text must not be empty")
        if len(text) > 256:
            raise RokuError("text is limited to 256 characters per command")
        for character in text:
            encoded = quote(character, safe="")
            self._request("POST", f"/keypress/Lit_{encoded}")
        return len(text)

    def launch(self, app_id: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", app_id):
            raise RokuError("app ID contains unsupported characters")
        self._request("POST", f"/launch/{quote(app_id, safe='')}")
        return app_id

    def power_off(self) -> None:
        canonical = _canonical_key("PowerOff", allow_power_off=True)
        self._request("POST", f"/keypress/{canonical}")


def device_summaries(devices: Iterable[DiscoveredRoku]) -> list[dict[str, object]]:
    """Return JSON-ready discovery records."""
    return [device.as_dict() for device in devices]
