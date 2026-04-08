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


class _ContentClient:
    def __init__(self, payload):
        self._payload = payload

    def get_message_content(self, account_id: str, folder_id: str, message_id: str) -> dict:
        return self._payload


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


def test_fetch_message_content_normalizes_nested_data_response() -> None:
    client = _ContentClient(
        {
            "data": {
                "messageId": "M1",
                "folderId": "F1",
                "subject": "Status",
                "sender": "alice@example.com",
                "textBody": "Original body",
            }
        }
    )

    msg = mail.fetch_message_content(client, "ACC", "F1", "M1")

    assert msg["messageId"] == "M1"
    assert msg["subject"] == "Status"
    assert msg["from"] == "alice@example.com"
    assert msg["textBody"] == "Original body"


def test_fetch_message_content_backfills_summary_when_content_response_is_sparse() -> None:
    class _SparseContentClient:
        def get_message_content(self, account_id: str, folder_id: str, message_id: str) -> dict:
            return {"data": {"messageId": "M1", "content": "Original body"}}

        def get_messages(self, account_id: str, folder_id: str, limit: int = 200) -> dict:
            return {
                "data": [
                    {
                        "messageId": "M1",
                        "folderId": "F1",
                        "subject": "Status",
                        "sender": "alice@example.com",
                        "toAddress": "bob@example.com",
                        "receivedTime": "1700000000000",
                        "isRead": True,
                        "hasAttachment": True,
                        "tags": ["inbox"],
                    }
                ]
            }

    msg = mail.fetch_message_content(_SparseContentClient(), "ACC", "F1", "M1")

    assert msg["messageId"] == "M1"
    assert msg["folderId"] == "F1"
    assert msg["subject"] == "Status"
    assert msg["from"] == "alice@example.com"
    assert msg["to"] == ["bob@example.com"]
    assert msg["date"] == "1700000000000"
    assert msg["unread"] is False
    assert msg["hasAttachments"] is True
    assert msg["textBody"] == "Original body"


def test_build_reply_payload_with_quote() -> None:
    payload = mail.build_reply_payload(
        from_address="me@example.com",
        to_address="you@example.com",
        subject="Status update",
        text="Looks good",
        quote_original=True,
        original_text="Line 1\nLine 2",
    )

    assert payload == {
        "fromAddress": "me@example.com",
        "toAddress": "you@example.com",
        "subject": "Re: Status update",
        "mailFormat": "plaintext",
        "content": "Looks good\n\n> Line 1\n> Line 2",
    }


def test_build_send_payload_plaintext_with_cc_bcc() -> None:
    payload = mail.build_send_payload(
        from_address="me@example.com",
        to_addresses=["to@example.com"],
        subject="Hello",
        text="Body",
        cc_addresses=["cc@example.com"],
        bcc_addresses=["bcc@example.com"],
    )

    assert payload == {
        "fromAddress": "me@example.com",
        "toAddress": "to@example.com",
        "subject": "Hello",
        "mailFormat": "plaintext",
        "content": "Body",
        "ccAddress": "cc@example.com",
        "bccAddress": "bcc@example.com",
    }


def test_build_send_payload_html_uses_alt_text() -> None:
    payload = mail.build_send_payload(
        from_address="me@example.com",
        to_addresses=["to@example.com", "to2@example.com"],
        subject="Hello",
        text="Fallback",
        html_body="<p>Hello</p>",
    )

    assert payload == {
        "fromAddress": "me@example.com",
        "toAddress": "to@example.com,to2@example.com",
        "subject": "Hello",
        "mailFormat": "html",
        "content": "<p>Hello</p>",
        "altText": "Fallback",
    }


def test_build_send_payload_requires_body() -> None:
    with pytest.raises(ValueError, match="text or html_body is required"):
        mail.build_send_payload(
            from_address="me@example.com",
            to_addresses=["to@example.com"],
            subject="Hello",
        )


def test_build_forward_payload_with_note() -> None:
    payload = mail.build_forward_payload(
        from_address="me@example.com",
        to_addresses=["a@example.com", "b@example.com"],
        subject="Original",
        original_from="sender@example.com",
        original_subject="Original",
        note="FYI",
        original_text="Body",
    )

    assert payload == {
        "fromAddress": "me@example.com",
        "toAddress": "a@example.com,b@example.com",
        "subject": "Fwd: Original",
        "mailFormat": "plaintext",
        "content": (
            "FYI"
            "\n\n---------- Forwarded message ----------\n"
            "From: sender@example.com\n"
            "Subject: Original\n\n"
            "Body"
        ),
    }


def test_build_send_status_extra_prefers_nested_data() -> None:
    extra = mail.build_send_status_extra({"data": {"messageId": "M1", "status": "queued"}})

    assert extra == {"messageId": "M1", "sendStatus": "queued"}


def test_build_send_status_extra_handles_top_level_response() -> None:
    extra = mail.build_send_status_extra({"messageId": 9001})

    assert extra == {"messageId": "9001"}
