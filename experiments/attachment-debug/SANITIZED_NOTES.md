# Sanitized debugging summary

## Symptom

`zoho mail attachments` failed because the CLI treated `resp["data"]` as a flat array.

## Actual API shape

The Zoho Mail response could return a structure like:

```json
{
  "data": {
    "attachments": [...],
    "inline": [...],
    "messageId": "..."
  }
}
```

## Fix

- normalize `data` into a `raw_atts` list
- merge `attachments` and `inline` when `data` is a dict
- keep compatibility when `data` is a list
- add defensive handling in `format_attachment()` for unexpected shapes

## Why keep this folder

It preserves the reasoning behind the change without publishing local operational residue.
