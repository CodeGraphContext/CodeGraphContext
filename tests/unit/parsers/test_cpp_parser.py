from unittest.mock import MagicMock

import pytest

from codegraphcontext.tools.languages.cpp import CppTreeSitterParser
from codegraphcontext.utils.tree_sitter_manager import get_tree_sitter_manager


@pytest.fixture(scope="module")
def cpp_parser():
    manager = get_tree_sitter_manager()
    if not manager.is_language_available("cpp"):
        pytest.skip("C++ tree-sitter grammar is not available in this environment")

    wrapper = MagicMock()
    wrapper.language_name = "cpp"
    wrapper.language = manager.get_language_safe("cpp")
    wrapper.parser = manager.create_parser("cpp")
    return CppTreeSitterParser(wrapper)


# --- Bugfix: _find_enums NameError ---

def test_enum_parsing(cpp_parser, temp_test_dir):
    code = """
enum Color { RED, GREEN, BLUE };

enum class Status { OK = 0, ERROR = 1 };
"""
    f = temp_test_dir / "enums.cpp"
    f.write_text(code)
    result = cpp_parser.parse(f)

    enum_names = [e["name"] for e in result.get("enums", [])]
    assert "Color" in enum_names
    assert "Status" in enum_names


def test_file_with_enums_and_classes(cpp_parser, temp_test_dir):
    """Ensure files containing both enums and classes parse without errors."""
    code = """
enum DataType { INT = 0, VARCHAR = 1 };

class Foo {
public:
    void bar() {}
};
"""
    f = temp_test_dir / "mixed.cpp"
    f.write_text(code)
    result = cpp_parser.parse(f)

    assert any(c["name"] == "Foo" for c in result["classes"])
    assert any(e["name"] == "DataType" for e in result.get("enums", []))


# --- Fix 1: Inheritance / base class extraction ---

def test_single_public_inheritance(cpp_parser, temp_test_dir):
    code = """
class Base {
public:
    virtual void execute() {}
};

class Derived : public Base {
public:
    void execute() override {}
};
"""
    f = temp_test_dir / "inherit_single.cpp"
    f.write_text(code)
    result = cpp_parser.parse(f)

    classes = {c["name"]: c for c in result["classes"]}
    assert "Base" in classes
    assert "Derived" in classes
    assert classes["Base"]["bases"] == []
    assert classes["Derived"]["bases"] == ["Base"]


def test_multiple_inheritance(cpp_parser, temp_test_dir):
    code = """
class A {};
class B {};
class C : public A, private B {};
"""
    f = temp_test_dir / "inherit_multi.cpp"
    f.write_text(code)
    result = cpp_parser.parse(f)

    classes = {c["name"]: c for c in result["classes"]}
    assert classes["C"]["bases"] == ["A", "B"]


def test_virtual_inheritance(cpp_parser, temp_test_dir):
    code = """
class Base {};
class Derived : virtual public Base {};
"""
    f = temp_test_dir / "inherit_virtual.cpp"
    f.write_text(code)
    result = cpp_parser.parse(f)

    classes = {c["name"]: c for c in result["classes"]}
    assert classes["Derived"]["bases"] == ["Base"]


def test_template_base_class(cpp_parser, temp_test_dir):
    code = """
template<typename T>
class Container {};

class IntContainer : public Container<int> {};
"""
    f = temp_test_dir / "inherit_template.cpp"
    f.write_text(code)
    result = cpp_parser.parse(f)

    classes = {c["name"]: c for c in result["classes"]}
    # Template args should be stripped for graph matching
    assert "Container" in classes["IntContainer"]["bases"]


def test_qualified_base_class(cpp_parser, temp_test_dir):
    code = """
namespace ns {
class Base {};
}
class Derived : public ns::Base {};
"""
    f = temp_test_dir / "inherit_qualified.cpp"
    f.write_text(code)
    result = cpp_parser.parse(f)

    classes = {c["name"]: c for c in result["classes"]}
    assert len(classes["Derived"]["bases"]) == 1
    # Should capture the qualified name
    assert "Base" in classes["Derived"]["bases"][0]


# --- Fix 2: Qualified function definitions (ClassName::method in .cpp files) ---

def test_qualified_method_definition(cpp_parser, temp_test_dir):
    code = """
void QueueElement::execute() {
    return;
}

void QueueElement::setStatus(int status) {
    this->status = status;
}

void free_function() {
    return;
}
"""
    f = temp_test_dir / "methods.cpp"
    f.write_text(code)
    result = cpp_parser.parse(f)

    func_names = [fn["name"] for fn in result["functions"]]
    assert "execute" in func_names
    assert "setStatus" in func_names
    assert "free_function" in func_names

    # Verify class_context is set for qualified methods
    execute_fn = next(fn for fn in result["functions"] if fn["name"] == "execute")
    assert execute_fn.get("class_context") == "QueueElement"

    set_status_fn = next(fn for fn in result["functions"] if fn["name"] == "setStatus")
    assert set_status_fn.get("class_context") == "QueueElement"

    free_fn = next(fn for fn in result["functions"] if fn["name"] == "free_function")
    assert free_fn.get("class_context") is None


def test_nested_qualified_method(cpp_parser, temp_test_dir):
    code = """
void Namespace::Class::method() {
    return;
}
"""
    f = temp_test_dir / "nested_method.cpp"
    f.write_text(code)
    result = cpp_parser.parse(f)

    func_names = [fn["name"] for fn in result["functions"]]
    assert "method" in func_names

    method_fn = next(fn for fn in result["functions"] if fn["name"] == "method")
    assert method_fn.get("class_context") == "Namespace::Class"


# --- Fix 3: Call expression matching (->  and :: calls) ---

def test_arrow_method_calls(cpp_parser, temp_test_dir):
    code = """
void doWork() {
    obj->execute();
    ptr->setStatus(1);
}
"""
    f = temp_test_dir / "arrow_calls.cpp"
    f.write_text(code)
    result = cpp_parser.parse(f)

    call_names = [c["name"] for c in result["function_calls"]]
    assert "execute" in call_names
    assert "setStatus" in call_names


def test_scoped_calls(cpp_parser, temp_test_dir):
    code = """
void doWork() {
    std::move(x);
    QueueElement::setStatus(1);
}
"""
    f = temp_test_dir / "scoped_calls.cpp"
    f.write_text(code)
    result = cpp_parser.parse(f)

    call_names = [c["name"] for c in result["function_calls"]]
    assert "move" in call_names
    assert "setStatus" in call_names

    # Check inferred_obj_type for scoped calls
    move_call = next(c for c in result["function_calls"] if c["name"] == "move")
    assert move_call["inferred_obj_type"] == "std"

    status_call = next(c for c in result["function_calls"] if c["name"] == "setStatus")
    assert status_call["inferred_obj_type"] == "QueueElement"


def test_this_pointer_calls(cpp_parser, temp_test_dir):
    code = """
void MyClass::doWork() {
    this->execute();
    this->setStatus(1);
}
"""
    f = temp_test_dir / "this_calls.cpp"
    f.write_text(code)
    result = cpp_parser.parse(f)

    call_names = [c["name"] for c in result["function_calls"]]
    assert "execute" in call_names
    assert "setStatus" in call_names

    for call in result["function_calls"]:
        assert call["inferred_obj_type"] == "this"


def test_direct_function_calls(cpp_parser, temp_test_dir):
    code = """
void doWork() {
    printf("hello");
    free_function();
}
"""
    f = temp_test_dir / "direct_calls.cpp"
    f.write_text(code)
    result = cpp_parser.parse(f)

    call_names = [c["name"] for c in result["function_calls"]]
    assert "printf" in call_names
    assert "free_function" in call_names


# --- Integration: realistic C++ header with inheritance + methods ---

def test_realistic_header(cpp_parser, temp_test_dir):
    code = """
class QueueElement_Manuell {
public:
    virtual std::string getRequestInformation() = 0;
};

class QueueElement : public QueueElement_Manuell {
public:
    virtual int execute() { return 0; }
    virtual std::string getMonitorInfo() = 0;
};

class QueueElement_Dialer : public QueueElement {
public:
    virtual int execute() { return 0; }
};

class QueueElement_Dialer_Export : public QueueElement_Dialer {
public:
    virtual int execute();
    virtual std::string getMonitorInfo();
};

class QueueElement_Dialer_Export_File : public QueueElement_Dialer_Export {
public:
    QueueElement_Dialer_Export_File() {}
};

class QueueElement_Dialer_Export_Axa : public QueueElement_Dialer_Export {
public:
    virtual int execute();
    virtual std::string getMonitorInfo();
};
"""
    f = temp_test_dir / "realistic.h"
    f.write_text(code)
    result = cpp_parser.parse(f)

    classes = {c["name"]: c for c in result["classes"]}

    assert classes["QueueElement_Manuell"]["bases"] == []
    assert classes["QueueElement"]["bases"] == ["QueueElement_Manuell"]
    assert classes["QueueElement_Dialer"]["bases"] == ["QueueElement"]
    assert classes["QueueElement_Dialer_Export"]["bases"] == ["QueueElement_Dialer"]
    assert classes["QueueElement_Dialer_Export_File"]["bases"] == ["QueueElement_Dialer_Export"]
    assert classes["QueueElement_Dialer_Export_Axa"]["bases"] == ["QueueElement_Dialer_Export"]
