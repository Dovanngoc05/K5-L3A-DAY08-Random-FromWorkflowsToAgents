# Run from src/: .\scripts\verify_lab9.ps1
$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
$lab9Python = Join-Path $PSScriptRoot '..\.venv\Scripts\python.exe'
$lab9Log = Join-Path $PSScriptRoot '..\..\docs\lab9_verification.txt'
Set-Content -LiteralPath $lab9Log -Value 'Lab 9 verification — actual command output' -Encoding UTF8

function Invoke-Lab9Check {
    param([string[]]$CommandArgs, [int]$ExpectedExit = 0)
    $line = 'python ' + ($CommandArgs -join ' ')
    Write-Output $line
    Add-Content -LiteralPath $lab9Log -Value "`n> $line" -Encoding UTF8
    $output = & $lab9Python @CommandArgs 2>&1
    $exitCode = $LASTEXITCODE
    $output | ForEach-Object { Write-Output $_; Add-Content -LiteralPath $lab9Log -Value $_ -Encoding UTF8 }
    Add-Content -LiteralPath $lab9Log -Value "exit code: $exitCode (expected $ExpectedExit)" -Encoding UTF8
    if ($exitCode -ne $ExpectedExit) { throw "Unexpected exit code for $line : $exitCode" }
}

Invoke-Lab9Check -CommandArgs @('-m','lab9.smoke')
Invoke-Lab9Check -CommandArgs @('-m','lab9.evalset','--check')
Invoke-Lab9Check -CommandArgs @('-m','lab9.evalset','--v2')
Invoke-Lab9Check -CommandArgs @('-m','lab9.eval','--shape','swarm','--out','reports/eval_pr.json')
Invoke-Lab9Check -CommandArgs @('-m','lab9.gate','--pr','reports/eval_pr.json','--baseline','reports/baseline_v1.json')
Invoke-Lab9Check -CommandArgs @('-m','lab9.ci_check','--pr','reports/eval_pr.json','--baseline','reports/baseline_v1.json')
Invoke-Lab9Check -CommandArgs @('-m','lab9.gate','--pr','reports/eval_fixed.json','--baseline','reports/baseline_v1.json')
Invoke-Lab9Check -CommandArgs @('-m','lab9.gate','--pr','reports/eval_seeded_regression.json','--baseline','reports/baseline_v1.json') -ExpectedExit 1
Invoke-Lab9Check -CommandArgs @('-m','lab9.mutation','--detect')
Invoke-Lab9Check -CommandArgs @('-m','lab9.mutation','--spec','config/metric_spec_v2.yaml','--aa','66,77,88,99,110')
Invoke-Lab9Check -CommandArgs @('-m','lab9.mutation','--spec','config/metric_spec_v2.yaml','--baseline','reports/baseline_v2.json')
Invoke-Lab9Check -CommandArgs @('-m','lab9.traps','--pr','reports/eval_slice_regression_v2.json','--baseline','reports/baseline_v2.json','--spec','config/metric_spec_v2.yaml')
foreach ($trapName in @('evaluator_errors_as_nan','dropped_failing_rows','cherry_picked_seeds','loosened_spec')) {
    $trapArgs = @('-m','lab9.gate','--pr',"reports/traps/$trapName.json",'--baseline','reports/baseline_v2.json','--spec','config/metric_spec_v2.yaml')
    if ($trapName -eq 'loosened_spec') {
        $trapArgs = @('-m','lab9.gate','--pr',"reports/traps/$trapName.json",'--baseline','reports/baseline_v2.json','--spec',"reports/traps/$trapName.spec.yaml",'--base-spec','config/metric_spec_v2.yaml')
    }
    Invoke-Lab9Check -CommandArgs $trapArgs -ExpectedExit 1
}
Write-Output "Verification complete: $lab9Log"
