$ScriptDir = $PSScriptRoot
Set-Location -Path $ScriptDir

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Starting Antigravity Bridge Dashboard" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Kill any existing backend/frontend processes on our ports
Write-Host "[0/2] Cleaning up old processes..." -ForegroundColor DarkGray
$ports = @(8000, 4000)
foreach ($port in $ports) {
    $pids = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue |
            Select-Object -ExpandProperty OwningProcess -Unique |
            Where-Object { $_ -ne 0 }
    foreach ($processId in $pids) {
        try {
            Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
            Write-Host "  Killed old process on port $port (PID $processId)" -ForegroundColor DarkGray
        } catch {}
    }
}
Start-Sleep -Seconds 1

Write-Host "[1/2] Starting FastAPI Backend on port 8000..." -ForegroundColor Yellow
Start-Process "python" -ArgumentList "-m uvicorn api_server:app --host 0.0.0.0 --port 8000" -PassThru

Write-Host "[2/2] Starting Next.js Frontend on port 4000..." -ForegroundColor Yellow
Set-Location -Path .\bridge_web
Start-Process "npm.cmd" -ArgumentList "run dev" -PassThru

Write-Host ""
Write-Host "Opening Dashboard in your default browser..." -ForegroundColor Green
Start-Process "http://localhost:4000"

Write-Host "Done! The dashboard is available at: http://localhost:4000" -ForegroundColor Green
Write-Host "The API server is running at: http://localhost:8000" -ForegroundColor Green
Write-Host "Note: It may take 10-15 seconds for Next.js to compile on the first run." -ForegroundColor Gray
