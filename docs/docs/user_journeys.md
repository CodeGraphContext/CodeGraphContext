# User Journeys - CodeGraphContext

This document provides detailed, step-by-step user journeys for different personas using CodeGraphContext. Each journey includes **concrete examples** with actual commands and expected outputs.

---

## Table of Contents

1. [Persona 1: AI-Assisted Developer (MCP User)](#persona-1-ai-assisted-developer-mcp-user)
2. [Persona 2: New Developer/Contributor (CLI User)](#persona-2-new-developercontributor-cli-user)
3. [Persona 3: Experienced Developer - Refactoring (CLI + MCP User)](#persona-3-experienced-developer-refactoring-cli-mcp-user)

---

## Persona 1: AI-Assisted Developer (MCP User)

### Profile
- **Name**: Sarah, Senior Full-Stack Developer
- **Tools**: Uses Cursor IDE with Claude/GPT-4 for daily coding
- **Context**: Working on a large e-commerce platform (50k+ lines of code)
- **Pain Point**: AI assistant often hallucinates about code relationships or provides incorrect context

### Concrete Example Scenario

Sarah needs to refactor the `calculateShippingCost` function in the checkout module. She wants to know what will break before making changes.

### Step-by-Step Journey

#### **Step 1: One-Time Setup** (5 minutes)

```bash
# Install CodeGraphContext
pip install codegraphcontext

# Index the repository
cd ~/projects/ecommerce-platform
cgc index .

# Output:
# ✓ Indexed 1,247 files
# ✓ Found 3,421 functions
# ✓ Found 892 classes
# ✓ Created 15,234 relationships
# ✓ Database: FalkorDB (auto-selected)
```

```bash
# Setup MCP integration
cgc mcp setup

# Output:
# ✓ MCP configuration created at ~/.config/cursor/mcp.json
# ✓ Server command: cgc mcp start
# ✓ Restart Cursor to activate
```

#### **Step 2: Start MCP Server** (Every time, or run in background)

```bash
# Start the MCP server
cgc mcp start

# Output:
# ✓ CodeGraphContext MCP Server started
# ✓ Listening on stdio
# ✓ Database: FalkorDB connected
# ✓ Watching: /home/sarah/projects/ecommerce-platform
```

**Alternative**: Add to shell startup script for auto-start

#### **Step 3: Use AI Assistant with CGC Context**

Sarah opens Cursor and asks her AI assistant:

**Sarah's Question:**
> "I want to refactor the calculateShippingCost function. What will be affected?"

**Behind the Scenes:**
1. Cursor AI recognizes this needs code relationship data
2. Calls CGC MCP tool: `find_all_callers` with target `calculateShippingCost`
3. CGC returns structured data

**CGC Response (via MCP):**
```json
{
  "function": "calculateShippingCost",
  "file": "src/checkout/shipping.py",
  "direct_callers": 3,
  "total_callers": 12,
  "callers": [
    {
      "function": "processCheckout",
      "file": "src/checkout/checkout_flow.py",
      "line": 145
    },
    {
      "function": "estimateTotal",
      "file": "src/cart/cart_service.py",
      "line": 89
    },
    {
      "function": "generateInvoice",
      "file": "src/billing/invoice_generator.py",
      "line": 234
    }
  ],
  "indirect_callers": [
    "handleCheckoutAPI",
    "updateCartTotal",
    "previewOrder",
    // ... 9 more
  ]
}
```

**AI Assistant's Response to Sarah:**
> "The `calculateShippingCost` function is called by 12 functions across 3 modules:
> 
> **Direct callers (3):**
> 1. `processCheckout` in checkout_flow.py - Main checkout flow
> 2. `estimateTotal` in cart_service.py - Cart total calculation
> 3. `generateInvoice` in invoice_generator.py - Invoice generation
> 
> **Indirect impact (9 more functions):**
> - API endpoints: `handleCheckoutAPI`, `previewOrder`
> - Background jobs: `sendOrderConfirmation`
> 
> **Recommendation:** 
> - If you change the function signature, you'll need to update 3 direct callers
> - If you change the return value format, 12 functions are affected
> - Consider adding unit tests for the 3 direct callers before refactoring"

#### **Step 4: Deep Dive with Follow-up Questions**

**Sarah asks:**
> "Show me the call chain from the API endpoint to calculateShippingCost"

**CGC MCP Call:** `analyze_code_relationships(query_type="call_chain", target="calculateShippingCost")`

**AI Response:**
> "Here's the execution path:
> ```
> handleCheckoutAPI (api/checkout.py:45)
>   └─> processCheckout (checkout/checkout_flow.py:145)
>       └─> calculateShippingCost (checkout/shipping.py:78)
>           └─> getShippingRates (integrations/fedex_api.py:23)
> ```
> 
> This means changes to `calculateShippingCost` affect the public API endpoint."

#### **Step 5: Make Informed Changes**

Sarah now refactors with confidence, knowing:
- ✅ Exactly what will break
- ✅ Which tests to update
- ✅ What documentation to change
- ✅ The full impact radius

### Time Saved
- **Without CGC**: 2-3 hours of manual code searching, likely missing some dependencies
- **With CGC**: 10 minutes with complete, accurate information
- **Savings**: ~2.5 hours per refactoring task

---

## Persona 2: New Developer/Contributor (CLI User)

### Profile
- **Name**: Alex, Junior Developer (3 months experience)
- **Context**: Just joined a team maintaining a legacy Python project
- **Task**: Fix a bug in the payment processing module
- **Pain Point**: Doesn't understand the codebase architecture, doesn't know where to start

### Concrete Example Scenario

Alex's first task: "Fix bug #1234 - Payment confirmation emails not sending for international orders"

### Step-by-Step Journey

#### **Step 1: Setup** (First time only)

```bash
# Clone the repository
git clone https://github.com/company/payment-system.git
cd payment-system

# Install CGC
pip install codegraphcontext

# Index the codebase
cgc index .

# Output:
# ✓ Indexed 847 files
# ✓ Found 2,156 functions
# ✓ Found 423 classes
# ✓ Database: FalkorDB
```

#### **Step 2: Understand the Architecture** (10 minutes)

```bash
# Get an overview of the codebase structure
cgc stats

# Output:
# Repository Statistics:
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Files:      847
# Functions:  2,156
# Classes:    423
# Modules:    67
# 
# Top Modules by Size:
# 1. payment_processing (234 functions)
# 2. email_service (156 functions)
# 3. order_management (189 functions)
```

```bash
# Visualize the architecture
cgc visualize --output architecture.html

# Output:
# ✓ Generated visualization: architecture.html
# ✓ Open in browser to explore
```

**Alex opens `architecture.html` and sees:**
- Module dependency graph
- Payment processing module connects to email_service
- Clear separation between domestic and international payment flows

#### **Step 3: Find Relevant Code** (5 minutes)

```bash
# Search for email-related code
cgc find "email" --type function

# Output:
# Found 23 functions matching 'email':
# 
# 1. sendPaymentConfirmation
#    File: src/email_service/notifications.py:45
#    
# 2. sendInternationalPaymentEmail
#    File: src/email_service/international.py:12
#    
# 3. queueEmailJob
#    File: src/workers/email_queue.py:78
# 
# ... (20 more)
```

```bash
# Find international payment handling
cgc find "international" --type function

# Output:
# Found 8 functions matching 'international':
# 
# 1. processInternationalPayment
#    File: src/payment_processing/international.py:34
#    
# 2. sendInternationalPaymentEmail
#    File: src/email_service/international.py:12
```

#### **Step 4: Trace the Bug** (15 minutes)

```bash
# See what calls the international payment function
cgc analyze callers processInternationalPayment

# Output:
# Callers of 'processInternationalPayment':
# 
# Direct Callers (2):
# ┌────────────────────────────────────────────────────────────┐
# │ Function              │ File                    │ Line     │
# ├────────────────────────────────────────────────────────────┤
# │ handlePayment         │ api/payment_api.py      │ 123      │
# │ retryFailedPayment    │ workers/retry_worker.py │ 56       │
# └────────────────────────────────────────────────────────────┘
```

```bash
# Check what processInternationalPayment calls
cgc analyze callees processInternationalPayment

# Output:
# Functions called by 'processInternationalPayment':
# 
# ┌────────────────────────────────────────────────────────────┐
# │ Function              │ File                    │ Line     │
# ├────────────────────────────────────────────────────────────┤
# │ validateCurrency      │ utils/currency.py       │ 23       │
# │ chargeCard            │ integrations/stripe.py  │ 89       │
# │ logTransaction        │ logging/audit.py        │ 45       │
# │ updateOrderStatus     │ orders/order_service.py │ 167      │
# └────────────────────────────────────────────────────────────┘
```

**Alex notices:** `sendInternationalPaymentEmail` is NOT in the callees list! This is the bug!

#### **Step 5: Verify the Fix Location** (5 minutes)

```bash
# Check how domestic payments work
cgc analyze callees processDomesticPayment

# Output:
# Functions called by 'processDomesticPayment':
# 
# ┌────────────────────────────────────────────────────────────┐
# │ Function              │ File                    │ Line     │
# ├────────────────────────────────────────────────────────────┤
# │ validateCurrency      │ utils/currency.py       │ 23       │
# │ chargeCard            │ integrations/stripe.py  │ 89       │
# │ logTransaction        │ logging/audit.py        │ 45       │
# │ updateOrderStatus     │ orders/order_service.py │ 167      │
# │ sendPaymentConfirmation │ email_service/notifications.py │ 45 │
# └────────────────────────────────────────────────────────────┘
```

**Aha!** Domestic payments call `sendPaymentConfirmation`, but international payments don't call `sendInternationalPaymentEmail`!

#### **Step 6: Make the Fix**

Alex adds the missing email call to `processInternationalPayment` function.

#### **Step 7: Verify No Side Effects** (5 minutes)

```bash
# Check if the change affects anything else
cgc analyze callers sendInternationalPaymentEmail

# Output:
# Callers of 'sendInternationalPaymentEmail':
# 
# No callers found.
# 
# ⚠️  This function appears to be unused (dead code)
```

Perfect! Adding this call won't break anything.

### Time Saved
- **Without CGC**: 4-6 hours of reading code, asking senior developers, trial and error
- **With CGC**: 40 minutes to understand the bug and fix it
- **Savings**: ~5 hours, plus reduced senior developer interruptions

### Learning Outcome
Alex now understands:
- ✅ The payment processing architecture
- ✅ How domestic vs international payments differ
- ✅ The email notification system
- ✅ How to navigate the codebase independently

---

## Persona 3: Experienced Developer - Refactoring (CLI + MCP User)

### Profile
- **Name**: Marcus, Tech Lead
- **Context**: Leading a major refactoring of a 5-year-old Django application
- **Task**: Remove deprecated `OldAuthService` and migrate to `NewAuthService`
- **Pain Point**: Needs to ensure zero downtime, no broken functionality

### Concrete Example Scenario

The team is migrating from a custom authentication system to OAuth2. Marcus needs to:
1. Find all usages of the old auth system
2. Identify dead code that can be removed
3. Plan the migration in safe, incremental steps

### Step-by-Step Journey

#### **Step 1: Initial Assessment** (10 minutes)

```bash
# Index the current codebase
cgc index .

# Find all references to old auth
cgc find "OldAuthService" --type class

# Output:
# Found 1 class matching 'OldAuthService':
# 
# Class: OldAuthService
# File: src/auth/legacy_auth.py:23
# Methods: 12
```

```bash
# Find all functions that use it
cgc analyze callers OldAuthService

# Output:
# Callers of 'OldAuthService':
# 
# Direct Callers (15):
# ┌────────────────────────────────────────────────────────────┐
# │ Function              │ File                    │ Line     │
# ├────────────────────────────────────────────────────────────┤
# │ login                 │ api/auth_api.py         │ 34       │
# │ logout                │ api/auth_api.py         │ 67       │
# │ validateToken         │ middleware/auth.py      │ 89       │
# │ refreshSession        │ api/session_api.py      │ 123      │
# ... (11 more)
# └────────────────────────────────────────────────────────────┘
# 
# Total: 15 direct callers, 47 indirect callers
```

**Marcus realizes:** This affects 47 functions! Need a careful migration plan.

#### **Step 2: Find Dead Code to Remove First** (5 minutes)

```bash
# Find unused code in the auth module
cgc analyze dead-code --exclude-decorated @api_endpoint @celery_task

# Output:
# Potentially Unused Functions:
# 
# ┌────────────────────────────────────────────────────────────┐
# │ Function              │ File                    │ Complexity│
# ├────────────────────────────────────────────────────────────┤
# │ _legacyHashPassword   │ auth/legacy_auth.py     │ 8         │
# │ _migrateUserSession   │ auth/migration.py       │ 12        │
# │ validateLegacyToken   │ auth/legacy_auth.py     │ 15        │
# └────────────────────────────────────────────────────────────┘
# 
# Total: 3 unused functions (can be safely removed)
```

**Marcus notes:** Remove these 3 functions first to reduce complexity.

#### **Step 3: Identify High-Risk Areas** (10 minutes)

```bash
# Find the most complex functions that use OldAuthService
cgc analyze complexity --filter-calls OldAuthService

# Output:
# Complex Functions Using 'OldAuthService':
# 
# ┌────────────────────────────────────────────────────────────┐
# │ Function              │ Complexity │ Callers │ Priority    │
# ├────────────────────────────────────────────────────────────┤
# │ validateToken         │ 23         │ 34      │ CRITICAL    │
# │ refreshSession        │ 18         │ 12      │ HIGH        │
# │ login                 │ 15         │ 8       │ HIGH        │
# │ logout                │ 7          │ 6       │ MEDIUM      │
# └────────────────────────────────────────────────────────────┘
```

**Marcus's migration plan:**
1. Start with low-complexity, low-usage functions (logout)
2. End with high-complexity, high-usage functions (validateToken)
3. Add comprehensive tests for each before migrating

#### **Step 4: Create Migration Checklist** (15 minutes)

```bash
# For each function, see its full call chain
cgc analyze chain login OldAuthService

# Output:
# Call Chain from 'login' to 'OldAuthService':
# 
# login (api/auth_api.py:34)
#   └─> OldAuthService.authenticate (auth/legacy_auth.py:45)
#       └─> _hashPassword (auth/legacy_auth.py:123)
#       └─> _validateCredentials (auth/legacy_auth.py:156)
#           └─> database.query (core/db.py:89)
```

Marcus repeats this for all 15 direct callers, creating a detailed migration map.

#### **Step 5: Use MCP for AI-Assisted Migration** (Ongoing)

Marcus uses Cursor with CGC MCP to help with the migration:

**Marcus asks AI:**
> "Generate a migration plan to replace OldAuthService with NewAuthService in the login function"

**AI (using CGC MCP):**
1. Calls `find_callees` on `login` to see what it does
2. Calls `find_callers` on `login` to see impact
3. Analyzes the code structure

**AI Response:**
> "Migration Plan for `login` function:
> 
> **Current Flow:**
> ```python
> def login(username, password):
>     auth = OldAuthService()
>     user = auth.authenticate(username, password)
>     session = auth.createSession(user)
>     return session.token
> ```
> 
> **Proposed New Flow:**
> ```python
> def login(username, password):
>     auth = NewAuthService()
>     user = auth.authenticate(username, password)  # Compatible API
>     session = auth.createSession(user)
>     return session.token
> ```
> 
> **Impact Analysis:**
> - `login` is called by 8 functions
> - Return value format is the same (session token string)
> - No breaking changes expected
> 
> **Testing Checklist:**
> - [ ] Unit test: test_login_success
> - [ ] Unit test: test_login_invalid_credentials
> - [ ] Integration test: test_login_api_endpoint
> - [ ] Load test: Verify performance is similar
> 
> **Rollout Strategy:**
> 1. Deploy with feature flag `use_new_auth_service`
> 2. Enable for 10% of traffic
> 3. Monitor error rates
> 4. Gradually increase to 100%
> 5. Remove OldAuthService after 2 weeks"

#### **Step 6: Execute Migration** (Over 2 weeks)

Marcus follows the plan:
- Week 1: Migrate 5 low-risk functions
- Week 2: Migrate 10 medium-risk functions
- After each migration, uses CGC to verify:

```bash
# Verify old service usage is decreasing
cgc analyze callers OldAuthService

# Week 1: 15 callers → 10 callers
# Week 2: 10 callers → 0 callers
```

```bash
# Final verification: Is OldAuthService still used?
cgc analyze callers OldAuthService

# Output:
# Callers of 'OldAuthService':
# 
# No callers found.
# 
# ✓ Safe to remove OldAuthService
```

#### **Step 7: Cleanup** (30 minutes)

```bash
# Find all dead code after migration
cgc analyze dead-code

# Output:
# Potentially Unused Functions:
# 
# ┌────────────────────────────────────────────────────────────┐
# │ Function              │ File                    │ LOC       │
# ├────────────────────────────────────────────────────────────┤
# │ OldAuthService.*      │ auth/legacy_auth.py     │ 456       │
# │ _legacyHashPassword   │ auth/legacy_auth.py     │ 23        │
# │ _migrateUserSession   │ auth/migration.py       │ 34        │
# └────────────────────────────────────────────────────────────┘
# 
# Total: 513 lines of code can be safely removed
```

Marcus deletes the old code, reducing technical debt by 513 lines.

### Time Saved
- **Without CGC**: 3-4 weeks of risky, manual migration with likely bugs
- **With CGC**: 2 weeks of safe, incremental migration with zero bugs
- **Savings**: 1-2 weeks, plus avoided production incidents

### Business Impact
- ✅ Zero downtime migration
- ✅ No customer-facing bugs
- ✅ 513 lines of dead code removed
- ✅ Improved security (OAuth2)
- ✅ Team confidence in future refactorings

---

## Summary: Key Takeaways

### For MCP Users (AI-Assisted Development)
- **Setup**: One-time 5-minute setup, then seamless integration
- **Workflow**: Ask questions in natural language, get precise answers
- **Value**: AI provides accurate context instead of hallucinations
- **Time Saved**: 2-3 hours per refactoring task

### For CLI Users (Direct Tool Usage)
- **Setup**: One-time `cgc index` command
- **Workflow**: Use specific commands for specific tasks
- **Value**: Self-service code exploration, no senior dev needed
- **Time Saved**: 4-6 hours for onboarding, 1-2 hours per bug investigation

### For Both
- **Integration**: Works alongside existing tools (IDE, git, CI/CD)
- **Learning Curve**: Minimal - intuitive commands and natural language
- **ROI**: Pays for itself in the first week of use
- **Scalability**: Works on codebases from 1k to 1M+ lines

---

## Next Steps

- **New to CGC?** → Start with [SETUP_WORKFLOWS.md](./setup_workflows.md)
- **Want specific examples?** → See [USE_CASES_DETAILED.md](./use_cases_detailed.md)
- **Need integration help?** → Read [INTEGRATION_GUIDE.md](./integration_guide.md)
- **CLI Reference** → See [CLI Reference](reference/cli_master.md)
- **MCP Reference** → See [MCP Reference](reference/mcp_master.md)
