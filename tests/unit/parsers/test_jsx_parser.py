import pytest
from codegraphcontext.utils.tree_sitter_manager import get_tree_sitter_manager
from codegraphcontext.tools.languages.javascript import JavascriptTreeSitterParser
from unittest.mock import MagicMock


class TestJSXParser:
    """Test the JSX Parser logic (uses JavaScript parser with JSX syntax support)."""

    @pytest.fixture(scope="class")
    def parser(self):
        manager = get_tree_sitter_manager()

        wrapper = MagicMock()
        wrapper.language_name = "javascript"
        wrapper.language = manager.get_language_safe("javascript")
        wrapper.parser = manager.create_parser("javascript")

        return JavascriptTreeSitterParser(wrapper)

    def test_parse_functional_component(self, parser, temp_test_dir):
        """Parse a functional React component with JSX."""
        code = """
import React from 'react';

function Greeting({ name }) {
    return <div className="greeting">Hello {name}</div>;
}
"""
        f = temp_test_dir / "component.jsx"
        f.write_text(code)

        result = parser.parse(str(f))

        assert "functions" in result
        funcs = result["functions"]
        assert len(funcs) >= 1
        assert any(f["name"] == "Greeting" for f in funcs)

    def test_parse_arrow_function_component(self, parser, temp_test_dir):
        """Parse an arrow function React component."""
        code = """
const Button = ({ onClick, children }) => {
    return <button onClick={onClick}>{children}</button>;
};
"""
        f = temp_test_dir / "button.jsx"
        f.write_text(code)

        result = parser.parse(str(f))

        assert "functions" in result
        funcs = result["functions"]
        assert any(f["name"] == "Button" for f in funcs)

    def test_parse_class_component(self, parser, temp_test_dir):
        """Parse a class component extending React.Component."""
        code = """
import React from 'react';

class Counter extends React.Component {
    constructor(props) {
        super(props);
        this.state = { count: 0 };
    }

    render() {
        return <div>{this.state.count}</div>;
    }
}
"""
        f = temp_test_dir / "counter.jsx"
        f.write_text(code)

        result = parser.parse(str(f))

        assert "classes" in result
        classes = result["classes"]
        assert any(c["name"] == "Counter" for c in classes)

        assert "functions" in result
        funcs = result["functions"]
        method_names = [f["name"] for f in funcs]
        assert "constructor" in method_names
        assert "render" in method_names

    def test_parse_imports(self, parser, temp_test_dir):
        """Parse ES6 import statements."""
        code = """
import React, { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import * as Utils from './utils';
"""
        f = temp_test_dir / "imports.jsx"
        f.write_text(code)

        result = parser.parse(str(f))

        assert "imports" in result
        imports = result["imports"]
        assert len(imports) >= 2

        sources = [imp["source"] for imp in imports]
        assert "react" in sources
        assert "prop-types" in sources

    def test_parse_hooks(self, parser, temp_test_dir):
        """Parse components using React hooks."""
        code = """
function useCounter(initialValue) {
    const [count, setCount] = useState(initialValue);
    
    useEffect(() => {
        document.title = `Count: ${count}`;
    }, [count]);
    
    return [count, setCount];
}
"""
        f = temp_test_dir / "hooks.jsx"
        f.write_text(code)

        result = parser.parse(str(f))

        assert "functions" in result
        funcs = result["functions"]
        func_names = [f["name"] for f in funcs]
        assert "useCounter" in func_names

    def test_parse_jsx_with_nested_elements(self, parser, temp_test_dir):
        """Parse JSX with nested elements and attributes."""
        code = """
function Card({ title, children }) {
    return (
        <div className="card">
            <h2 className="card-title">{title}</h2>
            <div className="card-body">
                {children}
            </div>
        </div>
    );
}
"""
        f = temp_test_dir / "card.jsx"
        f.write_text(code)

        result = parser.parse(str(f))

        assert "functions" in result
        funcs = result["functions"]
        assert any(f["name"] == "Card" for f in funcs)

    def test_parse_sample_jsx_file(self, parser, javascript_sample_project):
        """Parse the sample JSX file from fixtures."""
        jsx_path = javascript_sample_project / "sample_jsx.jsx"
        if not jsx_path.exists():
            pytest.skip("sample_jsx.jsx not found in fixtures")

        result = parser.parse(str(jsx_path))

        assert "functions" in result
        funcs = result["functions"]
        func_names = [f["name"] for f in funcs]

        assert "Greeting" in func_names
        assert "Button" in func_names
        assert "Counter" in func_names
        assert "useWindowSize" in func_names

        assert "classes" in result
        classes = result["classes"]
        assert any(c["name"] == "ToggleSwitch" for c in classes)
