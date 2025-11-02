#!/usr/bin/env python3
"""Test R phylogenetic service integration."""

import numpy as np
from backend.interop.r_client import RPhyloClient

def test_r_service():
    """Test basic R service functionality."""
    print("Testing R phylogenetic service...")
    print()
    
    # Create simple distance matrix for 4 languages
    distance_matrix = np.array([
        [0.0, 0.2, 0.4, 0.6],
        [0.2, 0.0, 0.3, 0.5],
        [0.4, 0.3, 0.0, 0.4],
        [0.6, 0.5, 0.4, 0.0]
    ])
    
    labels = ["eng", "deu", "fra", "spa"]
    
    print(f"Testing tree inference for {len(labels)} languages")
    print(f"Labels: {labels}")
    print()
    
    try:
        with RPhyloClient() as client:
            # Test ping
            print("1. Testing ping...")
            if client.ping():
                print("✓ R service is responsive")
            else:
                print("✗ R service ping failed")
                return False
            
            print()
            
            # Test tree inference
            print("2. Testing tree inference (NJ)...")
            tree = client.infer_tree(distance_matrix, labels, method="nj")
            print(f"✓ Tree inferred: {tree.n_tips} tips")
            print(f"  Newick: {tree.newick}")
            print(f"  Cophenetic correlation: {tree.cophenetic_correlation:.3f}")
            print(f"  Rooted: {tree.rooted}, Binary: {tree.binary}")
            print()
            
            # Test UPGMA
            print("3. Testing tree inference (UPGMA)...")
            tree_upgma = client.infer_tree(distance_matrix, labels, method="upgma")
            print(f"✓ UPGMA tree inferred")
            print(f"  Newick: {tree_upgma.newick}")
            print()
            
            # Test tree comparison
            print("4. Testing tree comparison...")
            comparison = client.compare_trees(tree.newick, tree_upgma.newick)
            print(f"✓ Trees compared")
            print(f"  Robinson-Foulds distance: {comparison.robinson_foulds}")
            print(f"  Normalized RF: {comparison.normalized_rf:.3f}")
            print(f"  Trees identical: {comparison.trees_identical}")
            print()
            
            print("✓ All tests passed!")
            return True
            
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_r_service()
    sys.exit(0 if success else 1)

