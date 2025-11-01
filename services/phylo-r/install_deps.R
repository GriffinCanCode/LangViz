#!/usr/bin/env Rscript
# Install dependencies for R phylo service

cat("Installing R packages for LangViz phylogenetic service...\n")

# CRAN mirror
options(repos = c(CRAN = "https://cloud.r-project.org"))

# Required packages
packages <- c(
  "jsonlite",    # JSON encoding/decoding
  "ape",         # Phylogenetic analysis
  "phangorn",    # Extended phylogenetics
  "pvclust"      # Hierarchical clustering with p-values
)

# Install missing packages
for (pkg in packages) {
  if (!require(pkg, character.only = TRUE, quietly = TRUE)) {
    cat(sprintf("Installing %s...\n", pkg))
    install.packages(pkg, dependencies = TRUE)
  } else {
    cat(sprintf("%s already installed.\n", pkg))
  }
}

cat("\nVerifying installations...\n")
for (pkg in packages) {
  if (require(pkg, character.only = TRUE, quietly = TRUE)) {
    cat(sprintf("✓ %s\n", pkg))
  } else {
    cat(sprintf("✗ %s FAILED\n", pkg))
  }
}

cat("\nInstallation complete!\n")

