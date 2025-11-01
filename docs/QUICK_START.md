# LangViz Quick Start: Data Acquisition

## TL;DR - The Practical Reality

After comprehensive research, here's the **optimal strategy** for getting sufficient Indo-European language data:

### ✅ What Actually Works (Recommended Approach)

**Phase 1: Start Small, Validate Fast** (Do this NOW)
1. Use the existing `data/raw/example_swadesh.csv` to test the pipeline
2. Manually download UT Austin PIE Lexicon (scrape/copy ~2000 roots)
3. Download Perseus Greek & Latin dictionaries from GitHub

**Phase 2: Scale Up with Real Data**
1. Access Wiktionary parsed data from Kaikki.org or directly via Wiktionary API
2. Use ASJP Database for Proto-IE reconstructions
3. Integrate Academia Prisca PDF lexicon (4000+ Late PIE entries)

---

## Why the "CLDF-First" Ideal Doesn't Match Reality

### The Theory
- **IELex** is cited everywhere as the gold standard
- **Lexibank** supposedly has 100+ curated datasets
- Everything should be in nice, standardized CLDF format

### The Reality
- IELex GitHub repo doesn't exist at the expected URL
- Many Lex ibank datasets are either:
  - Non-IE languages
  - Paywalled/access-restricted
  - Incomplete or unmaintained
- CLDF is great IF you can find the data

---

## Verified Working Sources

### 1. University of Texas PIE Lexicon ⭐ START HERE
- **URL**: https://lrc.la.utexas.edu/lex
- **What**: ~2000 PIE roots with reflexes in 10+ IE languages
- **Format**: HTML tables (requires scraping)
- **Coverage**: English, German, Latin, Greek, Sanskrit, Avestan, Persian, Russian, Polish, Lithuanian, Old Irish
- **Quality**: ★★★★★ Academic, curated by linguists
- **Size**: Small but high-impact

**How to Get It**:
```bash
# Option 1: Manual scraping script (TODO: create)
python backend/cli/scrape_ut_lexicon.py

# Option 2: Manual copy-paste
# Visit site, export table data, convert to CSV
```

### 2. Perseus Digital Library ✅ VERIFIED
- **GitHub**: https://github.com/PerseusDL/lexica
- **What**: Ancient Greek (LSJ) and Latin (Lewis & Short) dictionaries
- **Format**: TEI XML
- **Coverage**: 116K Greek + 50K Latin entries
- **Quality**: ★★★★★ Canonical references

**How to Get It**:
```bash
cd data/sources/perseus
# Greek
curl -o lsj_greek.xml https://raw.githubusercontent.com/PerseusDL/lexica/master/CTS_XML_TEI/perseus/pdllex/grc/lsj/grc.lsj.perseus-eng1.xml

# Latin
curl -o lewis_short_latin.xml https://raw.githubusercontent.com/PerseusDL/lexica/master/CTS_XML_TEI/perseus/pdllex/lat/ls/lat.ls.perseus-eng1.xml
```

### 3. Academia Prisca Late PIE Lexicon
- **URL**: https://academiaprisca.org/dnghu/en/resources/
- **What**: 4000+ Late PIE reconstructions with derivatives
- **Format**: PDF (requires extraction)
- **License**: CC-BY-SA 3.0
- **Quality**: ★★★★ Academic, North-West IE focus

**How to Get It**:
```bash
cd data/sources/academia_prisca
curl -O https://academiaprisca.org/dnghu/en/resources/PIE_Lexicon.pdf
# Then use PDF extraction tool or GPT-4 Vision to structure
```

### 4. Wiktionary via Kaikki.org (If URLs work)
- **Base**: https://kaikki.org/dictionary/
- **What**: Parsed Wiktionary data for all languages
- **Format**: JSONL (JSON Lines)
- **Coverage**: 400+ languages including all major IE
- **Quality**: ★★★ Variable (community-sourced)

**How to Verify URLs**:
```bash
# Test if downloads are available
curl -I https://kaikki.org/dictionary/downloads.html
# Then find actual download links
```

**Alternative**: Use Wiktionary API directly
```python
import requests

API = "https://en.wiktionary.org/w/api.php"
params = {
    'action': 'parse',
    'page': 'dog',
    'format': 'json',
    'prop': 'wikitext'
}
response = requests.get(API, params=params)
```

### 5. ASJP Database - Proto-IE Wordlist
- **URL**: https://asjp.clld.org/languages/PROTO_INDO_EUROPEAN
- **What**: Swadesh-100 list for PIE with reconstructions
- **Format**: Web table (copy-paste or scrape)
- **Coverage**: 100 core concepts
- **Quality**: ★★★★ Peer-reviewed

---

## Recommended Implementation Sequence

### Week 1: Foundation (5-10K entries)
```bash
# 1. Test with existing data
python backend/cli/ingest.py data/raw/example_swadesh.csv --source swadesh_207

# 2. Download Perseus dictionaries
cd data/sources/perseus
curl -O https://raw.githubusercontent.com/PerseusDL/lexica/master/CTS_XML_TEI/perseus/pdllex/grc/lsj/grc.lsj.perseus-eng1.xml
curl -O https://raw.githubusercontent.com/PerseusDL/lexica/master/CTS_XML_TEI/perseus/pdllex/lat/ls/lat.ls.perseus-eng1.xml

# 3. Ingest Perseus data
python backend/cli/ingest.py data/sources/perseus/grc.lsj.perseus-eng1.xml --source perseus_greek --format xml
```

### Week 2: Core IE Data (20-30K entries)
```bash
# 4. Build UT Austin scraper
python backend/cli/scrape_ut_lexicon.py --output data/sources/ut_austin/pie_lexicon.csv

# 5. Process Academia Prisca PDF
python backend/cli/extract_pdf_lexicon.py \
  data/sources/academia_prisca/PIE_Lexicon.pdf \
  --output data/sources/academia_prisca/pie_entries.json

# 6. Ingest both
python backend/cli/ingest.py data/sources/ut_austin/pie_lexicon.csv --source ut_austin_pie
python backend/cli/ingest.py data/sources/academia_prisca/pie_entries.json --source academia_prisca_pie
```

### Week 3: Scale Up (100K+ entries)
```bash
# 7. Integrate Wiktionary data (either Kaikki or API)
python backend/cli/wiktionary_fetcher.py --languages en,de,es,fr,ru,hi --output data/sources/wiktionary/

# 8. Ingest modern language dictionaries
for lang in en de es fr ru hi; do
  python backend/cli/ingest.py data/sources/wiktionary/${lang}.jsonl --source wiktionary_${lang} --format jsonl
done
```

---

## Alternative: Start with What We Have

If external downloads are problematic, **build from Wiktionary API**:

```python
# backend/cli/wiktionary_bootstrap.py
import requests
from tqdm import tqdm

SWADESH_207 = ['I', 'you', 'we', 'this', 'that', 'who', 'what', 'not', 'all', 'many', ...]  # Full list

for word in tqdm(SWADESH_207):
    # Fetch from Wiktionary for each language
    for lang in ['English', 'German', 'Spanish', 'Russian', 'Hindi']:
        # Get page, parse etymology, IPA, definitions
        # Store in local database
        pass
```

This approach:
- ✅ No external downloads needed
- ✅ Always up-to-date
- ✅ Respects rate limits
- ✅ Focused on core vocabulary first
- ⚠️ Takes longer but is reliable

---

## Success Metrics (Realistic)

### Minimum Viable Dataset (MVP)
- [ ] 10 IE languages
- [ ] 100-200 core concepts (Swadesh list)
- [ ] 2,000-5,000 total entries
- [ ] Basic etymology links
- [ ] IPA transcriptions for 50%+

### Production Ready
- [ ] 30+ IE languages
- [ ] 500+ concepts per language
- [ ] 50,000+ total entries
- [ ] Cognate sets for Swadesh 100
- [ ] IPA transcriptions for 80%+

### Comprehensive
- [ ] 50+ IE languages (including ancient/extinct)
- [ ] Full dictionary coverage for major languages
- [ ] 200,000+ entries
- [ ] Complete cognate network
- [ ] 90%+ IPA coverage

---

## Next Immediate Actions

1. **Test existing pipeline** with `example_swadesh.csv`
   ```bash
   python backend/cli/ingest.py data/raw/example_swadesh.csv --source swadesh_207
   ```

2. **Download Perseus dictionaries** (verified working URLs)
   ```bash
   mkdir -p data/sources/perseus
   cd data/sources/perseus
   curl -O https://raw.githubusercontent.com/PerseusDL/lexica/master/CTS_XML_TEI/perseus/pdllex/grc/lsj/grc.lsj.perseus-eng1.xml
   ```

3. **Build UT Austin scraper** (priority task)
   - Create `backend/cli/scrape_ut_lexicon.py`
   - Parse HTML tables from https://lrc.la.utexas.edu/lex
   - Export to CSV

4. **Validate ingestion pipeline** with real data
   - Ensure provenance tracking works
   - Test deduplication
   - Verify IPA extraction

5. **Build Wiktionary API client** (sustainable solution)
   - Rate-limited requests
   - Etymology parsing
   - Batch processing

---

## The Intelligent Design Insight

**Why this approach is superior to "download all dictionaries"**:

1. **Focused Scope**: Start with core vocabulary (Swadesh lists) across many languages rather than complete dictionaries for a few
   
2. **Quality over Quantity**: 5000 well-curated, inter-linked entries beats 500K unstructured definitions

3. **Incremental Value**: Each source adds specific value:
   - Perseus: Ancient languages with scholarly rigor
   - UT Austin: PIE reconstructions with reflexes
   - Academia Prisca: Late PIE derivatives
   - Wiktionary: Modern usage + etymology chains

4. **API-First Where Possible**: Live APIs (Wiktionary) are better than stale dumps

5. **Validation Built-In**: Multiple sources for same concepts enables cross-validation

---

## Troubleshooting

### If downloads fail:
1. Check if URLs have changed (common for academic sites)
2. Look for mirrors or alternative hosts
3. Contact maintainers for data access
4. Fall back to API-based collection

### If a source is unavailable:
- Don't block on it
- Move to next priority source
- Build with what works
- Can always add more data later

### If quality is poor:
- Start with high-quality core (Perseus, UT Austin)
- Use as gold standard for validation
- Filter community data (Wiktionary) against it

---

**Remember**: Perfect is the enemy of good. Start with 5000 quality entries and grow from there.

