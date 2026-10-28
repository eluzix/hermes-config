"""Hermes handlers backed by the Roku ECP client."""

from __future__ import annotations

import json
from typing import Callable

from .roku_ecp import RokuClient, RokuError


ACTIONS = {
    "home": "Home",
    "back": "Back",
    "up": "Up",
    "down": "Down",
    "left": "Left",
    "right": "Right",
    "select": "Select",
    "play_pause": "Play",
    "rewind": "Rev",
    "fast_forward": "Fwd",
    "instant_replay": "InstantReplay",
    "info": "Info",
    "backspace": "Backspace",
    "enter": "Enter",
    "volume_up": "VolumeUp",
    "volume_down": "VolumeDown",
    "mute": "VolumeMute",
    "channel_up": "ChannelUp",
    "channel_down": "ChannelDown",
    "input_tuner": "InputTuner",
    "input_hdmi1": "InputHDMI1",
    "input_hdmi2": "InputHDMI2",
    "input_hdmi3": "InputHDMI3",
    "input_hdmi4": "InputHDMI4",
    "input_av1": "InputAV1",
    "find_remote": "FindRemote",
}


def _json_handler(function: Callable[..., dict[str, object]]) -> Callable[..., str]:
    def wrapped(params: dict, **kwargs) -> str:
        del kwargs
        try:
            return json.dumps(function(params), ensure_ascii=False)
        except RokuError as exc:
            return json.dumps({"ok": False, "error": str(exc)})
        except (TypeError, ValueError) as exc:
            return json.dumps({"ok": False, "error": f"invalid tool arguments: {exc}"})

    return wrapped


class RokuTools:
    def __init__(self, host: str, port: int, timeout: float):
        self._host = host
        self._port = port
        self._timeout = timeout

    def _client(self) -> RokuClient:
        if not self._host:
            raise RokuError("plugin setting 'host' is empty; configure the Roku TV's local IPv4 address")
        return RokuClient(self._host, self._port, self._timeout)

    def handlers(self) -> dict[str, Callable[..., str]]:
        return {
            "roku_status": _json_handler(self.status),
            "roku_list_apps": _json_handler(self.list_apps),
            "roku_remote": _json_handler(self.remote),
            "roku_launch_app": _json_handler(self.launch_app),
            "roku_type_text": _json_handler(self.type_text),
            "roku_power_off": _json_handler(self.power_off),
        }

    def status(self, _params: dict) -> dict[str, object]:
        client = self._client()
        info = client.device_info()
        media = client.media_player()
        return {
            "ok": True,
            "tv": {
                "name": info.get("user-device-name") or info.get("friendly-device-name"),
                "model": info.get("model-name"),
                "location": info.get("user-device-location"),
                "power_mode": info.get("power-mode"),
                "active_app": client.active_app(),
                "media_state": media.get("@attributes", {}).get("state")
                if isinstance(media.get("@attributes"), dict)
                else None,
            },
        }

    def list_apps(self, _params: dict) -> dict[str, object]:
        return {"ok": True, "apps": self._client().apps()}

    def remote(self, params: dict) -> dict[str, object]:
        action = params.get("action")
        if not isinstance(action, str) or action not in ACTIONS:
            raise ValueError(f"unsupported action {action!r}")
        key = self._client().keypress(ACTIONS[action])
        return {"ok": True, "action": action, "key": key}

    def launch_app(self, params: dict) -> dict[str, object]:
        requested = params.get("app")
        if not isinstance(requested, str) or not requested.strip():
            raise ValueError("app must be a non-empty app name or ID")
        requested = requested.strip()
        client = self._client()
        apps = client.apps()
        exact_id = [app for app in apps if app.get("id") == requested]
        exact_name = [app for app in apps if str(app.get("name", "")).casefold() == requested.casefold()]
        matches = exact_id or exact_name
        if not matches:
            raise RokuError(f"no installed Roku app exactly matches {requested!r}; call roku_list_apps")
        if len(matches) > 1:
            raise RokuError(f"multiple installed apps match {requested!r}; launch by app ID")
        app = matches[0]
        app_id = str(app["id"])
        client.launch(app_id)
        return {"ok": True, "app": {"id": app_id, "name": app.get("name")}}

    def type_text(self, params: dict) -> dict[str, object]:
        text = params.get("text")
        if not isinstance(text, str):
            raise ValueError("text must be a string")
        count = self._client().type_text(text)
        return {"ok": True, "characters_sent": count}

    def power_off(self, params: dict) -> dict[str, object]:
        if params.get("confirm") is not True:
            raise RokuError("power-off refused: confirm must be true after an explicit user request")
        self._client().power_off()
        return {"ok": True, "power": "off"}
