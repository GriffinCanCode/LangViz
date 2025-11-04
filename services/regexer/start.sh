#!/bin/bash
# Start Perl JSON-RPC parsing service

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Starting Perl parsing service..."
echo "  Host: localhost"
echo "  Port: 50051"
echo ""

# Check if Perl is installed
if ! command -v perl &> /dev/null; then
    echo "ERROR: Perl is not installed"
    echo "Install Perl from: https://www.perl.org/get.html"
    exit 1
fi

# Check if required modules are installed
echo "Checking Perl dependencies..."
if ! perl -MJSON::XS -e 1 2>/dev/null; then
    echo "ERROR: Required Perl module JSON::XS not found"
    echo "Install dependencies with: cpanm --installdeps ."
    exit 1
fi

echo "✓ Dependencies OK"
echo ""

# Start server
exec perl server.pl

