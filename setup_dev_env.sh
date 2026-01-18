#!/usr/bin/env bash
#
# setup_dev_env.sh
# ────────────────────────────────────────────────────────────────────────────
# Setup development environment for Binance Trading Bot
#
# This script:
# 1. Checks for Nix installation
# 2. Enables Nix flakes
# 3. Sets up direnv
# 4. Installs all dependencies
# 5. Runs basic tests
#

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

success() {
    echo -e "${GREEN}✓${NC} $1"
}

warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

error() {
    echo -e "${RED}✗${NC} $1"
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║     Binance Trading Bot - Development Setup                ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Step 1: Check for Nix
info "Checking for Nix installation..."
if ! command_exists nix; then
    error "Nix is not installed!"
    echo ""
    echo "Please install Nix first:"
    echo "  curl --proto '=https' --tlsv1.2 -sSf -L https://install.determinate.systems/nix | sh -s -- install"
    echo ""
    echo "Or visit: https://nixos.org/download.html"
    exit 1
fi
success "Nix is installed: $(nix --version | head -n1)"

# Step 2: Enable Nix flakes
info "Checking Nix flakes configuration..."
NIX_CONF_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/nix"
NIX_CONF_FILE="$NIX_CONF_DIR/nix.conf"

if [ ! -f "$NIX_CONF_FILE" ] || ! grep -q "experimental-features.*flakes" "$NIX_CONF_FILE" 2>/dev/null; then
    warning "Nix flakes not enabled, enabling now..."
    mkdir -p "$NIX_CONF_DIR"

    if [ -f "$NIX_CONF_FILE" ]; then
        # Append if file exists
        echo "experimental-features = nix-command flakes" >> "$NIX_CONF_FILE"
    else
        # Create new file
        cat > "$NIX_CONF_FILE" << 'EOF'
experimental-features = nix-command flakes
max-jobs = auto
EOF
    fi
    success "Nix flakes enabled"
else
    success "Nix flakes already enabled"
fi

# Step 3: Check for direnv
info "Checking for direnv..."
if ! command_exists direnv; then
    warning "direnv is not installed, installing via Nix..."
    nix profile install nixpkgs#direnv
    success "direnv installed"
else
    success "direnv is installed: $(direnv --version)"
fi

# Step 4: Hook direnv to shell
info "Checking direnv shell hook..."
SHELL_NAME=$(basename "$SHELL")
SHELL_RC="$HOME/.${SHELL_NAME}rc"

if [ ! -f "$SHELL_RC" ] || ! grep -q 'direnv hook' "$SHELL_RC" 2>/dev/null; then
    warning "direnv not hooked to $SHELL_NAME, adding hook..."
    echo "" >> "$SHELL_RC"
    echo "# direnv hook" >> "$SHELL_RC"
    echo 'eval "$(direnv hook '"$SHELL_NAME"')"' >> "$SHELL_RC"
    success "direnv hook added to $SHELL_RC"
    info "Please run: source $SHELL_RC"
else
    success "direnv already hooked to $SHELL_NAME"
fi

# Step 5: Allow direnv for this directory
info "Allowing direnv for this directory..."
if [ ! -f .envrc ]; then
    error ".envrc file not found!"
    exit 1
fi

direnv allow . 2>/dev/null || true
success "direnv allowed"

# Step 6: Build Nix environment
info "Building Nix development environment (this may take a while)..."
echo ""
if nix develop --command echo "Environment loaded successfully"; then
    success "Nix environment built successfully"
else
    error "Failed to build Nix environment"
    exit 1
fi

# Step 7: Enter environment and setup
info "Setting up Python virtual environment..."
nix develop --command bash -c '
    # Create venv if it doesn'"'"'t exist
    if [ ! -d .venv ]; then
        python -m venv .venv
    fi

    # Activate
    source .venv/bin/activate

    # Upgrade pip
    pip install --upgrade pip setuptools wheel --quiet

    # Install all requirements
    pip install -r requirements.txt --quiet

    echo "✓ All Python packages installed"
'

success "Development environment setup complete!"

# Step 8: Run basic tests
echo ""
info "Running basic tests to verify setup..."
echo ""

if nix develop --command python tests/orchestrator/test_pure_function_basic.py; then
    echo ""
    success "Basic tests passed! Environment is ready."
else
    warning "Some tests failed, but environment is set up."
fi

# Final instructions
echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                    Setup Complete! 🎉                      ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "Next steps:"
echo ""
echo "1. Enter the development environment:"
echo "   ${GREEN}nix develop${NC}"
echo ""
echo "2. Or just cd into the directory (direnv will auto-activate):"
echo "   ${GREEN}cd $(pwd)${NC}"
echo ""
echo "3. Run tests:"
echo "   ${GREEN}pytest tests/orchestrator/${NC}"
echo ""
echo "4. Start the application:"
echo "   ${GREEN}docker-compose --profile db up -d${NC}  # Start databases"
echo "   ${GREEN}python run_local.py${NC}                # Start API server"
echo "   ${GREEN}python worker.py${NC}                   # Start worker"
echo ""
echo "Environment variables can be set in ${YELLOW}.env${NC} file"
echo ""
