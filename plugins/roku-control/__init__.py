"""Hermes Roku control plugin registration."""

from . import schemas
from .tools import RokuTools


def register(ctx):
    host = ctx.get_config("host", default="")
    port = ctx.get_config("port", default=8060)
    timeout = ctx.get_config("timeout", default=3.0)
    handlers = RokuTools(host=host, port=port, timeout=timeout).handlers()

    registrations = (
        ("roku_status", schemas.ROKU_STATUS),
        ("roku_list_apps", schemas.ROKU_LIST_APPS),
        ("roku_remote", schemas.ROKU_REMOTE),
        ("roku_launch_app", schemas.ROKU_LAUNCH_APP),
        ("roku_type_text", schemas.ROKU_TYPE_TEXT),
        ("roku_power_off", schemas.ROKU_POWER_OFF),
    )
    for name, schema in registrations:
        ctx.register_tool(
            name=name,
            toolset="roku",
            schema=schema,
            handler=handlers[name],
        )
