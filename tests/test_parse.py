"""Tests for attachment parsing functionality."""

import tempfile
from pathlib import Path
import pytest
from zoho_cli.parse import parse_attachment, HAS_PANDAS, HAS_PDFPLUMBER


class TestParseAttachment:
    """Unit tests for parse_attachment function."""

    def test_json_parsing(self):
        """Test JSON file parsing with pretty print."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('{"name": "test", "value": 123}')
            json_path = f.name

        try:
            result = parse_attachment(json_path)
            assert '"name": "test"' in result
            assert '"value": 123' in result
        finally:
            Path(json_path).unlink()

    def test_text_parsing(self):
        """Test plain text file parsing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write('Hello, World!')
            txt_path = f.name

        try:
            result = parse_attachment(txt_path)
            assert result == 'Hello, World!'
        finally:
            Path(txt_path).unlink()

    def test_csv_without_pandas(self):
        """Test CSV parsing falls back to raw text when pandas missing."""
        if HAS_PANDAS:
            pytest.skip("pandas is installed, testing fallback not applicable")

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write('a,b,c\n1,2,3')
            csv_path = f.name

        try:
            result = parse_attachment(csv_path)
            assert 'pip install pandas' in result
            assert 'a,b,c' in result
        finally:
            Path(csv_path).unlink()

    def test_unsupported_format(self):
        """Test that unsupported formats return None."""
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.png', delete=False) as f:
            f.write(b'\x89PNG')
            png_path = f.name

        try:
            result = parse_attachment(png_path)
            assert result is None
        finally:
            Path(png_path).unlink()


class TestParseStructure:
    """Tests for parse module structure."""

    def test_parse_functions_exist(self):
        """Verify all expected parser functions exist."""
        from zoho_cli import parse as p
        
        assert hasattr(p, 'parse_attachment')
        assert hasattr(p, '_parse_text')
        assert hasattr(p, '_parse_json')
        assert hasattr(p, '_parse_csv')
        assert hasattr(p, '_parse_excel')
        assert hasattr(p, '_parse_pdf')
        assert hasattr(p, '_parse_docx')
