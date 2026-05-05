# Task Scheduler entrypoint for Auto Play Agent (Windows).
# Register via: scripts\setup-scheduler.ps1
#Requires -Version 5.1

$AgentDir  = Split-Path $PSScriptRoot -Parent
$LogFile   = "$AgentDir\logs\$(Get-Date -Format 'yyyy-MM-dd').log"

New-Item -ItemType Directory -Force -Path "$AgentDir\logs" | Out-Null

function Write-Log($msg) {
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $msg"
    Add-Content -Path $LogFile -Value $line -Encoding UTF8
    Write-Host $line
}

# Redirect all output to log
Start-Transcript -Path $LogFile -Append | Out-Null

Write-Log ""
Write-Log "=== Auto Play Agent start ============================================="

# Load .env
$EnvFile = "$AgentDir\.env"
if (Test-Path $EnvFile) {
    Get-Content $EnvFile | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+)=(.+)$') {
            [System.Environment]::SetEnvironmentVariable($Matches[1].Trim(), $Matches[2].Trim(), 'Process')
        }
    }
}

$Port = if ($env:OPENCODE_PORT) { $env:OPENCODE_PORT } else { "4096" }
$ProjectDir = $env:PROJECT_DIR

if (-not $ProjectDir) {
    Write-Log "ERROR: PROJECT_DIR is not set in .env"
    Stop-Transcript | Out-Null
    exit 1
}

# Start OpenCode if not already running
$opencodeProc = $null
try {
    Invoke-WebRequest "http://localhost:$Port/health" -TimeoutSec 3 -ErrorAction Stop | Out-Null
    Write-Log "OpenCode already running on port $Port"
} catch {
    Write-Log "Starting OpenCode on port $Port..."
    $opencodeProc = Start-Process -FilePath "opencode" `
        -ArgumentList "serve --port $Port" `
        -WorkingDirectory $ProjectDir `
        -WindowStyle Hidden -PassThru

    # Wait up to 30 s for OpenCode to be ready
    $ready = $false
    for ($i = 1; $i -le 30; $i++) {
        Start-Sleep -Seconds 1
        try {
            Invoke-WebRequest "http://localhost:$Port/health" -TimeoutSec 2 -ErrorAction Stop | Out-Null
            Write-Log "OpenCode ready (${i}s)"
            $ready = $true
            break
        } catch {}
    }
    if (-not $ready) {
        Write-Log "ERROR: OpenCode did not start within 30s"
        Stop-Transcript | Out-Null
        exit 1
    }
}

# Run agent
Set-Location $AgentDir
Write-Log "Running agent..."
uv run apa
$exitCode = $LASTEXITCODE

# Stop OpenCode only if this script started it
if ($opencodeProc) {
    Write-Log "Stopping OpenCode (PID $($opencodeProc.Id))..."
    Stop-Process -Id $opencodeProc.Id -Force -ErrorAction SilentlyContinue
}

Write-Log "=== Done (exit $exitCode) ============================================="
Stop-Transcript | Out-Null
exit $exitCode
