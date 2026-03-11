import re
import logging
#importing all the language toolkits
from ..tools.query_tool_languages.c_toolkit import CToolkit
from ..tools.query_tool_languages.cpp_toolkit import CppToolkit
from ..tools.query_tool_languages.go_toolkit import GoToolkit
from ..tools.query_tool_languages.java_toolkit import JavaToolkit
from ..tools.query_tool_languages.javascript_toolkit import JavascriptToolkit
from ..tools.query_tool_languages.python_toolkit import PythonToolkit
from ..tools.query_tool_languages.ruby_toolkit import RubyToolkit
from ..tools.query_tool_languages.rust_toolkit import RustToolkit
from ..tools.query_tool_languages.typescript_toolkit import TypescriptToolkit
from ..tools.query_tool_languages.csharp_toolkit import CSharpToolkit
from ..tools.query_tool_languages.dart_toolkit import DartToolkit
from ..tools.query_tool_languages.perl_toolkit import PerlToolkit

from ..core.database import DatabaseManager
from ..utils.debug_log import debug_log

logger = logging.getLogger(__name__)

class Advanced_language_query:
    """
    Tool implementation for executing a read-only language specific Cypher query.
    
    Important: Includes a safety check to prevent any database modification
    by disallowing keywords like CREATE, MERGE, DELETE, etc.
    """

    TOOLKITS = {
        "c": CToolkit,
        "cpp": CppToolkit,
        "go": GoToolkit,
        "java": JavaToolkit,
        "javascript": JavascriptToolkit,
        "python": PythonToolkit,
        "ruby": RubyToolkit,
        "rust": RustToolkit,
        "typescript": TypescriptToolkit,
        "c_sharp": CSharpToolkit,
        "dart": DartToolkit,
        "perl": PerlToolkit
    }
    Supported_queries = {
        "repository": "Repository",
        "directory": "Directory",
        "file": "File",
        "module": "Module",
        "function": "Function",
        "class": "Class",
        "struct": "Struct",
        "enum": "Enum",
        "union": "Union",
        "macro": "Macro",
        "variable": "Variable"
    }


    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    def advanced_language_query(self, language: str, query: str):
        # Validating whether query is valid or not
        query = query.strip().lower()
        if query not in self.Supported_queries:
            raise ValueError(
                f"Unsupported query type '{query}'"
                f"Supported: {', '.join(self.Supported_queries.keys())}"
            )
        label = self.Supported_queries[query]

        # Set toolkit for the specified language
        language = language.lower()

        if language not in self.TOOLKITS:
            raise ValueError(f"Unsupported language: {language}")
        self.toolkit = self.TOOLKITS[language]()

        # Getting the language query
        cypher_query = self.toolkit.get_cypher_query(label)
        try:
            debug_log(f"Executing Cypher query: {cypher_query}")
            with self.db_manager.get_driver().session() as session:
                result = session.run(cypher_query)
                # Convert results to a list of dictionaries for clean JSON serialization
                records = [record.data() for record in result]

                return {
                    "success": True, 
                    "language": language,
                    "query": cypher_query,
                    "results": records 
                }
        except Exception as e:
            debug_log(f"Error executing Cypher query: {str(e)}")
            return {
                "error": "An unexpected error occurred while executing the query.",
                "details": str(e)
            }




