"""Phylogenetic distance computation for multi-family language tree.

Provides tree-based distances for Bayesian priors in cognate detection.
Includes Indo-European, Dravidian, and Uralic families.
Based on Glottolog classification and linguistic consensus.
"""

from typing import Optional
from dataclasses import dataclass, field
from backend.core.similarity import PhylogeneticNode


@dataclass
class PhylogeneticTree:
    """Multi-family language tree with IE, Dravidian, and Uralic families.
    
    Provides path distances for weighting similarity by expected relatedness.
    For cross-family comparisons, returns appropriate large distances.
    """
    
    nodes: dict[str, PhylogeneticNode] = field(default_factory=dict)
    language_to_node: dict[str, str] = field(default_factory=dict)  # ISO code → node ID
    family_roots: dict[str, str] = field(default_factory=dict)  # Language family → root node ID
    
    def __post_init__(self):
        """Initialize multi-family tree structure."""
        self._build_ie_tree()
        self._build_dravidian_tree()
        self._build_uralic_tree()
    
    def _build_ie_tree(self):
        """Construct simplified IE tree from linguistic classification.
        
        Based on standard IE classification:
        - Major branches: Indo-Iranian, Hellenic, Italic, Germanic, Celtic, 
          Balto-Slavic, Armenian, Albanian, Anatolian, Tocharian
        - Sub-branches where relevant
        """
        
        # Root
        root = PhylogeneticNode(
            id="pie",
            name="Proto-Indo-European",
            parent=None,
            children=[
                "indo_iranian", "hellenic", "italic", "germanic", "celtic",
                "balto_slavic", "armenian", "albanian", "anatolian", "tocharian"
            ],
            depth=0
        )
        self.nodes["pie"] = root
        self.family_roots["indo-european"] = "pie"
        
        # Indo-Iranian branch
        indo_iranian = PhylogeneticNode(
            id="indo_iranian",
            name="Indo-Iranian",
            parent="pie",
            children=["indic", "iranian"],
            depth=1
        )
        self.nodes["indo_iranian"] = indo_iranian
        
        indic = PhylogeneticNode(
            id="indic",
            name="Indic",
            parent="indo_iranian",
            languages=["sa", "hi", "bn", "pa", "ur", "mr", "gu"],  # Sanskrit, Hindi, Bengali, Punjabi, Urdu, Marathi, Gujarati
            depth=2
        )
        self.nodes["indic"] = indic
        for lang in indic.languages:
            self.language_to_node[lang] = "indic"
        
        iranian = PhylogeneticNode(
            id="iranian",
            name="Iranian",
            parent="indo_iranian",
            languages=["fa", "ps", "tg", "ku"],  # Persian, Pashto, Tajik, Kurdish
            depth=2
        )
        self.nodes["iranian"] = iranian
        for lang in iranian.languages:
            self.language_to_node[lang] = "iranian"
        
        # Hellenic
        hellenic = PhylogeneticNode(
            id="hellenic",
            name="Hellenic",
            parent="pie",
            languages=["el", "grc"],  # Greek, Ancient Greek
            depth=1
        )
        self.nodes["hellenic"] = hellenic
        for lang in hellenic.languages:
            self.language_to_node[lang] = "hellenic"
        
        # Italic (Romance)
        italic = PhylogeneticNode(
            id="italic",
            name="Italic",
            parent="pie",
            children=["romance"],
            depth=1
        )
        self.nodes["italic"] = italic
        
        romance = PhylogeneticNode(
            id="romance",
            name="Romance",
            parent="italic",
            languages=["la", "it", "es", "fr", "pt", "ro", "ca"],  # Latin, Italian, Spanish, French, Portuguese, Romanian, Catalan
            depth=2
        )
        self.nodes["romance"] = romance
        for lang in romance.languages:
            self.language_to_node[lang] = "romance"
        
        # Germanic
        germanic = PhylogeneticNode(
            id="germanic",
            name="Germanic",
            parent="pie",
            children=["west_germanic", "north_germanic"],
            depth=1
        )
        self.nodes["germanic"] = germanic
        
        west_germanic = PhylogeneticNode(
            id="west_germanic",
            name="West Germanic",
            parent="germanic",
            languages=["en", "de", "nl", "af", "yi"],  # English, German, Dutch, Afrikaans, Yiddish
            depth=2
        )
        self.nodes["west_germanic"] = west_germanic
        for lang in west_germanic.languages:
            self.language_to_node[lang] = "west_germanic"
        
        north_germanic = PhylogeneticNode(
            id="north_germanic",
            name="North Germanic",
            parent="germanic",
            languages=["sv", "da", "no", "is", "fo"],  # Swedish, Danish, Norwegian, Icelandic, Faroese
            depth=2
        )
        self.nodes["north_germanic"] = north_germanic
        for lang in north_germanic.languages:
            self.language_to_node[lang] = "north_germanic"
        
        # Celtic
        celtic = PhylogeneticNode(
            id="celtic",
            name="Celtic",
            parent="pie",
            children=["insular_celtic"],
            depth=1
        )
        self.nodes["celtic"] = celtic
        
        insular_celtic = PhylogeneticNode(
            id="insular_celtic",
            name="Insular Celtic",
            parent="celtic",
            languages=["ga", "gd", "cy", "br", "gv"],  # Irish, Scottish Gaelic, Welsh, Breton, Manx
            depth=2
        )
        self.nodes["insular_celtic"] = insular_celtic
        for lang in insular_celtic.languages:
            self.language_to_node[lang] = "insular_celtic"
        
        # Balto-Slavic
        balto_slavic = PhylogeneticNode(
            id="balto_slavic",
            name="Balto-Slavic",
            parent="pie",
            children=["baltic", "slavic"],
            depth=1
        )
        self.nodes["balto_slavic"] = balto_slavic
        
        baltic = PhylogeneticNode(
            id="baltic",
            name="Baltic",
            parent="balto_slavic",
            languages=["lt", "lv"],  # Lithuanian, Latvian
            depth=2
        )
        self.nodes["baltic"] = baltic
        for lang in baltic.languages:
            self.language_to_node[lang] = "baltic"
        
        slavic = PhylogeneticNode(
            id="slavic",
            name="Slavic",
            parent="balto_slavic",
            children=["east_slavic", "west_slavic", "south_slavic"],
            depth=2
        )
        self.nodes["slavic"] = slavic
        
        east_slavic = PhylogeneticNode(
            id="east_slavic",
            name="East Slavic",
            parent="slavic",
            languages=["ru", "uk", "be"],  # Russian, Ukrainian, Belarusian
            depth=3
        )
        self.nodes["east_slavic"] = east_slavic
        for lang in east_slavic.languages:
            self.language_to_node[lang] = "east_slavic"
        
        west_slavic = PhylogeneticNode(
            id="west_slavic",
            name="West Slavic",
            parent="slavic",
            languages=["pl", "cs", "sk"],  # Polish, Czech, Slovak
            depth=3
        )
        self.nodes["west_slavic"] = west_slavic
        for lang in west_slavic.languages:
            self.language_to_node[lang] = "west_slavic"
        
        south_slavic = PhylogeneticNode(
            id="south_slavic",
            name="South Slavic",
            parent="slavic",
            languages=["bg", "mk", "sl", "hr", "sr"],  # Bulgarian, Macedonian, Slovene, Croatian, Serbian
            depth=3
        )
        self.nodes["south_slavic"] = south_slavic
        for lang in south_slavic.languages:
            self.language_to_node[lang] = "south_slavic"
        
        # Armenian
        armenian = PhylogeneticNode(
            id="armenian",
            name="Armenian",
            parent="pie",
            languages=["hy"],
            depth=1
        )
        self.nodes["armenian"] = armenian
        self.language_to_node["hy"] = "armenian"
        
        # Albanian
        albanian = PhylogeneticNode(
            id="albanian",
            name="Albanian",
            parent="pie",
            languages=["sq"],
            depth=1
        )
        self.nodes["albanian"] = albanian
        self.language_to_node["sq"] = "albanian"
    
    def _build_dravidian_tree(self):
        """Construct Dravidian language family tree.
        
        Major branches: South-Dravidian, South-Central, Central, North
        Focus on major literary languages with available data.
        """
        
        # Root
        root = PhylogeneticNode(
            id="proto_dravidian",
            name="Proto-Dravidian",
            parent=None,
            children=["south_dravidian_i", "south_central_dravidian"],
            depth=0
        )
        self.nodes["proto_dravidian"] = root
        self.family_roots["dravidian"] = "proto_dravidian"
        
        # South-Dravidian I (Literary languages)
        south_dravidian_i = PhylogeneticNode(
            id="south_dravidian_i",
            name="South-Dravidian I",
            parent="proto_dravidian",
            languages=["ta", "ml", "kn"],  # Tamil, Malayalam, Kannada
            depth=1
        )
        self.nodes["south_dravidian_i"] = south_dravidian_i
        for lang in south_dravidian_i.languages:
            self.language_to_node[lang] = "south_dravidian_i"
        
        # South-Central Dravidian (Telugu)
        south_central_dravidian = PhylogeneticNode(
            id="south_central_dravidian",
            name="South-Central Dravidian",
            parent="proto_dravidian",
            languages=["te"],  # Telugu
            depth=1
        )
        self.nodes["south_central_dravidian"] = south_central_dravidian
        for lang in south_central_dravidian.languages:
            self.language_to_node[lang] = "south_central_dravidian"
    
    def _build_uralic_tree(self):
        """Construct Uralic language family tree.
        
        Major branches: Finnic, Ugric
        Includes Finnish, Estonian (Finnic) and Hungarian (Ugric).
        """
        
        # Root
        root = PhylogeneticNode(
            id="proto_uralic",
            name="Proto-Uralic",
            parent=None,
            children=["finnic", "ugric"],
            depth=0
        )
        self.nodes["proto_uralic"] = root
        self.family_roots["uralic"] = "proto_uralic"
        
        # Finnic branch
        finnic = PhylogeneticNode(
            id="finnic",
            name="Finnic",
            parent="proto_uralic",
            languages=["fi", "et"],  # Finnish, Estonian
            depth=1
        )
        self.nodes["finnic"] = finnic
        for lang in finnic.languages:
            self.language_to_node[lang] = "finnic"
        
        # Ugric branch (Hungarian)
        ugric = PhylogeneticNode(
            id="ugric",
            name="Ugric",
            parent="proto_uralic",
            languages=["hu"],  # Hungarian
            depth=1
        )
        self.nodes["ugric"] = ugric
        self.language_to_node["hu"] = "ugric"
    
    def path_distance(self, lang_a: str, lang_b: str) -> int:
        """Compute tree path distance between languages.
        
        Returns number of edges in shortest path through tree.
        For cross-family comparisons, returns standardized large distance.
        Lower distance = more closely related.
        
        Args:
            lang_a: ISO 639 language code
            lang_b: ISO 639 language code
            
        Returns:
            Integer distance (0 = same language, 15 = cross-family, 999 = unknown)
        """
        
        if lang_a == lang_b:
            return 0
        
        # Find nodes containing each language
        node_a_id = self.language_to_node.get(lang_a)
        node_b_id = self.language_to_node.get(lang_b)
        
        if not node_a_id or not node_b_id:
            # Unknown language, return maximum distance
            return 999
        
        # Get paths to root for each language
        path_a = self._path_to_root(node_a_id)
        path_b = self._path_to_root(node_b_id)
        
        # Check if they share a common root (same family)
        root_a = path_a[-1] if path_a else None
        root_b = path_b[-1] if path_b else None
        
        if root_a != root_b:
            # Cross-family comparison (e.g., IE vs Dravidian)
            # Return standardized large distance for unrelated families
            return 15
        
        # Within same family: find lowest common ancestor
        lca = None
        for i, (na, nb) in enumerate(zip(reversed(path_a), reversed(path_b))):
            if na != nb:
                if i > 0:
                    lca = path_a[-(i)]
                break
        else:
            # One is ancestor of other
            lca = path_a[-1] if len(path_a) < len(path_b) else path_b[-1]
        
        if lca is None:
            # Fallback to root
            lca = root_a
        
        # Distance = edges from a to LCA + edges from LCA to b
        dist_a = len([n for n in path_a if n != lca])
        dist_b = len([n for n in path_b if n != lca])
        
        return dist_a + dist_b
    
    def cognate_prior(self, distance: int) -> float:
        """Prior probability of cognate relationship given tree distance.
        
        Based on empirical observations:
        - Same sub-branch (distance 1-2): P(cognate) ≈ 0.3
        - Same branch (distance 3-4): P(cognate) ≈ 0.15
        - Different branches (distance 5+): P(cognate) ≈ 0.05
        - Cross-family (distance 15): P(cognate) ≈ 0.001 (loanwords only)
        - Unknown (distance 999): P(cognate) ≈ 0.001
        
        Args:
            distance: Tree path distance
            
        Returns:
            Prior probability [0, 1]
        """
        
        if distance == 0:
            return 1.0  # Same language
        elif distance == 1:
            return 0.4  # Same sub-family (e.g., East Slavic)
        elif distance == 2:
            return 0.3  # Same family, different sub (e.g., East vs West Slavic)
        elif distance <= 4:
            return 0.15  # Same major branch
        elif distance <= 6:
            return 0.08  # Different branches, same superfamily
        elif distance <= 10:
            return 0.03  # Distant within family
        elif distance == 15:
            return 0.001  # Cross-family (possible loanword)
        else:
            return 0.001  # Unknown language or extreme distance
    
    def _path_to_root(self, node_id: str) -> list[str]:
        """Get path from node to root.
        
        Returns list of node IDs from node to root (inclusive).
        Works with multiple family roots (IE, Dravidian, Uralic).
        """
        
        path = [node_id]
        current = node_id
        
        # Traverse up until we hit a node with no parent (root)
        while True:
            node = self.nodes.get(current)
            if not node or not node.parent:
                break
            path.append(node.parent)
            current = node.parent
        
        return path
    
    def get_branch(self, lang: str) -> Optional[str]:
        """Get major branch for language.
        
        Returns branch name (e.g., "germanic", "slavic", "south_dravidian_i").
        """
        
        node_id = self.language_to_node.get(lang)
        if not node_id:
            return None
        
        path = self._path_to_root(node_id)
        
        # Return first non-root ancestor (major branch)
        if len(path) >= 2:
            return path[-2]
        
        return None
    
    def get_family(self, lang: str) -> Optional[str]:
        """Get language family for a language.
        
        Returns:
            "indo-european", "dravidian", "uralic", or None if unknown
        """
        
        node_id = self.language_to_node.get(lang)
        if not node_id:
            return None
        
        path = self._path_to_root(node_id)
        root = path[-1] if path else None
        
        # Map root nodes to family names
        for family_name, root_id in self.family_roots.items():
            if root == root_id:
                return family_name
        
        return None

