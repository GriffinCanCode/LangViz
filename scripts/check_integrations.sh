#!/bin/bash
# Check all required integrations are available

set -e

echo "========================================"
echo "LangViz Integration Check"
echo "========================================"
echo ""

ERRORS=0

# Check Python
echo -n "Checking Python 3... "
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    echo "✓ $PYTHON_VERSION"
else
    echo "✗ NOT FOUND"
    ERRORS=$((ERRORS+1))
fi

# Check Rust
echo -n "Checking Rust... "
if command -v cargo &> /dev/null; then
    RUST_VERSION=$(cargo --version)
    echo "✓ $RUST_VERSION"
else
    echo "✗ NOT FOUND"
    echo "  Install from: https://rustup.rs/"
    ERRORS=$((ERRORS+1))
fi

# Check R
echo -n "Checking R... "
if command -v Rscript &> /dev/null; then
    R_VERSION=$(Rscript --version 2>&1 | head -n1)
    echo "✓ $R_VERSION"
    
    # Check R packages
    echo -n "  Checking R packages (ape, phangorn)... "
    if Rscript -e 'library(ape); library(phangorn)' &> /dev/null; then
        echo "✓"
    else
        echo "✗ MISSING"
        echo "  Install with: cd services/phylo-r && Rscript install_deps.R"
        ERRORS=$((ERRORS+1))
    fi
else
    echo "✗ NOT FOUND"
    echo "  Install from: https://cran.r-project.org/"
    ERRORS=$((ERRORS+1))
fi

# Check Perl
echo -n "Checking Perl... "
if command -v perl &> /dev/null; then
    PERL_VERSION=$(perl --version | grep -oP 'v\d+\.\d+\.\d+' | head -n1)
    echo "✓ $PERL_VERSION"
    
    # Check Perl modules
    echo -n "  Checking Perl modules (JSON::XS)... "
    if perl -MJSON::XS -e 1 2>/dev/null; then
        echo "✓"
    else
        echo "✗ MISSING"
        echo "  Install with: cd services/regexer && cpanm --installdeps ."
        ERRORS=$((ERRORS+1))
    fi
else
    echo "✗ NOT FOUND"
    echo "  Install from: https://www.perl.org/get.html"
    ERRORS=$((ERRORS+1))
fi

# Check PostgreSQL
echo -n "Checking PostgreSQL... "
if command -v psql &> /dev/null; then
    PG_VERSION=$(psql --version)
    echo "✓ $PG_VERSION"
    
    # Check if langviz database exists
    echo -n "  Checking langviz database... "
    if psql -lqt | cut -d \| -f 1 | grep -qw langviz; then
        echo "✓"
    else
        echo "✗ NOT FOUND"
        echo "  Create with: make db-setup"
        ERRORS=$((ERRORS+1))
    fi
else
    echo "✗ NOT FOUND"
    ERRORS=$((ERRORS+1))
fi

# Check Redis
echo -n "Checking Redis... "
if command -v redis-cli &> /dev/null; then
    if redis-cli ping &> /dev/null; then
        echo "✓ Running"
    else
        echo "✗ Not running"
        echo "  Start with: redis-server"
        ERRORS=$((ERRORS+1))
    fi
else
    echo "✗ NOT FOUND"
    ERRORS=$((ERRORS+1))
fi

# Check Perl service
echo -n "Checking Perl service (port 50051)... "
if nc -z localhost 50051 2>/dev/null; then
    echo "✓ Running"
else
    echo "✗ Not running"
    echo "  Start with: make start-perl"
    ERRORS=$((ERRORS+1))
fi

echo ""
echo "========================================"
if [ $ERRORS -eq 0 ]; then
    echo "✓ All integrations ready!"
    echo "Run: make process-all"
else
    echo "✗ $ERRORS issue(s) found"
    echo "Fix the issues above before running process-all"
    exit 1
fi
echo "========================================"

