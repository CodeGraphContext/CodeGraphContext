from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from codegraphcontext.tools.agent_graph_builder import build_agent_graph


def test_agent_graph_builder_outputs(tmp_path: Path) -> None:
    (tmp_path / 'example.py').write_text('import os\n', encoding='utf-8')
    (tmp_path / 'README.md').write_text('[x](docs.md)\n', encoding='utf-8')

    code = build_agent_graph(tmp_path)
    assert code == 0

    assert (tmp_path / '.agent' / 'graph' / 'code_graph.json').exists()
    assert (tmp_path / '.agent' / 'graph' / 'code_graph.md').exists()
    assert (tmp_path / '.agent' / 'graph' / 'code_graph.mmd').exists()
    assert (tmp_path / '.agent' / 'graph' / 'code_graph.dot').exists()
    assert (tmp_path / '.agent' / 'context_index.md').exists()
    assert (tmp_path / '.agent' / 'README.md').exists()
    assert (tmp_path / '.agent' / 'work_notes' / 'README.md').exists()
