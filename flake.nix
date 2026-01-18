{
  description = "Binance Trading Bot - Python development environment";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs {
          inherit system;
          config = {
            allowUnfree = true;
          };
        };

        # Python with all required packages
        pythonEnv = pkgs.python312.withPackages (ps: with ps; [
          # Core Framework
          fastapi
          uvicorn
          pydantic
          pydantic-settings
          python-multipart

          # GraphQL
          # strawberry-graphql # May need to be installed via pip

          # Database
          motor
          pymongo
          redis
          asyncpg
          sqlalchemy
          alembic

          # Task Queue
          celery
          # flower # May need pip

          # Security
          python-jose
          passlib
          python-decouple
          pyjws

          # Data Processing
          numpy
          pandas
          numba
          # ta # Need pip

          # HTTP Client
          httpx
          aiohttp
          requests

          # Docker
          docker

          # Plotting/Visualization
          matplotlib
          plotly
          # mplfinance # Need pip
          # kaleido # Need pip

          # Utilities
          python-dateutil
          pytz
          orjson
          aiofiles
          tenacity

          # CLI Tools
          pyyaml
          schedule
          rich

          # Development / Testing
          pytest
          pytest-asyncio
          pytest-cov
          black
          flake8
          mypy
          pre-commit

          # Monitoring
          prometheus-client
          # opentelemetry packages # Some may need pip

          # Documentation
          # mkdocs # May need pip

          # Exchange API
          # python-binance # Need pip

          # Environment
          python-dotenv

          # WebSocket
          websockets
          anyio

          # Build tools
          pip
          setuptools
          wheel
          virtualenv
        ]);

      in
      {
        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [
            # Python environment
            pythonEnv

            # System dependencies
            docker
            docker-compose
            redis
            mongodb
            postgresql

            # Development tools
            git
            gnumake
            direnv
            nix-direnv

            # Python development
            ruff
            pyright

            # Utilities
            jq
            curl
            wget
          ];

          shellHook = ''
            echo "🚀 Binance Trading Bot Development Environment"
            echo "================================================"
            echo ""
            echo "Python version: $(python --version)"
            echo "Python path: $(which python)"
            echo ""
            echo "📦 Installing missing Python packages via pip..."

            # Create virtual environment if it doesn't exist
            if [ ! -d .venv ]; then
              echo "Creating virtual environment..."
              python -m venv .venv
            fi

            # Activate virtual environment
            source .venv/bin/activate

            # Upgrade pip
            pip install --upgrade pip setuptools wheel --quiet

            # Install packages not available in nixpkgs
            echo "Installing additional packages from requirements.txt..."
            pip install -q \
              strawberry-graphql[fastapi]==0.278.0 \
              vine==5.5.0 \
              flower==2.0.1 \
              ta==0.11.0 \
              mplfinance==0.12.9b7 \
              kaleido==0.2.1 \
              ujson==5.10.0 \
              slowapi==0.1.9 \
              pytest-benchmark==4.0.0 \
              pytest-env==1.1.5 \
              opentelemetry-api==1.36.0 \
              opentelemetry-sdk==1.36.0 \
              opentelemetry-instrumentation-fastapi==0.57b0 \
              mkdocs==1.6.1 \
              mkdocs-material==9.5.41 \
              python-binance==1.0.19 \
              fastapi-cors==0.0.6 \
              python-socketio==5.11.4 \
              pydevd-pycharm==251.26927.90 \
              kombu==5.5.4 \
              databases==0.9.0

            echo ""
            echo "✅ Environment ready!"
            echo ""
            echo "Available commands:"
            echo "  pytest tests/                     - Run all tests"
            echo "  pytest tests/orchestrator/        - Run orchestrator tests"
            echo "  python tests/orchestrator/test_pure_function_basic.py  - Run basic tests"
            echo "  python run_local.py               - Start FastAPI server"
            echo "  python worker.py                  - Start Celery worker"
            echo "  docker-compose up -d              - Start databases"
            echo ""
            echo "Environment variables:"
            echo "  PYTHONPATH=${PYTHONPATH:-.}"
            echo ""

            # Set PYTHONPATH
            export PYTHONPATH="$PWD:$PYTHONPATH"

            # Set up pre-commit hooks
            if [ ! -d .git/hooks/pre-commit ]; then
              echo "Setting up pre-commit hooks..."
              pre-commit install --quiet 2>/dev/null || true
            fi
          '';

          # Environment variables
          PYTHONPATH = ".";
          PYTHONUNBUFFERED = "1";

          # Prevent Python from writing bytecode
          PYTHONDONTWRITEBYTECODE = "1";

          # Enable better stack traces
          PYTHONFAULTHANDLER = "1";
        };
      }
    );
}
