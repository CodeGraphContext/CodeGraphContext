# Using On-Demand Bundles

Don't index everything yourself. Use pre-built graphs for popular libraries.

## What is a Bundle?
A `.cgc` bundle is a snapshot of a graph. It allows you to "import" the knowledge of `flask`, `pandas`, or `react` without parsing it yourself.

## How to use them

### 1. Search the Registry
```bash
cgc registry search react
```

### 2. Load a Bundle
```bash
cgc load react
```
*(This downloads ~5MB instead of parsing 50MB of source code).*

### 3. Query it
Now your AI knows about React's internals.
"How does `useEffect` work internally in React?" -> The AI can traverse the imported graph nodes.

## Requesting a Bundle
If a library isn't there, request it:
```bash
cgc registry request https://github.com/fastapi/fastapi
```
Our build servers will index it and make it available within minutes.
