"""CLI statistics acquired from an already-open database manager."""


def repository_stats(db_manager, repo_path=None):
    """Return the same metrics for direct and gateway-backed CLI reads.

    Scoped containment counts must be DISTINCT: a method can be reachable
    through both File->Function and File->Class->Function.
    """
    with db_manager.get_driver().session() as session:
        if repo_path is not None:
            if not session.run(
                "MATCH (r:Repository {path: $path}) RETURN r", path=repo_path
            ).single():
                return {"found": False, "counts": {}}
            queries = {
                "Files": "MATCH (r:Repository {path: $path})-[:CONTAINS*]->(f:File) RETURN count(DISTINCT f) as c",
                "Functions": "MATCH (r:Repository {path: $path})-[:CONTAINS*]->(func:Function) RETURN count(DISTINCT func) as c",
                "Classes": "MATCH (r:Repository {path: $path})-[:CONTAINS*]->(c:Class) RETURN count(DISTINCT c) as c",
                "Imported Modules": "MATCH (r:Repository {path: $path})-[:CONTAINS*]->(f:File)-[:IMPORTS]->(m:Module) RETURN count(DISTINCT m) as c",
            }
            return {"found": True, "counts": {
                label: session.run(query, path=repo_path).single()["c"]
                for label, query in queries.items()
            }}

        count = session.run("MATCH (r:Repository) RETURN count(r) as c").single()["c"]
        if not count:
            return {"found": True, "counts": {}}
        counts = {"Repositories": count}
        for label, node_type in (
            ("Files", "File"), ("Functions", "Function"), ("Classes", "Class"),
            ("Interfaces", "Interface"), ("Traits", "Trait"),
            ("Structs", "Struct"), ("Enums", "Enum"), ("Modules", "Module"),
        ):
            counts[label] = session.run(
                f"MATCH (n:{node_type}) RETURN count(n) as c"
            ).single()["c"]
        return {"found": True, "counts": counts}
