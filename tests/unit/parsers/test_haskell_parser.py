"""Haskell parser 冒烟测试（补上「其他语言都有、唯独 Haskell 缺失」的那一条）。

背景（2026-10-07）
--------------------
CI Build Test #33/#34/#35 连续红在三条 Haskell 用例上，**3 个 Python 版本
（3.12/3.13/3.14）失败完全相同**，且期间**代码零改动**（同一个 commit
`66ab4f1b`）。根因是 `tree-sitter-language-pack` 1.20.0 → 1.21.0 的上游漂移：
Haskell grammar 退化，**解析静默产出 0 个节点**（不报错），golden 回归因此报
「Missing 39 expected nodes」。

失效机制值得写下来，因为它是**静默**的：

1. ``HASKELL_QUERIES`` 依赖 grammar 的**具体节点名**：``function`` / ``bind`` /
   ``class`` / ``data_type`` / ``newtype`` / ``instance`` / ``apply`` /
   ``signature``，甚至包含 grammar 自带的拼写错误 ``type_synomym``。
   上游换 grammar 版本后 query 匹配不到 → 捕获数为 0。
2. ``_parse_classes`` 里是 ``if not name_node: continue`` —— grammar 的
   ``name`` 字段取不到时**逐个静默跳过**，返回空列表而不抛异常。
3. ``parse()`` 外层 ``except Exception`` 兜底成 ``_empty_result()``，
   与「真的什么都没有」无法区分。

为什么此前没被拦住（三重缺口）
------------------------------
1. **Haskell 没有专属 parser 测试** —— kotlin / swift / lua / ruby / php /
   elixir / dart … 都有 ``tests/unit/parsers/test_xxx_parser.py``，唯独没有 haskell。
2. 唯一覆盖它的是 golden 回归，报错是「缺失 39 个节点」，看不出根因是 grammar 没加载。
3. 其余 parser 测试用 ``if not is_language_available(...): pytest.skip(...)`` 兜底 ——
   **若 grammar 直接消失，测试会 skip，CI 反而变绿**，而能力已失效。

本文件的守点
------------
- 断言「**能解析出节点**」，而不是「grammar 能加载」—— 后者在上游回归时依然为真。
- Haskell 在 ``tools/tree_sitter_parser.py`` 的 ``LANGUAGE_PARSER_MAP`` 中被
  **宣称支持**，故不可用必须 **FAIL** 而非 skip；只有「整个 tree-sitter 栈
  缺失」才允许 skip（那是环境问题，不是能力问题）。
"""

from unittest.mock import MagicMock

import pytest

from codegraphcontext.tools.languages.haskell import HaskellTreeSitterParser
from codegraphcontext.tools.tree_sitter_parser import TreeSitterParser
from codegraphcontext.utils.tree_sitter_manager import get_tree_sitter_manager


def _require_haskell_grammar():
    """取 tree-sitter manager；Haskell grammar 不可用时**失败**而非跳过。

    刻意不同于其他 parser 测试的 ``pytest.skip`` 兜底：``haskell`` 在
    ``TreeSitterParser`` 的 LANGUAGE_PARSER_MAP 里被列为支持语言，宣称支持就必须能用。
    skip 会把「能力消失」伪装成「环境问题」，让 CI 变绿——那正是本次事故
    持续 3 天没人发现的原因之一。
    """
    manager = get_tree_sitter_manager()
    try:
        # 能构造成功即证明 haskell 仍在 LANGUAGE_PARSER_MAP 内（否则抛 ValueError）。
        # 注：该 map 定义在 __init__ 内部，不是模块级公开，故只能这样探测。
        TreeSitterParser("haskell")
    except ValueError:
        pytest.fail(
            "haskell 已从 LANGUAGE_PARSER_MAP 移除，但本测试仍要求它可用；"
            "若确为有意下线，请连同本测试与 golden 期望一起移除。"
        )
    if not manager.is_language_available("haskell"):
        pytest.fail(
            "Haskell grammar 不可用，但 haskell 仍被宣称支持 ⇒ 宣称与实际不一致。"
            "已知触发条件：tree-sitter-language-pack 1.21.0 起 haskell grammar 退化"
            "（CI #33/#34/#35，代码零改动）。索引时会静默产出空图谱，"
            "请检查该依赖版本（pyproject.toml 已临时锁 <1.21）。"
        )
    return manager


@pytest.fixture
def haskell_parser():
    manager = _require_haskell_grammar()
    wrapper = MagicMock()
    wrapper.language_name = "haskell"
    wrapper.language = manager.get_language_safe("haskell")
    wrapper.parser = manager.create_parser("haskell")
    return HaskellTreeSitterParser(wrapper)


SAMPLE_HS = """module Sample where

import Data.List (sort)

data Shape = Circle Float | Rectangle Float Float

class Descriptive a where
    describe :: a -> String

instance Descriptive Shape where
    describe _ = "shape"

addTwo :: Int -> Int
addTwo x = x + 2
"""


def test_tree_sitter_dispatches_haskell_parser():
    """分发器确实把 haskell 路由到 HaskellTreeSitterParser。"""
    parser = TreeSitterParser("haskell")
    assert isinstance(parser.language_specific_parser, HaskellTreeSitterParser)


def test_haskell_grammar_produces_nodes_not_silence(haskell_parser, temp_test_dir):
    """核心守点：grammar 不仅能加载，还必须**真的产出节点**。

    这是「能加载」与「能用」的分界。上游回归时 `is_language_available()` 仍为
    True，但 query 匹配不到 → 各类节点列表全空 → 图谱里少一整个语言而不报错。
    """
    f = temp_test_dir / "Sample.hs"
    f.write_text(SAMPLE_HS, encoding="utf-8")

    result = haskell_parser.parse(f)

    assert result["lang"] == "haskell"

    empty_hint = (
        "解析结果为空 —— Haskell grammar 很可能已退化（静默产出 0 节点）。"
        "参见 tree-sitter-language-pack 1.21.0 回归（CI #33/#34/#35）。"
    )
    assert result["functions"], f"未解析出任何 function/bind：{empty_hint}"
    assert result["classes"], f"未解析出任何 class/data/newtype：{empty_hint}"
    assert result["imports"], f"未解析出任何 import：{empty_hint}"
    assert result["typeclass_instances"], f"未解析出任何 instance：{empty_hint}"


def test_haskell_expected_declarations_are_recognised(haskell_parser, temp_test_dir):
    """不仅非空，还要认得出预期的声明名（防「解析出垃圾也算通过」）。"""
    f = temp_test_dir / "Sample.hs"
    f.write_text(SAMPLE_HS, encoding="utf-8")

    result = haskell_parser.parse(f)

    class_names = {c.get("name") for c in result["classes"]}
    assert "Descriptive" in class_names, f"未识别 typeclass Descriptive，实际: {class_names}"
    assert "Shape" in class_names, f"未识别 data type Shape，实际: {class_names}"

    function_names = {fn.get("name") for fn in result["functions"]}
    assert "addTwo" in function_names, f"未识别函数 addTwo，实际: {function_names}"

    imported = " ".join(
        str(imp.get("name") or "") + " " + str(imp.get("alias") or "")
        for imp in result["imports"]
    )
    assert "Data.List" in imported or "sort" in imported, f"未识别 import Data.List: {result['imports']}"


def test_haskell_parser_recovers_from_broken_source(haskell_parser, temp_test_dir):
    """语法错误时不得整体崩掉：应退化为部分结果，而不是抛异常中断整个索引。"""
    f = temp_test_dir / "Broken.hs"
    f.write_text("module Broken where\naddTwo x = = x +\n", encoding="utf-8")

    result = haskell_parser.parse(f)  # 不应抛异常

    assert result["lang"] == "haskell"
    assert isinstance(result["functions"], list)