def test_ruby_class_includes_module(graph):
    # Check that the module node exists
    rows = graph.query('MATCH (:Module {name:"Flyable"}) RETURN 1 AS ok LIMIT 1')
    assert rows, "Expected a Module node named 'Flyable' but none was found."

    # Check that the class node exists
    rows = graph.query('MATCH (:Class {name:"Bird"}) RETURN 1 AS ok LIMIT 1')
    assert rows, "Expected a Class node named 'Bird' but none was found."

    # Check that the INCLUDES relationship exists between Bird and Flyable
    rows = graph.query('''
        MATCH (:Class {name:"Bird"})-[:INCLUDES]->(:Module {name:"Flyable"})
        RETURN count(*) AS c
    ''')
    assert rows and rows[0]["c"] > 0, \
        "Expected an INCLUDES relationship from Class 'Bird' to Module 'Flyable', but none was found."


def test_module_is_unique(graph):
    # Ensure only one Module node named 'Flyable' exists
    rows = graph.query('MATCH (m:Module {name:"Flyable"}) RETURN count(m) AS c')
    assert rows and rows[0]["c"] == 1, \
        f"Expected exactly one Module node named 'Flyable', but found {rows[0]['c'] if rows else 0}."
