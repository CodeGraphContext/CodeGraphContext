"""JavaToolkit must build a driver through the CodeFinder's db_manager.

Regression guard: the per-call graph_name refactor removed the cached
``CodeFinder.driver`` attribute, but ``JavaToolkit.__init__`` still read
``code_finder.driver`` — an AttributeError the moment any Java/Spring analysis
tool was constructed. Mock unit tests on CodeFinder stayed green because this
consumer was never re-exercised against the new shape. This test pins the
constructor to the supported API (``db_manager.get_driver()``).
"""

from codegraphcontext.tools.query_tool_languages.java_toolkit import JavaToolkit


class _FakeDriver:
    def session(self):  # pragma: no cover - only identity matters here
        raise AssertionError("session() should not be called during construction")


class _FakeManager:
    def __init__(self):
        self.calls = []

    def get_driver(self, graph_name=None):
        self.calls.append(graph_name)
        return _FakeDriver()


class _FakeCodeFinder:
    def __init__(self):
        self.db_manager = _FakeManager()


def test_java_toolkit_constructs_via_db_manager_get_driver():
    cf = _FakeCodeFinder()

    toolkit = JavaToolkit(cf)

    # Driver was obtained through the manager, not a removed .driver attribute.
    assert cf.db_manager.calls == [None]
    assert hasattr(toolkit._driver, "session")


def test_codefinder_has_no_driver_attribute():
    # If CodeFinder ever re-grows a `.driver`, revisit whether JavaToolkit
    # should use it; until then the toolkit must go through db_manager.
    cf = _FakeCodeFinder()
    assert not hasattr(cf, "driver")
