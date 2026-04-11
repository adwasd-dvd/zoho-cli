from __future__ import annotations

import argparse
import json
import os
from typing import Any

from zoho_cli.cliq import ZohoCliqClient, infer_cliq_base_url


def _build_base_url(network: str | None, base_url: str | None) -> str:
    if base_url:
        return base_url.rstrip("/")
    return infer_cliq_base_url(network=network)


def main() -> None:
    parser = argparse.ArgumentParser(description="Semi-manual Cliq deep probe")
    parser.add_argument("--access-token", default=os.getenv("ZOHO_CLIQ_ACCESS_TOKEN"))
    parser.add_argument("--network", default=None)
    parser.add_argument("--base-url", default=None)

    parser.add_argument("--dm-user-id", default=None)
    parser.add_argument("--chat-id", default=None)
    parser.add_argument("--channel-id", default=None)

    parser.add_argument("--send-text", default=None)
    parser.add_argument("--send-media", default=None)
    parser.add_argument("--media-kind", default="file", choices=["file", "image", "voice"])
    parser.add_argument("--send-user-id", default=None)

    args = parser.parse_args()

    if not args.access_token:
        raise SystemExit("Missing access token. Use --access-token or ZOHO_CLIQ_ACCESS_TOKEN")

    base_url = _build_base_url(args.network, args.base_url)
    client = ZohoCliqClient(args.access_token, base_url=base_url)

    result: dict[str, Any] = {
        "baseUrl": base_url,
        "users": {},
        "dmHistory": {},
        "channelHistory": {},
        "sendText": {},
        "sendMedia": {},
    }

    users = client.get_all_users(limit=200)
    result["users"] = {"count": len(users), "sample": users[:3]}

    if args.dm_user_id:
        dm = client.get_dm_history(args.dm_user_id, limit=200)
        result["dmHistory"] = {
            "targetUserId": args.dm_user_id,
            "count": len(dm),
            "latestSample": dm[:3],
        }

    if args.chat_id or args.channel_id:
        history = client.get_chat_history(
            chat_id=args.chat_id,
            channel_id=args.channel_id,
            limit=200,
        )
        result["channelHistory"] = {
            "chatId": args.chat_id,
            "channelId": args.channel_id,
            "count": len(history),
            "latestSample": history[:3],
        }

    if args.send_text:
        if args.send_user_id:
            sent = client.send_message(args.send_text, user_id=args.send_user_id)
        elif args.channel_id:
            sent = client.send_message(args.send_text, channel_id=args.channel_id)
        else:
            raise SystemExit("--send-text requires --send-user-id or --channel-id")
        result["sendText"] = sent

    if args.send_media:
        if args.send_user_id:
            sent_media = client.send_local_file_message(
                args.send_media,
                text=args.send_text or "",
                user_id=args.send_user_id,
                media_kind=args.media_kind,
            )
        elif args.channel_id:
            sent_media = client.send_local_file_message(
                args.send_media,
                text=args.send_text or "",
                channel_id=args.channel_id,
                media_kind=args.media_kind,
            )
        else:
            raise SystemExit("--send-media requires --send-user-id or --channel-id")
        result["sendMedia"] = sent_media

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
