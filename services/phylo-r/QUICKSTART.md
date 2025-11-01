# R Service Quick Start

## 5-Minute Setup

### 1. Install R (if not already installed)

**macOS:**
```bash
brew install r
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install r-base r-base-dev
```

**Check installation:**
```bash
R --version
# Should show R version 4.0.0 or higher
```

### 2. Install Dependencies

```bash
cd services/phylo-r
Rscript install_deps.R
```

This installs: `jsonlite`, `ape`, `phangorn`, `pvclust`

### 3. Start R Service

```bash
./start.sh
```

You should see:
```
Starting R Phylogenetic Analysis Service...
Checking R package dependencies...
All dependencies installed.

Starting server on port 50052...
Starting R phylo service on port 50052...
Loaded packages: ape, phangorn, pvclust
Ready to accept connections.
```

### 4. Test from Python

Open a new terminal:

```python
cd backend
python3

>>> from backend.interop.r_client import RPhyloClient
>>> import numpy as np
>>>
>>> distances = np.array([[0.0, 0.3], [0.3, 0.0]])
>>> labels = ["English", "German"]
>>>
>>> with RPhyloClient() as client:
...     print(client.ping())  # Should print True
...     tree = client.infer_tree(distances, labels)
...     print(tree.newick)
True
(English:0.15,German:0.15);
```

✅ **Success!** R service is working.

## Common Issues

### "Connection refused"
- **Problem**: R service not running
- **Solution**: Start with `./start.sh` in `services/phylo-r/`

### "Package not found"
- **Problem**: R dependencies not installed
- **Solution**: Run `Rscript install_deps.R`

### "R: command not found"
- **Problem**: R not installed
- **Solution**: Install R (see step 1 above)

## What's Next?

1. **Read the docs**: See `README.md` for full API
2. **Try examples**: See `docs/R_INTEGRATION.md` for usage patterns
3. **Run tests**: `pytest backend/tests/test_r_integration.py -v`
4. **Enable in production**: Set `use_r=True` in `PhyloService` initialization

## Running in Production

### As systemd service (Linux)

Create `/etc/systemd/system/langviz-r.service`:

```ini
[Unit]
Description=LangViz R Phylogenetic Service
After=network.target

[Service]
Type=simple
User=langviz
WorkingDirectory=/path/to/LangViz/services/phylo-r
ExecStart=/usr/bin/Rscript server.R
Restart=always

[Install]
WantedBy=multi-user.target
```

Start:
```bash
sudo systemctl start langviz-r
sudo systemctl enable langviz-r
```

### As background process (macOS/Linux)

```bash
cd services/phylo-r
nohup Rscript server.R > r_service.log 2>&1 &
echo $! > r_service.pid
```

Stop:
```bash
kill $(cat r_service.pid)
```

### Docker (future)

```dockerfile
FROM r-base:4.3.0
WORKDIR /app
COPY services/phylo-r/ .
RUN Rscript install_deps.R
EXPOSE 50052
CMD ["Rscript", "server.R"]
```

## Performance Tips

1. **Keep service running**: Don't restart for each request
2. **Use caching**: `PhyloService` caches results automatically
3. **Batch operations**: Process multiple trees together
4. **Reduce bootstrap**: 50-100 replicates usually sufficient

## Help

- **Full docs**: `services/phylo-r/README.md`
- **Architecture**: `docs/R_INTEGRATION.md`
- **Tests**: `backend/tests/test_r_integration.py`
- **Issues**: Check logs in `r_service.log`

