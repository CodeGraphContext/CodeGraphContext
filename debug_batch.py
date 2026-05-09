import tempfile
from pathlib import Path
from src.codegraphcontext.tools.indexing.persistence.writer import GraphWriter
from src.codegraphcontext.core.database_kuzu import KuzuDBManager
from src.codegraphcontext.tools.indexing.persistence.writer import sanitize_props

# Simulate the batch creation like add_file_to_graph does
functions = [{
    "name": "run",
    "line_number": 3,
    "args": [],
    "class_context": "Worker",
    "class_context_line": 2,
}]

batch = []
for item in functions:
    row = dict(item)
    row["path"] = "/repo/Sample.kt"
    batch.append(sanitize_props(row))

print("Batch items:")
for i, item in enumerate(batch):
    print(f"  Item {i}: {item}")
    print(f"    Keys: {list(item.keys())}")
