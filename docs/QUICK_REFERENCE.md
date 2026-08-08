# 🚀 Quick Reference - Bundle Registry Commands

## 📋 **CLI Commands Cheat Sheet**

### **List Available Bundles**
```bash
cgc registry list                    # Show all bundles
cgc registry list --verbose          # Show with download URLs
cgc registry list -v                 # Short form
```

### **Search for Bundles**
```bash
cgc registry search flask            # Search by name
cgc registry search http             # Search by keyword
cgc registry search "web framework"  # Search phrase
```

### **Download Bundles**
```bash
cgc registry download flask          # Download to current dir
cgc registry download flask -o ./bundles  # Download to specific dir
cgc registry download flask --load   # Download and auto-load
cgc registry download flask -l       # Short form
```

### **Load Bundles (Auto-Download)**
```bash
cgc load flask                       # Auto-downloads if needed
cgc load httpx --clear               # Clear DB before loading
cgc load /path/to/bundle.cgc         # Load from local file
```

### **Request Custom Bundle**
```bash
cgc registry request https://github.com/encode/httpx
cgc registry request https://github.com/pallets/flask
```

---

## 🌐 **Website Features**

### **Browse Bundles**
- Visit: https://codegraphcontext.vercel.app
- Scroll to: "Pre-indexed Repositories"
- Features: Search, filter, download

### **Generate Custom Bundle**
- Scroll to: "Generate Custom Bundle"
- Enter: GitHub repository URL
- Click: "Generate Bundle"
- Wait: 5-10 minutes
- Download: When ready

---

## 📊 **Common Workflows**

### **Quick Start: Load a Bundle**
```bash
# One command - downloads and loads
cgc load flask
```

### **Browse Before Downloading**
```bash
# See what's available
cgc registry list

# Search for something specific
cgc registry search web

# Download and load
cgc load fastapi
```

### **Generate Custom Bundle**
```bash
# Request generation
cgc registry request https://github.com/psf/requests

# Wait 5-10 minutes, then:
cgc load requests
```

---

## 🔍 **Explore Loaded Bundles**

### **View Repository Info**
```bash
cgc list                             # List all loaded repos
cgc stats                            # Show database stats
cgc stats /path/to/repo              # Stats for specific repo
```

### **Query the Graph**
```bash
# Find all classes
cgc query "MATCH (c:Class) RETURN c.name LIMIT 20"

# Find all functions
cgc query "MATCH (f:Function) RETURN f.name LIMIT 20"

# Search for specific code
cgc find name Flask
cgc find name render_template
```

---

## 📦 **Available Bundles**

Current bundles in registry:
- **flask** - Lightweight web framework (316K)
- **httpx** - HTTP client (268K)
- **fastapi** - Modern API framework (796K)
- **requests** - HTTP library (224K)
- **StatWrap** - Statistics wrapper (380K)

*Use `cgc registry list` for latest*

---

## 🆘 **Help Commands**

```bash
cgc --help                           # General help
cgc registry --help                  # Registry commands help
cgc registry list --help             # Specific command help
cgc registry download --help
cgc registry search --help
cgc registry request --help
```

---

## 🎯 **Examples**

### **Example 1: Quick Load**
```bash
$ cgc load flask
Bundle 'flask' not found locally.
Attempting to download from registry...
✓ Downloaded successfully: flask-main-2579ce9.cgc
✅ Successfully imported flask-main-2579ce9.cgc
   Nodes: 4,534 | Edges: 9,218
```

### **Example 2: Search and Download**
```bash
$ cgc registry search http
Found 1 matching bundle(s)
┃ httpx │ encode/httpx │ main │ 268K ┃

$ cgc load httpx
✓ Downloaded and loaded successfully!
```

### **Example 3: Browse All**
```bash
$ cgc registry list
Available Bundles
┃ flask    │ pallets/flask   │ 316K ┃
┃ httpx    │ encode/httpx    │ 268K ┃
┃ fastapi  │ fastapi/fastapi │ 796K ┃
┃ requests │ psf/requests    │ 224K ┃
```

---

## 💡 **Tips**

1. **Auto-Download:** `cgc load` automatically downloads from registry if not found locally
2. **Search First:** Use `cgc registry search` to find bundles before downloading
3. **Verbose Mode:** Add `-v` to see download URLs
4. **Clear Database:** Use `--clear` flag to replace existing data
5. **Local Files:** `cgc load` works with both bundle names and file paths

---

## 🔗 **Resources**

- **Documentation:** `/docs/ON_DEMAND_BUNDLES.md`
- **CLI Guide:** `/CLI_REGISTRY_COMMANDS.md`
- **Website:** https://codegraphcontext.vercel.app
- **GitHub:** https://github.com/CodeGraphContext/CodeGraphContext

---

## ✅ **Quick Checklist**

- [ ] List available bundles: `cgc registry list`
- [ ] Search for a bundle: `cgc registry search <query>`
- [ ] Download a bundle: `cgc load <name>`
- [ ] View loaded repos: `cgc list`
- [ ] Query the graph: `cgc query "<query>"`

---

**Save this file for quick reference!** 📌

All commands are ready to use. Just run them in your terminal! 🚀
