import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from codegraphcontext.tools.indexing.resolution.calls import build_function_call_groups, resolve_function_call
from codegraphcontext.tools.languages.java import JavaTreeSitterParser, pre_scan_java
from codegraphcontext.tools.languages.kotlin import KotlinTreeSitterParser, pre_scan_kotlin
from codegraphcontext.utils.tree_sitter_manager import get_tree_sitter_manager


@pytest.fixture(scope="module")
def parser():
    manager = get_tree_sitter_manager()
    wrapper = MagicMock()
    wrapper.language_name = "kotlin"
    wrapper.language = manager.get_language_safe("kotlin")
    wrapper.parser = manager.create_parser("kotlin")
    return KotlinTreeSitterParser(wrapper)


def _write_and_parse(parser, src: str, suffix: str = ".kt") -> dict:
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=suffix, delete=False, encoding="utf-8"
    ) as f:
        f.write(src)
        tmp = f.name
    try:
        return parser.parse(Path(tmp))
    finally:
        os.unlink(tmp)


def _write_source(root: Path, relative_path: str, src: str) -> Path:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(src, encoding="utf-8")
    return path


EVENT_PROCESSOR_SRC = """
package com.example

data class Request(val id: String)

class EventProcessorGrpcService(
    private val progressService: ProgressService
) {
    fun submitEvents(request: Request): String {
        val events = getEventsFromRequest(request)
        progressService.applyEvent(events)
        directHelper(events)
        return events
    }

    private fun getEventsFromRequest(request: Request): String {
        return request.id
    }

    private fun directHelper(events: String): String {
        return events
    }
}
"""


PROGRESS_SERVICE_SRC = """
package com.example

class ProgressService {
    fun applyEvent(event: String): String {
        return event
    }
}
"""


RECEIVER_PATTERNS_SRC = """
package com.example

class ReceiverPatterns(
    private val ctorService: ProgressService,
    private val optionalService: ProgressService?,
    private val genericServices: List<ProgressService>
) {
    private val bodyService: ProgressService = ProgressService()
    private val optionalBodyService: ProgressService? = ProgressService()

    fun run(): String {
        val localService: ProgressService = ProgressService()
        val inferredLocal = ProgressService()

        ctorService.applyEvent("ctor")
        bodyService.applyEvent("body")
        localService.applyEvent("local")
        inferredLocal.applyEvent("inferred")
        optionalService?.applyEvent("safeCtor")
        optionalBodyService?.applyEvent("safeBody")
        genericServices.first()

        return "done"
    }
}
"""

OVERLOADED_SERVICE_SRC = """
package com.example

class OverloadedService {
    fun target(value: String): String {
        return value
    }

    fun target(value: String, flag: Boolean): String {
        return value
    }
}

class AmbiguousCache {
    fun get(values: Sequence<String>): List<String> {
        return emptyList()
    }

    fun get(values: Iterable<String>): List<String> {
        return emptyList()
    }
}

class LambdaOverloadService {
    fun target(predicate: (String) -> Boolean): String {
        return "lambda"
    }

    fun target(value: String): String {
        return value
    }
}
"""

OVERLOAD_CALLER_SRC = """
package com.example

class OverloadCaller(
    private val service: OverloadedService,
    private val cache: AmbiguousCache
) {
    fun run() {
        service.target("value", true)
        cache.get(listOf("value"))
    }
}
"""

AMBIGUOUS_OVERLOAD_CALLER_SRC = """
package com.example

class AmbiguousOverloadCaller(
    private val cache: AmbiguousCache
) {
    fun run(values: Any) {
        cache.get(values)
    }
}
"""

COLLECTION_INITIALIZER_CALLER_SRC = """
package com.example

class CollectionInitializerCaller(
    private val cache: AmbiguousCache
) {
    fun run(raw: List<String>) {
        val ids = raw.asSequence().map { it }
        cache.get(ids)
    }
}
"""

SEQUENCE_MAP_CALLER_SRC = """
package com.example

class SequenceMapCaller(
    private val cache: AmbiguousCache
) {
    fun run(ids: Sequence<String>) {
        cache.get(ids.map { it })
    }
}
"""

PARTITION_OVERLOAD_SERVICE_SRC = """
package com.example

class InstanceFilter

class InstanceStateService {
    fun asStates(ids: Set<String>, filter: InstanceFilter) {
    }

    fun asStates(ids: Iterable<String>, filter: InstanceFilter) {
    }
}
"""

PARTITION_OVERLOAD_CALLER_SRC = """
package com.example

class PartitionOverloadCaller(
    private val service: InstanceStateService
) {
    fun run(ids: Sequence<String>, instanceFilter: InstanceFilter) {
        val (valid, notFound) = ids.partition { it.isNotEmpty() }
        val items = valid.map { it }
        service.asStates(items, instanceFilter)
    }
}
"""

IMPLICIT_RECEIVER_PROPERTY_SRC = """
package com.example

interface EnrolmentState {
    fun isEnrolled(): Boolean
}

class EnrolmentStateImpl : EnrolmentState {
    override fun isEnrolled(): Boolean {
        return true
    }
}

class MatchState(
    val enrolmentState: EnrolmentState
)

fun MatchState.matches(): Boolean {
    return enrolmentState.isEnrolled()
}
"""

MAP_VALUE_RECEIVER_SRC = """
package com.example

class Context

interface EventsGroup {
    fun appendEvent(factory: () -> String)
    fun sendToExporter()
}

interface EventsExporter {
    fun buildEventsGroup(context: Context): EventsGroup
}

class CompositeEventsExporter(private val exporters: List<EventsExporter>) {
    private val exporterPerType = EnumMap<EventType, EventsExporter>(EventType::class.java).apply {
    }

    fun buildEventsGroup(context: Context): CompositeEventsGroup {
        val eventTypeToGroup = exporterPerType.mapValues { it.value.buildEventsGroup(context) }
        return CompositeEventsGroup(eventTypeToGroup)
    }
}

class CompositeEventsGroup(private val eventTypeToGroup: Map<EventType, EventsGroup>) {
    fun appendEvent(eventType: EventType, factory: () -> String) {
        eventTypeToGroup[eventType]?.appendEvent(factory)
    }

    fun sendToExporter() {
        eventTypeToGroup.values.forEach { it.sendToExporter() }
    }
}

enum class EventType {
    A
}
"""

PRETTY_STRING_RECEIVER_SRC = """
package com.example

class CategoryId
class ViewId
class RecordDefinitionId {
    companion object {
        fun newBuilder(): RecordDefinitionIdBuilder {
            return RecordDefinitionIdBuilder()
        }
    }
}
class RecordDefinitionIdBuilder {
    fun setRecordId(id: String): RecordDefinitionIdBuilder {
        return this
    }
    fun build(): RecordDefinitionId {
        return RecordDefinitionId()
    }
}

fun CategoryId.asPrettyString(): String {
    return "category"
}

fun ViewId.asPrettyString(): String {
    return "view"
}

fun RecordDefinitionId.asPrettyString(): String {
    return "record"
}

class PrettyStringCaller {
    fun fromNameOnly(): String {
        return categoryId.asPrettyString()
    }

    fun fromBuilder(): String {
        val fullRecordId = RecordDefinitionId.newBuilder()
            .setRecordId("record")
            .build()
        return fullRecordId.asPrettyString()
    }
}
"""

AMBIGUOUS_CALLABLE_REFERENCE_SRC = """
package com.example

class A
class B

class Accumulator {
    fun accumulate(value: A) {
    }

    fun accumulate(value: B) {
    }
}

class CallableReferenceCaller {
    fun run(accumulator: Accumulator, values: List<Any>) {
        accumulator.accumulate(A())
        values.forEach(accumulator::accumulate)
    }
}
"""

CALLABLE_REFERENCE_EXPECTED_TYPE_SRC = """
package com.example

class A
class B

class Accumulator {
    fun accumulate(value: A) {
    }

    fun accumulate(value: B) {
    }
}

class CallableReferenceCaller {
    fun run(accumulator: Accumulator, values: List<A>) {
        values.forEach(accumulator::accumulate)
    }
}
"""

CALLABLE_REFERENCE_COLLECTION_RETURN_SRC = """
package com.example

class A
class B
class Flow<T>

fun <T> mutableListOf(): MutableList<T> {
    TODO()
}

class Repository {
    fun load(): Flow<A> {
        TODO()
    }
}

class Accumulator {
    fun accumulate(value: A) {
    }

    fun accumulate(value: B) {
    }
}

class CallableReferenceCaller(
    private val repository: Repository
) {
    fun run(accumulator: Accumulator) {
        val values = repository.load().toCollection(mutableListOf())
        values.forEach(accumulator::accumulate)
    }
}
"""

TRAILING_LAMBDA_CALLER_SRC = """
package com.example

class TrailingLambdaCaller(
    private val service: LambdaOverloadService
) {
    fun run() {
        service.target { it.isNotEmpty() }
    }
}
"""

EXTERNAL_RECEIVER_SRC = """
package com.example

fun StringBuilder.escape() {
    append("external")
}

class ProjectWriter {
    fun append(value: String) {
    }
}

class ExternalReceiverCaller {
    fun run() {
        val buffer = StringBuilder()
        buffer.append("external")
        buffer.escape()
    }
}
"""

EXTENSION_OVERLOADS_SRC = """
package com.example

enum class FailureA {
    BAD
}

enum class FailureB {
    BAD
}

fun FailureA.asDetails(): String {
    return "a"
}

fun FailureB.asDetails(): String {
    return "b"
}

class ExtensionOverloadCaller {
    fun run() {
        FailureA.BAD.asDetails()
        FailureB.BAD.asDetails()
    }
}
"""

TAG_SPAN_SUPPORT_SRC = """
package com.example.trace

open class InternalEntity
class CommunityEntity : InternalEntity()
class Entity
class Span {
    companion object {
        fun current(): Span {
            return Span()
        }
    }
}
class SpanBuilder

fun Entity.tagSpan(span: Span) {
}

fun InternalEntity.tagSpan(span: SpanBuilder) {
}

fun InternalEntity.tagSpan(span: Span) {
}
"""

TAG_SPAN_CONSTANT_SRC = """
package com.example.community

import com.example.trace.CommunityEntity

val COMMUNITY_ENTITY = CommunityEntity()
"""

TAG_SPAN_CALLER_SRC = """
package com.example

import com.example.community.COMMUNITY_ENTITY
import com.example.trace.InternalEntity
import com.example.trace.Span
import com.example.trace.SpanBuilder
import com.example.trace.tagSpan

data class EventContext(val entity: InternalEntity)

class Caller {
    fun generated(request: SubmitRequest) {
        val span = Span.current()
        request.entity.tagSpan(span)
    }

    fun constant() {
        val span = Span.current()
        COMMUNITY_ENTITY.tagSpan(span)
    }

    fun member(eventContext: EventContext, span: Span) {
        eventContext.entity.tagSpan(span)
    }

    fun scoped(entity: InternalEntity) {
        val builder = SpanBuilder()
        builder.apply {
            entity.tagSpan(this)
        }
    }
}
"""

IMPLICIT_CLASS_RECEIVER_SRC = """
package com.example

class LocalWriter {
    fun append(value: String) {
    }

    fun append(value: Int) {
    }

    fun accept(value: String) {
        append(value)
    }
}

class OtherWriter {
    fun append(value: String) {
    }
}
"""


def _local_names(parsed: dict) -> set[str]:
    return (
        {f["name"] for f in parsed["functions"]}
        | {c["name"] for c in parsed["classes"]}
        | {c["name"] for c in parsed.get("interfaces", [])}
        | {c["name"] for c in parsed.get("objects", [])}
    )


def _local_imports(parsed: dict) -> dict:
    imports = {
        imp.get("alias") or imp["name"].split(".")[-1]: imp["name"]
        for imp in parsed.get("imports", [])
        if not imp["name"].endswith(".*")
    }
    wildcard_imports = [
        imp["name"][:-2]
        for imp in parsed.get("imports", [])
        if imp["name"].endswith(".*")
    ]
    if wildcard_imports:
        imports["__wildcards__"] = wildcard_imports
    return imports


def _resolve_with_progress_service(call: dict, caller_data: dict, progress_data: dict) -> dict:
    resolved = resolve_function_call(
        call,
        caller_file_path=caller_data["path"],
        local_names=_local_names(caller_data),
        local_imports={},
        imports_map={"ProgressService": [progress_data["path"]]},
        skip_external=False,
    )
    assert resolved is not None
    return resolved


class TestKotlinFunctionCallResolution:
    def test_function_type_parameters_are_split_at_top_level_commas(self, parser):
        data = _write_and_parse(
            parser,
            """
            package com.example

            class FunctionTypeConsumer {
                fun register(cb: (Int) -> String, x: Int, handlers: Map<String, (String) -> Unit> = emptyMap()) {
                    cb(x)
                }
            }
            """,
        )

        register = next(f for f in data["functions"] if f["name"] == "register")

        assert register["args"] == ["cb", "x", "handlers"]
        assert register["arg_types"] == ["(Int) -> String", "Int", "Map"]

    def test_top_level_callable_reference_is_parsed_and_resolved(self, parser):
        data = _write_and_parse(
            parser,
            """
            package com.example

            fun top(value: String): String {
                return value
            }

            class Caller {
                fun run(items: List<String>): List<String> {
                    return items.map(::top)
                }
            }
            """,
        )

        callable_ref = next(
            c for c in data["function_calls"]
            if c["call_kind"] == "callable_reference"
        )
        fn_to_fn, *_ = build_function_call_groups(
            [data],
            imports_map={"top": [data["path"]]},
        )

        assert callable_ref["name"] == "top"
        assert callable_ref["full_name"] == "top"
        assert callable_ref["base_obj"] is None
        assert any(
            edge["caller_name"] == "run"
            and edge["called_name"] == "top"
            and edge["called_file_path"] == str(Path(data["path"]).resolve())
            for edge in fn_to_fn
        )

    def test_function_class_context_includes_owner_line(self, parser):
        data = _write_and_parse(
            parser,
            """package p
fun top() {}
class A {
    class Worker {
        fun run() {}
    }
}
class B {
    class Worker {
        fun run() {}
    }
}
""",
        )

        workers = sorted(
            (cls["name"], cls["line_number"])
            for cls in data["classes"]
            if cls["name"] == "Worker"
        )
        runs = sorted(
            (fn["line_number"], fn["class_context"], fn["class_context_line"])
            for fn in data["functions"]
            if fn["name"] == "run"
        )
        top = next(fn for fn in data["functions"] if fn["name"] == "top")

        assert workers == [("Worker", 4), ("Worker", 9)]
        assert runs == [(5, "Worker", 4), (10, "Worker", 9)]
        assert "class_context_line" not in top

    def test_nested_constructor_call_resolves_nearest_same_named_class(self, parser):
        data = _write_and_parse(
            parser,
            """package p
class A {
    class Inner
    fun make() = Inner()
}
class B {
    class Inner
}
""",
        )

        a_inner = next(
            cls
            for cls in data["classes"]
            if cls["name"] == "Inner" and cls.get("class_context") == "A"
        )
        fn_to_fn, fn_to_cls, *_ = build_function_call_groups([data], imports_map={})
        constructor_edges = [
            edge
            for edge in fn_to_cls
            if edge["caller_name"] == "make" and edge["called_name"] == "Inner"
        ]

        assert fn_to_fn == []
        assert len(constructor_edges) == 1
        assert constructor_edges[0]["called_line_number"] == a_inner["line_number"]

    def test_same_named_nested_class_method_resolves_by_owner_line(self, parser):
        data = _write_and_parse(
            parser,
            """package p
class A {
    class Worker {
        fun helper() {}
        fun run() = helper()
    }
}
class B {
    class Worker {
        fun helper() {}
    }
}
""",
        )

        a_helper = next(
            fn
            for fn in data["functions"]
            if fn["name"] == "helper" and fn.get("class_context_line") == 3
        )
        fn_to_fn, *_ = build_function_call_groups([data], imports_map={})
        edges = [
            edge
            for edge in fn_to_fn
            if edge["caller_name"] == "run" and edge["full_call_name"] == "helper"
        ]

        assert len(edges) == 1
        assert edges[0]["called_line_number"] == a_helper["line_number"]
        assert edges[0]["called_context"] == "Worker"

    def test_qualified_nested_constructor_call_is_bucketed_as_class(self, parser):
        data = _write_and_parse(
            parser,
            """package p
class A {
    class Inner
}
fun make() = A.Inner()
""",
        )

        inner_class = next(cls for cls in data["classes"] if cls["name"] == "Inner")
        fn_to_fn, fn_to_cls, *_ = build_function_call_groups([data], imports_map={})
        edges = [
            edge
            for edge in fn_to_cls
            if edge["caller_name"] == "make" and edge["full_call_name"] == "A.Inner"
        ]

        assert fn_to_fn == []
        assert len(edges) == 1
        assert edges[0]["called_name"] == "Inner"
        assert edges[0]["called_line_number"] == inner_class["line_number"]

    def test_explicit_import_disambiguates_receiver_method_with_duplicate_class_names(self, parser, tmp_path):
        service_a_path = _write_source(
            tmp_path,
            "com/a/Service.kt",
            """
            package com.a

            class Service {
                fun run(): String {
                    return "a"
                }
            }
            """,
        )
        service_b_path = _write_source(
            tmp_path,
            "com/b/Service.kt",
            """
            package com.b

            class Service {
                fun run(): String {
                    return "b"
                }
            }
            """,
        )
        caller_path = _write_source(
            tmp_path,
            "com/c/Caller.kt",
            """
            package com.c

            import com.b.Service

            class Caller {
                fun execute(): String {
                    val service: Service = Service()
                    return service.run()
                }
            }
            """,
        )

        files = [service_a_path, service_b_path, caller_path]
        all_data = [parser.parse(path) for path in files]
        imports_map = pre_scan_kotlin(files, parser.generic_parser_wrapper)
        service_b_data = next(data for data in all_data if Path(data["path"]) == service_b_path)
        service_b_run = next(
            f for f in service_b_data["functions"]
            if f["name"] == "run" and f["context"] == "Service"
        )

        fn_to_fn, *_ = build_function_call_groups(all_data, imports_map)

        edge = next(
            e for e in fn_to_fn
            if e["caller_name"] == "execute" and e["full_call_name"] == "service.run"
        )
        assert Path(edge["called_file_path"]).resolve() == service_b_path.resolve()
        assert edge["called_context"] == "Service"
        assert edge["called_line_number"] == service_b_run["line_number"]

    def test_explicit_java_import_disambiguates_receiver_method_from_kotlin_class(self, parser, tmp_path):
        java_service_path = _write_source(
            tmp_path,
            "j/Service.java",
            """
            package j;

            public class Service {
                public String run() {
                    return "java";
                }
            }
            """,
        )
        kotlin_service_path = _write_source(
            tmp_path,
            "k/Service.kt",
            """
            package k

            class Service {
                fun run(): String {
                    return "kotlin"
                }
            }
            """,
        )
        caller_path = _write_source(
            tmp_path,
            "c/Use.kt",
            """
            package c

            import j.Service

            class Use {
                fun execute(): String {
                    val service: Service = Service()
                    return service.run()
                }
            }
            """,
        )
        manager = get_tree_sitter_manager()
        java_wrapper = MagicMock()
        java_wrapper.language_name = "java"
        java_wrapper.language = manager.get_language_safe("java")
        java_wrapper.parser = manager.create_parser("java")
        java_parser = JavaTreeSitterParser(java_wrapper)

        java_data = java_parser.parse(java_service_path)
        kotlin_service_data = parser.parse(kotlin_service_path)
        caller_data = parser.parse(caller_path)
        imports_map = {}
        for symbol_map in (
            pre_scan_java([java_service_path], java_wrapper),
            pre_scan_kotlin([kotlin_service_path, caller_path], parser.generic_parser_wrapper),
        ):
            for name, paths in symbol_map.items():
                imports_map.setdefault(name, []).extend(paths)
        java_run = next(f for f in java_data["functions"] if f["name"] == "run")

        fn_to_fn, *_ = build_function_call_groups(
            [java_data, kotlin_service_data, caller_data],
            imports_map,
        )

        edge = next(
            e for e in fn_to_fn
            if e["caller_name"] == "execute" and e["full_call_name"] == "service.run"
        )
        assert Path(edge["called_file_path"]).resolve() == java_service_path.resolve()
        assert edge["called_context"] == "Service"
        assert edge["called_line_number"] == java_run["line_number"]

    def test_kotlin_call_to_overloaded_java_method_uses_argument_types(self, parser, tmp_path):
        java_service_path = _write_source(
            tmp_path,
            "j/Service.java",
            """
            package j;

            public class Service {
                public void run(String value) {}
                public void run(int value) {}
            }
            """,
        )
        caller_path = _write_source(
            tmp_path,
            "c/Use.kt",
            """
            package c

            import j.Service

            fun use(service: Service) {
                service.run("x")
                service.run(1)
            }
            """,
        )
        manager = get_tree_sitter_manager()
        java_wrapper = MagicMock()
        java_wrapper.language_name = "java"
        java_wrapper.language = manager.get_language_safe("java")
        java_wrapper.parser = manager.create_parser("java")
        java_parser = JavaTreeSitterParser(java_wrapper)

        java_data = java_parser.parse(java_service_path)
        caller_data = parser.parse(caller_path)
        imports_map = {}
        for symbol_map in (
            pre_scan_java([java_service_path], java_wrapper),
            pre_scan_kotlin([caller_path], parser.generic_parser_wrapper),
        ):
            for name, paths in symbol_map.items():
                imports_map.setdefault(name, []).extend(paths)
        string_run = next(f for f in java_data["functions"] if f["name"] == "run" and f["arg_types"] == ["String"])
        int_run = next(f for f in java_data["functions"] if f["name"] == "run" and f["arg_types"] == ["Int"])

        fn_to_fn, *_ = build_function_call_groups([java_data, caller_data], imports_map)
        edges = [
            edge
            for edge in fn_to_fn
            if edge["caller_name"] == "use" and edge["full_call_name"] == "service.run"
        ]

        assert [edge["called_line_number"] for edge in edges] == [
            string_run["line_number"],
            int_run["line_number"],
        ]

    def test_kotlin_call_to_java_method_uses_imported_class_context(self, parser, tmp_path):
        java_service_path = _write_source(
            tmp_path,
            "j/Service.java",
            """
            package j;

            public class Service {
                public void run(String value) {}
            }

            class Helper {
                public void run(String value) {}
            }
            """,
        )
        caller_path = _write_source(
            tmp_path,
            "c/Use.kt",
            """
            package c

            import j.Service

            fun use(service: Service) {
                service.run("x")
            }
            """,
        )
        manager = get_tree_sitter_manager()
        java_wrapper = MagicMock()
        java_wrapper.language_name = "java"
        java_wrapper.language = manager.get_language_safe("java")
        java_wrapper.parser = manager.create_parser("java")
        java_parser = JavaTreeSitterParser(java_wrapper)

        java_data = java_parser.parse(java_service_path)
        caller_data = parser.parse(caller_path)
        imports_map = {}
        for symbol_map in (
            pre_scan_java([java_service_path], java_wrapper),
            pre_scan_kotlin([caller_path], parser.generic_parser_wrapper),
        ):
            for name, paths in symbol_map.items():
                imports_map.setdefault(name, []).extend(paths)
        service_run = next(
            f
            for f in java_data["functions"]
            if f["name"] == "run" and f["context"] == "Service"
        )

        fn_to_fn, *_ = build_function_call_groups([java_data, caller_data], imports_map)
        edges = [
            edge
            for edge in fn_to_fn
            if edge["caller_name"] == "use" and edge["full_call_name"] == "service.run"
        ]

        assert len(edges) == 1
        assert edges[0]["called_context"] == "Service"
        assert edges[0]["called_line_number"] == service_run["line_number"]

    def test_scope_function_receiver_does_not_apply_to_receiver_expression_call(self, parser, tmp_path):
        caller_path = _write_source(
            tmp_path,
            "com/example/Caller.kt",
            """
            package com.example

            fun makeSvc(): Svc {
                return Svc()
            }

            class Svc {
                fun makeSvc(): Svc {
                    return this
                }

                fun doWork(): String {
                    return "ok"
                }
            }

            class Caller {
                fun run(): String {
                    return makeSvc().apply { doWork() }.doWork()
                }
            }
            """,
        )

        caller_data = parser.parse(caller_path)
        make_call = next(
            c for c in caller_data["function_calls"]
            if c["name"] == "makeSvc"
        )
        imports_map = pre_scan_kotlin([caller_path], parser.generic_parser_wrapper)
        top_level_make_svc = next(
            f for f in caller_data["functions"]
            if f["name"] == "makeSvc" and f["context"] is None
        )

        fn_to_fn, *_ = build_function_call_groups([caller_data], imports_map)

        assert make_call["inferred_obj_type"] is None
        edge = next(
            edge for edge in fn_to_fn
            if edge["caller_name"] == "run" and edge["called_name"] == "makeSvc"
        )
        assert Path(edge["called_file_path"]).resolve() == caller_path.resolve()
        assert edge["called_line_number"] == top_level_make_svc["line_number"]

    def test_same_named_methods_keep_parameter_receiver_types_scoped_by_function(self, parser, tmp_path):
        source_path = _write_source(
            tmp_path,
            "com/example/Scopes.kt",
            """
            package com.example

            class A {
                fun run(service: AService) {
                    service.doIt()
                }
            }

            class B {
                fun run(service: BService) {
                    service.doIt()
                }
            }

            class AService {
                fun doIt(): String {
                    return "a"
                }
            }

            class BService {
                fun doIt(): String {
                    return "b"
                }
            }
            """,
        )
        data = parser.parse(source_path)
        imports_map = pre_scan_kotlin([source_path], parser.generic_parser_wrapper)
        targets = {
            f["context"]: f
            for f in data["functions"]
            if f["name"] == "doIt"
        }

        fn_to_fn, *_ = build_function_call_groups([data], imports_map)
        do_it_edges = sorted(
            (
                edge for edge in fn_to_fn
                if edge["full_call_name"] == "service.doIt"
            ),
            key=lambda edge: edge["line_number"],
        )

        assert len(do_it_edges) == 2
        assert do_it_edges[0]["called_context"] == "AService"
        assert do_it_edges[0]["called_line_number"] == targets["AService"]["line_number"]
        assert do_it_edges[1]["called_context"] == "BService"
        assert do_it_edges[1]["called_line_number"] == targets["BService"]["line_number"]

    def test_destructured_local_receiver_types_are_scoped_by_function(self, parser, tmp_path):
        source_path = _write_source(
            tmp_path,
            "com/example/DestructureScopes.kt",
            """
            package com.example

            class A {
                fun run() {
                    val (service) = AService()
                    service.doIt()
                }
            }

            class B {
                fun run() {
                    val (service) = BService()
                    service.doIt()
                }
            }

            class AService {
                fun doIt(): String {
                    return "a"
                }
            }

            class BService {
                fun doIt(): String {
                    return "b"
                }
            }
            """,
        )
        data = parser.parse(source_path)
        imports_map = pre_scan_kotlin([source_path], parser.generic_parser_wrapper)
        targets = {
            f["context"]: f
            for f in data["functions"]
            if f["name"] == "doIt"
        }
        services = [
            v for v in data["variables"]
            if v["name"] == "service"
        ]

        fn_to_fn, *_ = build_function_call_groups([data], imports_map)
        do_it_edges = sorted(
            (
                edge for edge in fn_to_fn
                if edge["full_call_name"] == "service.doIt"
            ),
            key=lambda edge: edge["line_number"],
        )

        assert {v["context"] for v in services} == {"run"}
        assert [v["line_number"] for v in services] == [6, 13]
        assert len(do_it_edges) == 2
        assert do_it_edges[0]["called_context"] == "AService"
        assert do_it_edges[0]["called_line_number"] == targets["AService"]["line_number"]
        assert do_it_edges[1]["called_context"] == "BService"
        assert do_it_edges[1]["called_line_number"] == targets["BService"]["line_number"]

    def test_overload_resolution_uses_unique_parameter_name_match(self, parser, tmp_path):
        source_path = _write_source(
            tmp_path,
            "com/example/Accumulator.kt",
            """
            package com.example

            class CategoryEnrolmentStates
            class InstanceProgressRow

            class Accumulator {
                fun accumulate(enrolmentStates: CategoryEnrolmentStates) {
                }

                fun accumulate(row: InstanceProgressRow) {
                }
            }

            class Caller {
                fun run(accumulator: Accumulator) {
                    rows.forEach { row ->
                        accumulator.accumulate(row)
                    }
                }
            }
            """,
        )
        data = parser.parse(source_path)
        imports_map = pre_scan_kotlin([source_path], parser.generic_parser_wrapper)
        row_target = next(
            f for f in data["functions"]
            if f["name"] == "accumulate" and f["args"] == ["row"]
        )

        fn_to_fn, *_ = build_function_call_groups([data], imports_map)

        edge = next(
            edge for edge in fn_to_fn
            if edge["full_call_name"] == "accumulator.accumulate"
        )
        assert edge["called_context"] == "Accumulator"
        assert edge["called_line_number"] == row_target["line_number"]

    def test_named_arguments_select_matching_overloads(self, parser, tmp_path):
        source_path = _write_source(
            tmp_path,
            "com/example/NamedArgs.kt",
            """
            package com.example

            class Svc {
                fun target(value: String) {
                }

                fun target(count: Int) {
                }

                fun pick(value: String, count: Int) {
                }

                fun pick(value: String, enabled: Boolean) {
                }
            }

            class Caller {
                fun run(svc: Svc) {
                    svc.target(count = 1)
                    svc.pick(count = 1, value = "x")
                }
            }
            """,
        )
        data = parser.parse(source_path)
        imports_map = pre_scan_kotlin([source_path], parser.generic_parser_wrapper)
        target_count = next(
            f for f in data["functions"]
            if f["name"] == "target" and f["arg_types"] == ["Int"]
        )
        pick_count = next(
            f for f in data["functions"]
            if f["name"] == "pick" and f["arg_types"] == ["String", "Int"]
        )

        fn_to_fn, *_ = build_function_call_groups([data], imports_map)
        edges = {
            edge["full_call_name"]: edge
            for edge in fn_to_fn
            if edge["called_name"] in {"target", "pick"}
        }

        assert edges["svc.target"]["called_line_number"] == target_count["line_number"]
        assert edges["svc.pick"]["called_line_number"] == pick_count["line_number"]

    def test_overload_selection_rejects_incompatible_exact_arity_for_default_param(self, parser):
        data = _write_and_parse(
            parser,
            """
            package com.example

            class Service {
                fun run(value: Int, suffix: String = "") {
                }

                fun run(value: String) {
                }
            }

            fun use(service: Service) {
                service.run(1)
            }
            """,
        )

        int_target = next(
            f
            for f in data["functions"]
            if f["name"] == "run" and f["arg_types"] == ["Int", "String"]
        )
        fn_to_fn, *_ = build_function_call_groups([data], imports_map={})
        edge = next(
            edge
            for edge in fn_to_fn
            if edge["caller_name"] == "use" and edge["full_call_name"] == "service.run"
        )

        assert edge["called_line_number"] == int_target["line_number"]

    def test_inherited_overload_uses_compatible_base_method(self, parser):
        data = _write_and_parse(
            parser,
            """
            package com.example

            open class Base {
                fun foo(value: Int) {
                }
            }

            class Derived : Base() {
                fun foo(value: String) {
                }
            }

            fun run(d: Derived) {
                d.foo(1)
            }
            """,
        )

        base_target = next(
            f
            for f in data["functions"]
            if f["name"] == "foo" and f["context"] == "Base"
        )
        fn_to_fn, *_ = build_function_call_groups([data], imports_map={})
        edge = next(
            edge
            for edge in fn_to_fn
            if edge["caller_name"] == "run" and edge["full_call_name"] == "d.foo"
        )

        assert edge["called_context"] == "Base"
        assert edge["called_line_number"] == base_target["line_number"]

    def test_extension_overload_used_when_member_overloads_incompatible(self, parser):
        data = _write_and_parse(
            parser,
            """
            package com.example

            class A {
                fun foo(value: Int) {
                }

                fun foo(value: Boolean) {
                }
            }

            fun A.foo(value: String) {
            }

            fun test(a: A) {
                a.foo("x")
            }
            """,
        )
        diagnostics = []

        extension_target = next(
            f
            for f in data["functions"]
            if f["name"] == "foo" and f.get("receiver_type") == "A"
        )
        fn_to_fn, *_ = build_function_call_groups(
            [data],
            imports_map={},
            diagnostics=diagnostics,
        )
        edge = next(
            edge
            for edge in fn_to_fn
            if edge["caller_name"] == "test" and edge["full_call_name"] == "a.foo"
        )

        assert edge["called_context"] is None
        assert edge["called_line_number"] == extension_target["line_number"]
        assert not diagnostics

    def test_incompatible_receiver_overload_skips_without_line_less_edge(self, parser):
        data = _write_and_parse(
            parser,
            """
            package com.example

            class A {
                fun foo(value: Int) {
                }

                fun foo(value: Boolean) {
                }
            }

            fun test(a: A) {
                a.foo("x")
            }
            """,
        )
        diagnostics = []

        fn_to_fn, *_ = build_function_call_groups(
            [data],
            imports_map={
                "A": [data["path"]],
                "com.example.A": [data["path"]],
            },
            diagnostics=diagnostics,
        )

        assert [
            edge for edge in fn_to_fn
            if edge["caller_name"] == "test" and edge["full_call_name"] == "a.foo"
        ] == []
        assert any(
            diagnostic["reason"] == "unresolved_overloaded_call"
            and diagnostic["full_call_name"] == "a.foo"
            for diagnostic in diagnostics
        )

    def test_ambiguous_top_level_overload_is_skipped_with_diagnostic(self, parser):
        data = _write_and_parse(
            parser,
            """
            package com.example

            fun caller(x: Any) {
                foo(x)
            }

            fun foo(value: String) {
            }

            fun foo(value: Int) {
            }
            """,
        )
        diagnostics = []

        fn_to_fn, *_ = build_function_call_groups(
            [data],
            imports_map={},
            diagnostics=diagnostics,
        )

        assert [
            edge for edge in fn_to_fn
            if edge["caller_name"] == "caller" and edge["full_call_name"] == "foo"
        ] == []
        assert any(
            diagnostic["reason"] == "ambiguous_function_target"
            and diagnostic["full_call_name"] == "foo"
            for diagnostic in diagnostics
        )

    def test_same_file_call_preserves_caller_function_context(self, parser):
        data = _write_and_parse(parser, EVENT_PROCESSOR_SRC)
        direct_helper_calls = [
            c for c in data["function_calls"] if c["name"] == "directHelper"
        ]
        assert direct_helper_calls, "Expected directHelper call to be parsed"

        resolved = resolve_function_call(
            direct_helper_calls[0],
            caller_file_path=data["path"],
            local_names=_local_names(data),
            local_imports={},
            imports_map={},
            skip_external=False,
        )

        assert resolved is not None
        assert resolved["type"] == "function"
        assert resolved["caller_name"] == "submitEvents"
        assert resolved["called_name"] == "directHelper"

    def test_constructor_property_receiver_resolves_cross_file(self, parser):
        processor_data = _write_and_parse(parser, EVENT_PROCESSOR_SRC)
        progress_data = _write_and_parse(parser, PROGRESS_SERVICE_SRC)

        progress_variables = [
            v for v in processor_data["variables"] if v["name"] == "progressService"
        ]
        assert progress_variables, "Expected constructor property progressService"
        assert progress_variables[0]["type"] == "ProgressService"

        apply_event_calls = [
            c for c in processor_data["function_calls"] if c["name"] == "applyEvent"
        ]
        assert apply_event_calls, "Expected progressService.applyEvent call"
        assert apply_event_calls[0]["inferred_obj_type"] == "ProgressService"

        resolved = resolve_function_call(
            apply_event_calls[0],
            caller_file_path=processor_data["path"],
            local_names=_local_names(processor_data),
            local_imports={},
            imports_map={"ProgressService": [progress_data["path"]]},
            skip_external=False,
        )

        assert resolved is not None
        assert resolved["type"] == "function"
        assert resolved["caller_name"] == "submitEvents"
        assert resolved["called_name"] == "applyEvent"
        assert resolved["called_file_path"] == progress_data["path"]

    def test_kotlin_call_arguments_are_parsed(self, parser):
        caller_data = _write_and_parse(parser, OVERLOAD_CALLER_SRC)

        target_call = next(
            c for c in caller_data["function_calls"]
            if c["full_name"] == "service.target"
        )

        assert target_call["args"] == ['"value"', "true"]

    def test_kotlin_trailing_lambda_call_argument_is_parsed(self, parser):
        caller_data = _write_and_parse(parser, TRAILING_LAMBDA_CALLER_SRC)

        target_call = next(
            c for c in caller_data["function_calls"]
            if c["full_name"] == "service.target"
        )

        assert target_call["args"] == ["{ it.isNotEmpty() }"]

    def test_overloaded_kotlin_method_uses_arity_for_target_line(self, parser):
        service_data = _write_and_parse(parser, OVERLOADED_SERVICE_SRC)
        caller_data = _write_and_parse(parser, OVERLOAD_CALLER_SRC)

        two_arg_target = next(
            f for f in service_data["functions"]
            if f["name"] == "target" and len(f["args"]) == 2
        )

        fn_to_fn, *_ = build_function_call_groups(
            [service_data, caller_data],
            imports_map={
                "OverloadedService": [service_data["path"]],
                "AmbiguousCache": [service_data["path"]],
            },
        )

        edge = next(
            e for e in fn_to_fn
            if e["full_call_name"] == "service.target"
        )
        assert edge["called_file_path"] == service_data["path"]
        assert edge["called_context"] == "OverloadedService"
        assert edge["called_line_number"] == two_arg_target["line_number"]

    def test_kotlin_overload_uses_argument_type_hint_for_target_line(self, parser):
        service_data = _write_and_parse(parser, OVERLOADED_SERVICE_SRC)
        caller_data = _write_and_parse(parser, OVERLOAD_CALLER_SRC)

        iterable_get = next(
            f for f in service_data["functions"]
            if f["name"] == "get" and f["arg_types"] == ["Iterable"]
        )

        fn_to_fn, *_ = build_function_call_groups(
            [service_data, caller_data],
            imports_map={
                "OverloadedService": [service_data["path"]],
                "AmbiguousCache": [service_data["path"]],
            },
        )

        edge = next(
            e for e in fn_to_fn
            if e["full_call_name"] == "cache.get"
        )
        assert edge["called_file_path"] == service_data["path"]
        assert edge["called_context"] == "AmbiguousCache"
        assert edge["called_line_number"] == iterable_get["line_number"]

    def test_kotlin_overload_uses_collection_initializer_type_hint(self, parser):
        service_data = _write_and_parse(parser, OVERLOADED_SERVICE_SRC)
        caller_data = _write_and_parse(parser, COLLECTION_INITIALIZER_CALLER_SRC)

        sequence_get = next(
            f for f in service_data["functions"]
            if f["name"] == "get" and f["arg_types"] == ["Sequence"]
        )
        ids_variable = next(
            v for v in caller_data["variables"]
            if v["name"] == "ids"
        )

        fn_to_fn, *_ = build_function_call_groups(
            [service_data, caller_data],
            imports_map={
                "AmbiguousCache": [service_data["path"]],
            },
        )

        edge = next(
            e for e in fn_to_fn
            if e["full_call_name"] == "cache.get"
        )
        assert ids_variable["initializer_inferred_type"] == "Sequence"
        assert edge["called_line_number"] == sequence_get["line_number"]

    def test_kotlin_sequence_map_expression_uses_receiver_type_hint(self, parser):
        service_data = _write_and_parse(parser, OVERLOADED_SERVICE_SRC)
        caller_data = _write_and_parse(parser, SEQUENCE_MAP_CALLER_SRC)

        sequence_get = next(
            f for f in service_data["functions"]
            if f["name"] == "get" and f["arg_types"] == ["Sequence"]
        )

        fn_to_fn, *_ = build_function_call_groups(
            [service_data, caller_data],
            imports_map={
                "AmbiguousCache": [service_data["path"]],
            },
        )

        edge = next(
            e for e in fn_to_fn
            if e["full_call_name"] == "cache.get"
        )
        assert edge["called_line_number"] == sequence_get["line_number"]

    def test_kotlin_partition_and_map_initializer_selects_iterable_overload(self, parser):
        service_data = _write_and_parse(parser, PARTITION_OVERLOAD_SERVICE_SRC)
        caller_data = _write_and_parse(parser, PARTITION_OVERLOAD_CALLER_SRC)

        iterable_target = next(
            f for f in service_data["functions"]
            if f["name"] == "asStates" and f["arg_types"] == ["Iterable", "InstanceFilter"]
        )
        variables = {
            v["name"]: v for v in caller_data["variables"]
            if v["name"] in {"valid", "notFound", "items"}
        }

        fn_to_fn, *_ = build_function_call_groups(
            [service_data, caller_data],
            imports_map={
                "InstanceStateService": [service_data["path"]],
            },
        )

        edge = next(
            e for e in fn_to_fn
            if e["full_call_name"] == "service.asStates"
        )
        assert variables["valid"]["initializer_inferred_type"] == "List"
        assert variables["notFound"]["initializer_inferred_type"] == "List"
        assert variables["items"]["initializer_inferred_type"] == "List"
        assert edge["called_line_number"] == iterable_target["line_number"]

    def test_kotlin_implicit_receiver_property_resolves_declared_member_type(self, parser):
        data = _write_and_parse(parser, IMPLICIT_RECEIVER_PROPERTY_SRC)

        interface_target = next(
            f for f in data["functions"]
            if f["name"] == "isEnrolled" and f["context"] == "EnrolmentState"
        )

        fn_to_fn, *_ = build_function_call_groups(
            [data],
            imports_map={
                "EnrolmentState": [data["path"]],
                "EnrolmentStateImpl": [data["path"]],
            },
        )

        edge = next(
            e for e in fn_to_fn
            if e["full_call_name"] == "enrolmentState.isEnrolled"
        )
        assert edge["called_context"] == "EnrolmentState"
        assert edge["called_line_number"] == interface_target["line_number"]

    def test_kotlin_map_value_and_values_lambda_receivers_use_generic_value_type(self, parser):
        data = _write_and_parse(parser, MAP_VALUE_RECEIVER_SRC)

        exporter_target = next(
            f for f in data["functions"]
            if f["name"] == "buildEventsGroup" and f["context"] == "EventsExporter"
        )
        append_target = next(
            f for f in data["functions"]
            if f["name"] == "appendEvent" and f["context"] == "EventsGroup"
        )
        send_target = next(
            f for f in data["functions"]
            if f["name"] == "sendToExporter" and f["context"] == "EventsGroup"
        )

        fn_to_fn, *_ = build_function_call_groups(
            [data],
            imports_map={
                "EventsExporter": [data["path"]],
                "EventsGroup": [data["path"]],
                "CompositeEventsExporter": [data["path"]],
                "CompositeEventsGroup": [data["path"]],
            },
        )

        edges = {
            (edge["caller_name"], edge["full_call_name"]): edge
            for edge in fn_to_fn
            if edge["called_name"] in {"buildEventsGroup", "appendEvent", "sendToExporter"}
        }
        assert edges[("buildEventsGroup", "it.value.buildEventsGroup")]["called_line_number"] == exporter_target["line_number"]
        assert edges[("appendEvent", "eventTypeToGroup[eventType].appendEvent")]["called_line_number"] == append_target["line_number"]
        assert edges[("sendToExporter", "it.sendToExporter")]["called_line_number"] == send_target["line_number"]

    def test_kotlin_extension_receiver_uses_variable_name_and_builder_type_hints(self, parser):
        data = _write_and_parse(parser, PRETTY_STRING_RECEIVER_SRC)

        category_target = next(
            f for f in data["functions"]
            if f["name"] == "asPrettyString" and f["receiver_type"] == "CategoryId"
        )
        record_target = next(
            f for f in data["functions"]
            if f["name"] == "asPrettyString" and f["receiver_type"] == "RecordDefinitionId"
        )
        full_record_id = next(
            v for v in data["variables"]
            if v["name"] == "fullRecordId"
        )

        fn_to_fn, *_ = build_function_call_groups(
            [data],
            imports_map={
                "CategoryId.asPrettyString": [data["path"]],
                "ViewId.asPrettyString": [data["path"]],
                "RecordDefinitionId.asPrettyString": [data["path"]],
                "asPrettyString": [data["path"]],
            },
        )

        edges = {
            (edge["caller_name"], edge["full_call_name"]): edge
            for edge in fn_to_fn
            if edge["called_name"] == "asPrettyString"
        }
        assert full_record_id["initializer_inferred_type"] == "RecordDefinitionId"
        assert edges[("fromNameOnly", "categoryId.asPrettyString")]["called_line_number"] == category_target["line_number"]
        assert edges[("fromBuilder", "fullRecordId.asPrettyString")]["called_line_number"] == record_target["line_number"]

    def test_ambiguous_overloaded_callable_reference_is_not_over_approximated(self, parser):
        data = _write_and_parse(parser, AMBIGUOUS_CALLABLE_REFERENCE_SRC)

        direct_target = next(
            f for f in data["functions"]
            if f["name"] == "accumulate" and f["arg_types"] == ["A"]
        )
        callable_line = next(
            c["line_number"] for c in data["function_calls"]
            if c["call_kind"] == "callable_reference"
        )

        fn_to_fn, *_ = build_function_call_groups(
            [data],
            imports_map={
                "Accumulator": [data["path"]],
            },
        )

        direct_edges = [
            edge for edge in fn_to_fn
            if edge["full_call_name"] == "accumulator.accumulate"
            and edge["line_number"] != callable_line
        ]
        callable_edges = [
            edge for edge in fn_to_fn
            if edge["full_call_name"] == "accumulator.accumulate"
            and edge["line_number"] == callable_line
        ]
        assert len(direct_edges) == 1
        assert direct_edges[0]["called_line_number"] == direct_target["line_number"]
        assert callable_edges == []

    def test_skipped_callable_reference_emits_resolution_diagnostic(self, parser):
        data = _write_and_parse(parser, AMBIGUOUS_CALLABLE_REFERENCE_SRC)
        diagnostics = []

        build_function_call_groups(
            [data],
            imports_map={"Accumulator": [data["path"]]},
            diagnostics=diagnostics,
        )

        assert any(
            diagnostic["reason"] == "unresolved_overloaded_callable_reference"
            and diagnostic["full_call_name"] == "accumulator.accumulate"
            for diagnostic in diagnostics
        )

    def test_callable_reference_expected_collection_type_selects_overload(self, parser):
        data = _write_and_parse(parser, CALLABLE_REFERENCE_EXPECTED_TYPE_SRC)

        target = next(
            f for f in data["functions"]
            if f["name"] == "accumulate" and f["arg_types"] == ["A"]
        )
        callable_call = next(
            c for c in data["function_calls"]
            if c["call_kind"] == "callable_reference"
        )

        fn_to_fn, *_ = build_function_call_groups(
            [data],
            imports_map={"Accumulator": [data["path"]]},
        )
        callable_edges = [
            edge for edge in fn_to_fn
            if edge["full_call_name"] == "accumulator.accumulate"
            and edge["line_number"] == callable_call["line_number"]
        ]

        assert callable_call["callable_reference_collection_receiver"] == "values"
        assert len(callable_edges) == 1
        assert callable_edges[0]["called_line_number"] == target["line_number"]

    def test_callable_reference_collection_return_type_selects_overload(self, parser):
        data = _write_and_parse(parser, CALLABLE_REFERENCE_COLLECTION_RETURN_SRC)

        target = next(
            f for f in data["functions"]
            if f["name"] == "accumulate" and f["arg_types"] == ["A"]
        )
        values_var = next(v for v in data["variables"] if v["name"] == "values")
        callable_call = next(
            c for c in data["function_calls"]
            if c["call_kind"] == "callable_reference"
        )

        fn_to_fn, *_ = build_function_call_groups(
            [data],
            imports_map={"Accumulator": [data["path"]], "Repository": [data["path"]]},
        )
        callable_edges = [
            edge for edge in fn_to_fn
            if edge["full_call_name"] == "accumulator.accumulate"
            and edge["line_number"] == callable_call["line_number"]
        ]

        assert values_var["initializer_collection_receiver_name"] == "repository"
        assert values_var["initializer_collection_member_name"] == "load"
        assert callable_call["callable_reference_collection_receiver"] == "values"
        assert len(callable_edges) == 1
        assert callable_edges[0]["called_line_number"] == target["line_number"]

    def test_kotlin_trailing_lambda_overload_uses_function_type_hint(self, parser):
        service_data = _write_and_parse(parser, OVERLOADED_SERVICE_SRC)
        caller_data = _write_and_parse(parser, TRAILING_LAMBDA_CALLER_SRC)

        lambda_target = next(
            f for f in service_data["functions"]
            if f["name"] == "target"
            and f["context"] == "LambdaOverloadService"
            and f["arg_types"] == ["(String) -> Boolean"]
        )

        fn_to_fn, *_ = build_function_call_groups(
            [service_data, caller_data],
            imports_map={
                "LambdaOverloadService": [service_data["path"]],
            },
        )

        edge = next(
            e for e in fn_to_fn
            if e["full_call_name"] == "service.target"
        )
        assert edge["called_file_path"] == service_data["path"]
        assert edge["called_context"] == "LambdaOverloadService"
        assert edge["called_line_number"] == lambda_target["line_number"]

    def test_known_external_receiver_does_not_fall_back_to_unrelated_project_method(self, parser):
        data = _write_and_parse(parser, EXTERNAL_RECEIVER_SRC)

        fn_to_fn, *_ = build_function_call_groups(
            [data],
            imports_map={
                "append": [data["path"]],
                "ProjectWriter": [data["path"]],
                "StringBuilder.escape": [data["path"]],
                "com.example.StringBuilder.escape": [data["path"]],
            },
        )

        append_edges = [
            edge
            for edge in fn_to_fn
            if edge["full_call_name"] in {"buffer.append", "append"}
            and edge["called_name"] == "append"
        ]
        escape_edge = next(
            edge for edge in fn_to_fn
            if edge["full_call_name"] == "buffer.escape"
        )

        assert append_edges == []
        assert escape_edge["called_line_number"] == 4

    def test_kotlin_extension_overload_uses_static_receiver_type(self, parser):
        data = _write_and_parse(parser, EXTENSION_OVERLOADS_SRC)

        failure_a_target = next(
            f for f in data["functions"]
            if f["name"] == "asDetails" and f["receiver_type"] == "FailureA"
        )
        failure_b_target = next(
            f for f in data["functions"]
            if f["name"] == "asDetails" and f["receiver_type"] == "FailureB"
        )

        fn_to_fn, *_ = build_function_call_groups(
            [data],
            imports_map={
                "asDetails": [data["path"]],
                "FailureA.asDetails": [data["path"]],
                "FailureB.asDetails": [data["path"]],
                "com.example.FailureA.asDetails": [data["path"]],
                "com.example.FailureB.asDetails": [data["path"]],
            },
        )

        edges = {
            edge["full_call_name"]: edge
            for edge in fn_to_fn
            if edge["called_name"] == "asDetails"
        }
        assert edges["FailureA.BAD.asDetails"]["called_line_number"] == failure_a_target["line_number"]
        assert edges["FailureB.BAD.asDetails"]["called_line_number"] == failure_b_target["line_number"]

    def test_kotlin_extension_overload_uses_property_constant_and_scope_hints(self, parser, tmp_path):
        support_path = _write_source(
            tmp_path,
            "com/example/trace/Tracing.kt",
            TAG_SPAN_SUPPORT_SRC,
        )
        constant_path = _write_source(
            tmp_path,
            "com/example/community/Common.kt",
            TAG_SPAN_CONSTANT_SRC,
        )
        caller_path = _write_source(
            tmp_path,
            "com/example/Caller.kt",
            TAG_SPAN_CALLER_SRC,
        )

        files = [support_path, constant_path, caller_path]
        support_data = parser.parse(support_path)
        all_data = [support_data, parser.parse(constant_path), parser.parse(caller_path)]
        imports_map = pre_scan_kotlin(files, parser.generic_parser_wrapper)

        entity_span_target = next(
            f for f in support_data["functions"]
            if f["name"] == "tagSpan"
            and f["receiver_type"] == "Entity"
            and f["arg_types"] == ["Span"]
        )
        internal_span_builder_target = next(
            f for f in support_data["functions"]
            if f["name"] == "tagSpan"
            and f["receiver_type"] == "InternalEntity"
            and f["arg_types"] == ["SpanBuilder"]
        )
        internal_span_target = next(
            f for f in support_data["functions"]
            if f["name"] == "tagSpan"
            and f["receiver_type"] == "InternalEntity"
            and f["arg_types"] == ["Span"]
        )

        fn_to_fn, *_ = build_function_call_groups(all_data, imports_map)
        edges = {
            (edge["caller_name"], edge["full_call_name"]): edge
            for edge in fn_to_fn
            if edge["called_name"] == "tagSpan"
        }

        assert edges[("generated", "request.entity.tagSpan")]["called_line_number"] == entity_span_target["line_number"]
        assert edges[("constant", "COMMUNITY_ENTITY.tagSpan")]["called_line_number"] == internal_span_target["line_number"]
        assert edges[("member", "eventContext.entity.tagSpan")]["called_line_number"] == internal_span_target["line_number"]
        assert edges[("scoped", "entity.tagSpan")]["called_line_number"] == internal_span_builder_target["line_number"]

    def test_unqualified_class_member_call_uses_enclosing_class_receiver(self, parser):
        data = _write_and_parse(parser, IMPLICIT_CLASS_RECEIVER_SRC)

        local_append = next(
            f for f in data["functions"]
            if f["name"] == "append" and f["context"] == "LocalWriter"
        )

        fn_to_fn, *_ = build_function_call_groups(
            [data],
            imports_map={
                "append": [data["path"]],
                "LocalWriter": [data["path"]],
                "OtherWriter": [data["path"]],
            },
        )

        edge = next(
            edge for edge in fn_to_fn
            if edge["caller_name"] == "accept" and edge["full_call_name"] == "append"
        )
        assert edge["called_context"] == "LocalWriter"
        assert edge["called_line_number"] == local_append["line_number"]

    def test_ambiguous_kotlin_overload_is_skipped_with_diagnostic(self, parser):
        service_data = _write_and_parse(parser, OVERLOADED_SERVICE_SRC)
        caller_data = _write_and_parse(parser, AMBIGUOUS_OVERLOAD_CALLER_SRC)
        diagnostics = []

        fn_to_fn, *_ = build_function_call_groups(
            [service_data, caller_data],
            imports_map={
                "OverloadedService": [service_data["path"]],
                "AmbiguousCache": [service_data["path"]],
            },
            diagnostics=diagnostics,
        )

        assert [
            e for e in fn_to_fn
            if e["full_call_name"] == "cache.get"
        ] == []
        assert any(
            diagnostic["reason"] == "unresolved_overloaded_call"
            and diagnostic["full_call_name"] == "cache.get"
            for diagnostic in diagnostics
        )

    def test_local_variable_receiver_resolves_cross_file(self, parser):
        caller_data = _write_and_parse(parser, RECEIVER_PATTERNS_SRC)
        progress_data = _write_and_parse(parser, PROGRESS_SERVICE_SRC)

        calls = [
            c for c in caller_data["function_calls"]
            if c["full_name"] == "localService.applyEvent"
        ]
        assert calls, "Expected localService.applyEvent call"
        assert calls[0]["inferred_obj_type"] == "ProgressService"

        resolved = _resolve_with_progress_service(calls[0], caller_data, progress_data)
        assert resolved["type"] == "function"
        assert resolved["caller_name"] == "run"
        assert resolved["called_file_path"] == progress_data["path"]

    def test_body_property_receiver_resolves_cross_file(self, parser):
        caller_data = _write_and_parse(parser, RECEIVER_PATTERNS_SRC)
        progress_data = _write_and_parse(parser, PROGRESS_SERVICE_SRC)

        calls = [
            c for c in caller_data["function_calls"]
            if c["full_name"] == "bodyService.applyEvent"
        ]
        assert calls, "Expected bodyService.applyEvent call"
        assert calls[0]["inferred_obj_type"] == "ProgressService"

        resolved = _resolve_with_progress_service(calls[0], caller_data, progress_data)
        assert resolved["type"] == "function"
        assert resolved["caller_name"] == "run"
        assert resolved["called_file_path"] == progress_data["path"]

    def test_class_property_receiver_survives_local_shadow_in_other_method(self, parser, tmp_path):
        source_path = _write_source(
            tmp_path,
            "com/example/PropertyShadow.kt",
            """
            package com.example

            class Caller(private val svc: Service) {
                fun run() {
                    svc.doIt()
                }

                fun other() {
                    val svc: Other = Other()
                }
            }

            class Service {
                fun doIt(): String {
                    return "service"
                }
            }

            class Other {
                fun doIt(): String {
                    return "other"
                }
            }
            """,
        )
        data = parser.parse(source_path)
        imports_map = pre_scan_kotlin([source_path], parser.generic_parser_wrapper)
        service_do_it = next(
            f for f in data["functions"]
            if f["name"] == "doIt" and f["context"] == "Service"
        )
        svc_call = next(
            c for c in data["function_calls"]
            if c["full_name"] == "svc.doIt"
        )

        fn_to_fn, *_ = build_function_call_groups([data], imports_map)
        edge = next(
            edge for edge in fn_to_fn
            if edge["caller_name"] == "run" and edge["full_call_name"] == "svc.doIt"
        )

        assert svc_call["inferred_obj_type"] == "Service"
        assert edge["called_context"] == "Service"
        assert edge["called_line_number"] == service_do_it["line_number"]

    def test_inherited_property_receiver_survives_local_shadow_in_other_method(self, parser, tmp_path):
        source_path = _write_source(
            tmp_path,
            "com/example/InheritedPropertyShadow.kt",
            """
            package com.example

            open class Base(protected val svc: Service)

            class Caller(svc: Service) : Base(svc) {
                fun run() {
                    svc.doIt()
                }

                fun other() {
                    val svc: Other = Other()
                }
            }

            class Service {
                fun doIt(): String {
                    return "service"
                }
            }

            class Other {
                fun doIt(): String {
                    return "other"
                }
            }
            """,
        )
        data = parser.parse(source_path)
        imports_map = pre_scan_kotlin([source_path], parser.generic_parser_wrapper)
        service_do_it = next(
            f for f in data["functions"]
            if f["name"] == "doIt" and f["context"] == "Service"
        )

        fn_to_fn, *_ = build_function_call_groups([data], imports_map)
        edge = next(
            edge for edge in fn_to_fn
            if edge["caller_name"] == "run" and edge["full_call_name"] == "svc.doIt"
        )

        assert edge["called_context"] == "Service"
        assert edge["called_line_number"] == service_do_it["line_number"]

    def test_same_method_local_shadow_blocks_class_property_receiver_fallback(self, parser, tmp_path):
        source_path = _write_source(
            tmp_path,
            "com/example/PropertyShadowLocal.kt",
            """
            package com.example

            class Caller(
                private val svc: Service,
                private val holder: Holder
            ) {
                fun run() {
                    val svc = holder.other
                    svc.doIt()
                }
            }

            class Holder(val other: Other)

            class Service {
                fun doIt(): String {
                    return "service"
                }
            }

            class Other {
                fun doIt(): String {
                    return "other"
                }
            }
            """,
        )
        data = parser.parse(source_path)
        imports_map = pre_scan_kotlin([source_path], parser.generic_parser_wrapper)
        other_do_it = next(
            f for f in data["functions"]
            if f["name"] == "doIt" and f["context"] == "Other"
        )
        svc_call = next(
            c for c in data["function_calls"]
            if c["full_name"] == "svc.doIt"
        )

        fn_to_fn, *_ = build_function_call_groups([data], imports_map)
        edge = next(
            edge for edge in fn_to_fn
            if edge["caller_name"] == "run" and edge["full_call_name"] == "svc.doIt"
        )

        assert svc_call["inferred_obj_type"] != "Service"
        assert edge["called_context"] == "Other"
        assert edge["called_line_number"] == other_do_it["line_number"]

    def test_local_receiver_inferred_from_companion_factory(self, parser, tmp_path):
        source_path = _write_source(
            tmp_path,
            "com/example/CompanionFactory.kt",
            """
            package com.example

            class Caller {
                fun run() {
                    val service = ServiceFactory.create()
                    service.doIt()
                }
            }

            class ServiceFactory {
                companion object {
                    fun create(): Service {
                        return Service()
                    }
                }
            }

            class Service {
                fun doIt(): String {
                    return "service"
                }
            }

            class Other {
                fun doIt(): String {
                    return "other"
                }
            }
            """,
        )
        data = parser.parse(source_path)
        imports_map = pre_scan_kotlin([source_path], parser.generic_parser_wrapper)
        service_do_it = next(
            f for f in data["functions"]
            if f["name"] == "doIt" and f["context"] == "Service"
        )

        fn_to_fn, *_ = build_function_call_groups([data], imports_map)
        edge = next(
            edge for edge in fn_to_fn
            if edge["caller_name"] == "run" and edge["full_call_name"] == "service.doIt"
        )

        assert edge["called_context"] == "Service"
        assert edge["called_line_number"] == service_do_it["line_number"]

    def test_local_receiver_inferred_from_named_companion_factory(self, parser, tmp_path):
        source_path = _write_source(
            tmp_path,
            "com/example/NamedCompanionFactory.kt",
            """
            package com.example

            class Caller {
                fun run() {
                    val service = ServiceFactory.create()
                    service.doIt()
                }
            }

            class ServiceFactory {
                companion object Factory {
                    fun create(): Service {
                        return Service()
                    }
                }
            }

            class Service {
                fun doIt(): String {
                    return "service"
                }
            }

            class Other {
                fun doIt(): String {
                    return "other"
                }
            }
            """,
        )
        data = parser.parse(source_path)
        imports_map = pre_scan_kotlin([source_path], parser.generic_parser_wrapper)
        service_do_it = next(
            f for f in data["functions"]
            if f["name"] == "doIt" and f["context"] == "Service"
        )

        fn_to_fn, *_ = build_function_call_groups([data], imports_map)
        edge = next(
            edge for edge in fn_to_fn
            if edge["caller_name"] == "run" and edge["full_call_name"] == "service.doIt"
        )

        assert edge["called_context"] == "Service"
        assert edge["called_line_number"] == service_do_it["line_number"]

    def test_later_local_declaration_does_not_shadow_earlier_property_call(self, parser, tmp_path):
        source_path = _write_source(
            tmp_path,
            "com/example/PropertyShadowOrder.kt",
            """
            package com.example

            class Caller(private val svc: Service) {
                fun run() {
                    svc.doIt()
                    val svc: Other = Other()
                    svc.doIt()
                }
            }

            class Service {
                fun doIt(): String {
                    return "service"
                }
            }

            class Other {
                fun doIt(): String {
                    return "other"
                }
            }
            """,
        )
        data = parser.parse(source_path)
        imports_map = pre_scan_kotlin([source_path], parser.generic_parser_wrapper)
        targets = {
            f["context"]: f
            for f in data["functions"]
            if f["name"] == "doIt"
        }
        svc_calls = sorted(
            (
                c for c in data["function_calls"]
                if c["full_name"] == "svc.doIt"
            ),
            key=lambda call: call["line_number"],
        )

        fn_to_fn, *_ = build_function_call_groups([data], imports_map)
        edges = sorted(
            (
                edge for edge in fn_to_fn
                if edge["caller_name"] == "run" and edge["full_call_name"] == "svc.doIt"
            ),
            key=lambda edge: edge["line_number"],
        )

        assert [call["inferred_obj_type"] for call in svc_calls] == ["Service", "Other"]
        assert [edge["called_context"] for edge in edges] == ["Service", "Other"]
        assert [edge["called_line_number"] for edge in edges] == [
            targets["Service"]["line_number"],
            targets["Other"]["line_number"],
        ]

    def test_generic_receiver_type_is_normalized(self, parser):
        caller_data = _write_and_parse(parser, RECEIVER_PATTERNS_SRC)

        variables = [
            v for v in caller_data["variables"] if v["name"] == "genericServices"
        ]
        assert variables, "Expected genericServices constructor property"
        assert variables[0]["type"] == "List<ProgressService>"

        calls = [
            c for c in caller_data["function_calls"]
            if c["full_name"] == "genericServices.first"
        ]
        assert calls, "Expected genericServices.first call"
        assert calls[0]["inferred_obj_type"] == "List"

    def test_safe_call_receiver_resolves_cross_file(self, parser):
        caller_data = _write_and_parse(parser, RECEIVER_PATTERNS_SRC)
        progress_data = _write_and_parse(parser, PROGRESS_SERVICE_SRC)

        for full_name in (
            "optionalService.applyEvent",
            "optionalBodyService.applyEvent",
        ):
            calls = [
                c for c in caller_data["function_calls"]
                if c["full_name"] == full_name
            ]
            assert calls, f"Expected {full_name} safe call"
            assert calls[0]["inferred_obj_type"] == "ProgressService"

            resolved = _resolve_with_progress_service(calls[0], caller_data, progress_data)
            assert resolved["type"] == "function"
            assert resolved["caller_name"] == "run"
            assert resolved["called_file_path"] == progress_data["path"]


class TestKotlinSemanticResolution:
    def test_parameter_receiver_resolves_cross_file(self, parser):
        caller_data = _write_and_parse(
            parser,
            """
            package com.example

            class ParameterCaller {
                fun run(paramService: ProgressService): String {
                    return paramService.applyEvent("param")
                }
            }
            """,
        )
        progress_data = _write_and_parse(parser, PROGRESS_SERVICE_SRC)

        calls = [
            c for c in caller_data["function_calls"]
            if c["full_name"] == "paramService.applyEvent"
        ]
        assert calls, "Expected paramService.applyEvent call"
        assert calls[0]["inferred_obj_type"] == "ProgressService"

        resolved = _resolve_with_progress_service(calls[0], caller_data, progress_data)
        assert resolved["type"] == "function"
        assert resolved["caller_name"] == "run"
        assert resolved["called_file_path"] == progress_data["path"]

    def test_imported_top_level_function_resolves_cross_file(self, parser, tmp_path):
        helper_path = _write_source(
            tmp_path,
            "com/example/util/Helpers.kt",
            """
            package com.example.util

            fun topLevelHelper(input: String): String {
                return input
            }
            """,
        )
        caller_path = _write_source(
            tmp_path,
            "com/example/Caller.kt",
            """
            package com.example

            import com.example.util.topLevelHelper

            class Caller {
                fun run(): String {
                    return topLevelHelper("value")
                }
            }
            """,
        )

        caller_data = parser.parse(caller_path)
        imports_map = pre_scan_kotlin([helper_path, caller_path], parser.generic_parser_wrapper)
        local_imports = {
            imp.get("alias") or imp["name"].split(".")[-1]: imp["name"]
            for imp in caller_data.get("imports", [])
        }
        calls = [
            c for c in caller_data["function_calls"]
            if c["name"] == "topLevelHelper"
        ]
        assert calls, "Expected topLevelHelper call"
        assert "topLevelHelper" in imports_map
        assert "com.example.util.topLevelHelper" in imports_map

        resolved = resolve_function_call(
            calls[0],
            caller_file_path=caller_data["path"],
            local_names=_local_names(caller_data),
            local_imports=local_imports,
            imports_map=imports_map,
            skip_external=False,
        )

        assert resolved is not None
        assert resolved["type"] == "function"
        assert resolved["caller_name"] == "run"
        assert resolved["called_name"] == "topLevelHelper"
        assert resolved["called_file_path"] == str(helper_path)

    def test_object_and_companion_calls_resolve_cross_file(self, parser, tmp_path):
        service_path = _write_source(
            tmp_path,
            "com/example/UserService.kt",
            """
            package com.example

            object UserService {
                fun findUser(id: String): String {
                    return id
                }
            }
            """,
        )
        logger_path = _write_source(
            tmp_path,
            "com/example/Logger.kt",
            """
            package com.example

            class Logger {
                companion object {
                    fun info(message: String): String {
                        return message
                    }
                }
            }
            """,
        )
        caller_path = _write_source(
            tmp_path,
            "com/example/Caller.kt",
            """
            package com.example

            class Caller {
                fun run(): String {
                    UserService.findUser("42")
                    return Logger.info("hello")
                }
            }
            """,
        )

        caller_data = parser.parse(caller_path)
        imports_map = pre_scan_kotlin(
            [service_path, logger_path, caller_path],
            parser.generic_parser_wrapper,
        )

        calls_by_name = {
            c["name"]: c for c in caller_data["function_calls"]
            if c["name"] in {"findUser", "info"}
        }
        assert set(calls_by_name) == {"findUser", "info"}

        find_user = resolve_function_call(
            calls_by_name["findUser"],
            caller_file_path=caller_data["path"],
            local_names=_local_names(caller_data),
            local_imports={},
            imports_map=imports_map,
            skip_external=False,
        )
        assert find_user is not None
        assert find_user["type"] == "function"
        assert find_user["called_file_path"] == str(service_path)

        info = resolve_function_call(
            calls_by_name["info"],
            caller_file_path=caller_data["path"],
            local_names=_local_names(caller_data),
            local_imports={},
            imports_map=imports_map,
            skip_external=False,
        )
        assert info is not None
        assert info["type"] == "function"
        assert info["called_file_path"] == str(logger_path)

    def test_imported_extension_function_resolves_cross_file(self, parser, tmp_path):
        event_path = _write_source(
            tmp_path,
            "com/example/ProgressEvent.kt",
            """
            package com.example

            class ProgressEvent(val id: String)
            """,
        )
        extension_path = _write_source(
            tmp_path,
            "com/example/ext/ProgressEventExtensions.kt",
            """
            package com.example.ext

            import com.example.ProgressEvent

            fun ProgressEvent.enrich(): String {
                return id
            }
            """,
        )
        caller_path = _write_source(
            tmp_path,
            "com/example/Caller.kt",
            """
            package com.example

            import com.example.ext.enrich

            class Caller {
                fun run(event: ProgressEvent): String {
                    return event.enrich()
                }
            }
            """,
        )

        caller_data = parser.parse(caller_path)
        imports_map = pre_scan_kotlin(
            [event_path, extension_path, caller_path],
            parser.generic_parser_wrapper,
        )
        local_imports = {
            imp.get("alias") or imp["name"].split(".")[-1]: imp["name"]
            for imp in caller_data.get("imports", [])
        }
        calls = [
            c for c in caller_data["function_calls"]
            if c["full_name"] == "event.enrich"
        ]
        assert calls, "Expected event.enrich extension call"
        assert calls[0]["inferred_obj_type"] == "ProgressEvent"
        assert calls[0]["extension_receiver_type"] == "ProgressEvent"
        assert "ProgressEvent.enrich" in imports_map
        assert "com.example.ext.enrich" in imports_map

        resolved = resolve_function_call(
            calls[0],
            caller_file_path=caller_data["path"],
            local_names=_local_names(caller_data),
            local_imports=local_imports,
            imports_map=imports_map,
            skip_external=False,
        )

        assert resolved is not None
        assert resolved["type"] == "function"
        assert resolved["caller_name"] == "run"
        assert resolved["called_name"] == "enrich"
        assert resolved["called_file_path"] == str(extension_path)

    def test_same_package_top_level_function_resolves_without_import(self, parser, tmp_path):
        helper_path = _write_source(
            tmp_path,
            "com/example/Helpers.kt",
            """
            package com.example

            fun samePackageHelper(input: String): String {
                return input
            }
            """,
        )
        caller_path = _write_source(
            tmp_path,
            "com/example/Caller.kt",
            """
            package com.example

            class Caller {
                fun run(): String {
                    return samePackageHelper("value")
                }
            }
            """,
        )

        caller_data = parser.parse(caller_path)
        imports_map = pre_scan_kotlin([helper_path, caller_path], parser.generic_parser_wrapper)
        calls = [
            c for c in caller_data["function_calls"]
            if c["name"] == "samePackageHelper"
        ]
        assert calls, "Expected samePackageHelper call"
        assert calls[0]["package"] == "com.example"
        assert "com.example.samePackageHelper" in imports_map

        resolved = resolve_function_call(
            calls[0],
            caller_file_path=caller_data["path"],
            local_names=_local_names(caller_data),
            local_imports={},
            imports_map=imports_map,
            skip_external=False,
        )

        assert resolved is not None
        assert resolved["type"] == "function"
        assert resolved["called_name"] == "samePackageHelper"
        assert resolved["called_file_path"] == str(helper_path)

    def test_same_package_extension_function_resolves_without_import(self, parser, tmp_path):
        event_path = _write_source(
            tmp_path,
            "com/example/ProgressEvent.kt",
            """
            package com.example

            class ProgressEvent(val id: String)
            """,
        )
        extension_path = _write_source(
            tmp_path,
            "com/example/ProgressEventExtensions.kt",
            """
            package com.example

            fun ProgressEvent.decorate(): String {
                return id
            }
            """,
        )
        caller_path = _write_source(
            tmp_path,
            "com/example/Caller.kt",
            """
            package com.example

            class Caller {
                fun run(event: ProgressEvent): String {
                    return event.decorate()
                }
            }
            """,
        )

        caller_data = parser.parse(caller_path)
        imports_map = pre_scan_kotlin(
            [event_path, extension_path, caller_path],
            parser.generic_parser_wrapper,
        )
        calls = [
            c for c in caller_data["function_calls"]
            if c["full_name"] == "event.decorate"
        ]
        assert calls, "Expected event.decorate extension call"
        assert calls[0]["package"] == "com.example"
        assert calls[0]["extension_receiver_type"] == "ProgressEvent"
        assert "com.example.ProgressEvent.decorate" in imports_map

        resolved = resolve_function_call(
            calls[0],
            caller_file_path=caller_data["path"],
            local_names=_local_names(caller_data),
            local_imports={},
            imports_map=imports_map,
            skip_external=False,
        )

        assert resolved is not None
        assert resolved["type"] == "function"
        assert resolved["called_name"] == "decorate"
        assert resolved["called_file_path"] == str(extension_path)

    def test_import_aliases_resolve_top_level_and_extension_functions(self, parser, tmp_path):
        event_path = _write_source(
            tmp_path,
            "com/example/ProgressEvent.kt",
            """
            package com.example

            class ProgressEvent(val id: String)
            """,
        )
        helper_path = _write_source(
            tmp_path,
            "com/example/util/AliasedHelpers.kt",
            """
            package com.example.util

            fun aliasedHelper(input: String): String {
                return input
            }
            """,
        )
        extension_path = _write_source(
            tmp_path,
            "com/example/ext/ProgressEventExtensions.kt",
            """
            package com.example.ext

            import com.example.ProgressEvent

            fun ProgressEvent.enrich(): String {
                return id
            }
            """,
        )
        caller_path = _write_source(
            tmp_path,
            "com/example/Caller.kt",
            """
            package com.example

            import com.example.util.aliasedHelper as helperAlias
            import com.example.ext.enrich as addContext

            class Caller {
                fun run(event: ProgressEvent): String {
                    helperAlias("value")
                    return event.addContext()
                }
            }
            """,
        )

        caller_data = parser.parse(caller_path)
        imports_map = pre_scan_kotlin(
            [event_path, helper_path, extension_path, caller_path],
            parser.generic_parser_wrapper,
        )
        local_imports = {
            imp.get("alias") or imp["name"].split(".")[-1]: imp["name"]
            for imp in caller_data.get("imports", [])
        }

        helper_call = next(
            c for c in caller_data["function_calls"] if c["name"] == "helperAlias"
        )
        helper_resolved = resolve_function_call(
            helper_call,
            caller_file_path=caller_data["path"],
            local_names=_local_names(caller_data),
            local_imports=local_imports,
            imports_map=imports_map,
            skip_external=False,
        )
        assert helper_resolved is not None
        assert helper_resolved["type"] == "function"
        assert helper_resolved["called_name"] == "aliasedHelper"
        assert helper_resolved["called_file_path"] == str(helper_path)

        extension_call = next(
            c for c in caller_data["function_calls"] if c["full_name"] == "event.addContext"
        )
        extension_resolved = resolve_function_call(
            extension_call,
            caller_file_path=caller_data["path"],
            local_names=_local_names(caller_data),
            local_imports=local_imports,
            imports_map=imports_map,
            skip_external=False,
        )
        assert extension_resolved is not None
        assert extension_resolved["type"] == "function"
        assert extension_resolved["called_name"] == "enrich"
        assert extension_resolved["called_file_path"] == str(extension_path)

    def test_this_and_super_calls_resolve_to_current_and_base_files(self, parser, tmp_path):
        base_path = _write_source(
            tmp_path,
            "com/example/BaseService.kt",
            """
            package com.example

            open class BaseService {
                open fun applyEvent(event: String): String {
                    return event
                }
            }
            """,
        )
        derived_path = _write_source(
            tmp_path,
            "com/example/DerivedService.kt",
            """
            package com.example

            class DerivedService : BaseService() {
                override fun applyEvent(event: String): String {
                    this.applyEventLocally(event)
                    return super.applyEvent(event)
                }

                fun applyEventLocally(event: String): String {
                    return event
                }
            }
            """,
        )

        derived_data = parser.parse(derived_path)
        imports_map = pre_scan_kotlin([base_path, derived_path], parser.generic_parser_wrapper)
        local_class_bases = {
            c["name"]: c.get("bases", []) for c in derived_data.get("classes", [])
        }

        calls = {
            c["full_name"]: c for c in derived_data["function_calls"]
            if c["full_name"] in {"this.applyEventLocally", "super.applyEvent"}
        }
        assert set(calls) == {"this.applyEventLocally", "super.applyEvent"}

        this_resolved = resolve_function_call(
            calls["this.applyEventLocally"],
            caller_file_path=derived_data["path"],
            local_names=_local_names(derived_data),
            local_imports={},
            imports_map=imports_map,
            skip_external=False,
            local_class_bases=local_class_bases,
        )
        assert this_resolved is not None
        assert this_resolved["type"] == "function"
        assert this_resolved["called_name"] == "applyEventLocally"
        assert this_resolved["called_file_path"] == str(derived_path)

        super_resolved = resolve_function_call(
            calls["super.applyEvent"],
            caller_file_path=derived_data["path"],
            local_names=_local_names(derived_data),
            local_imports={},
            imports_map=imports_map,
            skip_external=False,
            local_class_bases=local_class_bases,
        )
        assert super_resolved is not None
        assert super_resolved["type"] == "function"
        assert super_resolved["called_name"] == "applyEvent"
        assert super_resolved["called_file_path"] == str(base_path)

    def test_class_constructor_delegation_resolves_to_base_class(self, parser, tmp_path):
        base_path = _write_source(
            tmp_path,
            "com/example/BaseService.kt",
            """
            package com.example

            open class BaseService
            """,
        )
        derived_path = _write_source(
            tmp_path,
            "com/example/DerivedService.kt",
            """
            package com.example

            class DerivedService() : BaseService()
            """,
        )

        derived_data = parser.parse(derived_path)
        imports_map = pre_scan_kotlin([base_path, derived_path], parser.generic_parser_wrapper)
        calls = [
            c for c in derived_data["function_calls"]
            if c["name"] == "BaseService"
        ]
        assert calls, "Expected BaseService constructor delegation call"

        resolved = resolve_function_call(
            calls[0],
            caller_file_path=derived_data["path"],
            local_names=_local_names(derived_data),
            local_imports={},
            imports_map=imports_map,
            skip_external=False,
        )

        assert resolved is not None
        assert resolved["type"] == "function"
        assert resolved["caller_name"] == "DerivedService"
        assert resolved["called_name"] == "BaseService"
        assert resolved["called_file_path"] == str(base_path)

    def test_cross_file_chained_return_and_property_receivers_resolve(self, parser, tmp_path):
        progress_path = _write_source(
            tmp_path,
            "com/example/ProgressService.kt",
            """
            package com.example

            class ProgressService {
                fun applyEvent(event: String): String {
                    return event
                }
            }
            """,
        )
        provider_path = _write_source(
            tmp_path,
            "com/example/Provider.kt",
            """
            package com.example

            class Provider {
                val progressService: ProgressService = ProgressService()

                fun service(): ProgressService {
                    return ProgressService()
                }
            }
            """,
        )
        caller_path = _write_source(
            tmp_path,
            "com/example/Caller.kt",
            """
            package com.example

            class Caller {
                fun run(provider: Provider): String {
                    provider.service().applyEvent("chain")
                    provider.progressService.applyEvent("property")
                    return "done"
                }
            }
            """,
        )

        progress_data = parser.parse(progress_path)
        provider_data = parser.parse(provider_path)
        caller_data = parser.parse(caller_path)
        imports_map = pre_scan_kotlin(
            [progress_path, provider_path, caller_path],
            parser.generic_parser_wrapper,
        )
        member_return_types = {
            (f.get("context"), f["name"]): f["return_type"]
            for data in (progress_data, provider_data, caller_data)
            for f in data.get("functions", [])
            if f.get("return_type")
        }
        member_property_types = {
            (v.get("context"), v["name"]): v["type"]
            for data in (progress_data, provider_data, caller_data)
            for v in data.get("variables", [])
            if v.get("type")
        }

        calls = {
            c["full_name"]: c for c in caller_data["function_calls"]
            if c["full_name"] in {
                "provider.service().applyEvent",
                "provider.progressService.applyEvent",
            }
        }
        assert set(calls) == {
            "provider.service().applyEvent",
            "provider.progressService.applyEvent",
        }
        assert calls["provider.service().applyEvent"]["receiver_base_type"] == "Provider"
        assert calls["provider.service().applyEvent"]["receiver_member_name"] == "service"
        assert calls["provider.service().applyEvent"]["receiver_member_kind"] == "function"
        assert calls["provider.progressService.applyEvent"]["receiver_base_type"] == "Provider"
        assert calls["provider.progressService.applyEvent"]["receiver_member_name"] == "progressService"
        assert calls["provider.progressService.applyEvent"]["receiver_member_kind"] == "property"

        for call in calls.values():
            resolved = resolve_function_call(
                call,
                caller_file_path=caller_data["path"],
                local_names=_local_names(caller_data),
                local_imports={},
                imports_map=imports_map,
                skip_external=False,
                member_return_types=member_return_types,
                member_property_types=member_property_types,
            )

            assert resolved is not None
            assert resolved["type"] == "function"
            assert resolved["called_name"] == "applyEvent"
            assert resolved["called_file_path"] == str(progress_path)

        fn_to_fn, *_ = build_function_call_groups(
            [progress_data, provider_data, caller_data],
            imports_map,
        )
        resolved_edges = {
            (edge["full_call_name"], edge["called_file_path"])
            for edge in fn_to_fn
        }
        assert ("provider.service().applyEvent", str(progress_path)) in resolved_edges
        assert ("provider.progressService.applyEvent", str(progress_path)) in resolved_edges

    def test_wildcard_imports_resolve_top_level_and_extension_functions(self, parser, tmp_path):
        event_path = _write_source(
            tmp_path,
            "com/example/ProgressEvent.kt",
            """
            package com.example

            class ProgressEvent(val id: String)
            """,
        )
        helper_path = _write_source(
            tmp_path,
            "com/example/util/WildcardHelpers.kt",
            """
            package com.example.util

            import com.example.ProgressEvent

            fun wildcardHelper(input: String): String {
                return input
            }

            fun ProgressEvent.wildcardEnrich(): String {
                return id
            }
            """,
        )
        other_helper_path = _write_source(
            tmp_path,
            "com/example/other/WildcardHelpers.kt",
            """
            package com.example.other

            import com.example.ProgressEvent

            fun wildcardHelper(input: String): String {
                return "wrong"
            }

            fun ProgressEvent.wildcardEnrich(): String {
                return "wrong"
            }
            """,
        )
        caller_path = _write_source(
            tmp_path,
            "com/example/Caller.kt",
            """
            package com.example

            import com.example.util.*

            class Caller {
                fun run(event: ProgressEvent): String {
                    wildcardHelper("value")
                    return event.wildcardEnrich()
                }
            }
            """,
        )

        caller_data = parser.parse(caller_path)
        imports_map = pre_scan_kotlin(
            [event_path, other_helper_path, helper_path, caller_path],
            parser.generic_parser_wrapper,
        )
        local_imports = _local_imports(caller_data)
        assert local_imports["__wildcards__"] == ["com.example.util"]

        helper_call = next(
            c for c in caller_data["function_calls"] if c["name"] == "wildcardHelper"
        )
        helper_resolved = resolve_function_call(
            helper_call,
            caller_file_path=caller_data["path"],
            local_names=_local_names(caller_data),
            local_imports=local_imports,
            imports_map=imports_map,
            skip_external=False,
        )
        assert helper_resolved is not None
        assert helper_resolved["called_file_path"] == str(helper_path)

        extension_call = next(
            c for c in caller_data["function_calls"] if c["full_name"] == "event.wildcardEnrich"
        )
        extension_resolved = resolve_function_call(
            extension_call,
            caller_file_path=caller_data["path"],
            local_names=_local_names(caller_data),
            local_imports=local_imports,
            imports_map=imports_map,
            skip_external=False,
        )
        assert extension_resolved is not None
        assert extension_resolved["called_file_path"] == str(helper_path)

    def test_imported_typealias_receiver_resolves_to_target_type(self, parser, tmp_path):
        progress_path = _write_source(
            tmp_path,
            "com/example/ProgressService.kt",
            """
            package com.example

            class ProgressService {
                fun applyEvent(event: String): String {
                    return event
                }
            }
            """,
        )
        alias_path = _write_source(
            tmp_path,
            "com/example/types/Aliases.kt",
            """
            package com.example.types

            typealias ProgressAlias = com.example.ProgressService
            """,
        )
        caller_path = _write_source(
            tmp_path,
            "com/example/Caller.kt",
            """
            package com.example

            import com.example.types.ProgressAlias

            class Caller {
                fun run(service: ProgressAlias): String {
                    return service.applyEvent("alias")
                }
            }
            """,
        )

        progress_data = parser.parse(progress_path)
        alias_data = parser.parse(alias_path)
        caller_data = parser.parse(caller_path)
        assert alias_data["typealiases"] == [
            {
                "name": "ProgressAlias",
                "target": "com.example.ProgressService",
                "line_number": 4,
                "path": str(alias_path),
                "package": "com.example.types",
                "lang": "kotlin",
            }
        ]

        imports_map = pre_scan_kotlin(
            [progress_path, alias_path, caller_path],
            parser.generic_parser_wrapper,
        )
        fn_to_fn, *_ = build_function_call_groups(
            [progress_data, alias_data, caller_data],
            imports_map,
        )

        assert any(
            edge["caller_name"] == "run"
            and edge["called_name"] == "applyEvent"
            and edge["called_file_path"] == str(progress_path)
            for edge in fn_to_fn
        )

    def test_scope_functions_infer_receiver_for_common_kotlin_forms(self, parser, tmp_path):
        progress_path = _write_source(
            tmp_path,
            "com/example/ProgressService.kt",
            """
            package com.example

            class ProgressService {
                fun applyEvent(event: String): String {
                    return event
                }
            }
            """,
        )
        caller_path = _write_source(
            tmp_path,
            "com/example/Caller.kt",
            """
            package com.example

            class Caller {
                fun run(service: ProgressService): String {
                    service.apply { applyEvent("apply") }
                    service.run { applyEvent("run") }
                    service.let { it.applyEvent("let") }
                    service.also { it.applyEvent("also") }
                    service.let { current -> current.applyEvent("named") }
                    with(service) { applyEvent("with") }
                    return "done"
                }
            }
            """,
        )

        progress_data = parser.parse(progress_path)
        caller_data = parser.parse(caller_path)
        imports_map = pre_scan_kotlin(
            [progress_path, caller_path],
            parser.generic_parser_wrapper,
        )

        parsed_apply_event_calls = [
            c for c in caller_data["function_calls"] if c["name"] == "applyEvent"
        ]
        assert len(parsed_apply_event_calls) == 6
        assert all(
            call["inferred_obj_type"] == "ProgressService"
            for call in parsed_apply_event_calls
        )

        fn_to_fn, *_ = build_function_call_groups(
            [progress_data, caller_data],
            imports_map,
        )
        resolved_lines = {
            edge["line_number"]
            for edge in fn_to_fn
            if edge["caller_name"] == "run"
            and edge["called_name"] == "applyEvent"
            and edge["called_file_path"] == str(progress_path)
        }
        assert resolved_lines == {6, 7, 8, 9, 10, 11}

    def test_callable_references_resolve_instance_and_type_receivers(self, parser, tmp_path):
        progress_path = _write_source(
            tmp_path,
            "com/example/ProgressService.kt",
            """
            package com.example

            class ProgressService {
                fun applyEvent(event: String): String {
                    return event
                }
            }
            """,
        )
        caller_path = _write_source(
            tmp_path,
            "com/example/Caller.kt",
            """
            package com.example

            class Caller {
                fun run(service: ProgressService): String {
                    val instanceRef = service::applyEvent
                    val typeRef = ProgressService::applyEvent
                    return "done"
                }
            }
            """,
        )

        progress_data = parser.parse(progress_path)
        caller_data = parser.parse(caller_path)
        imports_map = pre_scan_kotlin(
            [progress_path, caller_path],
            parser.generic_parser_wrapper,
        )

        callable_refs = [
            c for c in caller_data["function_calls"]
            if c["call_kind"] == "callable_reference"
        ]
        assert {c["full_name"] for c in callable_refs} == {
            "service.applyEvent",
            "ProgressService.applyEvent",
        }
        instance_ref = next(c for c in callable_refs if c["base_obj"] == "service")
        assert instance_ref["inferred_obj_type"] == "ProgressService"

        fn_to_fn, *_ = build_function_call_groups(
            [progress_data, caller_data],
            imports_map,
        )
        resolved_refs = [
            edge for edge in fn_to_fn
            if edge["caller_name"] == "run"
            and edge["called_name"] == "applyEvent"
            and edge["called_file_path"] == str(progress_path)
        ]
        assert len(resolved_refs) == 2

    def test_cast_and_non_null_receivers_resolve_to_target_type(self, parser, tmp_path):
        progress_path = _write_source(
            tmp_path,
            "com/example/ProgressService.kt",
            """
            package com.example

            class ProgressService {
                fun applyEvent(event: String): String {
                    return event
                }
            }
            """,
        )
        caller_path = _write_source(
            tmp_path,
            "com/example/Caller.kt",
            """
            package com.example

            class Caller {
                fun run(service: Any?, nullableService: ProgressService?): String {
                    (service as ProgressService).applyEvent("cast")
                    nullableService!!.applyEvent("nonnull")
                    return "done"
                }
            }
            """,
        )

        progress_data = parser.parse(progress_path)
        caller_data = parser.parse(caller_path)
        imports_map = pre_scan_kotlin(
            [progress_path, caller_path],
            parser.generic_parser_wrapper,
        )

        apply_event_calls = [
            c for c in caller_data["function_calls"] if c["name"] == "applyEvent"
        ]
        assert len(apply_event_calls) == 2
        assert all(
            c["inferred_obj_type"] == "ProgressService"
            for c in apply_event_calls
        )

        fn_to_fn, *_ = build_function_call_groups(
            [progress_data, caller_data],
            imports_map,
        )
        resolved_lines = {
            edge["line_number"]
            for edge in fn_to_fn
            if edge["caller_name"] == "run"
            and edge["called_name"] == "applyEvent"
            and edge["called_file_path"] == str(progress_path)
        }
        assert resolved_lines == {6, 7}

    def test_generic_factory_and_assignment_flow_infer_receivers(self, parser, tmp_path):
        progress_path = _write_source(
            tmp_path,
            "com/example/ProgressService.kt",
            """
            package com.example

            class ProgressService {
                fun applyEvent(event: String): String {
                    return event
                }
            }
            """,
        )
        provider_path = _write_source(
            tmp_path,
            "com/example/Provider.kt",
            """
            package com.example

            class Provider {
                fun service(): ProgressService {
                    return ProgressService()
                }

                fun <T> get(): T {
                    TODO()
                }
            }
            """,
        )
        caller_path = _write_source(
            tmp_path,
            "com/example/Caller.kt",
            """
            package com.example

            class Caller {
                fun run(provider: Provider): String {
                    provider.get<ProgressService>().applyEvent("generic")
                    val assignedService = provider.service()
                    assignedService.applyEvent("assigned")
                    return "done"
                }
            }
            """,
        )

        progress_data = parser.parse(progress_path)
        provider_data = parser.parse(provider_path)
        caller_data = parser.parse(caller_path)
        imports_map = pre_scan_kotlin(
            [progress_path, provider_path, caller_path],
            parser.generic_parser_wrapper,
        )

        generic_call = next(
            c for c in caller_data["function_calls"]
            if c["full_name"] == "provider.get<ProgressService>().applyEvent"
        )
        assert generic_call["inferred_obj_type"] == "ProgressService"

        assigned_variable = next(
            v for v in caller_data["variables"]
            if v["name"] == "assignedService"
        )
        assert assigned_variable["initializer_receiver_name"] == "provider"
        assert assigned_variable["initializer_member_name"] == "service"
        assert assigned_variable["initializer_member_kind"] == "function"

        fn_to_fn, *_ = build_function_call_groups(
            [progress_data, provider_data, caller_data],
            imports_map,
        )
        resolved_lines = {
            edge["line_number"]
            for edge in fn_to_fn
            if edge["caller_name"] == "run"
            and edge["called_name"] == "applyEvent"
            and edge["called_file_path"] == str(progress_path)
        }
        assert resolved_lines == {6, 8}

    def test_import_precedence_prefers_explicit_then_same_package_before_wildcard(
        self,
        parser,
        tmp_path,
    ):
        explicit_path = _write_source(
            tmp_path,
            "com/example/util/ExplicitHelpers.kt",
            """
            package com.example.util

            fun explicitHelper(): String {
                return "explicit"
            }
            """,
        )
        same_package_path = _write_source(
            tmp_path,
            "com/example/SamePackageHelpers.kt",
            """
            package com.example

            fun explicitHelper(): String {
                return "same-package-wrong"
            }

            fun samePackageHelper(): String {
                return "same-package"
            }
            """,
        )
        wildcard_path = _write_source(
            tmp_path,
            "com/example/wild/WildcardHelpers.kt",
            """
            package com.example.wild

            fun samePackageHelper(): String {
                return "wildcard-wrong"
            }
            """,
        )
        caller_path = _write_source(
            tmp_path,
            "com/example/Caller.kt",
            """
            package com.example

            import com.example.util.explicitHelper
            import com.example.wild.*

            class Caller {
                fun run(): String {
                    explicitHelper()
                    samePackageHelper()
                    return "done"
                }
            }
            """,
        )

        caller_data = parser.parse(caller_path)
        imports_map = pre_scan_kotlin(
            [explicit_path, same_package_path, wildcard_path, caller_path],
            parser.generic_parser_wrapper,
        )
        local_imports = _local_imports(caller_data)

        explicit_call = next(
            c for c in caller_data["function_calls"] if c["name"] == "explicitHelper"
        )
        same_package_call = next(
            c for c in caller_data["function_calls"] if c["name"] == "samePackageHelper"
        )

        explicit_resolved = resolve_function_call(
            explicit_call,
            caller_file_path=caller_data["path"],
            local_names=_local_names(caller_data),
            local_imports=local_imports,
            imports_map=imports_map,
            skip_external=False,
        )
        same_package_resolved = resolve_function_call(
            same_package_call,
            caller_file_path=caller_data["path"],
            local_names=_local_names(caller_data),
            local_imports=local_imports,
            imports_map=imports_map,
            skip_external=False,
        )

        assert explicit_resolved is not None
        assert explicit_resolved["called_file_path"] == str(explicit_path)
        assert same_package_resolved is not None
        assert same_package_resolved["called_file_path"] == str(same_package_path)

    def test_if_and_when_smart_casts_infer_receiver_types(self, parser, tmp_path):
        progress_path = _write_source(
            tmp_path,
            "com/example/ProgressService.kt",
            """
            package com.example

            class ProgressService {
                fun applyEvent(event: String): String {
                    return event
                }
            }
            """,
        )
        caller_path = _write_source(
            tmp_path,
            "com/example/Caller.kt",
            """
            package com.example

            class Caller {
                fun run(service: Any): String {
                    if (service is ProgressService) {
                        service.applyEvent("if")
                    }
                    when (service) {
                        is ProgressService -> service.applyEvent("when")
                        else -> Unit
                    }
                    return "done"
                }
            }
            """,
        )

        progress_data = parser.parse(progress_path)
        caller_data = parser.parse(caller_path)
        imports_map = pre_scan_kotlin(
            [progress_path, caller_path],
            parser.generic_parser_wrapper,
        )

        smart_cast_calls = [
            c for c in caller_data["function_calls"]
            if c["full_name"] == "service.applyEvent"
        ]
        assert len(smart_cast_calls) == 2
        assert all(c["inferred_obj_type"] == "ProgressService" for c in smart_cast_calls)

        fn_to_fn, *_ = build_function_call_groups(
            [progress_data, caller_data],
            imports_map,
        )
        resolved_edges = [
            edge for edge in fn_to_fn
            if edge["caller_name"] == "run"
            and edge["called_name"] == "applyEvent"
            and edge["called_file_path"] == str(progress_path)
        ]
        assert len(resolved_edges) == 2

    def test_negated_and_or_type_checks_do_not_smart_cast(self, parser):
        caller_data = _write_and_parse(
            parser,
            """
            package com.example

            class ProgressService {
                fun applyEvent(event: String): String {
                    return event
                }
            }

            class OtherService

            class Caller {
                fun run(service: Any): String {
                    if (!(service is ProgressService)) {
                        service.applyEvent("negated")
                    }
                    if (service is ProgressService || service is OtherService) {
                        service.applyEvent("or")
                    }
                    return "done"
                }
            }
            """,
        )

        apply_event_calls = [
            c for c in caller_data["function_calls"]
            if c["full_name"] == "service.applyEvent"
        ]
        assert len(apply_event_calls) == 2
        assert all(
            c["inferred_obj_type"] != "ProgressService"
            for c in apply_event_calls
        )

    def test_inherited_member_calls_resolve_to_base_method_file(self, parser, tmp_path):
        base_path = _write_source(
            tmp_path,
            "com/example/BaseService.kt",
            """
            package com.example

            open class BaseService {
                fun applyEvent(event: String): String {
                    return event
                }
            }
            """,
        )
        child_path = _write_source(
            tmp_path,
            "com/example/ChildService.kt",
            """
            package com.example

            class ChildService : BaseService()
            """,
        )
        caller_path = _write_source(
            tmp_path,
            "com/example/Caller.kt",
            """
            package com.example

            class Caller {
                fun run(service: ChildService): String {
                    return service.applyEvent("base")
                }
            }
            """,
        )

        base_data = parser.parse(base_path)
        child_data = parser.parse(child_path)
        caller_data = parser.parse(caller_path)
        imports_map = pre_scan_kotlin(
            [base_path, child_path, caller_path],
            parser.generic_parser_wrapper,
        )

        fn_to_fn, *_ = build_function_call_groups(
            [base_data, child_data, caller_data],
            imports_map,
        )
        assert any(
            edge["caller_name"] == "run"
            and edge["called_name"] == "applyEvent"
            and edge["called_file_path"] == str(base_path)
            for edge in fn_to_fn
        )
        assert not any(
            edge["caller_name"] == "run"
            and edge["called_name"] == "applyEvent"
            and edge["called_file_path"] == str(child_path)
            for edge in fn_to_fn
        )

    def test_interface_default_member_resolves_through_base_interface(self, parser, tmp_path):
        interface_path = _write_source(
            tmp_path,
            "com/example/ProgressPort.kt",
            """
            package com.example

            interface ProgressPort {
                fun applyEvent(event: String): String {
                    return event
                }
            }
            """,
        )
        service_path = _write_source(
            tmp_path,
            "com/example/ProgressService.kt",
            """
            package com.example

            class ProgressService : ProgressPort
            """,
        )
        caller_path = _write_source(
            tmp_path,
            "com/example/Caller.kt",
            """
            package com.example

            class Caller {
                fun run(service: ProgressService): String {
                    return service.applyEvent("interface")
                }
            }
            """,
        )

        interface_data = parser.parse(interface_path)
        service_data = parser.parse(service_path)
        caller_data = parser.parse(caller_path)
        assert {c["name"] for c in interface_data["classes"] + interface_data["interfaces"]} == {"ProgressPort"}
        assert any(
            f["name"] == "applyEvent" and f["context"] == "ProgressPort"
            for f in interface_data["functions"]
        )

        imports_map = pre_scan_kotlin(
            [interface_path, service_path, caller_path],
            parser.generic_parser_wrapper,
        )
        fn_to_fn, *_ = build_function_call_groups(
            [interface_data, service_data, caller_data],
            imports_map,
        )
        assert any(
            edge["caller_name"] == "run"
            and edge["called_name"] == "applyEvent"
            and edge["called_file_path"] == str(interface_path)
            for edge in fn_to_fn
        )

    def test_elvis_and_safe_cast_receivers_infer_receiver_types(self, parser, tmp_path):
        progress_path = _write_source(
            tmp_path,
            "com/example/ProgressService.kt",
            """
            package com.example

            class ProgressService {
                fun applyEvent(event: String): String {
                    return event
                }
            }
            """,
        )
        caller_path = _write_source(
            tmp_path,
            "com/example/Caller.kt",
            """
            package com.example

            class Caller {
                fun run(primary: ProgressService?, fallback: ProgressService, unknown: Any?): String {
                    (primary ?: fallback).applyEvent("elvis");
                    (unknown as? ProgressService)?.applyEvent("safeCast")
                    return "done"
                }
            }
            """,
        )

        progress_data = parser.parse(progress_path)
        caller_data = parser.parse(caller_path)
        imports_map = pre_scan_kotlin(
            [progress_path, caller_path],
            parser.generic_parser_wrapper,
        )

        apply_event_calls = [
            c for c in caller_data["function_calls"]
            if c["name"] == "applyEvent"
        ]
        assert len(apply_event_calls) == 2
        assert all(c["inferred_obj_type"] == "ProgressService" for c in apply_event_calls)

        fn_to_fn, *_ = build_function_call_groups(
            [progress_data, caller_data],
            imports_map,
        )
        resolved_lines = {
            edge["line_number"]
            for edge in fn_to_fn
            if edge["caller_name"] == "run"
            and edge["called_name"] == "applyEvent"
            and edge["called_file_path"] == str(progress_path)
        }
        assert resolved_lines == {6, 7}

    def test_expression_initializer_flow_infers_receiver_types(self, parser, tmp_path):
        progress_path = _write_source(
            tmp_path,
            "com/example/ProgressService.kt",
            """
            package com.example

            class ProgressService {
                fun applyEvent(event: String): String {
                    return event
                }
            }
            """,
        )
        caller_path = _write_source(
            tmp_path,
            "com/example/Caller.kt",
            """
            package com.example

            class Caller {
                fun run(primary: ProgressService?, fallback: ProgressService, a: ProgressService, b: ProgressService, flag: Boolean): String {
                    val elvisService = primary ?: fallback
                    val nestedElvisService = primary ?: (a ?: b) ?: fallback
                    val ifService = if ((flag)) a else b
                    val whenService = when (flag) {
                        true -> a
                        else -> b
                    }
                    elvisService.applyEvent("elvis")
                    nestedElvisService.applyEvent("nestedElvis")
                    ifService.applyEvent("if")
                    whenService.applyEvent("when")
                    return "done"
                }
            }
            """,
        )

        progress_data = parser.parse(progress_path)
        caller_data = parser.parse(caller_path)
        imports_map = pre_scan_kotlin(
            [progress_path, caller_path],
            parser.generic_parser_wrapper,
        )

        variables_by_name = {
            v["name"]: v
            for v in caller_data["variables"]
            if v["name"] in {
                "elvisService",
                "nestedElvisService",
                "ifService",
                "whenService",
            }
        }
        assert variables_by_name["elvisService"]["initializer_candidate_names"] == [
            "primary",
            "fallback",
        ]
        assert variables_by_name["nestedElvisService"]["initializer_candidate_names"] == [
            "primary",
            "a",
            "b",
            "fallback",
        ]
        assert variables_by_name["ifService"]["initializer_candidate_names"] == [
            "a",
            "b",
        ]
        assert variables_by_name["whenService"]["initializer_candidate_names"] == [
            "a",
            "b",
        ]

        fn_to_fn, *_ = build_function_call_groups(
            [progress_data, caller_data],
            imports_map,
        )
        resolved_lines = {
            edge["line_number"]
            for edge in fn_to_fn
            if edge["caller_name"] == "run"
            and edge["called_name"] == "applyEvent"
            and edge["called_file_path"] == str(progress_path)
        }
        assert resolved_lines == {13, 14, 15, 16}

    def test_expression_initializer_flow_requires_consistent_candidate_types(self, parser):
        caller_data = _write_and_parse(
            parser,
            """
            package com.example

            class ProgressService {
                fun applyEvent(event: String): String {
                    return event
                }
            }

            class OtherService

            class Caller {
                fun run(primary: ProgressService, other: OtherService, flag: Boolean): String {
                    val mixed = if (flag) primary else other
                    mixed.applyEvent("mixed")
                    return "done"
                }
            }
            """,
        )

        mixed_call = next(
            c for c in caller_data["function_calls"]
            if c["full_name"] == "mixed.applyEvent"
        )
        assert mixed_call["inferred_obj_type"] is None

    def test_elvis_initializer_flow_requires_all_branches_to_be_candidates(self, parser):
        caller_data = _write_and_parse(
            parser,
            """
            package com.example

            class ProgressService {
                fun applyEvent(event: String): String {
                    return event
                }
            }

            class Caller {
                fun build(): ProgressService {
                    return ProgressService()
                }

                fun run(fallback: ProgressService, threshold: Int): String {
                    val fromCall = build() ?: fallback
                    val fromComparison = threshold > 0 ?: fallback
                    fromCall.applyEvent("call")
                    fromComparison.applyEvent("comparison")
                    return "done"
                }
            }
            """,
        )

        variables_by_name = {
            v["name"]: v
            for v in caller_data["variables"]
            if v["name"] in {"fromCall", "fromComparison"}
        }
        assert "initializer_candidate_names" not in variables_by_name["fromCall"]
        assert "initializer_candidate_names" not in variables_by_name["fromComparison"]

        calls_by_name = {
            c["full_name"]: c
            for c in caller_data["function_calls"]
            if c["full_name"] in {
                "fromCall.applyEvent",
                "fromComparison.applyEvent",
            }
        }
        assert calls_by_name["fromCall.applyEvent"]["inferred_obj_type"] is None
        assert calls_by_name["fromComparison.applyEvent"]["inferred_obj_type"] is None
