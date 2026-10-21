param([string]$Webots = $env:WEBOTS_EXECUTABLE)
$ErrorActionPreference = 'Stop'
$taskRepo = Split-Path $PSScriptRoot -Parent
if (-not $Webots) {
    $taskCandidates = @(
        (Join-Path $taskRepo '..\.tools\Webots\msys64\mingw64\bin\webots.exe'),
        'C:\Program Files\Webots\msys64\mingw64\bin\webots.exe',
        (Join-Path $env:LOCALAPPDATA 'Programs\Webots\msys64\mingw64\bin\webots.exe')
    )
    $Webots = $taskCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}
if (-not $Webots) { throw 'Webots not found. Pass -Webots PATH or set WEBOTS_EXECUTABLE.' }
python (Join-Path $PSScriptRoot 'build_worlds.py')
if ($LASTEXITCODE -ne 0) { throw 'World generation failed.' }
& $Webots '--batch' '--mode=realtime' '--stdout' '--stderr' (Join-Path $taskRepo 'sim\webots\worlds\inspection_room.wbt')
