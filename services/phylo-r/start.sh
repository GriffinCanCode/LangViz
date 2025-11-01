#!/bin/bash
# Start R phylogenetic analysis service

set -e

echo "Starting R Phylogenetic Analysis Service..."
echo ""

# Check if R is installed
if ! command -v Rscript &> /dev/null; then
    echo "ERROR: R is not installed."
    echo "Install R from: https://cran.r-project.org/"
    exit 1
fi

# Check if dependencies are installed
echo "Checking R package dependencies..."
Rscript -e "
packages <- c('jsonlite', 'ape', 'phangorn', 'pvclust')
missing <- packages[!sapply(packages, requireNamespace, quietly = TRUE)]
if (length(missing) > 0) {
  cat('Missing packages:', paste(missing, collapse=', '), '\n')
  cat('Installing dependencies...\n')
  source('install_deps.R')
} else {
  cat('All dependencies installed.\n')
}
"

echo ""
echo "Starting server on port 50052..."
echo "Press Ctrl+C to stop."
echo ""

# Start server
Rscript server.R

