"""
Unit tests for multi-language README localization (English default + Turkish & German).

Ensures cross-language switcher links, relative file links, internal GitHub heading
anchors, package version parity, and CLI command coverage stay in sync across all
localized READMEs.
"""

import re
import unicodedata
from pathlib import Path

import pytest

from smartbackup._version import __version__

REPO_ROOT = Path(__file__).resolve().parents[2]
README_FILES = {
    "en": REPO_ROOT / "README.md",
    "tr": REPO_ROOT / "docs" / "i18n" / "README.tr.md",
    "de": REPO_ROOT / "docs" / "i18n" / "README.de.md",
}

_MD_LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
_HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*$", re.MULTILINE)


def _github_heading_slug(heading: str) -> str:
    """Compute a GitHub-compatible Markdown heading anchor slug (preserving Unicode letters)."""
    text = heading.strip().lower()
    # Strip markdown formatting wrappers
    text = re.sub(r"[`*_~]", "", text)
    chars: list[str] = []
    for ch in text:
        if ch in (" ", "-"):
            chars.append("-")
        elif ch == "_":
            chars.append("_")
        else:
            cat = unicodedata.category(ch)
            # Keep letters (L*) and numbers (N*); drop emojis/symbols/punctuation
            if cat.startswith(("L", "N")):
                chars.append(ch)
    return "".join(chars)


def _extract_heading_slugs(markdown: str) -> set[str]:
    """Return all heading slugs defined outside fenced code blocks."""
    slugs: set[str] = set()
    in_fence = False
    for line in markdown.splitlines():
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = _HEADING_RE.match(line)
        if match:
            slugs.add(_github_heading_slug(match.group(1)))
    return slugs


class TestReadmeLocalization:
    """Contract checks for README.md (English) and docs/i18n/README.{tr,de}.md."""

    @pytest.mark.parametrize("lang", ["en", "tr", "de"])
    def test_readme_exists_and_contains_language_switcher(self, lang: str) -> None:
        path = README_FILES[lang]
        assert path.is_file(), f"Missing README for language {lang!r}: {path}"
        content = path.read_text(encoding="utf-8")

        assert "English" in content
        assert "Türkçe" in content
        assert "Deutsch" in content

        # Active language is bolded, not a broken self-link
        active_label = {"en": "**English**", "tr": "**Türkçe**", "de": "**Deutsch**"}[lang]
        assert active_label in content

    @pytest.mark.parametrize("lang", ["en", "tr", "de"])
    def test_all_relative_file_links_and_internal_anchors_resolve(self, lang: str) -> None:
        path = README_FILES[lang]
        content = path.read_text(encoding="utf-8")
        headings = _extract_heading_slugs(content)

        for target in _MD_LINK_RE.findall(content):
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            if target == "/":
                continue
            if target.startswith("#"):
                anchor = target[1:]
                assert anchor in headings, (
                    f"{path.name}: internal anchor '#{anchor}' not found in headings {sorted(headings)}"
                )
                continue

            file_part = target.split("#", 1)[0]
            resolved = (path.parent / file_part).resolve()
            assert resolved.exists(), (
                f"{path.name}: relative link '{target}' resolved to missing path {resolved}"
            )

    @pytest.mark.parametrize("lang", ["en", "tr", "de"])
    def test_version_and_cli_command_parity(self, lang: str) -> None:
        content = README_FILES[lang].read_text(encoding="utf-8")

        # Must reference the single-source package version in both --version and pinned installer
        assert f"smartbackup {__version__}" in content
        assert f"v{__version__}" in content

        # Core CLI commands, flags, and installer URLs must remain verbatim across all languages
        required_tokens = [
            "scripts/install.sh",
            "scripts/install.ps1",
            "smartbackup --select",
            "smartbackup --select --dry-run",
            "smartbackup --dry-run",
            "smartbackup --manifest-format sqlite",
            "smartbackup --notify",
            "smartbackup --compress zip",
            "smartbackup restore",
            "--conflict rename",
            "smartbackup config list",
            "smartbackup watch",
            "smartbackup daemon install",
            "smartbackup schedule --hours 24",
        ]
        for token in required_tokens:
            assert token in content, f"{lang} README missing required token: {token!r}"
