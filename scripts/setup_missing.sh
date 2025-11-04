#!/bin/bash
# Quick setup script for missing components

set -e

echo "========================================"
echo "LangViz - Setup Missing Components"
echo "========================================"
echo ""

# Install Perl modules
echo "1. Installing Perl modules..."
cd services/regexer
if perl -MJSON::XS -e 1 2>/dev/null; then
    echo "   ✓ Perl modules already installed"
else
    echo "   Installing JSON::XS and dependencies..."
    cpanm --installdeps .
    echo "   ✓ Perl modules installed"
fi
cd ../..

# Build Rust backend
echo ""
echo "2. Building Rust backend..."
if cd backend && . venv/bin/activate && python3 -c "import langviz_core" 2>/dev/null; then
    echo "   ✓ Rust backend already built"
    cd ..
else
    cd ..
    echo "   Compiling Rust code (this takes 2-3 minutes)..."
    make install-rust
    echo "   ✓ Rust backend built"
fi

# Check Redis
echo ""
echo "3. Checking Redis..."
if redis-cli ping &>/dev/null; then
    echo "   ✓ Redis is running"
else
    echo "   ✗ Redis is not running"
    echo "   Start with: redis-server &"
    echo "   Or on macOS: brew services start redis"
fi

echo ""
echo "========================================"
echo "Setup Complete!"
echo "========================================"
echo ""
echo "Run validation to verify:"
echo "  python3 scripts/validate_integrations.py"
echo ""
echo "If all checks pass, start processing:"
echo "  make process-all"

