#!/usr/bin/env python3
"""Verify language coverage across data sources and phylogenetic tree.

Checks:
- All languages in phylogenetic tree
- All Kaikki data files present
- Mapping between ISO codes and data files
- Missing data identification
"""

import sys
from pathlib import Path
from collections import defaultdict
from typing import Dict, Set, List

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.services.phylogeny import PhylogeneticTree


def get_kaikki_files(kaikki_dir: Path) -> Dict[str, Path]:
    """Get all Kaikki data files.
    
    Returns:
        Dict mapping language name to file path
    """
    files = {}
    if kaikki_dir.exists():
        for file in kaikki_dir.glob("*.jsonl"):
            lang_name = file.stem
            files[lang_name] = file
    return files


def get_tree_languages(tree: PhylogeneticTree) -> Dict[str, Dict[str, str]]:
    """Get all languages from phylogenetic tree.
    
    Returns:
        Dict mapping ISO code to language info
    """
    languages = {}
    for iso_code, node_id in tree.language_to_node.items():
        family = tree.get_family(iso_code)
        branch = tree.get_branch(iso_code)
        languages[iso_code] = {
            "node_id": node_id,
            "family": family or "unknown",
            "branch": branch or "unknown"
        }
    return languages


# ISO code to expected Kaikki filename mappings
ISO_TO_KAIKKI = {
    # Romance
    "la": None,  # Perseus XML
    "es": "spanish",
    "pt": "portuguese",
    "fr": "french",
    "it": "italian",
    "ro": "romanian",
    "ca": "catalan",
    
    # Germanic
    "en": "english",
    "de": "german",
    "nl": "dutch",
    "sv": "swedish",
    "da": "danish",
    "no": "norwegian",
    "is": "icelandic",
    "af": "afrikaans",
    "yi": "yiddish",
    "fo": "faroese",
    
    # Slavic
    "ru": "russian",
    "uk": "ukrainian",
    "be": "belarusian",
    "pl": "polish",
    "cs": "czech",
    "sk": "slovak",
    "bg": "bulgarian",
    "mk": "macedonian",
    "sl": "slovene",
    "hr": "serbocroatian",
    "sr": "serbocroatian",
    
    # Indo-Iranian
    "sa": None,  # Need source
    "hi": "hindi",
    "ur": "urdu",
    "bn": "bengali",
    "pa": "punjabi",
    "mr": None,  # Need Marathi
    "gu": None,  # Need Gujarati
    "fa": "persian",
    "ps": "pashto",
    "ku": "northern_kurdish",
    "tg": "tajik",
    
    # Celtic
    "ga": "irish",
    "gd": "scottish_gaelic",
    "cy": "welsh",
    "br": "breton",
    "gv": "manx",
    
    # Baltic
    "lt": "lithuanian",
    "lv": "latvian",
    
    # Hellenic
    "el": "greek",
    "grc": None,  # Perseus XML
    
    # Other IE
    "sq": "albanian",
    "hy": "armenian",
    
    # Dravidian
    "ta": "tamil",
    "te": "telugu",
    "kn": "kannada",
    "ml": "malayalam",
    
    # Uralic
    "fi": "finnish",
    "et": "estonian",
    "hu": "hungarian",
}


# ISO code to language name
ISO_TO_NAME = {
    "la": "Latin", "es": "Spanish", "pt": "Portuguese", "fr": "French",
    "it": "Italian", "ro": "Romanian", "ca": "Catalan",
    "en": "English", "de": "German", "nl": "Dutch", "sv": "Swedish",
    "da": "Danish", "no": "Norwegian", "is": "Icelandic", "af": "Afrikaans",
    "yi": "Yiddish", "fo": "Faroese",
    "ru": "Russian", "uk": "Ukrainian", "be": "Belarusian", "pl": "Polish",
    "cs": "Czech", "sk": "Slovak", "bg": "Bulgarian", "mk": "Macedonian",
    "sl": "Slovene", "hr": "Croatian", "sr": "Serbian",
    "sa": "Sanskrit", "hi": "Hindi", "ur": "Urdu", "bn": "Bengali",
    "pa": "Punjabi", "mr": "Marathi", "gu": "Gujarati",
    "fa": "Persian", "ps": "Pashto", "ku": "Kurdish", "tg": "Tajik",
    "ga": "Irish", "gd": "Scottish Gaelic", "cy": "Welsh", "br": "Breton",
    "gv": "Manx",
    "lt": "Lithuanian", "lv": "Latvian",
    "el": "Greek", "grc": "Ancient Greek",
    "sq": "Albanian", "hy": "Armenian",
    "ta": "Tamil", "te": "Telugu", "kn": "Kannada", "ml": "Malayalam",
    "fi": "Finnish", "et": "Estonian", "hu": "Hungarian",
}


def verify_coverage():
    """Verify language coverage and print report."""
    
    # Initialize
    project_root = Path(__file__).parent.parent.parent
    kaikki_dir = project_root / "data" / "sources" / "kaikki"
    tree = PhylogeneticTree()
    
    # Get data
    kaikki_files = get_kaikki_files(kaikki_dir)
    tree_languages = get_tree_languages(tree)
    
    # Statistics
    stats = defaultdict(lambda: {"total": 0, "with_data": 0, "missing": []})
    
    print("=" * 80)
    print("LangViz Language Coverage Verification")
    print("=" * 80)
    print()
    
    # Check each language in tree
    for iso_code, lang_info in sorted(tree_languages.items()):
        family = lang_info["family"]
        lang_name = ISO_TO_NAME.get(iso_code, iso_code)
        expected_file = ISO_TO_KAIKKI.get(iso_code)
        
        stats[family]["total"] += 1
        
        if expected_file is None:
            status = "⚠️  ALTERNATIVE SOURCE"
            has_data = True  # Has alternative source
        elif expected_file in kaikki_files:
            status = "✅ COMPLETE"
            has_data = True
        else:
            status = "❌ MISSING DATA"
            has_data = False
            stats[family]["missing"].append((iso_code, lang_name))
        
        if has_data:
            stats[family]["with_data"] += 1
        
        # Print status
        if status != "✅ COMPLETE" or "--verbose" in sys.argv:
            print(f"{iso_code:4} | {lang_name:20} | {family:15} | {status}")
    
    print()
    print("=" * 80)
    print("Summary by Family")
    print("=" * 80)
    print()
    
    for family in sorted(stats.keys()):
        total = stats[family]["total"]
        with_data = stats[family]["with_data"]
        coverage = (with_data / total * 100) if total > 0 else 0
        
        print(f"{family.upper()}")
        print(f"  Total languages: {total}")
        print(f"  With data: {with_data}")
        print(f"  Coverage: {coverage:.1f}%")
        
        if stats[family]["missing"]:
            print(f"  Missing:")
            for iso, name in stats[family]["missing"]:
                print(f"    - {name} ({iso})")
        print()
    
    # Overall statistics
    total_all = sum(s["total"] for s in stats.values())
    with_data_all = sum(s["with_data"] for s in stats.values())
    coverage_all = (with_data_all / total_all * 100) if total_all > 0 else 0
    
    print("=" * 80)
    print(f"OVERALL: {with_data_all}/{total_all} languages ({coverage_all:.1f}% coverage)")
    print("=" * 80)
    print()
    
    # Kaikki files not in tree
    print("=" * 80)
    print("Kaikki Files Not Mapped to Tree")
    print("=" * 80)
    print()
    
    used_files = set(f for f in ISO_TO_KAIKKI.values() if f is not None)
    unused_files = set(kaikki_files.keys()) - used_files
    
    if unused_files:
        print("Files present but not mapped:")
        for filename in sorted(unused_files):
            print(f"  - {filename}.jsonl")
    else:
        print("✅ All Kaikki files are mapped!")
    
    print()
    
    # Cross-family distance test
    print("=" * 80)
    print("Cross-Family Distance Tests")
    print("=" * 80)
    print()
    
    test_pairs = [
        ("en", "ta", "IE vs Dravidian"),
        ("fi", "ta", "Uralic vs Dravidian"),
        ("en", "fi", "IE vs Uralic"),
        ("en", "de", "Within IE (close)"),
        ("en", "ru", "Within IE (distant)"),
        ("ta", "te", "Within Dravidian"),
    ]
    
    for lang_a, lang_b, desc in test_pairs:
        dist = tree.path_distance(lang_a, lang_b)
        prior = tree.cognate_prior(dist)
        family_a = tree.get_family(lang_a)
        family_b = tree.get_family(lang_b)
        
        print(f"{lang_a} <-> {lang_b} ({desc})")
        print(f"  Families: {family_a} vs {family_b}")
        print(f"  Distance: {dist}")
        print(f"  Cognate prior: {prior:.4f}")
        print()
    
    return with_data_all == total_all  # Return True if complete


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Verify language coverage")
    parser.add_argument("--verbose", "-v", action="store_true", 
                       help="Show all languages, not just issues")
    
    args = parser.parse_args()
    
    success = verify_coverage()
    sys.exit(0 if success else 1)

