# ArbPlus v2.0 - Full test suite runner (PowerShell)
# Runs all .arb examples + module file
# Usage: powershell -ExecutionPolicy Bypass -File run_examples.ps1

Set-Location $PSScriptRoot

$pass = 0
$fail = 0
$failedFiles = @()

# Child scripts called by 24_run_arb.arb - skip these
$skipFiles = @("child.arb", "child_types.arb", "child_noreturn.arb")

Write-Host "Running ArbPlus v2.0 test suite..."
Write-Host "================================="
Write-Host ""

Get-ChildItem -Path "examples" -Filter "*.arb" | Sort-Object Name | ForEach-Object {
    $file = $_.FullName
    $relPath = "examples/$($_.Name)"

    # Check if this file should be skipped
    if ($skipFiles -contains $_.Name) {
        Write-Host "Skipping: $relPath (called by 24_run_arb.arb)"
        return
    }

    Write-Host "Running: $relPath"
    $output = & python interpreter.py $file 2>&1
    $exitCode = $LASTEXITCODE

    if ($exitCode -eq 0) {
        Write-Host "  PASS" -ForegroundColor Green
        $script:pass++
    } else {
        Write-Host "  FAIL" -ForegroundColor Red
        $script:fail++
        $script:failedFiles += $relPath
    }
}

Write-Host ""
Write-Host "============================="
Write-Host "Results: $pass passed, $fail failed"
if ($fail -gt 0) {
    Write-Host "Failed files:"
    foreach ($f in $failedFiles) {
        Write-Host "  - $f"
    }
}
Write-Host "============================="
