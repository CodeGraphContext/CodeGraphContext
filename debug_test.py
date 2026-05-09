import tempfile
from pathlib import Path
from src.codegraphcontext.tools.indexing.persistence.writer import GraphWriter
from src.codegraphcontext.core.database_kuzu import KuzuDBManager

with tempfile.TemporaryDirectory() as tmp_dir:
    tmp_path = Path(tmp_dir)
    manager = KuzuDBManager(tmp_path / 'test-db')
    driver = manager.get_driver()
    writer = GraphWriter(driver)
    repo_path = tmp_path / 'repo'
    repo_path.mkdir()
    file_path = repo_path / 'Sample.kt'
    file_path.write_text('', encoding='utf-8')
    
    print(f"File path: {file_path}")
    print(f"File path (str): {str(file_path)}")
    print(f"File path (resolve): {file_path.resolve()}")
    
    writer.add_repository_to_graph(repo_path)
    writer.add_file_to_graph({
        'path': str(file_path),
        'repo_path': str(repo_path),
        'lang': 'kotlin',
        'is_dependency': False,
        'functions': [{
            'name': 'run',
            'line_number': 3,
            'args': [],
            'class_context': 'Worker',
            'class_context_line': 2,
        }],
        'classes': [{'name': 'Worker', 'line_number': 2, 'node_type': 'class_declaration'}],
        'variables': [],
        'imports': [],
        'function_calls': [],
    }, repo_path.name, {}, repo_path_str=str(repo_path))
    
    with driver.session() as session:
        classes = session.run('MATCH (c:Class) RETURN c.name, c.path, c.line_number').data()
        functions = session.run('MATCH (f:Function) RETURN f.name, f.path, f.line_number').data()
        rels = session.run('MATCH ()-[r:CONTAINS]->() RETURN count(r) AS count').data()
        
        print('\nClasses:', classes)
        print('Functions:', functions)
        print('Relationships:', rels)
    
    manager.close_driver()
