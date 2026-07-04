$ScriptDir = $PSScriptRoot
Set-Location -Path $ScriptDir

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Starting Antigravity Bridge Dashboard" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "[1/2] Starting FastAPI Backend on port 8000..." -ForegroundColor Yellow
Start-Process "python" -ArgumentList "-m uvicorn api_server:app --host 127.0.0.1 --port 8000" -PassThru

Write-Host "[2/2] Starting Next.js Frontend on port 4000..." -ForegroundColor Yellow
Set-Location -Path .\bridge_web
Start-Process "npm.cmd" -ArgumentList "run dev" -PassThru

Write-Host ""
Write-Host "Opening Dashboard in your default browser..." -ForegroundColor Green
Start-Process "http://localhost:4000"

Write-Host "Done! The dashboard is available at: http://localhost:4000" -ForegroundColor Green
Write-Host "The API server is running at: http://localhost:8000" -ForegroundColor Green
Write-Host "Note: It may take 10-15 seconds for Next.js to compile on the first run." -ForegroundColor Gray
