# Development Environment Setup

This document explains how to set up your development environment using Nix flakes and direnv.

## Prerequisites

### Required

- **Nix** (with flakes enabled)
- **direnv** (will be installed automatically if using Nix)
- **Git**

### Optional

- Docker (for running MongoDB, Redis, PostgreSQL)
- Docker Compose

## Quick Start (Automated)

Run the automated setup script:

```bash
./setup_dev_env.sh
```

This script will:
1. Check for Nix installation
2. Enable Nix flakes
3. Install and configure direnv
4. Build the development environment
5. Install all Python dependencies
6. Run basic tests

## Manual Setup

### 1. Install Nix (if not already installed)

```bash
# Using Determinate Systems installer (recommended)
curl --proto '=https' --tlsv1.2 -sSf -L https://install.determinate.systems/nix | sh -s -- install

# Or using official installer
sh <(curl -L https://nixos.org/nix/install) --daemon
```

### 2. Enable Nix Flakes

Add to `~/.config/nix/nix.conf`:

```
experimental-features = nix-command flakes
```

### 3. Install direnv

```bash
# Using Nix
nix profile install nixpkgs#direnv

# Or using your package manager
# Ubuntu/Debian
sudo apt install direnv

# macOS
brew install direnv
```

### 4. Hook direnv to Your Shell

Add to your shell RC file (`~/.bashrc`, `~/.zshrc`, etc.):

```bash
eval "$(direnv hook bash)"  # For bash
eval "$(direnv hook zsh)"   # For zsh
```

Reload your shell:

```bash
source ~/.bashrc  # or ~/.zshrc
```

### 5. Clone and Enter Project

```bash
cd /path/to/binanceTradingBot

# Allow direnv for this directory
direnv allow

# Or manually enter the environment
nix develop
```

The environment will automatically activate when you `cd` into the directory (thanks to direnv).

## What Gets Installed?

### System Packages

- Python 3.12
- Docker & Docker Compose
- MongoDB, Redis, PostgreSQL clients
- Git, Make, curl, wget, jq
- Development tools (ruff, pyright, mypy, black, flake8)

### Python Packages

All packages from `requirements.txt`:

- **Core Framework**: FastAPI, Uvicorn, Pydantic
- **Database**: Motor, PyMongo, Redis, AsyncPG, SQLAlchemy
- **Task Queue**: Celery, Flower
- **Data Processing**: NumPy, Pandas, Numba, TA
- **Testing**: pytest, pytest-asyncio, pytest-cov
- **And many more...**

Total: ~100 packages

## Project Structure

```
binanceTradingBot/
├── flake.nix                   # Nix flake configuration
├── .envrc                      # direnv configuration
├── setup_dev_env.sh            # Automated setup script
├── DEVELOPMENT.md              # This file
├── requirements.txt            # Python dependencies
│
├── app/                        # Application code
│   └── services/
│       └── orchestrator/
│           ├── DataPrefetchService.py     # ✅ NEW
│           └── OrchestratorService.py     # ✅ MODIFIED
│
├── strategyOrchestrator/       # Strategy execution
│   └── StrategyOrchestrator.py # ✅ MODIFIED (pure function)
│
└── tests/                      # Test suite
    └── orchestrator/           # ✅ NEW: Organized tests
        ├── test_pure_orchestrator.py
        ├── test_integration_pure_orchestrator.py
        ├── test_pure_function_basic.py
        └── test_strategy_orchestrator.py
```

## Development Workflow

### Entering the Environment

```bash
# Option 1: Automatic (with direnv)
cd /path/to/binanceTradingBot
# Environment activates automatically

# Option 2: Manual
nix develop
```

### Running Tests

```bash
# Basic tests (no dependencies)
python tests/orchestrator/test_pure_function_basic.py

# Unit tests
pytest tests/orchestrator/test_pure_orchestrator.py -v

# Integration tests (requires Docker/MongoDB)
pytest tests/orchestrator/test_integration_pure_orchestrator.py -v

# All orchestrator tests
pytest tests/orchestrator/ -v

# All tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=app --cov=strategyOrchestrator --cov-report=html
```

### Starting Services

```bash
# 1. Start databases (MongoDB, Redis, PostgreSQL)
docker-compose --profile db up -d

# 2. Start API server
python run_local.py

# 3. Start Celery worker (in another terminal)
python worker.py

# 4. Start Flower (Celery monitoring)
celery -A app.celery_app flower
```

### Code Quality

```bash
# Format code
black .

# Lint
flake8 app/ strategyOrchestrator/

# Type checking
mypy app/ strategyOrchestrator/

# Run pre-commit hooks
pre-commit run --all-files
```

## Environment Variables

Create a `.env` file in the project root:

```bash
# Profile
PROFILE=development

# MongoDB
MONGO_URI_MASTER=mongodb://localhost:27017
MONGO_URI_SLAVE=mongodb://localhost:27018
MONGO_DB_APP=trading
MONGO_DB_OHLCV=ohlcv_data
MONGO_AUTH_ENABLED=0

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# Binance API (optional)
BINANCE_API_KEY=your_api_key
BINANCE_API_SECRET=your_secret

# CoinMarketCap API (optional)
COINMARKETCAP_API_KEY=your_cmc_key

# Security
SECRET_KEY=your-secret-key-change-this
```

## Troubleshooting

### Nix flakes not working

```bash
# Check if flakes are enabled
nix show-config | grep experimental-features

# Should show: experimental-features = nix-command flakes
```

### direnv not activating

```bash
# Check if hook is in your shell RC
cat ~/.bashrc | grep direnv

# Manually allow direnv
direnv allow .
```

### Python packages not found

```bash
# Rebuild environment
nix develop --command bash -c 'pip install -r requirements.txt'

# Or enter environment and install
nix develop
pip install -r requirements.txt
```

### Tests fail due to missing dependencies

```bash
# Ensure you're in the Nix environment
nix develop

# Verify Python can find modules
python -c "import pandas; import pytest; import fastapi; print('OK')"

# Check PYTHONPATH
echo $PYTHONPATH
```

### Docker/MongoDB issues

```bash
# Check Docker is running
docker ps

# Start databases
docker-compose --profile db up -d

# Check logs
docker-compose logs mongo1
docker-compose logs redis
```

## Updating Dependencies

### Add new Python package

1. Add to `requirements.txt`
2. Update `flake.nix` (if available in nixpkgs)
3. Rebuild environment:

```bash
nix develop --command pip install -r requirements.txt
```

### Update Nix flake

```bash
# Update flake inputs
nix flake update

# Rebuild environment
nix develop
```

## IDE Setup

### VSCode

Install extensions:
- Python
- Pylance
- Nix IDE

Settings (`.vscode/settings.json`):

```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
  "python.linting.enabled": true,
  "python.linting.flake8Enabled": true,
  "python.formatting.provider": "black",
  "python.testing.pytestEnabled": true,
  "python.testing.pytestArgs": ["tests"]
}
```

### PyCharm

1. File → Settings → Project → Python Interpreter
2. Add Interpreter → Existing Environment
3. Select: `.venv/bin/python`
4. Enable pytest as default test runner

## Performance Tips

### Faster rebuilds

```bash
# Use binary cache
nix develop --option substituters "https://cache.nixos.org"

# Build in parallel
nix develop --option max-jobs 8
```

### Smaller environment

If you don't need certain features, comment them out in `flake.nix`:

```nix
# Comment out if not needed
# mongodb
# postgresql
```

## Best Practices

1. **Always use Nix environment**: Don't install system packages globally
2. **Commit flake.lock**: Ensures reproducible builds
3. **Use direnv**: Automatic environment activation
4. **Keep .venv in .gitignore**: Virtual env is project-specific
5. **Update regularly**: Run `nix flake update` monthly

## Resources

- [Nix Documentation](https://nixos.org/manual/nix/stable/)
- [Nix Flakes](https://nixos.wiki/wiki/Flakes)
- [direnv Documentation](https://direnv.net/)
- [Project Documentation](./PURE_ORCHESTRATOR_REFACTOR.md)

## Support

For issues:
1. Check this documentation
2. Review error messages carefully
3. Try rebuilding: `nix develop --rebuild`
4. Check GitHub issues
5. Ask in team chat

---

**Happy Coding! 🚀**
