"""
Unit tests for multi-language documentation localization (English default + Turkish & German).

Covers both README.md and docs/USER_GUIDE.md along with their localized counterparts under
docs/i18n/. Ensures cross-language switcher links, relative file links, internal and
cross-file GitHub heading anchors, package version parity, and CLI command coverage stay
in sync across all languages.
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
USER_GUIDE_FILES = {
    "en": REPO_ROOT / "docs" / "USER_GUIDE.md",
    "tr": REPO_ROOT / "docs" / "i18n" / "USER_GUIDE.tr.md",
    "de": REPO_ROOT / "docs" / "i18n" / "USER_GUIDE.de.md",
}
ALL_LOCALIZED_DOCS = [
    ("readme", lang, path) for lang, path in README_FILES.items()
] + [
    ("user_guide", lang, path) for lang, path in USER_GUIDE_FILES.items()
]

_MD_LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
_HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*$", re.MULTILINE)


def _github_heading_slug(heading: str) -> str:
    """Compute a GitHub-compatible Markdown heading anchor slug (preserving Unicode letters)."""
    text = heading.strip().lower()
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


class TestDocsLocalization:
    """Contract checks for localized READMEs and User Guides (en, tr, de)."""

    @pytest.mark.parametrize(("doc_kind", "lang", "path"), ALL_LOCALIZED_DOCS)
    def test_doc_exists_and_contains_language_switcher(
        self, doc_kind: str, lang: str, path: Path
    ) -> None:
        assert path.is_file(), f"Missing {doc_kind} for language {lang!r}: {path}"
        content = path.read_text(encoding="utf-8")

        assert "English" in content
        assert "Türkçe" in content
        assert "Deutsch" in content

        active_label = {"en": "**English**", "tr": "**Türkçe**", "de": "**Deutsch**"}[lang]
        assert active_label in content

    @pytest.mark.parametrize(("doc_kind", "lang", "path"), ALL_LOCALIZED_DOCS)
    def test_all_relative_links_and_anchors_resolve(
        self, doc_kind: str, lang: str, path: Path
    ) -> None:
        content = path.read_text(encoding="utf-8")
        local_headings = _extract_heading_slugs(content)

        for target in _MD_LINK_RE.findall(content):
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            if target == "/":
                continue
            if target.startswith("#"):
                anchor = target[1:]
                assert anchor in local_headings, (
                    f"{path.name}: internal anchor '#{anchor}' not found in {sorted(local_headings)}"
                )
                continue

            if "#" in target:
                file_part, anchor = target.split("#", 1)
            else:
                file_part, anchor = target, None

            resolved = (path.parent / file_part).resolve()
            assert resolved.exists(), (
                f"{path.name}: relative link '{target}' resolved to missing path {resolved}"
            )
            if anchor and resolved.suffix.lower() == ".md":
                target_headings = _extract_heading_slugs(resolved.read_text(encoding="utf-8"))
                assert anchor in target_headings, (
                    f"{path.name}: cross-file anchor '{target}' not found in {resolved.name}"
                )

    @pytest.mark.parametrize("lang", ["en", "tr", "de"])
    def test_readme_version_cli_and_user_guide_link_parity(self, lang: str) -> None:
        content = README_FILES[lang].read_text(encoding="utf-8")

        assert f"smartbackup {__version__}" in content
        assert f"v{__version__}" in content

        expected_guide = {"en": "docs/USER_GUIDE.md", "tr": "USER_GUIDE.tr.md", "de": "USER_GUIDE.de.md"}[lang]
        assert expected_guide in content

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

    @pytest.mark.parametrize("lang", ["en", "tr", "de"])
    def test_user_guide_version_and_cli_section_parity(self, lang: str) -> None:
        content = USER_GUIDE_FILES[lang].read_text(encoding="utf-8")

        assert f"smartbackup {__version__}" in content

        required_tokens = [
            "smartbackup --select",
            "smartbackup --select --dry-run",
            "smartbackup --dry-run",
            "--manifest-format",
            "selective_backups",
            "--notify",
            "smartbackup restore",
            "--conflict rename",
            "smartbackup compress",
            "smartbackup watch",
            "smartbackup schedule",
            "smartbackup config",
            "smartbackup daemon install",
            "smartbackup daemon clear-state",
            "DEFAULT_EXCLUSIONS",
        ]
        for token in required_tokens:
            assert token in content, f"{lang} USER_GUIDE missing required token: {token!r}"
