# ArbPlus v2.0 - Full test suite runner (PowerShell)
# Runs all .arb examples recursively under the Examples folder.
# Usage: powershell -ExecutionPolicy Bypass -File run_examples.ps1

Set-StrictMode -Version Latest
Set-Location $PSScriptRoot

$pass = 0
$fail = 0
$skip = 0
$failedFiles = @()

# Child scripts called by 24_run_arb.arb - skip these
$skipFiles = @("child.arb", "child_types.arb", "child_noreturn.arb")
$examplesRoot = Join-Path $PSScriptRoot "AI_Examples"

if (-not (Test-Path -LiteralPath $examplesRoot)) {
    Write-Error "Examples directory not found: $examplesRoot"
    exit 1
}

Write-Host "Running ArbPlus v2.0 test suite..."
Write-Host "================================="
Write-Host ""

$files = Get-ChildItem -Path $examplesRoot -Recurse -File -Filter "*.arb" | Sort-Object FullName

if ($files.Count -eq 0) {
    Write-Error "No .arb example files found under $examplesRoot"
    exit 1
}

foreach ($file in $files) {
    $relPath = $file.FullName.Substring($PSScriptRoot.Length + 1).Replace('\\', '/')

    if ($skipFiles -contains $file.Name) {
        Write-Host "Skipping: $relPath (called by 24_run_arb.arb)"
        $script:skip++
        continue
    }

    Write-Host "Running: $relPath"
    $output = & python interpreter.py $file.FullName 2>&1
    $exitCode = $LASTEXITCODE

    if ($exitCode -eq 0) {
        Write-Host "  PASS" -ForegroundColor Green
        $script:pass++
    } else {
        Write-Host "  FAIL" -ForegroundColor Red
        $script:fail++
        $script:failedFiles += $relPath

        if ($output) {
            foreach ($line in $output) {
                Write-Host "  $line"
            }
        }
    }
}

Write-Host ""
Write-Host "============================="
Write-Host "Results: $pass passed, $fail failed, $skip skipped"
if ($fail -gt 0) {
    Write-Host "Failed files:"
    foreach ($f in $failedFiles) {
        Write-Host "  - $f"
    }
}
Write-Host "============================="

if ($fail -gt 0) {
    exit 1
}

exit 0
