from tree_sitter import Parser

from codegraphcontext.utils.tree_sitter_manager import get_tree_sitter_manager
from codegraphcontext.tools.languages.go import GoTreeSitterParser


class _DummyGenericParserWrapper:
    def __init__(self):
        self.language_name = "go"
        self.ts_manager = get_tree_sitter_manager()
        self.language = self.ts_manager.get_language_safe("go")
        self.parser = Parser(self.language)


def test_go_cyclomatic_complexity_increases_for_control_flow():
    wrapper = _DummyGenericParserWrapper()
    parser = GoTreeSitterParser(wrapper)

    code = """
    package p

    func SimpleHelper() int {
        return 1
    }

    func SomeComplexFunction(x int, ch1 chan int) int {
        if x > 0 {
            x = x + 1
        } else {
            x = x - 1
        }

        for i := 0; i < 10; i++ {
            if i%2 == 0 && x > 0 {
                x = x + i
            }
        }

        switch x {
        case 1:
            x = x + 2
        case 2, 3:
            x = x + 3
        default:
            x = 0
        }

        select {
        case <-ch1:
            x = x + 10
        default:
            x = x - 10
        }

        return x
    }
    """

    tree = wrapper.parser.parse(bytes(code, "utf8"))
    functions = parser._find_functions(tree.root_node)

    by_name = {f["name"]: f for f in functions}
    assert "SimpleHelper" in by_name
    assert "SomeComplexFunction" in by_name

    assert by_name["SimpleHelper"]["cyclomatic_complexity"] <= 2
    assert by_name["SomeComplexFunction"]["cyclomatic_complexity"] > 10

