.PHONY: help setup install build dev test clean proto

help:
	@echo "LangViz Development Commands"
	@echo "============================"
	@echo "make setup       - Initial project setup"
	@echo "make install     - Install Python and TypeScript dependencies"
	@echo "make build       - Build Perl, Rust, and TypeScript components"
	@echo "make dev         - Start development servers"
	@echo "make test        - Run all tests"
	@echo "make clean       - Clean build artifacts"
	@echo "make proto       - Generate protobuf code"

setup:
	@echo "Setting up LangViz..."
	cp .env.example .env
	cd backend && python3 -m venv venv && . venv/bin/activate && pip install -r requirements.txt
	cd services/phonetic-rs && pip install maturin && maturin develop --release
	cd services/regexer && cpanm --installdeps .
	cd frontend && npm install
	@echo "Setup complete! Edit .env and run 'make dev' to start services."

install:
	@echo "Installing dependencies..."
	@echo "Installing Python dependencies..."
	cd backend && test -d venv || python3 -m venv venv
	cd backend && . venv/bin/activate && pip install -r requirements.txt
	@echo "Installing TypeScript dependencies..."
	cd frontend && npm install
	@echo "Dependencies installed!"

build:
	@echo "Building components..."
	builder build

dev:
	@echo "Starting development servers..."
	@echo "Backend on http://localhost:8000"
	@echo "Frontend on http://localhost:5173"
	cd backend && . venv/bin/activate && python3 -m backend.main &
	cd frontend && npm run dev &
	wait

test:
	@echo "Running tests..."
	cd backend && . venv/bin/activate && pytest
	cd services/phonetic-rs && cargo test
	@echo "All tests passed!"

clean:
	@echo "Cleaning build artifacts..."
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name "node_modules" -exec rm -rf {} +
	find . -type d -name "target" -exec rm -rf {} +
	@echo "Clean complete!"

proto:
	@echo "Generating protobuf code..."
	cd services/regexer/proto && python3 -m grpc_tools.protoc -I. --python_out=../../../backend/interop --grpc_python_out=../../../backend/interop parser.proto
	@echo "Protobuf code generated!"

