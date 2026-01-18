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

      in
      {
        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [
            # Python 3.12 (no packages, just the interpreter)
            python312

            # Python package managers
            uv  # Fast Python package installer (handles everything pip does)
            python312Packages.virtualenv
          ];

          shellHook = ''
            echo "🚀 Binance Trading Bot Development Environment"
            echo "================================================"
            echo ""
            echo "Python version: $(python --version)"
            echo "uv version: $(uv --version)"
            echo ""

            # Create virtual environment if it doesn't exist
            if [ ! -d .venv ]; then
              echo "📦 Creating virtual environment with uv..."
              uv venv .venv
            fi

            # Activate virtual environment
            source .venv/bin/activate

            # Install all requirements using uv (much faster than pip)
            if [ -f requirements.txt ]; then
              echo "📦 Installing Python packages with uv..."
              uv pip install -r requirements.txt
            fi

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
            echo "Python packages managed by uv (fast!)"
            echo "Virtual environment: .venv/"
            echo ""

            # Set PYTHONPATH
            export PYTHONPATH="$PWD:$PYTHONPATH"
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
