"""Integration tests for R phylogenetic service.

Tests the full Python <-> R communication stack.
Requires R service to be running (or mocks for CI).
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock

from backend.interop.r_client import (
    RPhyloClient,
    PhylogeneticTree,
    BootstrapResult,
    HierarchicalClustering,
    TreeComparison
)
from backend.services.phylo import PhyloService, create_distance_matrix_from_similarities


class TestRPhyloClient:
    """Test R client communication (mocked)."""
    
    def test_client_connection(self):
        """Test connection lifecycle."""
        client = RPhyloClient("localhost", 50052)
        
        # Should not be connected initially
        assert client._socket is None
        
        # Mock socket
        with patch('socket.socket') as mock_socket:
            mock_sock_instance = MagicMock()
            mock_socket.return_value = mock_sock_instance
            
            client.connect()
            
            # Should be connected
            assert client._socket is mock_sock_instance
            mock_sock_instance.connect.assert_called_once_with(("localhost", 50052))
            
            client.disconnect()
            mock_sock_instance.close.assert_called_once()
    
    def test_ping(self):
        """Test ping method."""
        client = RPhyloClient()
        
        with patch.object(client, '_call') as mock_call:
            mock_call.return_value = {"status": "ok", "message": "R phylo service is running"}
            
            result = client.ping()
            
            assert result is True
            mock_call.assert_called_once_with("ping", {})
    
    def test_infer_tree(self):
        """Test tree inference."""
        client = RPhyloClient()
        
        # Sample distance matrix
        distances = np.array([
            [0.0, 0.3, 0.5, 0.7],
            [0.3, 0.0, 0.4, 0.6],
            [0.5, 0.4, 0.0, 0.5],
            [0.7, 0.6, 0.5, 0.0]
        ])
        
        labels = ["en", "de", "fr", "hi"]
        
        with patch.object(client, '_call') as mock_call:
            mock_call.return_value = {
                "newick": "((en:0.15,de:0.15):0.25,(fr:0.20,hi:0.20):0.20);",
                "method": "nj",
                "n_tips": 4,
                "tip_labels": labels,
                "edge_lengths": [0.15, 0.15, 0.25, 0.20, 0.20, 0.20],
                "cophenetic_correlation": 0.95,
                "rooted": False,
                "binary": True
            }
            
            tree = client.infer_tree(distances, labels, method="nj")
            
            assert isinstance(tree, PhylogeneticTree)
            assert tree.method == "nj"
            assert tree.n_tips == 4
            assert tree.cophenetic_correlation == 0.95
            assert "en" in tree.tip_labels
            
            # Verify call
            call_args = mock_call.call_args[0]
            assert call_args[0] == "infer_tree"
            assert call_args[1]["method"] == "nj"
            assert call_args[1]["labels"] == labels
    
    def test_bootstrap_tree(self):
        """Test bootstrap analysis."""
        client = RPhyloClient()
        
        distances = np.array([
            [0.0, 0.3, 0.5],
            [0.3, 0.0, 0.4],
            [0.5, 0.4, 0.0]
        ])
        
        labels = ["en", "de", "fr"]
        
        with patch.object(client, '_call') as mock_call:
            mock_call.return_value = {
                "consensus_newick": "((en,de),fr);",
                "support_values": [0.85, 0.92, 1.0],
                "n_bootstrap": 100,
                "method": "nj"
            }
            
            result = client.bootstrap_tree(distances, labels, n_bootstrap=100)
            
            assert isinstance(result, BootstrapResult)
            assert result.n_bootstrap == 100
            assert len(result.support_values) == 3
            assert result.method == "nj"
    
    def test_hierarchical_clustering(self):
        """Test hierarchical clustering."""
        client = RPhyloClient()
        
        distances = np.array([
            [0.0, 0.2, 0.8, 0.9],
            [0.2, 0.0, 0.7, 0.8],
            [0.8, 0.7, 0.0, 0.1],
            [0.9, 0.8, 0.1, 0.0]
        ])
        
        labels = ["word1", "word2", "word3", "word4"]
        
        with patch.object(client, '_call') as mock_call:
            mock_call.return_value = {
                "method": "ward.D2",
                "labels": labels,
                "merge": [[-1, -2], [-3, -4], [1, 2]],
                "height": [0.2, 0.1, 0.8],
                "order": [0, 1, 2, 3],
                "suggested_k_range": [2, 4]
            }
            
            result = client.cluster_hierarchical(distances, labels)
            
            assert isinstance(result, HierarchicalClustering)
            assert result.method == "ward.D2"
            assert result.suggested_k_range == (2, 4)
            assert len(result.height) == 3
    
    def test_compare_trees(self):
        """Test tree comparison."""
        client = RPhyloClient()
        
        tree1 = "((en,de),(fr,es));"
        tree2 = "((en,fr),(de,es));"
        
        with patch.object(client, '_call') as mock_call:
            mock_call.return_value = {
                "robinson_foulds": 2.0,
                "normalized_rf": 0.5,
                "max_possible_rf": 4.0,
                "trees_identical": False
            }
            
            result = client.compare_trees(tree1, tree2)
            
            assert isinstance(result, TreeComparison)
            assert result.robinson_foulds == 2.0
            assert result.normalized_rf == 0.5
            assert result.trees_identical is False


class TestPhyloService:
    """Test high-level phylo service."""
    
    def test_service_initialization(self):
        """Test service initialization."""
        service = PhyloService(use_r=False)
        
        assert service.r_port == 50052
        assert service.use_r is False
    
    def test_static_tree_fallback(self):
        """Test fallback to static tree when R not available."""
        service = PhyloService(use_r=False)
        
        # Should use static tree
        distance = service.path_distance("en", "de")
        assert isinstance(distance, int)
        assert distance >= 0
        
        prior = service.cognate_prior(distance)
        assert 0.0 <= prior <= 1.0
    
    def test_infer_tree_requires_r(self):
        """Test that tree inference requires R service."""
        service = PhyloService(use_r=False)
        
        distances = np.array([[0.0, 0.3], [0.3, 0.0]])
        labels = ["en", "de"]
        
        with pytest.raises(RuntimeError, match="R service not enabled"):
            service.infer_tree_from_distances(distances, labels)
    
    def test_infer_tree_with_r(self):
        """Test tree inference with R enabled."""
        service = PhyloService(use_r=True)
        
        distances = np.array([
            [0.0, 0.3, 0.5],
            [0.3, 0.0, 0.4],
            [0.5, 0.4, 0.0]
        ])
        labels = ["en", "de", "fr"]
        
        # Mock R client
        with patch('backend.services.phylo.RPhyloClient') as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value.__enter__.return_value = mock_instance
            
            mock_tree = PhylogeneticTree(
                newick="((en,de),fr);",
                method="nj",
                n_tips=3,
                tip_labels=labels,
                edge_lengths=[0.15, 0.15, 0.25],
                cophenetic_correlation=0.95,
                rooted=False,
                binary=True
            )
            mock_instance.infer_tree.return_value = mock_tree
            
            tree = service.infer_tree_from_distances(distances, labels, method="nj")
            
            assert tree.newick == "((en,de),fr);"
            assert tree.method == "nj"
            assert tree.cophenetic_correlation == 0.95
            
            # Verify call
            mock_instance.infer_tree.assert_called_once()
    
    def test_tree_caching(self):
        """Test that trees are cached."""
        service = PhyloService(use_r=True)
        
        distances = np.array([[0.0, 0.3], [0.3, 0.0]])
        labels = ["en", "de"]
        
        with patch('backend.services.phylo.RPhyloClient') as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value.__enter__.return_value = mock_instance
            
            mock_tree = PhylogeneticTree(
                newick="(en,de);",
                method="nj",
                n_tips=2,
                tip_labels=labels,
                edge_lengths=[0.15],
                cophenetic_correlation=1.0,
                rooted=False,
                binary=True
            )
            mock_instance.infer_tree.return_value = mock_tree
            
            # First call - should call R
            tree1 = service.infer_tree_from_distances(distances, labels)
            assert mock_instance.infer_tree.call_count == 1
            
            # Second call - should use cache
            tree2 = service.infer_tree_from_distances(distances, labels)
            assert mock_instance.infer_tree.call_count == 1  # Not called again
            
            assert tree1.newick == tree2.newick


class TestHelperFunctions:
    """Test utility functions."""
    
    def test_create_distance_matrix(self):
        """Test similarity to distance matrix conversion."""
        similarities = [
            ("word1", "word2", 0.8),
            ("word1", "word3", 0.3),
            ("word2", "word3", 0.2)
        ]
        
        matrix, labels = create_distance_matrix_from_similarities(similarities)
        
        assert matrix.shape == (3, 3)
        assert len(labels) == 3
        assert "word1" in labels
        assert "word2" in labels
        assert "word3" in labels
        
        # Check distances (1 - similarity)
        idx1 = labels.index("word1")
        idx2 = labels.index("word2")
        idx3 = labels.index("word3")
        
        assert matrix[idx1, idx2] == pytest.approx(0.2)  # 1 - 0.8
        assert matrix[idx1, idx3] == pytest.approx(0.7)  # 1 - 0.3
        assert matrix[idx2, idx3] == pytest.approx(0.8)  # 1 - 0.2
        
        # Matrix should be symmetric
        assert matrix[idx1, idx2] == matrix[idx2, idx1]
        
        # Diagonal should be zero
        assert matrix[idx1, idx1] == 0.0


@pytest.mark.integration
@pytest.mark.skipif(True, reason="Requires R service running")
class TestRServiceIntegration:
    """Integration tests requiring actual R service.
    
    To run: 
    1. Start R service: cd services/phylo-r && Rscript server.R
    2. Run: pytest tests/test_r_integration.py::TestRServiceIntegration -v
    """
    
    def test_real_tree_inference(self):
        """Test actual tree inference with R service."""
        # Indo-European language distances (simplified)
        distances = np.array([
            [0.0, 0.25, 0.50, 0.60, 0.70],  # English
            [0.25, 0.0, 0.45, 0.55, 0.65],  # German
            [0.50, 0.45, 0.0, 0.30, 0.40],  # French
            [0.60, 0.55, 0.30, 0.0, 0.35],  # Spanish
            [0.70, 0.65, 0.40, 0.35, 0.0]   # Italian
        ])
        
        labels = ["English", "German", "French", "Spanish", "Italian"]
        
        with RPhyloClient() as client:
            # Test connection
            assert client.ping()
            
            # Infer tree
            tree = client.infer_tree(distances, labels, method="nj")
            
            assert tree.n_tips == 5
            assert tree.cophenetic_correlation > 0.8
            assert "English" in tree.tip_labels
            
            # Bootstrap
            bootstrap = client.bootstrap_tree(distances, labels, n_bootstrap=50)
            assert len(bootstrap.support_values) > 0
    
    def test_real_hierarchical_clustering(self):
        """Test actual hierarchical clustering."""
        # Cognate distances
        distances = np.array([
            [0.0, 0.1, 0.8, 0.9],
            [0.1, 0.0, 0.7, 0.8],
            [0.8, 0.7, 0.0, 0.1],
            [0.9, 0.8, 0.1, 0.0]
        ])
        
        labels = ["water_en", "wasser_de", "eau_fr", "agua_es"]
        
        with RPhyloClient() as client:
            clustering = client.cluster_hierarchical(distances, labels)
            
            assert clustering.method == "ward.D2"
            assert len(clustering.labels) == 4
            assert clustering.suggested_k_range[0] == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

