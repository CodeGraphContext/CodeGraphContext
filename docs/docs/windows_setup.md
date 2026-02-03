# CodeGraphContext – Windows Setup Guide

This guide explains how to set up **CodeGraphContext on Windows**.

⚠️ **Important Note for Windows Users**
- **FalkorDB Lite (redislite) is not supported natively on Windows**
- Recommended approach: **Use WSL (Windows Subsystem for Linux)**
- Alternative: Use **Neo4j** as the database backend

---

## Option 1 (Recommended): Setup Using WSL

WSL allows you to run CodeGraphContext in a Linux environment on Windows, enabling **FalkorDB Lite** and ensuring the smoothest setup experience.

---

### Step 1: Install WSL

Open **PowerShell as Administrator** and run:

```powershell
wsl --install
````

Restart your system if prompted.

Verify WSL installation:

```powershell
wsl --version
```

---

### Step 2: Open Ubuntu (WSL Terminal)

After restart:

* Open the Start Menu
* Search for **Ubuntu**
* Open it

Update packages:

```bash
sudo apt update
sudo apt upgrade -y
```

---

### Step 3: Install Python (3.12+ Recommended)

Inside the WSL terminal:

```bash
sudo apt install python3.12 python3-pip -y
```

Verify installation:

```bash
python3 --version
pip3 --version
```

> CodeGraphContext supports **Python 3.10 – 3.14**.
> **FalkorDB Lite works best with Python 3.12+**.

---

### Step 4: Install CodeGraphContext

```bash
pip install codegraphcontext
```

Verify installation:

```bash
cgc --help
```

---

### Step 5: Index a Project

Navigate to your project directory.

Example (accessing Windows files from WSL):

```bash
cd /mnt/c/Users/<yourname>/Desktop/<your-project-folder>
```

Index the codebase:

```bash
cgc index .
```

---

### Step 6 (Optional): Live Watch Mode

To automatically update the graph when files change:

```bash
cgc watch .
```

---

### Step 7 (Optional): MCP Setup (AI Integration)

To use CodeGraphContext as an MCP server for AI assistants/IDEs:

```bash
cgc mcp setup
```

Start the MCP server:

```bash
cgc mcp start
```

---

## Option 2: Native Windows Setup Using Neo4j

If you do not want WSL, CodeGraphContext can be configured to use **Neo4j** as its database backend.

---

### Step 1: Install Python (Windows)

Download Python from:
[https://www.python.org/downloads/](https://www.python.org/downloads/)

During installation, ensure:
✅ **Add Python to PATH**

Verify:

```powershell
python --version
pip --version
```

---

### Step 2: Install CodeGraphContext

```powershell
pip install codegraphcontext
```

Verify:

```powershell
cgc --help
```

---

### Step 3: Install & Run Neo4j

Neo4j can be installed using one of the following:

* Neo4j Desktop (GUI)
* Neo4j via Docker (recommended)
* Neo4j AuraDB (cloud)

Ensure Neo4j is running and note:

* URI (example: `bolt://localhost:7687`)
* Username
* Password

---

### Step 4: Configure Neo4j in CodeGraphContext

Run:

```bash
cgc neo4j setup
```

Follow the prompts to enter your Neo4j credentials.

---

### Step 5: Index a Project

Navigate to your project:

```powershell
cd path\to\your\project
```

Index the codebase:

```powershell
cgc index .
```

---

## Ignoring Files (`.cgcignore`)

To ignore files and folders while indexing, create a `.cgcignore` file in your project root.

Example `.cgcignore`:

```txt
/build/
/dist/
/node_modules/
/vendor/
*.log
```

---

## Common Windows Issues

### `'cgc' command not found`

* Restart your terminal after installation
* Ensure Python Scripts directory is in PATH
* Try: `python -m pip install codegraphcontext`

### WSL path confusion

Windows drives can be accessed from WSL using:

```bash
cd /mnt/c/
```

### Neo4j connection issues

* Ensure Neo4j is running
* Check URI format: `bolt://localhost:7687`
* Double-check username/password

---

## Verify Installation

Run:

```bash
cgc list
```
If no errors are shown, setup is complete 

