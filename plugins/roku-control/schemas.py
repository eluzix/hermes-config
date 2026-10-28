"""Model-facing tool schemas for Roku control."""

ROKU_STATUS = {
    "name": "roku_status",
    "description": (
        "Get the configured Roku TV's current power mode, active app, playback state, "
        "name, and model. Use this before acting when TV availability or state is unclear."
    ),
    "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
}

ROKU_LIST_APPS = {
    "name": "roku_list_apps",
    "description": "List apps and TV inputs installed on the configured Roku TV, including IDs used to launch them.",
    "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
}

ROKU_REMOTE = {
    "name": "roku_remote",
    "description": (
        "Send one non-power remote-control action to the configured Roku TV. "
        "Only call when the user asked to control or navigate the TV."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "home", "back", "up", "down", "left", "right", "select",
                    "play_pause", "rewind", "fast_forward", "instant_replay", "info",
                    "backspace", "enter", "volume_up", "volume_down", "mute",
                    "channel_up", "channel_down", "input_tuner", "input_hdmi1",
                    "input_hdmi2", "input_hdmi3", "input_hdmi4", "input_av1", "find_remote"
                ],
                "description": "Exactly one remote action. play_pause toggles playback; mute toggles mute.",
            }
        },
        "required": ["action"],
        "additionalProperties": False,
    },
}

ROKU_LAUNCH_APP = {
    "name": "roku_launch_app",
    "description": (
        "Launch an installed Roku app or TV input by exact app name or app ID. "
        "Use roku_list_apps first if the name is uncertain."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "app": {"type": "string", "description": "Exact installed app name or app ID."}
        },
        "required": ["app"],
        "additionalProperties": False,
    },
}

ROKU_TYPE_TEXT = {
    "name": "roku_type_text",
    "description": (
        "Type text into the currently focused Roku on-screen text field. "
        "This does not open a keyboard or search screen by itself."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "text": {"type": "string", "minLength": 1, "maxLength": 256}
        },
        "required": ["text"],
        "additionalProperties": False,
    },
}

ROKU_POWER_OFF = {
    "name": "roku_power_off",
    "description": (
        "Turn off the configured Roku TV. Call only after the user explicitly asks to turn "
        "the TV off; never infer this from ending a session or stopping playback."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "confirm": {
                "type": "boolean",
                "description": "Must be true, confirming the user explicitly requested power-off.",
            }
        },
        "required": ["confirm"],
        "additionalProperties": False,
    },
}
