"""`_parse_calls` must not carry a mutable default for `variables`.

swift.py and scala.py declared `variables: ... = []`, the classic shared-mutable-default
anti-pattern: one list instance is reused across every call that omits the argument. The
parameter is only read today (both sole callers pass a list), so this was latent rather than
actively wrong, but the default must be `None` with a local `[]` fallback.
"""

import inspect

import pytest

from codegraphcontext.tools.languages.scala import ScalaTreeSitterParser
from codegraphcontext.tools.languages.swift import SwiftTreeSitterParser


@pytest.mark.parametrize("parser_cls", [SwiftTreeSitterParser, ScalaTreeSitterParser])
def test_parse_calls_variables_default_is_not_mutable(parser_cls):
    default = inspect.signature(parser_cls._parse_calls).parameters["variables"].default
    assert default is None, (
        f"{parser_cls.__name__}._parse_calls uses a mutable default for 'variables' "
        f"({default!r}); it must default to None"
    )
