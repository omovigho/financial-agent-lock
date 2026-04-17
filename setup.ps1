# Agent-Lock Setup Script for Windows
# Run: powershell -ExecutionPolicy Bypass -File setup.ps1

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptRoot

Write-Host "Agent-Lock Setup Script" -ForegroundColor Cyan
Write-Host "==========================" -ForegroundColor Cyan

# Setup backend
Write-Host "Setting up backend..." -ForegroundColor Yellow
Push-Location backend
python -m venv venv
& .\venv\Scripts\python.exe -m pip install -r requirements.txt
Pop-Location

# Setup frontend
Write-Host "Setting up frontend..." -ForegroundColor Yellow
Push-Location frontend
npm install
Pop-Location

# Initialize database
Write-Host "Initializing database..." -ForegroundColor Yellow
Push-Location backend
& .\venv\Scripts\python.exe -c "from database import init_db; init_db(); print('Database initialized')"
Pop-Location

Write-Host "Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Backend: cd backend; .\venv\Scripts\Activate.ps1; python app.py"
Write-Host "2. Frontend: cd frontend; npm run dev"
Write-Host "3. Open http://localhost:3000"
Write-Host ""
Write-Host "Demo login: Use any email and password from test_usage.txt"
