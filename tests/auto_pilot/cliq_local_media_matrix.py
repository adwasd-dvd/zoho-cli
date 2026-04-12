from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict, dataclass
from typing import Any

from zoho_cli import auth, config, utils
from zoho_cli.cliq import ZohoCliqClient, infer_cliq_base_url


@dataclass
class ProbeResult:
    destination: str
    mediaKind: str
    sourcePath: str
    status: str
    errorCode: str = ""
    errorDetails: str = ""
    uploadPath: str = ""
    uploadField: str = ""


class ProbeError(RuntimeError):
    def __init__(self, code: str, details: str) -> None:
        super().__init__(f"{code}: {details}")
        self.code = code
        self.details = details


def _refresh_token(config_path: str, account: str) -> tuple[str, dict[str, Any]]:
    cfg = config.load(config_path)
    account_cfg = cfg.get("accounts", {}).get(account, {})
    token = auth.refresh_access_token(
        account,
        (cfg.get("client_id") or "").strip(),
        (cfg.get("client_secret") or "").strip(),
        accounts_base_url=account_cfg.get("accounts_server"),
    )
    return token, account_cfg


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Single-token Cliq local media matrix probe"
    )
    parser.add_argument("--config", required=True)
    parser.add_argument("--account", required=True)
    parser.add_argument("--network", default=None)
    parser.add_argument("--channel-id", required=True)
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--image-path", required=True)
    parser.add_argument("--voice-path", required=True)
    parser.add_argument("--file-path", required=True)
    parser.add_argument("--cooldown-secs", type=float, default=5.0)
    args = parser.parse_args()

    original_error_exit = utils.error_exit

    def _raise_probe_error(code: str, details: str) -> None:
        raise ProbeError(code, details)

    utils.error_exit = _raise_probe_error

    try:
        token, account_cfg = _refresh_token(args.config, args.account)
    except ProbeError as exc:
        print(
            json.dumps(
                {
                    "status": "error",
                    "error": exc.code,
                    "details": exc.details,
                    "channelId": args.channel_id,
                    "userId": args.user_id,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        utils.error_exit = original_error_exit
        return

    base_url = infer_cliq_base_url(
        mail_base_url=account_cfg.get("mail_base_url"),
        accounts_server=account_cfg.get("accounts_server"),
        network=args.network,
    )
    client = ZohoCliqClient(token, base_url=base_url)

    probes: list[tuple[str, str, str, dict[str, str]]] = [
        ("channel", "image", args.image_path, {"channel_id": args.channel_id}),
        ("channel", "voice", args.voice_path, {"channel_id": args.channel_id}),
        ("channel", "file", args.file_path, {"channel_id": args.channel_id}),
        ("user", "image", args.image_path, {"user_id": args.user_id}),
        ("user", "voice", args.voice_path, {"user_id": args.user_id}),
        ("user", "file", args.file_path, {"user_id": args.user_id}),
    ]

    results: list[ProbeResult] = []
    try:
        for idx, (destination, media_kind, source_path, kwargs) in enumerate(probes):
            if idx > 0 and args.cooldown_secs > 0:
                time.sleep(args.cooldown_secs)
            try:
                resp = client.send_local_file_message(
                    source_path,
                    text=f"SCAP single-token {destination} {media_kind}",
                    media_kind=media_kind,
                    **kwargs,
                )
                data = resp.get("data", resp) if isinstance(resp, dict) else {}
                upload = data.get("upload") if isinstance(data, dict) else {}
                if not isinstance(upload, dict):
                    upload = {}
                results.append(
                    ProbeResult(
                        destination=destination,
                        mediaKind=media_kind,
                        sourcePath=source_path,
                        status="ok",
                        uploadPath=str(upload.get("path") or ""),
                        uploadField=str(upload.get("field") or ""),
                    )
                )
            except ProbeError as exc:
                results.append(
                    ProbeResult(
                        destination=destination,
                        mediaKind=media_kind,
                        sourcePath=source_path,
                        status="error",
                        errorCode=exc.code,
                        errorDetails=exc.details,
                    )
                )
    finally:
        utils.error_exit = original_error_exit

    summary = {
        "baseUrl": base_url,
        "channelId": args.channel_id,
        "userId": args.user_id,
        "cooldownSecs": args.cooldown_secs,
        "ok": len([r for r in results if r.status == "ok"]),
        "errors": len([r for r in results if r.status != "ok"]),
        "results": [asdict(r) for r in results],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
