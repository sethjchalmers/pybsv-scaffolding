# PowerShell script to setup Teranode Teratestnet on Windows (via WSL2)
# This script helps automate the setup process

param(
    [switch]$NoNgrok,
    [switch]$CheckOnly
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  BSV Teranode Teratestnet Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check prerequisites
function Test-Prerequisites {
    $errors = @()

    # Check Docker
    Write-Host "Checking Docker..." -ForegroundColor Yellow
    try {
        $dockerVersion = docker --version 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  [OK] Docker: $dockerVersion" -ForegroundColor Green
        } else {
            $errors += "Docker is not installed or not running"
        }
    } catch {
        $errors += "Docker is not installed or not in PATH"
    }

    # Check Docker Compose
    Write-Host "Checking Docker Compose..." -ForegroundColor Yellow
    try {
        $composeVersion = docker compose version 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  [OK] Docker Compose: $composeVersion" -ForegroundColor Green
        } else {
            $errors += "Docker Compose is not available"
        }
    } catch {
        $errors += "Docker Compose is not available"
    }

    # Check Git
    Write-Host "Checking Git..." -ForegroundColor Yellow
    try {
        $gitVersion = git --version 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  [OK] Git: $gitVersion" -ForegroundColor Green
        } else {
            $errors += "Git is not installed"
        }
    } catch {
        $errors += "Git is not installed or not in PATH"
    }

    # Check WSL2 (for running bash scripts)
    Write-Host "Checking WSL2..." -ForegroundColor Yellow
    try {
        $wslVersion = wsl --status 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  [OK] WSL2 is available" -ForegroundColor Green
        } else {
            Write-Host "  [WARN] WSL2 may not be configured (optional for Docker Desktop)" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "  [WARN] WSL2 check skipped" -ForegroundColor Yellow
    }

    # Check available disk space
    Write-Host "Checking disk space..." -ForegroundColor Yellow
    $drive = (Get-Location).Drive
    $freeSpaceGB = [math]::Round((Get-PSDrive $drive.Name).Free / 1GB, 2)
    if ($freeSpaceGB -ge 40) {
        Write-Host "  [OK] Free disk space: $($freeSpaceGB)GB (40GB+ required)" -ForegroundColor Green
    } else {
        $errors += "Insufficient disk space: $($freeSpaceGB)GB (need 40GB+)"
    }

    # Check RAM (approximate)
    Write-Host "Checking system memory..." -ForegroundColor Yellow
    $totalRAM = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 2)
    if ($totalRAM -ge 16) {
        Write-Host "  [OK] Total RAM: $($totalRAM)GB (32GB+ recommended)" -ForegroundColor Green
    } else {
        Write-Host "  [WARN] Total RAM: $($totalRAM)GB (32GB+ recommended)" -ForegroundColor Yellow
    }

    Write-Host ""

    if ($errors.Count -gt 0) {
        Write-Host "Errors found:" -ForegroundColor Red
        foreach ($err in $errors) {
            Write-Host "  [X] $err" -ForegroundColor Red
        }
        return $false
    }

    Write-Host "All prerequisites met!" -ForegroundColor Green
    return $true
}

# Clone Teratestnet repository
function Get-TeratestnetRepo {
    $repoPath = Join-Path (Get-Location) "teranode-teratestnet"

    if (Test-Path $repoPath) {
        Write-Host "Teratestnet repository already exists at: $repoPath" -ForegroundColor Yellow
        $update = Read-Host "Do you want to update it? (y/n)"
        if ($update -eq "y") {
            Push-Location $repoPath
            git pull
            Pop-Location
        }
    } else {
        Write-Host "Cloning Teratestnet repository..." -ForegroundColor Yellow
        git clone https://github.com/bsv-blockchain/teranode-teratestnet.git
    }

    return $repoPath
}

# Main execution
Write-Host "Step 1: Checking Prerequisites" -ForegroundColor Cyan
Write-Host "==============================" -ForegroundColor Cyan
$prereqMet = Test-Prerequisites

if ($CheckOnly) {
    exit
}

if (-not $prereqMet) {
    Write-Host ""
    Write-Host "Please install missing prerequisites before continuing." -ForegroundColor Red
    Write-Host ""
    Write-Host "Installation links:" -ForegroundColor Yellow
    Write-Host "  Docker Desktop: https://docker.com/products/docker-desktop" -ForegroundColor White
    Write-Host "  Git: https://git-scm.com/download/win" -ForegroundColor White
    Write-Host "  ngrok: https://ngrok.com/download" -ForegroundColor White
    exit 1
}

Write-Host ""
Write-Host "Step 2: Clone Teratestnet Repository" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
$repoPath = Get-TeratestnetRepo

Write-Host ""
Write-Host "Step 3: Setup Instructions" -ForegroundColor Cyan
Write-Host "==========================" -ForegroundColor Cyan
Write-Host ""
Write-Host "The Teratestnet setup uses bash scripts. On Windows, you have two options:" -ForegroundColor Yellow
Write-Host ""
Write-Host "Option A: Use Git Bash (Recommended)" -ForegroundColor Green
Write-Host "  1. Open Git Bash" -ForegroundColor White
Write-Host "  2. cd $(Resolve-Path $repoPath)" -ForegroundColor White
Write-Host "  3. ./start-teratestnet.sh" -ForegroundColor White
Write-Host ""
Write-Host "Option B: Use WSL2" -ForegroundColor Green
Write-Host "  1. Open WSL terminal" -ForegroundColor White
Write-Host "  2. cd /mnt/c/Users/Seth/Code/monitized-llm/teranode-teratestnet" -ForegroundColor White
Write-Host "  3. ./start-teratestnet.sh" -ForegroundColor White
Write-Host ""
Write-Host "During setup you will be prompted for:" -ForegroundColor Yellow
Write-Host "  - ngrok domain (or use --no-ngrok if you have a public IP)" -ForegroundColor White
Write-Host "  - RPC username" -ForegroundColor White
Write-Host "  - RPC password" -ForegroundColor White
Write-Host "  - Optional Miner Tag" -ForegroundColor White
Write-Host ""
Write-Host "After setup, update your .env file with the RPC credentials!" -ForegroundColor Cyan
Write-Host ""

# Ask if user wants to proceed with Docker in PowerShell
$proceed = Read-Host "Would you like to start Docker services directly? (This runs 'docker compose up -d') (y/n)"
if ($proceed -eq "y") {
    Push-Location $repoPath

    # Check if settings have been configured
    $settingsPath = Join-Path $repoPath "base\settings_local.conf"
    if (-not (Test-Path $settingsPath)) {
        Write-Host ""
        Write-Host "Warning: settings_local.conf not found!" -ForegroundColor Red
        Write-Host "You need to run the setup script first to configure your node." -ForegroundColor Yellow
        Write-Host "Run: ./start-teratestnet.sh in Git Bash or WSL2" -ForegroundColor Yellow
        Pop-Location
        exit 1
    }

    Write-Host "Starting Docker services..." -ForegroundColor Yellow
    docker compose up -d

    Write-Host ""
    Write-Host "Waiting for services to start..." -ForegroundColor Yellow
    Start-Sleep -Seconds 10

    Write-Host ""
    Write-Host "Service Status:" -ForegroundColor Cyan
    docker compose ps

    Pop-Location
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Configure your node (if not done): ./start-teratestnet.sh" -ForegroundColor White
Write-Host "  2. Update .env with your RPC credentials" -ForegroundColor White
Write-Host "  3. Activate Python venv: .\venv\Scripts\activate" -ForegroundColor White
Write-Host "  4. Install deps: pip install -r requirements.txt" -ForegroundColor White
Write-Host "  5. Run health check: python scripts\check_node.py" -ForegroundColor White
