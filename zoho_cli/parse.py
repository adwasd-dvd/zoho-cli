"""Attachment content parsers for zoho-cli."""

import json
from pathlib import Path
from typing import Optional, Union

try:
    import pandas as pd

    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

try:
    import pdfplumber

    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False


def parse_attachment(filepath: Union[str, Path]) -> Optional[str]:
    """
    Parse attachment content based on file extension.

    Returns parsed text content, or None if format is not supported.
    Raises an exception for critical errors (e.g., corrupted file).
    """
    path = Path(filepath)
    ext = path.suffix.lower()

    parsers = {
        ".txt": _parse_text,
        ".md": _parse_text,
        ".json": _parse_json,
        ".csv": _parse_csv,
        ".xlsx": _parse_excel,
        ".pdf": _parse_pdf,
        ".docx": _parse_docx,
    }

    if ext not in parsers:
        return None

    try:
        result = parsers[ext](path)
        return result
    except Exception as e:
        raise RuntimeError(f"Failed to parse {filepath}: {e}")


def _parse_text(path: Path) -> str:
    """Parse plain text or markdown files."""
    return path.read_text(encoding="utf-8")


def _parse_json(path: Path) -> str:
    """Parse JSON file with pretty printing."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return json.dumps(data, indent=2, ensure_ascii=False)


def _parse_csv(path: Path) -> str:
    """Parse CSV file and format as table string."""
    if not HAS_PANDAS:
        return "⚠️ CSV 解析需要 pandas：pip install pandas\n\n" + path.read_text(
            encoding="utf-8"
        )

    df = pd.read_csv(path)
    return df.to_string(index=False)


def _parse_excel(path: Path) -> str:
    """Parse Excel file and format as table string."""
    if not HAS_PANDAS:
        return "⚠️ Excel 解析需要 pandas：pip install pandas"

    try:
        xl = pd.ExcelFile(path)
        sheets = [
            f"Sheet: {s}\n{pd.read_excel(xl, sheet_name=s).to_string(index=False)}\n"
            for s in xl.sheet_names
        ]
        return "\n---\n".join(sheets)
    except Exception as e:
        raise RuntimeError(f"Failed to parse Excel file: {e}")


def _parse_pdf(path: Path) -> str:
    """Parse PDF file and extract text."""
    if not HAS_PDFPLUMBER:
        return "⚠️ PDF 解析需要 pdfplumber：pip install pdfplumber\n\n无法提取内容，请手动下载后使用 pdftotext 或其他工具。"

    try:
        with pdfplumber.open(path) as pdf:
            texts = [page.extract_text() or "" for page in pdf.pages]
        return "\n".join(texts)
    except Exception as e:
        raise RuntimeError(f"Failed to parse PDF file: {e}")


def _parse_docx(path: Path) -> str:
    """Parse Word document and extract text."""
    try:
        from docx import Document
    except ImportError:
        return "⚠️ Word 解析需要 python-docx：pip install python-docx\n\n无法提取内容，请手动下载后使用其他工具。"

    try:
        doc = Document(path)
        paragraphs = [p.text for p in doc.paragraphs]
        return "\n".join(p for p in paragraphs if p.text.strip())
    except Exception as e:
        raise RuntimeError(f"Failed to parse Word file: {e}")
