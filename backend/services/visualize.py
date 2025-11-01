"""Dimensionality reduction for visualization of concept spaces.

Uses UMAP for manifold-aware reduction. NOT used for similarity computation.
"""

from typing import Optional, Literal
from dataclasses import dataclass
import numpy as np
from numpy.typing import NDArray
from umap import UMAP
from sklearn.manifold import TSNE


DimensionMode = Literal[2, 3]


@dataclass
class VisualizationReducer:
    """Reduces high-dimensional embeddings to 2D/3D for visualization.
    
    Important: These reductions preserve LOCAL structure but lose global
    distances. Never use reduced embeddings for similarity computation.
    """
    
    method: Literal["umap", "tsne", "pca"] = "umap"
    n_dimensions: DimensionMode = 2
    random_state: int = 42
    
    def __post_init__(self):
        self._model: Optional[object] = None
    
    def fit_transform(
        self,
        embeddings: NDArray,
        labels: Optional[NDArray] = None
    ) -> NDArray:
        """Fit reducer and transform embeddings.
        
        Args:
            embeddings: High-dimensional vectors (n_samples, n_features)
            labels: Optional cluster labels for supervised UMAP
            
        Returns:
            Reduced embeddings (n_samples, n_dimensions)
        """
        
        if self.method == "umap":
            self._model = UMAP(
                n_neighbors=15,
                n_components=self.n_dimensions,
                metric='cosine',
                min_dist=0.1,
                spread=1.0,
                random_state=self.random_state,
                n_jobs=1  # Use single job for stability
            )
            
            if labels is not None:
                # Supervised UMAP (better cluster separation)
                return self._model.fit_transform(embeddings, y=labels)
            else:
                return self._model.fit_transform(embeddings)
        
        elif self.method == "tsne":
            self._model = TSNE(
                n_components=self.n_dimensions,
                metric='cosine',
                random_state=self.random_state,
                n_jobs=-1  # Use all CPUs
            )
            return self._model.fit_transform(embeddings)
        
        elif self.method == "pca":
            from sklearn.decomposition import PCA
            self._model = PCA(
                n_components=self.n_dimensions,
                random_state=self.random_state
            )
            return self._model.fit_transform(embeddings)
        
        else:
            raise ValueError(f"Unknown method: {self.method}")
    
    def transform(self, embeddings: NDArray) -> NDArray:
        """Transform new embeddings using fitted model.
        
        Only works with UMAP (TSNE doesn't support transform).
        """
        
        if self._model is None:
            raise ValueError("Must call fit_transform first")
        
        if self.method != "umap":
            raise ValueError(f"Transform not supported for {self.method}")
        
        return self._model.transform(embeddings)
    
    def explained_variance(self) -> Optional[float]:
        """Get explained variance ratio (PCA only)."""
        
        if self.method == "pca" and self._model is not None:
            return float(np.sum(self._model.explained_variance_ratio_))
        
        return None


@dataclass
class ConceptVisualizer:
    """Visualizes concept clusters in 2D/3D space."""
    
    reducer: VisualizationReducer
    
    def visualize_concepts(
        self,
        concept_centroids: NDArray,
        concept_labels: list[str],
        member_embeddings: Optional[NDArray] = None,
        member_labels: Optional[NDArray] = None
    ) -> dict:
        """Create visualization data for concepts.
        
        Args:
            concept_centroids: Centroid vectors (n_concepts, n_features)
            concept_labels: Human-readable labels
            member_embeddings: Optional member point embeddings
            member_labels: Optional cluster assignment for members
            
        Returns:
            Dictionary with plot data and metadata
        """
        
        # Reduce concept centroids
        reduced_centroids = self.reducer.fit_transform(concept_centroids)
        
        plot_data = {
            "centroids": {
                "x": reduced_centroids[:, 0].tolist(),
                "y": reduced_centroids[:, 1].tolist(),
                "z": reduced_centroids[:, 2].tolist() if self.reducer.n_dimensions == 3 else None,
                "labels": concept_labels,
                "type": "centroids"
            }
        }
        
        # Optionally add member points
        if member_embeddings is not None:
            reduced_members = self.reducer.transform(member_embeddings)
            
            plot_data["members"] = {
                "x": reduced_members[:, 0].tolist(),
                "y": reduced_members[:, 1].tolist(),
                "z": reduced_members[:, 2].tolist() if self.reducer.n_dimensions == 3 else None,
                "cluster": member_labels.tolist() if member_labels is not None else None,
                "type": "members"
            }
        
        plot_data["metadata"] = {
            "method": self.reducer.method,
            "dimensions": self.reducer.n_dimensions,
            "n_concepts": len(concept_labels),
            "explained_variance": self.reducer.explained_variance()
        }
        
        return plot_data
    
    def visualize_language_space(
        self,
        entries: list,
        language_codes: list[str]
    ) -> dict:
        """Visualize entries colored by language.
        
        Shows how different languages cluster in semantic space.
        """
        
        embeddings = np.array([e.embedding for e in entries if e.embedding])
        languages = np.array([e.language for e in entries if e.embedding])
        
        # Create language->int mapping
        lang_to_idx = {lang: idx for idx, lang in enumerate(sorted(set(language_codes)))}
        lang_indices = np.array([lang_to_idx[lang] for lang in languages])
        
        # Reduce with language supervision
        reduced = self.reducer.fit_transform(embeddings, labels=lang_indices)
        
        plot_data = {
            "points": {
                "x": reduced[:, 0].tolist(),
                "y": reduced[:, 1].tolist(),
                "z": reduced[:, 2].tolist() if self.reducer.n_dimensions == 3 else None,
                "language": languages.tolist(),
                "headword": [e.headword for e in entries if e.embedding]
            },
            "metadata": {
                "method": self.reducer.method,
                "dimensions": self.reducer.n_dimensions,
                "n_points": len(entries),
                "n_languages": len(lang_to_idx),
                "languages": list(lang_to_idx.keys())
            }
        }
        
        return plot_data
    
    def visualize_similarity_network(
        self,
        entries: list,
        similarities: list[tuple],
        threshold: float = 0.7
    ) -> dict:
        """Visualize entries as network graph with similarity edges.
        
        Args:
            entries: List of Entry objects
            similarities: List of (entry_a_id, entry_b_id, score) tuples
            threshold: Minimum similarity to draw edge
            
        Returns:
            Network graph data
        """
        
        # Build nodes
        entry_map = {e.id: e for e in entries}
        embeddings = np.array([e.embedding for e in entries if e.embedding])
        
        # Reduce for layout
        reduced = self.reducer.fit_transform(embeddings)
        
        nodes = []
        for i, entry in enumerate(entries):
            if entry.embedding:
                nodes.append({
                    "id": entry.id,
                    "label": entry.headword,
                    "language": entry.language,
                    "x": float(reduced[i, 0]),
                    "y": float(reduced[i, 1]),
                    "z": float(reduced[i, 2]) if self.reducer.n_dimensions == 3 else 0
                })
        
        # Build edges
        edges = []
        for entry_a, entry_b, score in similarities:
            if score >= threshold:
                edges.append({
                    "source": entry_a,
                    "target": entry_b,
                    "weight": float(score)
                })
        
        return {
            "nodes": nodes,
            "edges": edges,
            "metadata": {
                "n_nodes": len(nodes),
                "n_edges": len(edges),
                "threshold": threshold
            }
        }


def export_plotly_scatter(plot_data: dict, output_path: str):
    """Export visualization as interactive Plotly HTML.
    
    Requires plotly: pip install plotly
    """
    
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
    except ImportError:
        raise ImportError("plotly required for export: pip install plotly")
    
    if plot_data["metadata"]["dimensions"] == 2:
        fig = go.Figure()
        
        # Add centroids if present
        if "centroids" in plot_data:
            fig.add_trace(go.Scatter(
                x=plot_data["centroids"]["x"],
                y=plot_data["centroids"]["y"],
                mode='markers+text',
                marker=dict(size=15, symbol='diamond'),
                text=plot_data["centroids"]["labels"],
                textposition="top center",
                name="Concepts"
            ))
        
        # Add members if present
        if "members" in plot_data and plot_data["members"]["cluster"] is not None:
            fig.add_trace(go.Scatter(
                x=plot_data["members"]["x"],
                y=plot_data["members"]["y"],
                mode='markers',
                marker=dict(
                    size=5,
                    color=plot_data["members"]["cluster"],
                    colorscale='Viridis'
                ),
                name="Entries"
            ))
        
        fig.update_layout(
            title=f"Concept Space ({plot_data['metadata']['method'].upper()})",
            xaxis_title="Dimension 1",
            yaxis_title="Dimension 2",
            hovermode='closest'
        )
    
    else:  # 3D
        fig = go.Figure()
        
        if "centroids" in plot_data:
            fig.add_trace(go.Scatter3d(
                x=plot_data["centroids"]["x"],
                y=plot_data["centroids"]["y"],
                z=plot_data["centroids"]["z"],
                mode='markers+text',
                marker=dict(size=10, symbol='diamond'),
                text=plot_data["centroids"]["labels"],
                name="Concepts"
            ))
        
        if "members" in plot_data:
            fig.add_trace(go.Scatter3d(
                x=plot_data["members"]["x"],
                y=plot_data["members"]["y"],
                z=plot_data["members"]["z"],
                mode='markers',
                marker=dict(
                    size=3,
                    color=plot_data["members"]["cluster"],
                    colorscale='Viridis'
                ),
                name="Entries"
            ))
        
        fig.update_layout(
            title=f"Concept Space 3D ({plot_data['metadata']['method'].upper()})",
            scene=dict(
                xaxis_title="Dimension 1",
                yaxis_title="Dimension 2",
                zaxis_title="Dimension 3"
            )
        )
    
    fig.write_html(output_path)
    print(f"Visualization saved to {output_path}")

