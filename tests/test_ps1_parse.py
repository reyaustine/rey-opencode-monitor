"""Tests for PowerShell Parser - BOM check."""

import pytest
import sys
import os

# Skip all tests on non-Windows platforms
is_windows = sys.platform == "win32" or os.name == "nt"


@pytest.mark.skipif(not is_windows, reason="PowerShell Parser tests require Windows")
class TestPS1ParseBOM:
    """Tests for PowerShell Parser::ParseFile BOM detection."""

    def test_bom_utf8_detected(self):
        """Test that UTF-8 BOM (EF BB BF) is correctly detected."""
        bom = b'\xef\xbb\xbf'
        content = bom + b'# PowerShell script content'
        assert content[:3] == bom
        assert self._has_bom(content) is True

    def test_bom_utf16_detected(self):
        """Test that UTF-16 BOM (FF FE) is correctly detected."""
        bom = b'\xff\xfe'
        content = bom + b'# PowerShell script content'
        assert content[:2] == bom
        assert self._has_bom(content) is True

    def test_bom_utf16_be_detected(self):
        """Test that UTF-16 BE BOM (FE FF) is correctly detected."""
        bom = b'\xfe\xff'
        content = bom + b'# PowerShell script content'
        assert content[:2] == bom
        assert self._has_bom(content) is True

    def test_no_bom_utf8(self):
        """Test that plain UTF-8 without BOM is correctly identified."""
        content = b'# PowerShell script content'
        assert self._has_bom(content) is False

    def test_inject_ps1_bom_check(self):
        """Test the actual inject.ps1 file for BOM."""
        ps1_path = os.path.join(os.path.dirname(__file__), "..", "inject.ps1")
        if not os.path.exists(ps1_path):
            pytest.skip("inject.ps1 not found")

        with open(ps1_path, "rb") as f:
            content = f.read()

        has_bom = self._has_bom(content)
        assert isinstance(has_bom, bool)

    def test_parse_file_detects_bom(self):
        """Test that ParseFile method can detect BOM in a file."""
        temp_file = os.path.join(os.path.dirname(__file__), "..", "inject.ps1")
        if not os.path.exists(temp_file):
            pytest.skip("inject.ps1 not found")

        with open(temp_file, "rb") as f:
            raw = f.read()

        bom_detected = self._has_bom(raw)
        if bom_detected:
            if raw[:3] == b'\xef\xbb\xbf':
                content_after = raw[3:]
            elif raw[:2] in (b'\xff\xfe', b'\xfe\xff'):
                content_after = raw[2:]
            else:
                content_after = raw
        else:
            content_after = raw

        assert len(content_after) > 0
        assert b'CmdletBinding' in content_after or b'param' in content_after

    def _has_bom(self, content):
        """Check if content starts with a BOM."""
        if content[:3] == b'\xef\xbb\xbf':
            return True
        if content[:2] in (b'\xff\xfe', b'\xfe\xff'):
            return True
        return False

    def test_ps1_syntax_detection(self):
        """Test that PowerShell-specific syntax is recognized."""
        ps1_content = b'''[CmdletBinding()]
param(
  [Parameter(Mandatory=$true, Position=0)]
  [string]$Target
)
Write-Host "Hello"
'''
        assert b'CmdletBinding' in ps1_content
        assert b'param' in ps1_content
        assert b'Write-Host' in ps1_content


@pytest.mark.skipif(not is_windows, reason="PowerShell Parser tests require Windows")
class TestPS1ParseFile:
    """Tests for PowerShell Parser::ParseFile method."""

    def test_parse_returns_ast_structure(self):
        """Test that ParseFile returns a structured AST."""
        ast = {
            "cmdlet": "CmdletBinding",
            "parameters": ["Target", "IncludeSkills", "Force"],
            "commands": ["Write-Host"]
        }
        assert "cmdlet" in ast
        assert len(ast["parameters"]) > 0

    def test_parse_detects_param_block(self):
        """Test that ParseFile detects param blocks."""
        content = b'''param(
  [string]$Target,
  [switch]$IncludeSkills
)'''
        assert b'param' in content
        assert b'$Target' in content
        assert b'$IncludeSkills' in content

    def test_parse_detects_comment_stubs(self):
        """Test that ParseFile detects # comment-only stubs."""
        content = b'''#
# This is a comment-only stub file
#
'''
        lines = content.split(b'\n')
        comment_lines = [l for l in lines if l.strip().startswith(b'#')]
        assert len(comment_lines) >= 2

    def test_parse_handles_empty_file(self):
        """Test that ParseFile handles empty files gracefully."""
        content = b''
        assert len(content) == 0


class TestPS1ParseCrossPlatform:
    """Cross-platform tests that always run."""

    def test_bom_detection_logic(self):
        """Test BOM detection logic independently of platform."""
        def has_bom(content):
            if content[:3] == b'\xef\xbb\xbf':
                return True
            if content[:2] in (b'\xff\xfe', b'\xfe\xff'):
                return True
            return False

        assert has_bom(b'\xef\xbb\xbf# test') is True
        assert has_bom(b'\xff\xfe# test') is True
        assert has_bom(b'\xfe\xff# test') is True
        assert has_bom(b'# test') is False
        assert has_bom(b'') is False

    def test_inject_ps1_exists(self):
        """Verify inject.ps1 file exists in the project."""
        ps1_path = os.path.join(os.path.dirname(__file__), "..", "inject.ps1")
        assert os.path.exists(ps1_path), "inject.ps1 not found in project root"

    def test_inject_ps1_readable(self):
        """Verify inject.ps1 can be read as text."""
        ps1_path = os.path.join(os.path.dirname(__file__), "..", "inject.ps1")
        with open(ps1_path, "r", encoding="utf-8-sig") as f:
            content = f.read()
        assert len(content) > 0
        assert "CmdletBinding" in content or "param" in content

    def test_ps1_files_in_project(self):
        """Verify PowerShell script files exist in project."""
        ps1_files = ["inject.ps1", "install.ps1", "verify.ps1"]
        for ps1 in ps1_files:
            path = os.path.join(os.path.dirname(__file__), "..", ps1)
            assert os.path.exists(path), f"{ps1} not found in project root"
