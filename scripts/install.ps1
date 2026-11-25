# SmartBackup standalone installer for Windows (no Python/pip/uv required).
#
# Usage:
#   irm https://raw.githubusercontent.com/CodingWithMK/smartbackup_file-backup-automation/main/scripts/install.ps1 | iex
#
# Optional environment variables:
#   $env:SMARTBACKUP_VERSION      Release tag to install (e.g. v0.9.0); defaults to latest.
#   $env:SMARTBACKUP_INSTALL_DIR  Destination directory; defaults to "$env:LOCALAPPDATA\Programs\SmartBackup".

$ErrorActionPreference = "Stop"

# Ensure TLS 1.2 on older Windows PowerShell 5.1 hosts
try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
} catch {
    # Ignore on newer PowerShell where TLS 1.2+ is already default
}

$Repo = "CodingWithMK/smartbackup_file-backup-automation"
$AssetName = "smartbackup-windows-x86_64.exe"
$InstallDir = if ($env:SMARTBACKUP_INSTALL_DIR) {
    $env:SMARTBACKUP_INSTALL_DIR
} else {
    Join-Path $env:LOCALAPPDATA "Programs\SmartBackup"
}

function Assert-SupportedArchitecture {
    $arch = $env:PROCESSOR_ARCHITECTURE
    if ($env:PROCESSOR_ARCHITEW6432) {
        $arch = $env:PROCESSOR_ARCHITEW6432
    }
    switch ($arch) {
        "AMD64" { return }
        "ARM64" { return } # Windows ARM64 runs x86_64 binaries via built-in emulation
        default {
            throw "Unsupported Windows architecture '$arch'. SmartBackup standalone binaries require 64-bit Windows (x86_64)."
        }
    }
}

function Get-BaseDownloadUrl {
    if ($env:SMARTBACKUP_VERSION) {
        $tag = $env:SMARTBACKUP_VERSION.Trim()
        if (-not $tag.StartsWith("v")) {
            $tag = "v$tag"
        }
        return "https://github.com/$Repo/releases/download/$tag"
    }
    return "https://github.com/$Repo/releases/latest/download"
}

function Verify-Checksum {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string]$ExpectedAsset,
        [Parameter(Mandatory = $true)][string]$SumsPath
    )

    $expectedHash = $null
    foreach ($line in Get-Content -Path $SumsPath -Encoding UTF8) {
        if ($line -match '^\s*([0-9a-fA-F]{64})\s+\*?(.+?)\s*$') {
            if ($Matches[2] -eq $ExpectedAsset) {
                $expectedHash = $Matches[1].ToLowerInvariant()
                break
            }
        }
    }

    if (-not $expectedHash) {
        Write-Warning "$ExpectedAsset not listed in SHA256SUMS.txt; skipping checksum verification."
        return
    }

    $actualHash = (Get-FileHash -Path $FilePath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualHash -ne $expectedHash) {
        throw "SHA-256 checksum mismatch for $ExpectedAsset (expected $expectedHash, got $actualHash)."
    }
}

function Add-ToUserPath {
    param([Parameter(Mandatory = $true)][string]$Directory)

    $normalizedTarget = $Directory.TrimEnd('\')

    # Update current PowerShell session PATH
    $sessionEntries = ($env:Path -split ';') | Where-Object { $_ -ne '' }
    $inSession = $sessionEntries | Where-Object { $_.TrimEnd('\') -ieq $normalizedTarget }
    if (-not $inSession) {
        $env:Path = "$Directory;$env:Path"
    }

    # Persist to Windows User PATH
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $userEntries = if ($userPath) {
        ($userPath -split ';') | Where-Object { $_ -ne '' }
    } else {
        @()
    }
    $inUser = $userEntries | Where-Object { $_.TrimEnd('\') -ieq $normalizedTarget }
    if (-not $inUser) {
        $newUserPath = if ($userEntries.Count -gt 0) {
            ($userEntries + $Directory) -join ';'
        } else {
            $Directory
        }
        [Environment]::SetEnvironmentVariable("Path", $newUserPath, "User")
        Write-Host "Added '$Directory' to your User PATH."
    }
}

Assert-SupportedArchitecture

$BaseUrl = Get-BaseDownloadUrl
$BinaryUrl = "$BaseUrl/$AssetName"
$SumsUrl = "$BaseUrl/SHA256SUMS.txt"

$TempDir = Join-Path ([IO.Path]::GetTempPath()) ("smartbackup-install-" + [Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $TempDir -Force | Out-Null

try {
    $TempBinary = Join-Path $TempDir $AssetName
    $TempSums = Join-Path $TempDir "SHA256SUMS.txt"

    Write-Host "Downloading $BinaryUrl..."
    try {
        Invoke-WebRequest -Uri $BinaryUrl -OutFile $TempBinary -UseBasicParsing
    } catch {
        throw "Failed to download $BinaryUrl. Verify the release exists at https://github.com/$Repo/releases. Details: $($_.Exception.Message)"
    }

    if (-not (Test-Path $TempBinary) -or (Get-Item $TempBinary).Length -eq 0) {
        throw "Downloaded binary is missing or empty: $BinaryUrl"
    }

    try {
        Invoke-WebRequest -Uri $SumsUrl -OutFile $TempSums -UseBasicParsing
        Verify-Checksum -FilePath $TempBinary -ExpectedAsset $AssetName -SumsPath $TempSums
    } catch {
        if ($_.Exception.Message -like "*checksum mismatch*") {
            throw
        }
        Write-Warning "Could not download SHA256SUMS.txt; skipping checksum verification."
    }

    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
    $TargetExe = Join-Path $InstallDir "smartbackup.exe"
    Move-Item -Path $TempBinary -Destination $TargetExe -Force

    Add-ToUserPath -Directory $InstallDir

    Write-Host "Installed smartbackup to $TargetExe"
    & $TargetExe --version
    Write-Host "Run 'smartbackup --help' to get started (open a new terminal if 'smartbackup' is not recognized in other shells)."
} finally {
    if (Test-Path $TempDir) {
        Remove-Item -Path $TempDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}
