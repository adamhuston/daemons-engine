# Daemonswright Development Environment Setup (PowerShell)
# Run this script to install development tools and pre-commit hooks

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Daemonswright Development Environment Setup" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Get Python executable from venv
$pythonExe = ".\.venv\Scripts\python.exe"

if (-not (Test-Path $pythonExe)) {
    Write-Host "Error: Virtual environment not found at .venv" -ForegroundColor Red
    Write-Host "Please create a virtual environment first:" -ForegroundColor Yellow
    Write-Host "  python -m venv .venv" -ForegroundColor Yellow
    Write-Host "  .\.venv\Scripts\Activate.ps1" -ForegroundColor Yellow
    exit 1
}

# Install development dependencies
Write-Host "1. Installing development dependencies..." -ForegroundColor Green
$devPackages = @(
    "pytest",
    "pytest-asyncio",
    "pytest-cov",
    "pytest-timeout",
    "pytest-xdist",
    "pre-commit",
    "ruff",
    "black",
    "isort",
    "mypy",
    "safety"
)

& $pythonExe -m pip install --upgrade pip
& $pythonExe -m pip install --upgrade $devPackages

if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to install development dependencies" -ForegroundColor Red
    exit 1
}

Write-Host ""

# Install project dependencies
Write-Host "2. Installing project dependencies..." -ForegroundColor Green
$requirementsFile = ".\backend\requirements.txt"

if (Test-Path $requirementsFile) {
    & $pythonExe -m pip install -r $requirementsFile
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to install project dependencies" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "Warning: $requirementsFile not found" -ForegroundColor Yellow
}

Write-Host ""

# Setup pre-commit hooks
Write-Host "3. Setting up pre-commit hooks..." -ForegroundColor Green
& pre-commit install

if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to install pre-commit hooks" -ForegroundColor Red
    exit 1
}

Write-Host ""

# Run pre-commit on all files
Write-Host "4. Running pre-commit on all files (this may take a while)..." -ForegroundColor Green
Write-Host "   (Some failures are expected on first run)" -ForegroundColor Yellow
pre-commit run --all-files

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Setup Complete!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Run tests: cd backend; pytest" -ForegroundColor White
Write-Host "  2. Check coverage: cd backend; pytest --cov=app --cov-report=html" -ForegroundColor White
Write-Host "  3. Open coverage report: start backend\htmlcov\index.html" -ForegroundColor White
Write-Host ""
Write-Host "Pre-commit hooks are now active and will run on every commit." -ForegroundColor Cyan
Write-Host "To bypass hooks: git commit --no-verify" -ForegroundColor Cyan
Write-Host ""
