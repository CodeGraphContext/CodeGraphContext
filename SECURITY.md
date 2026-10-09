
Secret redaction applies to stored content, including source, docstrings and
values. Graph identifiers (name, uid, path, lang, and properties ending
in _name or _path) are preserved so redaction cannot change merge keys or
break symbol resolution. Do not place credentials in identifiers or file paths.
Existing graphs with redacted symbol names require re-indexing with
cgc index --force after upgrading.
