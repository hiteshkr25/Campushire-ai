# PowerShell Production environment startup script for Windows
$env:FLASK_ENV="production"
$env:FLASK_DEBUG="false"

Write-Host "Validating database schema and seeding values..." -ForegroundColor Green
python scripts/init_db.py

Write-Host "Starting Flask development server as fallback on port 8000..." -ForegroundColor Cyan
python run.py
