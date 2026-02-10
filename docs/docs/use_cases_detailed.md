# Real-World Use Cases & ROI

This guide demonstrates **10 concrete scenarios** where CodeGraphContext delivers immediate value.

Each case compares the **Traditional Manual Approach** vs. the **CodeGraphContext Automated Approach**, highlighting time and cost savings.

---

## Use Case 1: Safe Refactoring
**Scenario**: Renaming a critical function `execute_cypher_query` used throughout usage.

| Context | Problem |
| :--- | :--- |
| **Role** | Senior Engineer ($75/hr) |
| **Task** | Rename widely used function |
| **Risk** | Breaking indirect callers |

**The Manual Way**
1.  **Grep**: `grep -r "execute_cypher_query" .` (Finds 150+ lines, many false positives).
2.  **Filter**: Manually check each line to ignore strings/comments.
3.  **Trace Indirect**: Grep for callers of callers (The "Rabbit Hole").
4.  **Fix & Pray**: Rename and hope tests catch everything.

**Result**: 3 hours wasted. High risk of regression.

**The Automated Way**
**Command**:
```bash
cgc analyze callers execute_cypher_query --all
```

**Output**:

*   Returns **exact list** of 50 functions.
*   Shows **indirect impact** (who calls the functions that call this?).
*   **0 False Positives** (ignores comments/strings).

**Result**: Done in **20 minutes**. 100% confidence.

!!! success "ROI Impact"
    *   **Time Saved**: 2.5 Hours
    *   **Cost Saved**: $200
    *   **ROI**: 800%

---

## Use Case 2: Code Cleanup
**Scenario**: identifying dead code before a major release.

| Context | Problem |
| :--- | :--- |
| **Role** | Mid-level Engineer ($60/hr) |
| **Task** | Delete unused legacy features |
| **Risk** | Deleting something that is actually used dynamically |

**The Manual Way**
1.  **List Candidates**: Guess which functions look unused.
2.  **Search**: Grep for each function name.
3.  **Validate**: Manually verify if usages are real or just tests.
4.  **Hesitate**: "I better keep it just in case."

**Result**: 8 hours. Codebase remains bloated.

**The Automated Way**
**Command**:
```bash
cgc analyze dead-code --exclude-decorated @app.route
```

**Output**:

*   Lists **50 functions** with **0 callers**.
*   Automatically excludes API endpoints (via decorators).
*   Provides **Risk Score** for each deletion.

**Result**: Cleanup completed in **45 minutes**.

!!! success "ROI Impact"
    *   **Time Saved**: 7 Hours
    *   **Cost Saved**: $420
    *   **Lines Removed**: 2,345
    *   **ROI**: 933%

---

## Use Case 3: Technical Debt Assessment
**Scenario**: Prioritizing refactoring for next quarter.

**The Manual Way**
*   "I feel like `billing.py` is messy."
*   "Let's refactor the User class."
*   **Result**: Refactoring code that nobody uses. Wasted effort.

**The Automated Way**
**Command**:
```bash
cgc analyze complexity --limit 20 --with-callers
```

**Output (Matrix)**:

| Function | Complexity | Usage (Callers) | Priority |
| :--- | :--- | :--- | :--- |
| `processPayment` | 45 (High) | 34 (High) | **CRITICAL** |
| `old_export` | 40 (High) | 1 (Low) | **LOW** |

**Result**: Focus engineering time where it matters (High Complexity + High Usage).

!!! success "ROI Impact"
    *   **Time Saved**: 3.5 Hours (Analysis)
    *   **Value**: Prevented weeks of wasted refactoring on low-impact code.

---

## Use Case 4: Onboarding New Developers
**Scenario**: Junior dev needs to fix a bug in Auth.

**The Manual Way**
1.  Read README (outdated).
2.  Try to trace code manually.
3.  Get stuck.
4.  **Interrupt Senior Dev**: "Hey, how does auth flow work?" (30 min distraction).

**The Automated Way**
**Command**:
```bash
cgc visualize --focus auth
```
**Action**:

*   Developer explores interactive map.
*   Sees `Login` -> `Validate` -> `DB`.
*   Understands flow **independently**.

!!! success "ROI Impact"
    *   **Total Savings**: $237.50
    *   **Senior Dev Time Saved**: 30 mins (Most expensive resource).
    *   **Onboarding Speed**: Days -> Hours.

---

## Use Case 5: Bug Investigation
**Scenario**: "International emails not sending."

**The Manual Way**
1.  Add print statements.
2.  Reproduce locally (hard).
3.  Step through debugger for hours.

**The Automated Way**
**Command**:
```bash
cgc analyze callees processInternationalPayment
```
**Output**:

*   List: `validateCurrency`, `chargeCard`, `logTransaction`.
*   **Missing**: `sendEmail` is NOT in the list!

**Diagnosis**: "Ah, we forgot to call `sendEmail` in the international flow."
**Time**: 5 seconds.

!!! success "ROI Impact"
    *   **Time Saved**: 3.5 Hours
    *   **Cost Saved**: $228
    *   **ROI**: 700%

---

## Use Case 6: API Deprecation
**Scenario**: Deprecating `add_package_v1`.

**The Manual Way**
*   Grep and hope.
*   Miss one usage in a utility script.
*   **Production Incident**: Script fails after upgrade.

**The Automated Way**
**Command**:
```bash
cgc analyze callers add_package_v1 --all
```
**Output**:

*   Detailed report of **every single usage**, including tests and scripts.
*   Migration Plan generated automatically.

---

## Use Case 7: Architecture Review
**Scenario**: Preparing for SOC 2 Audit.

**The Manual Way**
*   Manually draw diagrams in Lucidchart.
*   Diagrams are outdated the next day.

**The Automated Way**
**Command**:
```bash
cgc visualize --mode architecture --output soc2_report.html
```
**Output**:

*   Live, always-up-to-date architecture diagram.
*   Highlights **Circular Dependencies** automatically.

---

## Use Case 8: Security Audit (HIPAA)
**Scenario**: "List all places where we access patient data."

**The Manual Way**
*   Manual code audit (Weeks unique).

**The Automated Way**
**Query**:
```cypher
MATCH (f:Function)-[:CALLS]->(db:Database)
RETURN f.name
```
**Output**:

*   Exact list of all 20 data-access functions.
*   Confidence: 100%.

!!! success "ROI Impact"
    *   **Time Saved**: 4.5 Hours
    *   **Cost Saved**: $883
    *   **Benefit**: Passed Audit.

---

## Use Case 9: Performance Optimization
**Scenario**: Indexing is slow.

**The Manual Way**
*   Profiling everywhere.

**The Automated Way**
**Analysis**:

*   Found `create_node` called inside a double loop via call graph analysis.
*   Refactored to batch mode.
*   **Result**: 10x Speedup.

---

## Use Case 10: Code Review Impact
**Scenario**: Reviewing a PR with changes to `graph_builder.py`.

**The Manual Way**
*   Read diff. Look at changed lines.
*   "Looks good to me." (Misses that this function is called by 50 other modules).

**The Automated Way**
**Command**:
```bash
cgc analyze callers process_file
```
**Output**:

*   "Warning: `process_file` is used by 15 modules. Only 2 are covered by tests."

**Action**: Request changes. "Please add integration tests."

!!! success "ROI Impact"
    *   **Time Saved**: 2 Hours
    *   **Value**: Prevented Production Incident.

---

## Summary ROI

| Metric | Savings |
| :--- | :--- |
| **Monthly Time Saved** | 36 Hours |
| **Monthly Cost Saved** | ~$3,100 |
| **Risk Reduction** | ~86% |
| **Break-even Point** | < 1 Day |
