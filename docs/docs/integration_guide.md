# Integration Guide - CodeGraphContext

This document explains how CodeGraphContext **integrates seamlessly** into typical developer workflows, rather than requiring "step-outs" or context switching.

---

## Table of Contents

1. [Philosophy: Integration vs Step-Out](#philosophy-integration-vs-step-out)
2. [IDE Integration (Primary Workflow)](#ide-integration-primary-workflow)
3. [CI/CD Integration](#cicd-integration)
4. [Git Workflow Integration](#git-workflow-integration)
5. [Code Review Integration](#code-review-integration)
6. [Documentation Integration](#documentation-integration)
7. [Team Collaboration Integration](#team-collaboration-integration)
8. [Comparison: CGC vs Alternatives](#comparison-cgc-vs-alternatives)

---

## Philosophy: Integration vs Step-Out

### ❌ Step-Out Workflow (What We Avoid)

**Traditional code analysis tools require context switching:**

```
Developer Workflow (Broken):
1. Writing code in IDE
2. ❌ STOP - Open terminal
3. ❌ Run analysis tool
4. ❌ Read output in terminal
5. ❌ Switch back to IDE
6. ❌ Remember what you were doing
7. Continue coding (context lost)
```

**Problems:**
- Context switching kills productivity
- Interrupts flow state
- Requires remembering to use the tool
- Separate from where you work

### ✅ Integrated Workflow (What CGC Provides)

**CGC integrates into your existing tools:**

```
Developer Workflow (Seamless):
1. Writing code in IDE
2. ✅ Ask AI assistant (already in IDE)
3. ✅ AI uses CGC automatically (invisible)
4. ✅ Get answer in same context
5. Continue coding (flow maintained)
```

**Benefits:**
- No context switching
- Natural language interface
- Automatic, not manual
- Integrated where you already work

---

## IDE Integration (Primary Workflow)

### Cursor IDE (Recommended)

#### Setup (One-Time, 5 minutes)

```bash
# 1. Install CGC
pip install codegraphcontext

# 2. Index your project
cd ~/projects/my-project
cgc index .

# 3. Setup MCP
cgc mcp setup
# Select: Cursor

# 4. Start MCP server (auto-start recommended)
cgc mcp start &

# 5. Restart Cursor
```

#### Daily Workflow (Zero Extra Steps)

**Scenario 1: Understanding Code**

```
You're reading unfamiliar code:

// You see this function call
processPayment(order, user);

// You wonder: "What does this do?"

Traditional Approach:
1. ❌ Search for function definition
2. ❌ Open file
3. ❌ Read code
4. ❌ Find what IT calls
5. ❌ Repeat...

CGC Integrated Approach:
1. ✅ Highlight "processPayment"
2. ✅ Ask AI: "What does this function do?"
3. ✅ AI uses CGC, shows:
   - Function definition
   - What it calls
   - Who calls it
   - Full execution flow
4. ✅ Continue reading (no context switch)
```

**Scenario 2: Before Refactoring**

```
You want to rename a function:

Traditional Approach:
1. ❌ Open terminal
2. ❌ Run: grep -r "oldFunction" .
3. ❌ Read 100+ lines of output
4. ❌ Manually filter false positives
5. ❌ Switch back to IDE
6. ❌ Start refactoring (hope you didn't miss anything)

CGC Integrated Approach:
1. ✅ Right-click function name
2. ✅ Ask AI: "What will break if I rename this?"
3. ✅ AI uses CGC, shows:
   - All 23 callers
   - Files affected
   - Test coverage
4. ✅ IDE refactor tool with confidence
5. ✅ No terminal, no context switch
```

**Scenario 3: Code Review**

```
You're reviewing a PR:

Traditional Approach:
1. ❌ Read PR diff
2. ❌ Open terminal
3. ❌ Run analysis commands
4. ❌ Switch back to GitHub
5. ❌ Write review
6. ❌ Repeat for each file

CGC Integrated Approach:
1. ✅ Open PR in Cursor
2. ✅ Ask AI: "Analyze the impact of this PR"
3. ✅ AI uses CGC, provides:
   - Functions affected
   - Test coverage
   - Risk assessment
4. ✅ Write review in same window
5. ✅ No context switch
```

### VS Code (with Continue.dev)

#### Setup

```bash
# 1-3: Same as Cursor

# 4. Setup MCP for Continue
cgc mcp setup
# Select: VS Code (Continue.dev)

# 5. Restart VS Code
```

#### Integration Points

**1. Inline Chat (Cmd+I)**
```
While editing code:
1. Press Cmd+I (inline chat)
2. Ask: "Who calls this function?"
3. Get answer inline
4. Continue editing
```

**2. Sidebar Chat**
```
While exploring codebase:
1. Open Continue sidebar
2. Ask: "Show me the architecture of the auth module"
3. Get visualization
4. Click through to files
```

**3. Code Actions**
```
Right-click on function:
1. "Ask Continue: Find callers"
2. "Ask Continue: Show call chain"
3. "Ask Continue: Check complexity"
```

### JetBrains IDEs (IntelliJ, PyCharm, etc.)

#### Setup

```bash
# 1-3: Same as above

# 4. Setup MCP for JetBrains
cgc mcp setup
# Select: JetBrains (AI Assistant)

# 5. Restart IDE
```

#### Integration Points

**1. AI Assistant Panel**
```
While coding:
1. Open AI Assistant (Alt+Enter)
2. Ask questions about code
3. AI uses CGC automatically
```

**2. Quick Actions**
```
Right-click on code:
1. "AI Assistant: Analyze Impact"
2. "AI Assistant: Find Usages (Deep)"
3. "AI Assistant: Show Architecture"
```

---

## CI/CD Integration

### GitHub Actions

**Automatic Code Quality Checks**

```yaml
# .github/workflows/code-quality.yml
name: Code Quality

on: [pull_request]

jobs:
  analyze:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      
      - name: Install CodeGraphContext
        run: pip install codegraphcontext
      
      - name: Index codebase
        run: cgc index .
      
      - name: Find dead code
        run: |
          cgc analyze dead-code --exclude-decorated @api.route > dead-code.txt
          if [ -s dead-code.txt ]; then
            echo "⚠️ Dead code found:"
            cat dead-code.txt
            echo "::warning::Dead code detected. Consider cleanup."
          fi
      
      - name: Check complexity
        run: |
          cgc analyze complexity --limit 10 --threshold 15 > complex.txt
          if [ -s complex.txt ]; then
            echo "⚠️ Complex functions found:"
            cat complex.txt
            echo "::warning::High complexity detected. Consider refactoring."
          fi
      
      - name: Find circular dependencies
        run: |
          cgc query "
            MATCH (m1:Module)-[:IMPORTS]->(m2:Module)-[:IMPORTS]->(m1)
            RETURN m1.name, m2.name
          " > circular.txt
          if [ -s circular.txt ]; then
            echo "❌ Circular dependencies found:"
            cat circular.txt
            echo "::error::Circular dependencies detected!"
            exit 1
          fi
      
      - name: Comment on PR
        uses: actions/github-script@v6
        with:
          script: |
            const fs = require('fs');
            const deadCode = fs.readFileSync('dead-code.txt', 'utf8');
            const complex = fs.readFileSync('complex.txt', 'utf8');
            
            let comment = '## Code Quality Report\n\n';
            
            if (deadCode) {
              comment += '### ⚠️ Dead Code\n```\n' + deadCode + '\n```\n\n';
            }
            
            if (complex) {
              comment += '### ⚠️ Complex Functions\n```\n' + complex + '\n```\n\n';
            }
            
            if (!deadCode && !complex) {
              comment += '✅ No issues found!\n';
            }
            
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: comment
            });
```

**Result**: Every PR automatically gets code quality feedback

### GitLab CI

```yaml
# .gitlab-ci.yml
code_quality:
  stage: test
  image: python:3.10
  script:
    - pip install codegraphcontext
    - cgc index .
    - cgc analyze dead-code > dead-code.txt || true
    - cgc analyze complexity --limit 10 > complexity.txt || true
  artifacts:
    reports:
      codequality: 
        - dead-code.txt
        - complexity.txt
  only:
    - merge_requests
```

---

## Git Workflow Integration

### Pre-Commit Hooks

**Automatic checks before every commit**

```bash
# .git/hooks/pre-commit
#!/bin/bash

# Index changed files only (fast)
cgc reindex

# Check if commit introduces dead code
DEAD_CODE=$(cgc analyze dead-code --changed-only)
if [ -n "$DEAD_CODE" ]; then
    echo "⚠️  Warning: This commit may introduce dead code:"
    echo "$DEAD_CODE"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check if commit introduces high complexity
COMPLEX=$(cgc analyze complexity --changed-only --threshold 15)
if [ -n "$COMPLEX" ]; then
    echo "⚠️  Warning: This commit introduces complex functions:"
    echo "$COMPLEX"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

exit 0
```

**Make it executable:**
```bash
chmod +x .git/hooks/pre-commit
```

### Git Aliases

**Add CGC commands to git workflow**

```bash
# ~/.gitconfig
[alias]
    # Show impact of current changes
    impact = !cgc analyze callers $(git diff --name-only | xargs cgc find --files)
    
    # Find dead code in current branch
    dead = !cgc analyze dead-code --branch $(git branch --show-current)
    
    # Show architecture diff between branches
    arch-diff = !cgc visualize --branch main && cgc visualize --branch $(git branch --show-current) && echo "Compare: main_arch.html vs current_arch.html"
    
    # Check complexity of changed functions
    complexity = !cgc analyze complexity --changed-only
```

**Usage:**
```bash
git impact          # See what your changes affect
git dead            # Find dead code in your branch
git arch-diff       # Compare architecture
git complexity      # Check if you're adding complex code
```

---

## Code Review Integration

### GitHub PR Template

**Automatic CGC analysis in PR description**

```markdown
<!-- .github/pull_request_template.md -->
## Description
<!-- Describe your changes -->

## Impact Analysis
<!-- Run: cgc analyze callers <changed_function> -->

**Functions Modified:**
- [ ] `function_name` - X callers, Y files affected

**Test Coverage:**
- [ ] All modified functions have tests
- [ ] No new dead code introduced
- [ ] Complexity within acceptable limits

## CGC Checks
<!-- Automatically filled by CI -->
- [ ] No circular dependencies
- [ ] No high-complexity functions (>15)
- [ ] No dead code introduced

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Comments added for complex logic
- [ ] Documentation updated
- [ ] Tests pass locally
- [ ] CGC analysis reviewed
```

### Review Checklist Script

```bash
#!/bin/bash
# scripts/review-pr.sh

PR_BRANCH=$1

echo "🔍 Analyzing PR: $PR_BRANCH"
echo

# Get changed files
CHANGED_FILES=$(git diff main...$PR_BRANCH --name-only --diff-filter=M | grep '\.py$')

echo "📝 Changed Files:"
echo "$CHANGED_FILES"
echo

# For each changed file, find modified functions
for file in $CHANGED_FILES; do
    echo "📄 Analyzing: $file"
    
    # Find functions in this file
    FUNCTIONS=$(cgc find --file $file --type function)
    
    # For each function, check impact
    echo "$FUNCTIONS" | while read func; do
        echo "  Function: $func"
        CALLERS=$(cgc analyze callers $func --count-only)
        echo "    Callers: $CALLERS"
    done
    echo
done

# Check for new dead code
echo "🧹 Checking for dead code..."
cgc analyze dead-code --branch $PR_BRANCH

# Check complexity
echo "📊 Checking complexity..."
cgc analyze complexity --branch $PR_BRANCH --threshold 15

# Check for circular dependencies
echo "🔄 Checking for circular dependencies..."
cgc query "
MATCH (m1:Module)-[:IMPORTS]->(m2:Module)-[:IMPORTS]->(m1)
RETURN m1.name, m2.name
"

echo
echo "✅ Review complete!"
```

**Usage:**
```bash
./scripts/review-pr.sh feature-branch
```

---

## Documentation Integration

### Auto-Generated Architecture Docs

**Keep docs in sync with code**

```bash
# scripts/update-docs.sh
#!/bin/bash

echo "📚 Updating documentation..."

# Generate architecture diagram
cgc visualize --output docs/architecture.html

# Generate module dependency graph
cgc analyze deps --all --output docs/dependencies.md

# Generate complexity report
cgc analyze complexity --limit 20 --output docs/complexity.md

# Generate API surface area
cgc find --type function --decorated @api.route --output docs/api-endpoints.md

echo "✅ Documentation updated!"
```

**Add to CI:**
```yaml
# .github/workflows/docs.yml
name: Update Docs

on:
  push:
    branches: [main]

jobs:
  docs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - run: pip install codegraphcontext
      - run: cgc index .
      - run: ./scripts/update-docs.sh
      - uses: stefanzweifel/git-auto-commit-action@v4
        with:
          commit_message: "docs: auto-update architecture docs"
          file_pattern: docs/*
```

**Result**: Documentation automatically updates with every commit

---

## Team Collaboration Integration

### Slack Integration

**Share CGC insights in Slack**

```python
# scripts/slack-bot.py
import os
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import subprocess

client = WebClient(token=os.environ['SLACK_BOT_TOKEN'])

def handle_cgc_command(channel, command):
    """Handle /cgc slash command in Slack"""
    
    # Run CGC command
    result = subprocess.run(
        ['cgc'] + command.split(),
        capture_output=True,
        text=True
    )
    
    # Post result to Slack
    try:
        client.chat_postMessage(
            channel=channel,
            text=f"```\n{result.stdout}\n```"
        )
    except SlackApiError as e:
        print(f"Error: {e}")

# Example usage:
# /cgc analyze callers processPayment
# /cgc find "authentication" --type function
# /cgc analyze dead-code
```

### Shared Graph Database

**Team shares one graph (optional)**

```bash
# Setup shared Neo4j instance
cgc neo4j setup --host team-neo4j.company.com

# All team members connect to same graph
cgc config set db.host team-neo4j.company.com
cgc config set db.user team
cgc config set db.password <shared-password>

# Now everyone sees the same graph
# Updates from one developer visible to all
```

**Benefits:**
- Consistent view of codebase
- No duplicate indexing
- Faster onboarding (graph already built)

---

## Comparison: CGC vs Alternatives

### CGC vs IDE Built-in Tools

| Feature | IDE Built-in | CodeGraphContext |
|---------|-------------|------------------|
| **Find References** | ✅ Direct only | ✅ Direct + Indirect |
| **Call Hierarchy** | ✅ Limited | ✅ Complete graph |
| **Cross-language** | ❌ No | ✅ Yes |
| **Dead Code** | ❌ No | ✅ Yes |
| **Complexity** | ❌ No | ✅ Yes |
| **Architecture** | ❌ No | ✅ Yes |
| **AI Integration** | ❌ No | ✅ Yes (MCP) |
| **CI/CD** | ❌ No | ✅ Yes |

**Verdict**: CGC complements IDE tools, doesn't replace them

### CGC vs SourceGraph

| Feature | SourceGraph | CodeGraphContext |
|---------|------------|------------------|
| **Code Search** | ✅ Excellent | ✅ Good |
| **Graph Analysis** | ⚠️ Limited | ✅ Complete |
| **Local Use** | ❌ No | ✅ Yes |
| **AI Integration** | ❌ No | ✅ Yes (MCP) |
| **Open Source** | ⚠️ Limited | ✅ Yes |
| **Cost** | 💰 $$ | ✅ Free |
| **GitHub Only** | ✅ Yes | ✅ Any repo |

**Verdict**: CGC better for local, AI-integrated workflows

### CGC vs Context7 (MCP)

| Feature | Context7 | CodeGraphContext |
|---------|----------|------------------|
| **Context Type** | Docstrings only | Full graph |
| **Relationships** | ❌ No | ✅ Yes |
| **Call Chains** | ❌ No | ✅ Yes |
| **Dead Code** | ❌ No | ✅ Yes |
| **Architecture** | ❌ No | ✅ Yes |
| **Accuracy** | ⚠️ Depends on docs | ✅ Code-based |

**Verdict**: CGC provides structural intelligence, not just text

---

## Integration Best Practices

### 1. Start Small
```bash
# Day 1: Just index
cgc index .

# Day 2: Add MCP
cgc mcp setup
cgc mcp start &

# Week 1: Add to git hooks
# Week 2: Add to CI/CD
# Month 1: Team adoption
```

### 2. Make it Automatic
```bash
# Auto-start MCP server
echo 'cgc mcp start &' >> ~/.bashrc

# Auto-reindex on file changes
cgc watch .

# Auto-update docs
# Add to CI/CD pipeline
```

### 3. Integrate Where You Work
- ✅ Use MCP in IDE (primary)
- ✅ Add to git workflow (secondary)
- ✅ Add to CI/CD (automated)
- ❌ Don't require manual terminal commands

### 4. Provide Value Immediately
- First use should solve a real problem
- Show time savings concretely
- Integrate into existing workflows
- Don't require behavior change

---

## Summary: Integration Philosophy

### ❌ What CGC is NOT:
- Not a separate tool you "switch to"
- Not a manual process you "remember to run"
- Not a terminal-only tool
- Not a replacement for your IDE

### ✅ What CGC IS:
- **Invisible enhancement** to your AI assistant
- **Automatic analysis** in your CI/CD
- **Integrated intelligence** in your IDE
- **Seamless addition** to your workflow

### The Goal:
**You shouldn't think about CGC. You should just get better answers, faster reviews, and safer refactorings—automatically.**

---

## Next Steps

- **Setup MCP integration** → [SETUP_WORKFLOWS.md](./setup_workflows.md)
- **See it in action** → [USER_JOURNEYS.md](./user_journeys.md)
- **Detailed use cases** → [USE_CASES_DETAILED.md](./use_cases_detailed.md)
- **CLI reference** → [CLI Reference](reference/cli_master.md)
- **MCP reference** → [MCP Reference](reference/mcp_master.md)
