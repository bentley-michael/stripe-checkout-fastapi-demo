# save as .\smoke_test.ps1 and Run with PowerShell
param(
  [string]$BaseUrl = "http://127.0.0.1:8000"
)

$project = Split-Path -Parent $MyInvocation.MyCommand.Path
$python  = Join-Path $project ".venv\Scripts\python.exe"

function Wait-Port($host, $port, $timeoutSec=20) {
  $deadline = (Get-Date).AddSeconds($timeoutSec)
  do {
    if ((Test-NetConnection $host -Port $port -WarningAction SilentlyContinue).TcpTestSucceeded) { return $true }
    Start-Sleep -Milliseconds 500
  } while ((Get-Date) -lt $deadline)
  return $false
}

# 1) ensure server is running
$serverStarted = $false
if (-not (Test-NetConnection 127.0.0.1 -Port 8000 -WarningAction SilentlyContinue).TcpTestSucceeded) {
  if (-not (Test-Path $python)) { throw "Venv python not found at $python" }
  $serverProc = Start-Process -FilePath $python -ArgumentList "-m","uvicorn","app.main:app","--reload" -PassThru -WindowStyle Minimized
  $serverStarted = $true
  if (-not (Wait-Port 127.0.0.1 8000 25)) { throw "Server didn't open port 8000 in time." }
}

# 2) /pdf/weasy-test -> TariffTest_*.pdf
$payload = @{
  country_of_origin = "CN"
  destination       = "US"
  hs_code           = "9403.60.8081"
  incoterm          = "FOB"
  base_rate         = 0.03
  tariff_rate       = 0.25
  line_items        = @(@{ sku="A1"; description="Chair"; qty=10; unit_value=25; unit_wt=2 })
  totals            = @{ merch_value=250; freight=50; insurance=10; duty=62.5; brokerage=0; other_fees=0; total_landed=372.5 }
} | ConvertTo-Json -Depth 6

$testFile = Join-Path $project ("TariffTest_{0:yyyyMMdd_HHmmss}.pdf" -f (Get-Date))
Invoke-WebRequest -Uri "$BaseUrl/pdf/weasy-test" -Method POST -ContentType 'application/json' -Body $payload -OutFile $testFile
if ((Test-Path $testFile) -and ((Get-Item $testFile).Length -gt 0)) {
  Write-Host "PASS /pdf/weasy-test -> $testFile"
} else { Write-Host "FAIL /pdf/weasy-test" -ForegroundColor Red }

# 3) /generate -> TariffOrder_*.pdf
$form = @{
  country_of_origin = 'CN'
  destination       = 'US'
  hs_code           = '9403.60.8081'
  incoterm          = 'FOB'
  base_rate         = '0.03'
  tariff_rate       = '0.25'
  freight           = '50'
  insurance         = '10'
  brokerage         = '0'
  other_fees        = '0'
  sku               = 'A1'
  description       = 'Chair'
  qty               = '10'
  unit_value        = '25'
  unit_wt           = '2'
}
$orderFile = Join-Path $project ("TariffOrder_{0:yyyyMMdd_HHmmss}.pdf" -f (Get-Date))
Invoke-WebRequest -Uri "$BaseUrl/generate" -Method POST -Body $form -OutFile $orderFile
if ((Test-Path $orderFile) -and ((Get-Item $orderFile).Length -gt 0)) {
  Write-Host "PASS /generate -> $orderFile"
} else { Write-Host "FAIL /generate" -ForegroundColor Red }

# 4) stop server if we started it
if ($serverStarted -and $serverProc -and -not $serverProc.HasExited) {
  Stop-Process -Id $serverProc.Id -ErrorAction SilentlyContinue
  Write-Host "Server stopped."
}
