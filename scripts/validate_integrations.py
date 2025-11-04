#!/usr/bin/env python3
"""Validate all integrations are properly configured (dry run test)."""

import sys
import subprocess
import socket
from pathlib import Path

def check_command(cmd: str, name: str) -> bool:
    """Check if a command exists."""
    try:
        subprocess.run([cmd, "--version"], capture_output=True, check=True)
        print(f"✓ {name} installed")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print(f"✗ {name} NOT FOUND")
        return False

def check_port(port: int, name: str) -> bool:
    """Check if a port is open."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('localhost', port))
        sock.close()
        if result == 0:
            print(f"✓ {name} running on port {port}")
            return True
        else:
            print(f"✗ {name} not running on port {port}")
            return False
    except Exception as e:
        print(f"✗ {name} check failed: {e}")
        return False

def check_python_import(module: str, name: str) -> bool:
    """Check if a Python module can be imported."""
    try:
        __import__(module)
        print(f"✓ {name} importable")
        return True
    except ImportError:
        print(f"✗ {name} NOT importable")
        return False

def check_r_packages() -> bool:
    """Check if required R packages are installed."""
    try:
        result = subprocess.run(
            ["Rscript", "-e", "library(ape); library(phangorn); library(jsonlite)"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print("✓ R packages (ape, phangorn, jsonlite) installed")
            return True
        else:
            print("✗ R packages missing")
            print(f"  Error: {result.stderr}")
            return False
    except Exception as e:
        print(f"✗ R package check failed: {e}")
        return False

def check_perl_modules() -> bool:
    """Check if required Perl modules are installed."""
    try:
        result = subprocess.run(
            ["perl", "-MJSON::XS", "-e", "1"],
            capture_output=True
        )
        if result.returncode == 0:
            print("✓ Perl modules (JSON::XS) installed")
            return True
        else:
            print("✗ Perl modules missing")
            return False
    except Exception as e:
        print(f"✗ Perl module check failed: {e}")
        return False

def main():
    print("="*70)
    print("LANGVIZ INTEGRATION VALIDATION")
    print("="*70)
    print()
    
    checks = []
    
    print("1. Core Dependencies")
    print("-" * 70)
    checks.append(check_command("python3", "Python 3"))
    checks.append(check_command("cargo", "Rust"))
    checks.append(check_command("Rscript", "R"))
    checks.append(check_command("perl", "Perl"))
    checks.append(check_command("psql", "PostgreSQL"))
    checks.append(check_command("redis-cli", "Redis"))
    print()
    
    print("2. Language-Specific Packages")
    print("-" * 70)
    checks.append(check_r_packages())
    checks.append(check_perl_modules())
    print()
    
    print("3. Python Modules (from venv)")
    print("-" * 70)
    # These will only work if run from venv
    venv_checks = [
        check_python_import("asyncpg", "asyncpg"),
        check_python_import("sentence_transformers", "sentence_transformers"),
        check_python_import("redis", "redis"),
    ]
    checks.extend(venv_checks)
    
    # Rust backend check (may fail if not compiled yet)
    try:
        import langviz_core
        print("✓ Rust backend (langviz_core) compiled")
        checks.append(True)
    except ImportError:
        print("✗ Rust backend not compiled (run: make install-rust)")
        checks.append(False)
    print()
    
    print("4. Running Services")
    print("-" * 70)
    checks.append(check_port(6379, "Redis"))
    checks.append(check_port(5432, "PostgreSQL"))
    checks.append(check_port(50051, "Perl service"))
    print()
    
    print("5. File Structure")
    print("-" * 70)
    project_root = Path(__file__).parent.parent
    
    files_to_check = [
        "services/regexer/server.pl",
        "services/regexer/start.sh",
        "services/phylo-r/server.R",
        "services/phylo-r/start.sh",
        "backend/services/optimized.py",
        "backend/cli/process.py",
    ]
    
    for file_path in files_to_check:
        full_path = project_root / file_path
        if full_path.exists():
            print(f"✓ {file_path}")
            checks.append(True)
        else:
            print(f"✗ {file_path} NOT FOUND")
            checks.append(False)
    print()
    
    # Summary
    print("="*70)
    passed = sum(checks)
    total = len(checks)
    print(f"RESULTS: {passed}/{total} checks passed")
    print("="*70)
    print()
    
    if passed == total:
        print("✓ ALL CHECKS PASSED")
        print()
        print("Ready to run:")
        print("  make process-all")
        return 0
    else:
        failed = total - passed
        print(f"✗ {failed} CHECK(S) FAILED")
        print()
        print("Fix the issues above, then run:")
        print("  ./scripts/validate_integrations.py")
        return 1

if __name__ == "__main__":
    sys.exit(main())

