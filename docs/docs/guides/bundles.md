# Portable Code Bundles

CodeGraphContext (CGC) introduces the concept of **Bundles** (`.cgc` files)—portable snapshots of an indexed codebase. Bundles allow you to share or load pre-indexed graphs instantly without the overhead of parsing source code.

## 1. Creating a Bundle

Once you have indexed a repository, you can export it as a bundle:

```bash
cgc bundle create --name "my-project-v1"
```

This generates a `.cgc` file containing the entire graph structure and metadata.

## 2. Loading a Bundle

To load a bundle into your current session:

```bash
cgc bundle load ./my-project-v1.cgc
```

The graph is now immediately queryable via the CLI and MCP tools.

---

## 3. The CGC Bundle Registry

CGC maintains a registry of pre-indexed bundles for popular open-source libraries. This allows AI agents to understand your dependencies without you needing to have their source code locally.

### Search the Registry
Find available bundles for your tech stack:

```bash
cgc bundle search "flask"
```

### Download and Load
Fetch a bundle directly from the registry:

```bash
cgc bundle load flask
```

---

## 4. Use Cases for Bundles

*   **CI/CD**: Build a code graph as part of your CI pipeline and attach it to releases.
*   **Onboarding**: Provide new team members with a pre-indexed bundle of the entire microservices architecture.
*   **AI Context**: Attach bundles of common libraries (e.g., `requests`, `numpy`, `react`) to your AI assistant for better library-specific suggestions.

---

## Managing Local Bundles

You can list all bundles currently stored in your local registry:

```bash
cgc bundle list
```

To remove a bundle and free up space:

```bash
cgc bundle remove <bundle_id>
```
