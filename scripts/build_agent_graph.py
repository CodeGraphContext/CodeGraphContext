#!/usr/bin/env python3
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from codegraphcontext.tools.agent_graph_builder import build_agent_graph


if __name__ == '__main__':
    raise SystemExit(build_agent_graph(ROOT))
