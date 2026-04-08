"""Tests for zoho_cli.mail shared helpers."""

from __future__ import annotations

import pytest

from zoho_cli import mail, utils


class _LookupClient:
    def get_folders(self, account_id: str) -> dict:
        return {"data": [{"folderId": "F1"}, {"folderId": "F2"}]}

    def get_messages(self, account_id: str, folder_id: str, limit: int = 200) -> dict:
        if folder_id == "F2":
            return {"data": [{"messageId": "M1"}]}
        return {"data": []}


class _AttachmentClient:
    def __init__(self, payload):
        self._payload = payload

    def get_attachment_info(self, account_id: str, folder_id: str, message_id: str) -> dict:
        return {"data": self._payload}


def test_resolve_message_folder_id_uses_explicit_folder_id() -> None:
    class _NoopClient:
        pass

    assert mail.resolve_message_folder_id(_NoopClient(), "A1", "M1", "F9") == "F9"


def test_resolve_message_folder_id_finds_message_folder() -> None:
    client = _LookupClient()
    assert mail.resolve_message_folder_id(client, "A1", "M1") == "F2"


def test_resolve_message_folder_id_errors_when_not_found(capsys: pytest.CaptureFixture) -> None:
    class _EmptyClient:
        def get_folders(self, account_id: str) -> dict:
            return {"data": []}

    utils.configure(md=False)
    with pytest.raises(SystemExit) as exc_info:
        mail.resolve_message_folder_id(_EmptyClient(), "A1", "M404")

    assert exc_info.value.code == 1
    assert "message_not_found" in capsys.readouterr().err


def test_list_attachments_handles_dict_payload_and_string_entries() -> None:
    client = _AttachmentClient(
        {
            "attachments": [
                {"attachmentId": "A1", "attachmentName": "a.txt", "attachmentSize": "2"},
                "A2",
                99,
            ],
            "inline": [{"attachId": "A3", "fileName": "b.pdf", "size": 10}],
        }
    )

    atts = mail.list_attachments(client, "ACC", "F1", "M1")

    assert atts == [
        {"attachmentId": "A1", "fileName": "a.txt", "size": 2},
        {"attachmentId": "A2", "fileName": "", "size": 0},
        {"attachmentId": "A3", "fileName": "b.pdf", "size": 10},
    ]


def test_list_attachments_handles_list_payload() -> None:
    client = _AttachmentClient(
        [
            {"attachmentId": "A1", "fileName": "report.csv", "size": 123},
            "A2",
        ]
    )

    atts = mail.list_attachments(client, "ACC", "F1", "M1")

    assert [a["attachmentId"] for a in atts] == ["A1", "A2"]
