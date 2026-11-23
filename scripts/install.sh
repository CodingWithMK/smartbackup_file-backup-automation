#!/bin/sh
# SmartBackup standalone installer for macOS and Linux (no Python/pip/uv required).
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/CodingWithMK/smartbackup_file-backup-automation/main/scripts/install.sh | sh
#
# Optional environment variables:
#   SMARTBACKUP_VERSION      Release tag to install (e.g. v0.9.0); defaults to latest.
#   SMARTBACKUP_INSTALL_DIR  Destination directory; defaults to "$HOME/.local/bin".

set -eu

REPO="CodingWithMK/smartbackup_file-backup-automation"
INSTALL_DIR="${SMARTBACKUP_INSTALL_DIR:-$HOME/.local/bin}"

fail() {
    printf 'Error: %s\n' "$1" >&2
    exit 1
}

detect_os() {
    os="$(uname -s 2>/dev/null || printf 'unknown')"
    case "$os" in
        Linux)  printf 'linux' ;;
        Darwin) printf 'macos' ;;
        *)      fail "Unsupported operating system: $os (expected Linux or Darwin/macOS)." ;;
    esac
}

detect_arch() {
    os="$1"
    arch="$(uname -m 2>/dev/null || printf 'unknown')"
    case "$arch" in
        x86_64|amd64)
            printf 'x86_64'
            ;;
        aarch64|arm64)
            if [ "$os" = "macos" ]; then
                printf 'arm64'
            else
                printf 'aarch64'
            fi
            ;;
        *)
            fail "Unsupported CPU architecture: $arch (expected x86_64/amd64 or aarch64/arm64)."
            ;;
    esac
}

download_file() {
    url="$1"
    dest="$2"
    if command -v curl >/dev/null 2>&1; then
        curl -fsSL --retry 3 --output "$dest" "$url"
    elif command -v wget >/dev/null 2>&1; then
        wget -qO "$dest" "$url"
    else
        fail "Neither 'curl' nor 'wget' is installed. Install curl and try again."
    fi
}

verify_checksum() {
    file_path="$1"
    asset_name="$2"
    sums_path="$3"

    expected="$(awk -v name="$asset_name" '$2 == name || $2 == "*" name { print $1; exit }' "$sums_path")"
    if [ -z "$expected" ]; then
        printf 'Warning: %s not listed in SHA256SUMS.txt; skipping checksum check.\n' "$asset_name" >&2
        return 0
    fi

    if command -v sha256sum >/dev/null 2>&1; then
        actual="$(sha256sum "$file_path" | awk '{ print $1 }')"
    elif command -v shasum >/dev/null 2>&1; then
        actual="$(shasum -a 256 "$file_path" | awk '{ print $1 }')"
    else
        printf 'Warning: Neither sha256sum nor shasum found; skipping checksum check.\n' >&2
        return 0
    fi

    if [ "$actual" != "$expected" ]; then
        fail "SHA-256 checksum mismatch for $asset_name (expected $expected, got $actual)."
    fi
}

main() {
    os="$(detect_os)"
    arch="$(detect_arch "$os")"
    asset="smartbackup-${os}-${arch}"

    if [ -n "${SMARTBACKUP_VERSION:-}" ]; then
        case "$SMARTBACKUP_VERSION" in
            v*) tag="$SMARTBACKUP_VERSION" ;;
            *)  tag="v$SMARTBACKUP_VERSION" ;;
        esac
        base_url="https://github.com/${REPO}/releases/download/${tag}"
    else
        base_url="https://github.com/${REPO}/releases/latest/download"
    fi

    binary_url="${base_url}/${asset}"
    sums_url="${base_url}/SHA256SUMS.txt"

    tmp_dir="$(mktemp -d 2>/dev/null || mktemp -d -t smartbackup-install)"
    trap 'rm -rf "$tmp_dir"' EXIT INT TERM

    tmp_bin="${tmp_dir}/${asset}"
    tmp_sums="${tmp_dir}/SHA256SUMS.txt"

    printf 'Downloading %s...\n' "$binary_url"
    if ! download_file "$binary_url" "$tmp_bin"; then
        fail "Failed to download ${binary_url}. Check that a release binary exists for ${os}/${arch} at https://github.com/${REPO}/releases"
    fi

    if [ ! -s "$tmp_bin" ]; then
        fail "Downloaded binary is empty: ${binary_url}"
    fi

    if download_file "$sums_url" "$tmp_sums" 2>/dev/null; then
        verify_checksum "$tmp_bin" "$asset" "$tmp_sums"
    fi

    mkdir -p "$INSTALL_DIR"
    chmod 755 "$tmp_bin"
    mv "$tmp_bin" "${INSTALL_DIR}/smartbackup"

    printf 'Installed smartbackup to %s/smartbackup\n' "$INSTALL_DIR"

    if "${INSTALL_DIR}/smartbackup" --version >/dev/null 2>&1; then
        "${INSTALL_DIR}/smartbackup" --version
    fi

    case ":${PATH:-}:" in
        *":${INSTALL_DIR}:"*)
            printf 'Run "smartbackup --help" to get started.\n'
            ;;
        *)
            printf '\nNote: %s is not currently in your PATH.\n' "$INSTALL_DIR"
            printf 'Add it to your shell profile (~/.bashrc, ~/.zshrc, or ~/.profile):\n\n'
            printf '    export PATH="%s:$PATH"\n\n' "$INSTALL_DIR"
            printf 'Then restart your terminal or run: source ~/.bashrc (or ~/.zshrc)\n'
            ;;
    esac
}

main "$@"
