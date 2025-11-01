# Indo-European Language Data Acquisition Strategy

## Executive Summary

**Optimal Approach: Multi-Tier CLDF-First Strategy**

Instead of downloading individual dictionaries for 100+ Indo-European languages, we leverage **standardized linguistic databases** that provide:
1. Pre-aligned concept lists (Swadesh, etc.)
2. Cognate sets already identified by linguists
3. IPA transcriptions and phonological data
4. Machine-readable formats (CLDF/JSON)
5. Provenance tracking and citation metadata

This is **superior** to raw dictionary scraping because:
- **Efficiency**: One CLDF dataset = 50+ languages with aligned concepts
- **Quality**: Curated by computational linguists, peer-reviewed
- **Interoperability**: Standardized format our system already supports
- **Completeness**: Includes metadata (sources, phonetics, cognate sets)
- **Legal**: All sources have clear academic licenses

---

## Tier 1: Primary Sources (CLDF Format - Highest Priority)

### 1.1 IELex (IE-CoR) - **START HERE**
- **URL**: https://github.com/lexibank/ielex
- **Coverage**: 95 Indo-European varieties across all major branches
- **Concepts**: 207 Swadesh items + extended vocabulary
- **Format**: CLDF (pycldf compatible)
- **Quality**: Peer-reviewed, gold standard
- **License**: CC-BY-4.0
- **Size**: ~20,000 lexical entries
- **Cognate Sets**: Pre-computed by historical linguists

**Action**: 
```bash
cd data/sources
git clone https://github.com/lexibank/ielex.git
```

### 1.2 Additional Lexibank IE Datasets

All available at `https://github.com/lexibank/`:

- **abvd** - Austronesian, but includes Indo-Aryan loans
- **allenbai** - Chinese dialects (IE loanword analysis)
- **bowernpny** - Comparative wordlists with IE loans
- **castrosui** - Southern Uto-Aztecan (IE contacts)
- **kleinewillinghoeferroelke** - Indo-Iranian focus
- **ratcliffearabic** - Arabic (massive IE loans)
- **ruhlenprotoworld** - Global comparison (includes full IE)
- **savelyevturkic** - Turkic languages (IE substrate/contacts)
- **suntlapproto** - Proto-Uralic (IE contacts)
- **transnewguineaorg** - Papua (for contrast studies)

**Priority for IE Research**:
```bash
# Clone these systematically
for dataset in ielex kleinewillinghoeferroelke ruhlenprotoworld; do
    git clone https://github.com/lexibank/$dataset.git data/sources/$dataset
done
```

### 1.3 Concepticon Integration
- **URL**: https://concepticon.clld.org/
- **Purpose**: Standardized concept IDs (map "dog" across all languages)
- **Integration**: IELex already uses Concepticon IDs
- **Action**: Use concepticon Python library for concept alignment

---

## Tier 2: Comprehensive Coverage (Machine-Readable)

### 2.1 Kaikki.org Wiktionary Extracts - **MASSIVE SCALE**
- **URL**: https://kaikki.org/dictionary/downloads.html
- **Coverage**: ALL languages with Wiktionary entries (400+ languages)
- **IE Languages**: English, German, Spanish, French, Russian, Hindi, Persian, Armenian, Albanian, Greek, Latin, Sanskrit, Welsh, Irish, Lithuanian, etc.
- **Format**: JSONL (JSON Lines) - one entry per line
- **Size**: ~10GB compressed, 100GB+ uncompressed
- **Quality**: Variable (community-sourced) but comprehensive
- **License**: CC-BY-SA 3.0
- **Updates**: Monthly dumps

**Unique Value**: 
- Modern vocabulary (not just Swadesh lists)
- Etymology chains already parsed
- Multiple definitions per word
- Pronunciation data (IPA when available)

**Download Strategy**:
```bash
# Download by language, not all at once
curl -O https://kaikki.org/dictionary/English/kaikki.org-dictionary-English.json
curl -O https://kaikki.org/dictionary/German/kaikki.org-dictionary-German.json
# Repeat for all IE languages
```

**Processing Pipeline**:
1. Filter entries with etymology sections
2. Extract cognate mentions
3. Parse IPA transcriptions
4. Build cross-reference graph

### 2.2 University of Texas PIE Lexicon
- **URL**: https://lrc.la.utexas.edu/lex
- **Format**: HTML (requires scraping)
- **Coverage**: ~2,000 PIE roots with reflexes in 10+ languages
- **Quality**: Academic, maintained by linguists
- **Action**: Write focused scraper (low volume, high value)

### 2.3 Academia Prisca Late PIE Lexicon
- **URL**: https://academiaprisca.org/dnghu/en/resources/PIE_Lexicon.pdf
- **Format**: PDF (4000+ entries)
- **Coverage**: Late PIE vocabulary with North-West IE focus
- **License**: CC-BY-SA 3.0
- **Action**: PDF text extraction → structure with GPT-4 assistance

---

## Tier 3: Specialized Resources

### 3.1 Starling Database
- **URL**: http://starling.rinet.ru/
- **Coverage**: Full IE etymological database
- **Format**: Custom (requires Starling software OR scraping)
- **Quality**: Professional, but interface is dated
- **Action**: Consider lower priority due to access complexity

### 3.2 Language-Specific Academic Dictionaries

**Sanskrit**:
- Monier-Williams Sanskrit-English Dictionary (public domain)
- Digital Corpus of Sanskrit (https://www.sanskrit-linguistics.org/)

**Ancient Greek**:
- Liddell-Scott-Jones Greek-English Lexicon (Perseus Digital Library)
- URL: http://www.perseus.tufts.edu/hopper/

**Latin**:
- Lewis & Short Latin Dictionary (Perseus)
- URL: http://www.perseus.tufts.edu/hopper/

**Old Church Slavonic**:
- Slovník jazyka staroslověnského (Lexicon Linguae Palaeoslovenicae)

**Celtic Languages**:
- eDIL (Electronic Dictionary of the Irish Language)
- URL: http://www.dil.ie/

---

## Tier 4: APIs and Real-Time Sources

### 4.1 Wiktionary API (MediaWiki)
- **URL**: https://en.wiktionary.org/w/api.php
- **Rate Limit**: 200 requests/second (with bot flag)
- **Coverage**: Real-time access to all Wiktionary content
- **Use Case**: Supplementary data, etymology verification

### 4.2 Oxford API (Commercial)
- **URL**: https://developer.oxforddictionaries.com/
- **Cost**: Free tier (1000 requests/month), paid tiers available
- **Coverage**: Modern languages, high quality
- **Use Case**: Validation and modern usage data

---

## Recommended Implementation Sequence

### Phase 1: Foundation (Week 1)
1. **Download IELex** (5-10 minutes)
   - Full CLDF dataset with 95 IE varieties
   - Immediate value for prototyping

2. **Set up CLDF loader** (already done!)
   - Test with IELex
   - Validate provenance tracking

3. **Ingest first 10 languages**
   - English, German, Latin, Greek, Sanskrit, Russian, Spanish, French, Hindi, Persian
   - Establish baseline for visualization

### Phase 2: Comprehensive Coverage (Week 2-3)
1. **Download Kaikki.org extracts** for top 30 IE languages
   - Parallel downloads
   - ~100GB storage needed

2. **Build Kaikki.org loader**
   - Parse JSONL format
   - Extract etymology links
   - Filter for quality markers

3. **Ingest full dataset**
   - ~500k-1M entries across IE languages

### Phase 3: Deep Resources (Week 4)
1. **Scrape UT Austin PIE Lexicon**
   - ~2000 roots with reflexes
   - Critical for cognate validation

2. **Process Academia Prisca PDF**
   - 4000+ Late PIE entries
   - Cross-reference with IELex

3. **Integrate Perseus dictionaries**
   - Ancient Greek, Latin, Sanskrit
   - Deep historical data

### Phase 4: Validation & Enhancement (Ongoing)
1. **Cross-reference cognate sets**
2. **Validate phonetic correspondences**
3. **Build confidence scores**
4. **Community feedback integration**

---

## Storage Requirements

| Source | Compressed | Uncompressed | Entries |
|--------|-----------|--------------|---------|
| IELex | 5 MB | 25 MB | 20,000 |
| Kaikki (30 langs) | 3 GB | 30 GB | 1M+ |
| UT PIE Lexicon | 1 MB | 5 MB | 2,000 |
| Academia Prisca | 2 MB | 10 MB | 4,000 |
| Perseus (3 langs) | 50 MB | 200 MB | 100,000 |
| **Total** | **~3.5 GB** | **~35 GB** | **~1.13M** |

---

## Data Quality Validation

### Automated Checks
1. **IPA validation** (using panphon)
2. **Concept alignment** (using Concepticon)
3. **Cognate consistency** (phonetic distance metrics)
4. **Etymology chain validation** (graph cycles)

### Manual Review Checkpoints
1. Sample 100 entries per language
2. Verify cognate sets for Swadesh 100 core
3. Cross-reference disputed etymologies with academic sources

---

## Legal & Ethical Considerations

All recommended sources:
- ✅ Have explicit licenses (CC-BY, CC-BY-SA, Public Domain)
- ✅ Are intended for academic/research use
- ✅ Include proper attribution metadata
- ✅ Respect rate limits for APIs
- ✅ Provide citation information

**Our Implementation**:
- Store source metadata with every entry (provenance tracking)
- Include citation templates for users
- Respect robots.txt for any scraping
- Attribute community contributors (Wiktionary)

---

## Why This Approach is Superior

### vs. Individual Dictionary Downloads
- **Time**: Days instead of months
- **Coverage**: Pre-aligned concepts
- **Quality**: Expert-curated cognate sets
- **Maintenance**: Active communities updating data

### vs. Commercial APIs Only
- **Cost**: Free and open
- **Scale**: No rate limits on local data
- **Depth**: Historical data not in modern APIs
- **Research**: Full dataset access for novel algorithms

### vs. Pure Wiktionary Scraping
- **Structure**: CLDF provides relational structure
- **Cognates**: Pre-identified by linguists
- **Phonetics**: Standardized IPA in CLDF
- **Validation**: Peer-reviewed baseline (IELex)

---

## Next Steps

1. **Clone IELex immediately** - validate our CLDF pipeline
2. **Update catalog.toml** with detailed source metadata
3. **Build download automation** for Kaikki.org
4. **Create data validation dashboard** for quality monitoring
5. **Implement parallel ingestion** for 30+ languages

## Success Metrics

- [ ] 50+ IE languages with 100+ Swadesh items each
- [ ] 10,000+ cognate sets identified
- [ ] 100,000+ lexical entries ingested
- [ ] 90%+ entries with IPA transcription
- [ ] Full provenance tracking for all entries
- [ ] <5% duplicate entries after deduplication


