"""Cliq bot command builders."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Optional

import typer

from zoho_cli import utils


@dataclass(frozen=True)
class CliqBotsContext:
    """Runtime hooks needed by the Cliq bot command surface."""

    load_config: Callable[[], dict[str, Any]]
    require_account: Callable[[dict[str, Any]], str]
    get_cliq_client: Callable[..., Any]


def _client(context: CliqBotsContext, network: str | None) -> Any:
    cfg = context.load_config()
    email = context.require_account(cfg)
    return context.get_cliq_client(cfg, email, network=network)


def _data(resp: Any) -> Any:
    return resp.get("data", resp) if isinstance(resp, dict) else resp


def _dict_rows(data: Any, keys: tuple[str, ...]) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        for key in keys:
            candidate = data.get(key)
            if isinstance(candidate, list):
                return [item for item in candidate if isinstance(item, dict)]
    return []


def build_cliq_post_to_bot_command(context: CliqBotsContext) -> Callable[..., None]:
    """Build ``zoho cliq post-to-bot`` with injected runtime state."""

    def cliq_post_to_bot(
        bot_id: str = typer.Argument(..., help="Bot id or unique name."),
        text: str = typer.Option(..., "--text", "-t", help="Message text."),
        title: Optional[str] = typer.Option(
            None,
            "--title",
            help="Optional title/context field for bot message payloads.",
        ),
        network: Optional[str] = typer.Option(
            None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
        ),
    ) -> None:
        """Post one message to a bot."""
        client = _client(context, network)

        target_bot = bot_id.strip()
        data = _data(client.post_to_bot(target_bot, text, title=title))

        message_id = ""
        if isinstance(data, dict):
            for key in ("message_id", "messageId", "id"):
                value = data.get(key)
                if isinstance(value, str) and value.strip():
                    message_id = value.strip()
                    break

        utils.output_status(
            "Cliq bot message sent",
            extra={
                "botId": target_bot,
                "messageId": message_id,
                "result": data,
            },
        )

    return cliq_post_to_bot


def build_cliq_bot_subscribers_command(
    context: CliqBotsContext,
) -> Callable[..., None]:
    """Build ``zoho cliq bot-subscribers`` with injected runtime state."""

    def cliq_bot_subscribers(
        bot_id: str = typer.Argument(..., help="Bot id or unique name."),
        limit: int = typer.Option(50, "--limit", "-n", help="Max rows to return."),
        network: Optional[str] = typer.Option(
            None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
        ),
    ) -> None:
        """List subscribers/followers for one bot."""
        client = _client(context, network)

        target_bot = bot_id.strip()
        data = _data(client.list_bot_subscribers(target_bot, limit=limit))
        subscribers = _dict_rows(
            data, ("subscribers", "followers", "members", "data", "list", "items")
        )
        utils.output(
            {
                "botId": target_bot,
                "count": len(subscribers),
                "subscribers": subscribers,
            }
        )

    return cliq_bot_subscribers


def build_cliq_trigger_bot_command(context: CliqBotsContext) -> Callable[..., None]:
    """Build ``zoho cliq trigger-bot`` with injected runtime state."""

    def cliq_trigger_bot(
        bot_id: str = typer.Argument(..., help="Bot id or unique name."),
        call_name: str = typer.Argument(..., help="Bot call/action name."),
        inputs_json: Optional[str] = typer.Option(
            None,
            "--inputs-json",
            help="Optional JSON object payload for bot call inputs.",
        ),
        network: Optional[str] = typer.Option(
            None, "--network", help="Cliq network slug (e.g. happydistrouklimited)."
        ),
    ) -> None:
        """Trigger one named bot call/action."""
        client = _client(context, network)

        payload_inputs: dict[str, Any] = {}
        raw_inputs = (inputs_json or "").strip()
        if raw_inputs:
            try:
                parsed = json.loads(raw_inputs)
            except ValueError as exc:
                utils.error_exit(
                    "invalid_inputs_json", f"inputs-json must be valid JSON: {exc}"
                )
            if not isinstance(parsed, dict):
                utils.error_exit(
                    "invalid_inputs_json",
                    "inputs-json must decode to a JSON object",
                )
            payload_inputs = parsed

        target_bot = bot_id.strip()
        target_call = call_name.strip()
        data = _data(
            client.trigger_bot_call(target_bot, target_call, inputs=payload_inputs)
        )

        call_id = ""
        if isinstance(data, dict):
            for key in ("call_id", "callId", "id"):
                value = data.get(key)
                if isinstance(value, str) and value.strip():
                    call_id = value.strip()
                    break

        utils.output_status(
            "Cliq bot call triggered",
            extra={
                "botId": target_bot,
                "callName": target_call,
                "callId": call_id,
                "result": data,
            },
        )

    return cliq_trigger_bot
