#requires -Version 5.1

[CmdletBinding()]
param(
    [switch]$Setup
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Find-HarnessPython {
    $candidates = @()

    if (-not [string]::IsNullOrWhiteSpace($env:VIRTUAL_ENV)) {
        $candidates += @{
            Executable = (Join-Path $env:VIRTUAL_ENV "Scripts\python.exe")
            Prefix = @()
            IsPath = $true
        }
    }
    if (-not [string]::IsNullOrWhiteSpace($env:CONDA_PREFIX)) {
        $candidates += @{
            Executable = (Join-Path $env:CONDA_PREFIX "python.exe")
            Prefix = @()
            IsPath = $true
        }
    }
    $candidates += @{
        Executable = "py"
        Prefix = @("-3")
        IsPath = $false
    }
    $candidates += @{
        Executable = "python"
        Prefix = @()
        IsPath = $false
    }
    $candidates += @{
        Executable = "python3"
        Prefix = @()
        IsPath = $false
    }

    foreach ($candidate in $candidates) {
        $executable = $candidate.Executable
        if ($candidate.IsPath) {
            if (-not (Test-Path -LiteralPath $executable -PathType Leaf)) {
                continue
            }
        }
        else {
            $command = Get-Command `
                -Name $executable `
                -CommandType Application `
                -ErrorAction SilentlyContinue |
                Select-Object -First 1
            if ($null -eq $command) {
                continue
            }
            $executable = $command.Path
        }

        try {
            $probeArguments = @()
            $probeArguments += $candidate.Prefix
            $probeArguments += "-c"
            $probeArguments += (
                "import sys; raise SystemExit(" +
                "0 if sys.version_info >= (3, 10) else 1)"
            )
            & $executable @probeArguments *> $null
            if ($LASTEXITCODE -eq 0) {
                return @{
                    Executable = $executable
                    Prefix = $candidate.Prefix
                }
            }
        }
        catch {
            continue
        }
    }

    return $null
}

$automaticInstallName = "PYTHON_MANAGER_AUTOMATIC_INSTALL"
$previousAutomaticInstall = [Environment]::GetEnvironmentVariable(
    $automaticInstallName,
    [EnvironmentVariableTarget]::Process
)
$nativePreferenceExists = Test-Path `
    -LiteralPath "Variable:\PSNativeCommandUseErrorActionPreference"
$previousNativePreference = $null
if ($nativePreferenceExists) {
    $previousNativePreference = $PSNativeCommandUseErrorActionPreference
    $PSNativeCommandUseErrorActionPreference = $false
}

$python = $null
$locationPushed = $false
$exitCode = 1
try {
    [Environment]::SetEnvironmentVariable(
        $automaticInstallName,
        "false",
        [EnvironmentVariableTarget]::Process
    )
    try {
        $python = Find-HarnessPython
    }
    finally {
        [Environment]::SetEnvironmentVariable(
            $automaticInstallName,
            $previousAutomaticInstall,
            [EnvironmentVariableTarget]::Process
        )
    }

    if ($null -eq $python) {
        [Console]::Error.WriteLine(
            "ERROR: Harness Core requires Python 3.10 or newer. " +
            "Checked active virtual environments, py -3, python, and python3."
        )
    }
    else {
        Push-Location -LiteralPath $PSScriptRoot
        $locationPushed = $true

        $harnessArguments = @()
        $harnessArguments += $python.Prefix
        $harnessArguments += (Join-Path $PSScriptRoot "scripts\harness.py")
        $harnessArguments += "init"
        if ($Setup.IsPresent) {
            $harnessArguments += "--setup"
        }

        & $python.Executable @harnessArguments
        $exitCode = $LASTEXITCODE
    }
}
catch {
    [Console]::Error.WriteLine("ERROR: " + $_.Exception.Message)
    $exitCode = 1
}
finally {
    if ($locationPushed) {
        Pop-Location
    }
    [Environment]::SetEnvironmentVariable(
        $automaticInstallName,
        $previousAutomaticInstall,
        [EnvironmentVariableTarget]::Process
    )
    if ($nativePreferenceExists) {
        $PSNativeCommandUseErrorActionPreference = $previousNativePreference
    }
}

exit $exitCode
