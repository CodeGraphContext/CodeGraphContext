# Setup Workflows - CodeGraphContext

This document provides **exact, step-by-step workflows** for setting up and using CodeGraphContext, both for first-time setup and everyday use.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [First-Time Setup: CLI Users](#first-time-setup-cli-users)
3. [First-Time Setup: MCP Users](#first-time-setup-mcp-users)
4. [Every-Time Workflow: CLI Users](#every-time-workflow-cli-users)
5. [Every-Time Workflow: MCP Users](#every-time-workflow-mcp-users)
6. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required
- **Python 3.8+** installed on your system
- **pip** package manager
- **Git** (for cloning repositories)

### Optional (for advanced features)
- **Neo4j** (for large-scale repositories > 100k LOC)
- **Docker** (for containerized deployment)

### Check Prerequisites

```bash
# Check Python version
python --version
# Expected: Python 3.8.0 or higher

# Check pip
pip --version
# Expected: pip 20.0.0 or higher

# Check git
git --version
# Expected: git version 2.0.0 or higher
```

---

## First-Time Setup: CLI Users

**Time Required**: 5-10 minutes  
**Frequency**: Once per machine

### Step 1: Install CodeGraphContext

```bash
# Install via pip
pip install codegraphcontext

# Verify installation
cgc --version

# Expected output:
# CodeGraphContext version 1.0.0
```

**Troubleshooting**: If `cgc` command not found, add Python scripts to PATH:
```bash
# Linux/Mac
export PATH="$HOME/.local/bin:$PATH"

# Windows
# Add %APPDATA%\Python\Scripts to PATH
```

### Step 2: Choose Database Backend (Optional)

CodeGraphContext automatically uses **FalkorDB** (embedded, no setup needed) for most use cases.

**When to use Neo4j instead:**
- Repository > 100,000 lines of code
- Need to share graph across team members
- Want persistent storage across machines

```bash
# Option A: Use FalkorDB (default, recommended for most users)
# No action needed - works out of the box

# Option B: Setup Neo4j (for large repositories)
cgc neo4j setup

# This will:
# 1. Check if Neo4j is installed
# 2. If not, provide installation instructions
# 3. Configure connection settings
# 4. Test the connection
```

**Neo4j Setup Output:**
```
Checking for Neo4j installation...
✗ Neo4j not found

Would you like to install Neo4j? (y/n): y

Installing Neo4j...
✓ Neo4j 5.x installed
✓ Started Neo4j service
✓ Default credentials: neo4j/neo4j

Please change the default password:
New password: ********
Confirm password: ********

✓ Password updated
✓ Connection tested successfully

Configuration saved to: ~/.cgc/config.yml
```

### Step 3: Index Your First Repository

```bash
# Navigate to your project
cd ~/projects/my-project

# Index the repository
cgc index .

# Expected output:
# Indexing repository: /home/user/projects/my-project
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Scanning files...        ✓ 1,247 files found
# Parsing Python files...  ✓ 892 files (71%)
# Parsing JavaScript...    ✓ 234 files (19%)
# Parsing TypeScript...    ✓ 121 files (10%)
# 
# Building graph...
# ✓ Created 3,421 function nodes
# ✓ Created 892 class nodes
# ✓ Created 234 module nodes
# ✓ Created 15,234 relationships
# 
# Database: FalkorDB (embedded)
# Indexing completed in 23.4 seconds
```

### Step 4: Verify Setup

```bash
# Check repository statistics
cgc stats

# Expected output:
# Repository Statistics
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Repository: my-project
# Path: /home/user/projects/my-project
# 
# Code Elements:
#   Files:      1,247
#   Functions:  3,421
#   Classes:    892
#   Modules:    234
# 
# Relationships:
#   Function calls:    8,234
#   Imports:           2,456
#   Inheritance:       234
#   Total:             15,234
# 
# Database: FalkorDB
# Last indexed: 2026-01-30 01:15:23
```

```bash
# Try a simple query
cgc find "main" --type function

# Expected output:
# Found 5 functions matching 'main':
# 
# 1. main
#    File: src/app.py:123
#    
# 2. main_loop
#    File: src/core/event_loop.py:45
# 
# ... (3 more)
```

### Step 5: Explore Available Commands

```bash
# See all available commands
cgc help

# Expected output:
# CodeGraphContext CLI
# 
# Usage: cgc [COMMAND] [OPTIONS]
# 
# Project Management:
#   index [PATH]              Index a repository
#   reindex                   Re-index current repository
#   stats                     Show repository statistics
#   clean                     Clear the database
# 
# Code Discovery:
#   find <query>              Search for code elements
#   visualize                 Generate architecture visualization
# 
# Code Analysis:
#   analyze callers <name>    Find who calls a function
#   analyze callees <name>    Find what a function calls
#   analyze chain <a> <b>     Show call chain between functions
#   analyze deps <module>     Show module dependencies
#   analyze dead-code         Find unused functions
#   analyze complexity        Find complex functions
# 
# ... (more commands)
```

**✅ Setup Complete!** You're ready to use CodeGraphContext.

---

## First-Time Setup: MCP Users

**Time Required**: 10-15 minutes  
**Frequency**: Once per machine

### Step 1-3: Same as CLI Users

Follow Steps 1-3 from [First-Time Setup: CLI Users](#first-time-setup-cli-users)

### Step 4: Configure MCP Integration

```bash
# Setup MCP configuration
cgc mcp setup

# Interactive prompts:
# 
# Select your IDE/Editor:
# 1. Cursor
# 2. VS Code (with Continue.dev)
# 3. Claude Desktop
# 4. Custom (manual configuration)
# 
# Choice: 1
```

**For Cursor:**
```
Configuring MCP for Cursor...

✓ Found Cursor config at: ~/.config/cursor/mcp.json
✓ Added CodeGraphContext MCP server
✓ Server command: cgc mcp start

Configuration:
{
  "mcpServers": {
    "codegraphcontext": {
      "command": "cgc",
      "args": ["mcp", "start"],
      "env": {
        "CGC_DB": "falkordb"
      }
    }
  }
}

✓ Configuration saved

Next steps:
1. Restart Cursor
2. Open Command Palette (Cmd/Ctrl + Shift + P)
3. Run: "MCP: Reload Servers"
4. Verify CodeGraphContext appears in MCP server list
```

**For VS Code (Continue.dev):**
```
Configuring MCP for VS Code (Continue.dev)...

✓ Found Continue config at: ~/.continue/config.json
✓ Added CodeGraphContext MCP server

Next steps:
1. Restart VS Code
2. Open Continue sidebar
3. Verify CodeGraphContext tools are available
```

**For Claude Desktop:**
```
Configuring MCP for Claude Desktop...

✓ Created config at: ~/Library/Application Support/Claude/claude_desktop_config.json

Next steps:
1. Restart Claude Desktop
2. Start a new conversation
3. Ask: "What MCP tools do you have access to?"
4. Verify CodeGraphContext tools are listed
```

### Step 5: Start MCP Server

```bash
# Start the MCP server
cgc mcp start

# Expected output:
# CodeGraphContext MCP Server
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ✓ Server started
# ✓ Protocol: Model Context Protocol (MCP)
# ✓ Transport: stdio
# ✓ Database: FalkorDB connected
# ✓ Repository: /home/user/projects/my-project
# ✓ Watching for file changes: enabled
# 
# Available tools: 18
#   - find_code
#   - analyze_code_relationships
#   - find_dead_code
#   - execute_cypher_query
#   ... (14 more)
# 
# Server ready. Listening for requests...
```

**Note**: Keep this terminal open, or run in background:

```bash
# Run in background (Linux/Mac)
cgc mcp start &

# Or use tmux/screen for persistent session
tmux new -s cgc
cgc mcp start
# Press Ctrl+B, then D to detach
```

### Step 6: Verify MCP Integration

**In Cursor/VS Code:**

1. Open your IDE
2. Start a new chat with AI assistant
3. Ask: "What CodeGraphContext tools do you have?"

**Expected AI Response:**
> "I have access to 18 CodeGraphContext tools:
> 
> **Code Discovery:**
> - find_code - Search for functions, classes, files
> - list_indexed_repositories - Show indexed projects
> 
> **Code Analysis:**
> - analyze_code_relationships - Find callers, callees, call chains
> - find_dead_code - Find unused functions
> - find_most_complex_functions - Find complex code
> - calculate_cyclomatic_complexity - Measure function complexity
> 
> **Graph Queries:**
> - execute_cypher_query - Run custom graph queries
> - visualize_graph_query - Generate graph visualizations
> 
> ... (10 more tools)
> 
> How can I help you explore your codebase?"

**Test with a real query:**

Ask AI: "Find all functions that call `authenticate`"

**Expected AI Response:**
> "I found 12 functions that call `authenticate`:
> 
> **Direct callers (3):**
> 1. `login` in api/auth.py:45
> 2. `verify_token` in middleware/auth.py:89
> 3. `refresh_session` in api/session.py:123
> 
> **Indirect callers (9 more):**
> ... (AI lists them)
> 
> Would you like me to show the call chain for any of these?"

**✅ MCP Setup Complete!** Your AI assistant now has code intelligence.

---

## Every-Time Workflow: CLI Users

**Time Required**: 2-5 minutes per session  
**Frequency**: Daily/as needed

### Typical Daily Workflow

#### **Morning: Start of Day**

```bash
# 1. Navigate to your project
cd ~/projects/my-project

# 2. Pull latest changes
git pull origin main

# 3. Update the code graph (if files changed)
cgc reindex

# Output:
# Detecting changes...
# ✓ 12 files modified
# ✓ 3 files added
# ✓ 1 file deleted
# 
# Updating graph...
# ✓ Updated 45 nodes
# ✓ Updated 123 relationships
# 
# Reindexing completed in 3.2 seconds
```

**Alternative**: Use auto-watch mode (set once, forget it)

```bash
# Enable auto-watch for this repository
cgc watch .

# Output:
# ✓ Watching: /home/user/projects/my-project
# ✓ Auto-reindex on file changes: enabled
# 
# The graph will automatically update when files change.
# Press Ctrl+C to stop watching.
```

#### **During Development: Common Tasks**

**Task 1: Understanding a new feature**

```bash
# Find the entry point
cgc find "handle_payment" --type function

# See what it calls
cgc analyze callees handle_payment

# See the full execution flow
cgc analyze chain handle_payment process_payment
```

**Task 2: Before refactoring**

```bash
# Find all usages of a function
cgc analyze callers calculate_total

# Check complexity
cgc analyze complexity calculate_total

# Find dead code to remove first
cgc analyze dead-code
```

**Task 3: Code review**

```bash
# Check what a PR changes
git diff main...feature-branch --name-only > changed_files.txt

# For each changed file, check impact
cgc analyze callers MyChangedClass

# Verify test coverage
cgc find "test_my_changed_class" --type function
```

**Task 4: Debugging**

```bash
# Find where a variable is modified
cgc analyze modifies user_session

# Trace execution path
cgc analyze chain api_endpoint database_query

# Find similar code patterns
cgc find "try.*except.*pass" --regex
```

#### **End of Day: Cleanup**

```bash
# Optional: Clear cache if needed
cgc clean --cache-only

# Optional: Export graph for documentation
cgc visualize --output daily_architecture.html
```

### Quick Reference: Most Used Commands

```bash
# Search
cgc find <query>                    # Find code elements
cgc find <query> --type function    # Find only functions
cgc find <query> --type class       # Find only classes

# Analysis
cgc analyze callers <name>          # Who calls this?
cgc analyze callees <name>          # What does this call?
cgc analyze chain <a> <b>           # Call path from A to B
cgc analyze dead-code               # Find unused code
cgc analyze complexity              # Find complex functions

# Visualization
cgc visualize                       # Generate architecture diagram
cgc stats                           # Show repository statistics

# Maintenance
cgc reindex                         # Update after code changes
cgc watch .                         # Auto-update on file changes
```

---

## Every-Time Workflow: MCP Users

**Time Required**: 1-2 minutes per session  
**Frequency**: Daily/as needed

### Typical Daily Workflow

#### **Morning: Start of Day**

```bash
# Option 1: Start MCP server manually
cgc mcp start

# Option 2: Auto-start with system (set once)
# Add to ~/.bashrc or ~/.zshrc:
# cgc mcp start &

# Option 3: Use tmux/screen for persistent session
tmux attach -t cgc || tmux new -s cgc "cgc mcp start"
```

**Verify server is running:**

```bash
# Check if MCP server is running
ps aux | grep "cgc mcp"

# Expected output:
# user  12345  0.1  0.5  cgc mcp start
```

#### **During Development: Natural Language Queries**

Open your IDE and ask your AI assistant:

**Understanding Code:**
- "What does the `process_payment` function do?"
- "Show me all functions that call `authenticate`"
- "What's the call chain from the API endpoint to the database?"

**Before Refactoring:**
- "What will break if I change `calculate_total`?"
- "Find all dead code in the auth module"
- "Show me the most complex functions"

**Code Review:**
- "What's the impact of changing `UserService`?"
- "Are there any circular dependencies?"
- "Find all functions that access the database"

**Debugging:**
- "Trace the execution from `handle_request` to `send_email`"
- "Who modifies the `session_state` variable?"
- "Find all error handling code"

#### **End of Day: Cleanup**

```bash
# Optional: Stop MCP server if running manually
# Press Ctrl+C in the terminal running cgc mcp start

# Or kill the process
pkill -f "cgc mcp start"
```

### Integration with AI Workflows

**Example 1: Feature Development**

1. **Ask AI**: "I need to add a new payment method. Show me how existing payment methods are implemented."
2. **AI uses CGC**: Finds `PaymentMethod` class, shows all implementations
3. **AI generates**: Boilerplate code following existing patterns
4. **You review**: AI-generated code with full context

**Example 2: Bug Investigation**

1. **Ask AI**: "Users report checkout fails for international orders. Help me debug."
2. **AI uses CGC**: Traces call chain from checkout to payment processing
3. **AI identifies**: Missing email notification call (like in User Journey #2)
4. **AI suggests**: Exact fix with line numbers

**Example 3: Refactoring**

1. **Ask AI**: "I want to refactor `OldAuthService` to `NewAuthService`. Create a migration plan."
2. **AI uses CGC**: Finds all 47 usages, analyzes complexity
3. **AI generates**: Step-by-step migration plan with risk assessment
4. **You execute**: Safe, incremental migration

---

## Troubleshooting

### Common Issues

#### **Issue 1: `cgc` command not found**

**Symptoms:**
```bash
cgc --version
# bash: cgc: command not found
```

**Solution:**
```bash
# Find where pip installed cgc
pip show codegraphcontext | grep Location

# Add to PATH
export PATH="$HOME/.local/bin:$PATH"

# Make permanent (add to ~/.bashrc or ~/.zshrc)
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

#### **Issue 2: Indexing fails with "Permission denied"**

**Symptoms:**
```bash
cgc index .
# Error: Permission denied: /some/file.py
```

**Solution:**
```bash
# Check file permissions
ls -la /some/file.py

# Option 1: Fix permissions
chmod +r /some/file.py

# Option 2: Skip problematic files
cgc index . --ignore-errors
```

#### **Issue 3: MCP server not connecting**

**Symptoms:**
- AI assistant says "CodeGraphContext tools not available"
- MCP server starts but IDE doesn't see it

**Solution:**

```bash
# 1. Verify server is running
cgc mcp start
# Should show "Server ready. Listening for requests..."

# 2. Check MCP configuration
cat ~/.config/cursor/mcp.json
# Should contain "codegraphcontext" entry

# 3. Restart IDE completely
# Not just reload - full quit and reopen

# 4. Check IDE logs
# Cursor: Help > Toggle Developer Tools > Console
# Look for MCP connection errors

# 5. Test with manual MCP call
echo '{"method":"tools/list"}' | cgc mcp start
# Should return list of 18 tools
```

#### **Issue 4: Slow indexing on large repositories**

**Symptoms:**
```bash
cgc index .
# Takes > 5 minutes on 100k+ LOC repository
```

**Solution:**

```bash
# Option 1: Use Neo4j instead of FalkorDB
cgc neo4j setup
cgc index . --db neo4j

# Option 2: Exclude test files and dependencies
cgc index . --exclude "tests/*" --exclude "node_modules/*"

# Option 3: Index in parallel
cgc index . --parallel 4

# Option 4: Use pre-built bundle if available
cgc load <package-name>
```

#### **Issue 5: Graph out of sync with code**

**Symptoms:**
- CGC shows old function names
- Missing new files

**Solution:**

```bash
# Full reindex
cgc reindex --force

# Or use watch mode to auto-sync
cgc watch .
```

### Getting Help

```bash
# Built-in help
cgc help
cgc help <command>

# Check version
cgc --version

# Enable debug logging
cgc --debug index .

# Report issues
# GitHub: https://github.com/CodeGraphContext/CodeGraphContext/issues
```

---

## Next Steps

- **Learn by example** → [USER_JOURNEYS.md](./user_journeys.md)
- **Detailed use cases** → [USE_CASES_DETAILED.md](./use_cases_detailed.md)
- **Integration patterns** → [INTEGRATION_GUIDE.md](./integration_guide.md)
- **CLI reference** → [CLI Reference](reference/cli_master.md)
- **MCP reference** → [MCP Reference](reference/mcp_master.md)

---

## Summary: Quick Start Cheat Sheet

### First Time (CLI)
```bash
pip install codegraphcontext
cd ~/my-project
cgc index .
cgc stats
```

### First Time (MCP)
```bash
pip install codegraphcontext
cd ~/my-project
cgc index .
cgc mcp setup
cgc mcp start
# Restart IDE
```

### Every Time (CLI)
```bash
cd ~/my-project
cgc reindex  # or cgc watch .
cgc analyze callers <function>
```

### Every Time (MCP)
```bash
cgc mcp start  # or auto-start
# Ask AI questions in natural language
```

**That's it! You're ready to use CodeGraphContext.** 🚀
