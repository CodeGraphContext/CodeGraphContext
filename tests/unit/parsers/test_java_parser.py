"""
Tests for the Java tree-sitter parser — cross-file CALLS via DI field injection.

Fixes issue #823: Java CALLS graph does not resolve cross-file method invocations.

Root cause: `inferred_obj_type` was always None, so calls on field/local-variable
receivers could not be resolved to a cross-file target by resolve_function_call.

Fix: build a var_type_map from field and local-variable declarations, then
populate `inferred_obj_type` when the base object of a method call matches a
known variable name. The resolver uses this to look up imports_map and produce
accurate cross-file CALLS edges.
"""

import os
import tempfile
import pytest
from unittest.mock import MagicMock
from pathlib import Path

from codegraphcontext.tools.languages.java import JavaTreeSitterParser
from codegraphcontext.tools.indexing.resolution.calls import resolve_function_call
from codegraphcontext.utils.tree_sitter_manager import get_tree_sitter_manager


# ---------------------------------------------------------------------------
# Shared fixture — follows the pattern from test_python_parser.py
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def parser():
    manager = get_tree_sitter_manager()
    wrapper = MagicMock()
    wrapper.language_name = "java"
    wrapper.language = manager.get_language_safe("java")
    wrapper.parser = manager.create_parser("java")
    return JavaTreeSitterParser(wrapper)


def _write_and_parse(parser, src: str, suffix: str = ".java") -> dict:
    """Write src to a temp file and parse it."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=suffix, delete=False, encoding="utf-8"
    ) as f:
        f.write(src)
        tmp = f.name
    try:
        return parser.parse(Path(tmp))
    finally:
        os.unlink(tmp)


# ---------------------------------------------------------------------------
# Sample sources
# ---------------------------------------------------------------------------

CONTROLLER_SRC = """
package com.example.app;

import com.example.app.service.WorkService;

public class Controller {
    private WorkService workService;

    public void setWorkService(WorkService workService) {
        this.workService = workService;
    }

    public String handle(String input) {
        String result = workService.doWork(input);
        int computed = workService.computeResult(42);
        return result + " (" + computed + ")";
    }
}
"""

WORK_SERVICE_SRC = """
package com.example.app.service;

public class WorkService {
    public String doWork(String input) {
        return "processed: " + input;
    }

    public int computeResult(int value) {
        return value * 2;
    }
}
"""

GENERIC_FIELD_SRC = """
package com.example.app;

import java.util.List;
import com.example.app.service.WorkService;

public class GenericHolder {
    private List<WorkService> services;

    public void process() {
        // services is typed List — strip_generic should resolve to 'List', not 'WorkService'
        services.add(null);
    }
}
"""


# ---------------------------------------------------------------------------
# Tests: inferred_obj_type population (issue #823 regression tests)
# ---------------------------------------------------------------------------

class TestJavaDiCrossFileCalls:

    def test_di_field_call_has_inferred_obj_type(self, parser):
        """workService.doWork() must carry inferred_obj_type='WorkService' (fix for #823)."""
        data = _write_and_parse(parser, CONTROLLER_SRC)
        calls = data["function_calls"]

        do_work_calls = [c for c in calls if c["name"] == "doWork"]
        assert do_work_calls, "Expected at least one doWork call to be parsed"

        call = do_work_calls[0]
        assert call["inferred_obj_type"] == "WorkService", (
            f"Expected inferred_obj_type='WorkService', got {call['inferred_obj_type']!r}. "
            "Cross-file DI field call resolution is broken (issue #823)."
        )

    def test_second_di_call_on_same_field_also_inferred(self, parser):
        """workService.computeResult() must also carry inferred_obj_type='WorkService'."""
        data = _write_and_parse(parser, CONTROLLER_SRC)
        calls = data["function_calls"]

        compute_calls = [c for c in calls if c["name"] == "computeResult"]
        assert compute_calls, "Expected at least one computeResult call"
        assert compute_calls[0]["inferred_obj_type"] == "WorkService"

    def test_calls_without_receiver_have_no_inferred_type(self, parser):
        """Bare method calls (no object receiver) must have inferred_obj_type=None."""
        data = _write_and_parse(parser, WORK_SERVICE_SRC)
        for call in data["function_calls"]:
            assert call["inferred_obj_type"] is None, (
                f"Unexpected inferred_obj_type={call['inferred_obj_type']!r} "
                f"for call '{call['name']}' in WorkService (no DI fields present)"
            )

    def test_generic_field_strips_type_parameter(self, parser):
        """List<WorkService> field receiver resolves to 'List', not 'WorkService'."""
        data = _write_and_parse(parser, GENERIC_FIELD_SRC)
        add_calls = [c for c in data["function_calls"] if c["name"] == "add"]
        assert add_calls, "Expected 'add' call on List field"
        # The field is typed List<WorkService>; strip_generic gives 'List'
        assert add_calls[0]["inferred_obj_type"] == "List"

    def test_strip_generic_static_method(self, parser):
        """Verify _strip_generic handles all common forms correctly."""
        assert JavaTreeSitterParser._strip_generic("WorkService") == "WorkService"
        assert JavaTreeSitterParser._strip_generic("List<String>") == "List"
        assert JavaTreeSitterParser._strip_generic("Map<String, Object>") == "Map"
        assert JavaTreeSitterParser._strip_generic("  RoidFraudCheckService  ") == "RoidFraudCheckService"


class TestJavaParameterParsing:
    def test_annotation_string_commas_do_not_split_parameters(self, parser):
        src = """
        package com.example.app;

        public class AnnotatedController {
            public void handle(
                @Named(value = "text, with (parentheses)", escaped = "quote: \\"") String name,
                java.util.List<java.util.Map<String, Integer>> values
            ) {}
        }

        @interface Named {
            String value();
            String escaped() default "";
        }
        """

        data = _write_and_parse(parser, src)
        handle = next(f for f in data["functions"] if f["name"] == "handle")

        assert handle["args"] == ["name", "values"]
        assert handle["arg_types"] == ["String", "java.util.List"]

    def test_annotation_array_values_do_not_split_parameters(self, parser):
        src = """
        package com.example.app;

        public class AnnotatedController {
            public void handle(@Flags({"a,b", "(x,y)"}) String name, int count) {}
        }

        @interface Flags {
            String[] value();
        }
        """

        data = _write_and_parse(parser, src)
        handle = next(f for f in data["functions"] if f["name"] == "handle")

        assert handle["args"] == ["name", "count"]
        assert handle["arg_types"] == ["String", "Int"]

    def test_final_with_non_space_whitespace_is_stripped(self, parser):
        src = """
        package com.example.app;

        public class AnnotatedController {
            public void handle(
                @Named("a,b") final
                String name,
                final\tint count
            ) {}
        }

        @interface Named {
            String value();
        }
        """

        data = _write_and_parse(parser, src)
        handle = next(f for f in data["functions"] if f["name"] == "handle")

        assert handle["args"] == ["name", "count"]
        assert handle["arg_types"] == ["String", "Int"]


# ---------------------------------------------------------------------------
# End-to-end: full cross-file CALLS resolution via resolve_function_call
# ---------------------------------------------------------------------------

class TestJavaCrossFileResolution:

    def test_di_call_resolves_to_cross_file_path(self, parser):
        """End-to-end: workService.doWork() resolves to WorkService.java, not self."""
        controller_data = _write_and_parse(parser, CONTROLLER_SRC)
        service_data = _write_and_parse(parser, WORK_SERVICE_SRC)

        controller_path = controller_data["path"]
        service_path = service_data["path"]

        # imports_map mirrors what GraphBuilder builds during indexing:
        # class simple name -> [absolute file path]
        imports_map = {"WorkService": [service_path]}

        local_names = {f["name"] for f in controller_data["functions"]} | {
            c["name"] for c in controller_data["classes"]
        }
        local_imports = {
            imp.get("alias") or imp["name"].split(".")[-1]: imp["name"]
            for imp in controller_data.get("imports", [])
        }

        do_work_calls = [c for c in controller_data["function_calls"] if c["name"] == "doWork"]
        assert do_work_calls, "doWork call not found — parser may have regressed"

        resolved = resolve_function_call(
            do_work_calls[0],
            caller_file_path=controller_path,
            local_names=local_names,
            local_imports=local_imports,
            imports_map=imports_map,
            skip_external=False,
        )

        assert resolved is not None, "resolve_function_call returned None"
        assert resolved["called_file_path"] == service_path, (
            f"Expected cross-file path {service_path!r}, "
            f"got {resolved['called_file_path']!r}. "
            "DI CALLS edge would be self-referential (issue #823 not fixed)."
        )

    def test_non_di_call_stays_in_caller_file(self, parser):
        """Calls where the receiver is not a known typed variable stay in the caller file."""
        service_data = _write_and_parse(parser, WORK_SERVICE_SRC)
        service_path = service_data["path"]
        local_names = {f["name"] for f in service_data["functions"]} | {
            c["name"] for c in service_data["classes"]
        }

        for call in service_data["function_calls"]:
            resolved = resolve_function_call(
                call,
                caller_file_path=service_path,
                local_names=local_names,
                local_imports={},
                imports_map={},
                skip_external=False,
            )
            if resolved:
                assert resolved["called_file_path"] == service_path, (
                    f"WorkService has no DI fields; expected self-resolution for '{call['name']}'"
                )


    def test_super_call_without_base_context_stays_in_caller_file(self):
        """Non-Kotlin super.method() calls must not resolve to unrelated same-name symbols."""
        caller_path = "/tmp/Controller.java"
        external_path = "/tmp/Audit.java"

        resolved = resolve_function_call(
            {
                "name": "audit",
                "full_name": "super.audit",
                "line_number": 12,
                "args": [],
                "context": ("handle", "function", 10),
            },
            caller_file_path=caller_path,
            local_names={"Controller", "handle"},
            local_imports={},
            imports_map={"audit": [external_path]},
            skip_external=False,
        )

        assert resolved is not None
        assert resolved["called_file_path"] == caller_path


# ---------------------------------------------------------------------------
# ORM / datasource mapping extraction tests (#843)
# ---------------------------------------------------------------------------

JPA_ENTITY_SRC = """
package com.example;

import javax.persistence.Entity;
import javax.persistence.Table;
import javax.persistence.Column;

@Entity
@Table(name = "users")
public class User {
    @Column(name = "email")
    private String email;

    @Column(name = "created_at")
    private java.time.Instant createdAt;
}
"""

CASSANDRA_TABLE_SRC = """
package com.example;

import org.springframework.data.cassandra.core.mapping.Table;

@Table(value = "events")
public class EventEntity {
    private String id;
}
"""

REDIS_HASH_SRC = """
package com.example;

import org.springframework.data.redis.core.RedisHash;

@RedisHash(value = "session")
public class SessionData {
    private String token;
}
"""

SPRING_QUERY_SRC = """
package com.example;

import org.springframework.data.jpa.repository.Query;

public interface UserRepository {
    @Query("SELECT u FROM users u WHERE u.id = :id")
    User findById(Long id);

    @Query("INSERT INTO audit_log(user_id, action) VALUES (:userId, :action)")
    void logAction(Long userId, String action);
}
"""

MYBATIS_SRC = """
package com.example;

import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Insert;

public interface UserMapper {
    @Select("SELECT * FROM users WHERE id = #{id}")
    User selectById(int id);

    @Insert("INSERT INTO orders(user_id, total) VALUES(#{userId}, #{total})")
    int createOrder(int userId, double total);
}
"""


class TestOrmMappingExtraction:
    def test_jpa_entity_table_mapping(self, parser):
        data = _write_and_parse(parser, JPA_ENTITY_SRC)
        orm = data.get("orm_mappings", [])
        class_maps = [r for r in orm if r["kind"] == "class_table"]
        assert len(class_maps) == 1
        assert class_maps[0]["orm_table"] == "users"
        assert class_maps[0]["datastore"] == "mysql"
        assert class_maps[0]["class_name"] == "User"

    def test_cassandra_table_mapping(self, parser):
        data = _write_and_parse(parser, CASSANDRA_TABLE_SRC)
        orm = data.get("orm_mappings", [])
        class_maps = [r for r in orm if r["kind"] == "class_table"]
        assert len(class_maps) == 1
        assert class_maps[0]["orm_table"] == "events"
        assert class_maps[0]["datastore"] == "cassandra"

    def test_redis_hash_mapping(self, parser):
        data = _write_and_parse(parser, REDIS_HASH_SRC)
        orm = data.get("orm_mappings", [])
        class_maps = [r for r in orm if r["kind"] == "class_table"]
        assert len(class_maps) == 1
        assert class_maps[0]["orm_table"] == "session"
        assert class_maps[0]["datastore"] == "redis"

    def test_spring_query_read_detection(self, parser):
        data = _write_and_parse(parser, SPRING_QUERY_SRC)
        orm = data.get("orm_mappings", [])
        reads = [r for r in orm if r.get("operation") == "READS"]
        assert any("users" in r.get("db_tables", []) for r in reads), (
            "Expected a READS edge to 'users'"
        )

    def test_spring_query_write_detection(self, parser):
        data = _write_and_parse(parser, SPRING_QUERY_SRC)
        orm = data.get("orm_mappings", [])
        writes = [r for r in orm if r.get("operation") == "WRITES"]
        assert any("audit_log" in r.get("db_tables", []) for r in writes), (
            "Expected a WRITES edge to 'audit_log'"
        )

    def test_mybatis_select_annotation(self, parser):
        data = _write_and_parse(parser, MYBATIS_SRC)
        orm = data.get("orm_mappings", [])
        reads = [r for r in orm if r.get("operation") == "READS"]
        assert any("users" in r.get("db_tables", []) for r in reads)

    def test_mybatis_insert_annotation(self, parser):
        data = _write_and_parse(parser, MYBATIS_SRC)
        orm = data.get("orm_mappings", [])
        writes = [r for r in orm if r.get("operation") == "WRITES"]
        assert any("orders" in r.get("db_tables", []) for r in writes)

    def test_orm_mappings_key_present(self, parser):
        """orm_mappings key must always be present in parse() output."""
        data = _write_and_parse(parser, CONTROLLER_SRC)
        assert "orm_mappings" in data
        assert isinstance(data["orm_mappings"], list)


# ──────────────────────────────────────────────────────────────────────────────
# Spring Data repository derived-query method detection
# ──────────────────────────────────────────────────────────────────────────────

SPRING_DATA_REPO_SRC = """\
package com.example.db;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.repository.CrudRepository;
import java.util.List;
import java.util.Optional;

public interface UserAuthenticationRepository extends JpaRepository<UserAuthentication, Long> {

    Optional<UserAuthentication> findByUserId(String userId);

    List<UserAuthentication> findByEmailAndStatus(String email, String status);

    long countByStatus(String status);

    boolean existsByUserId(String userId);

    void deleteByUserId(String userId);

    List<UserAuthentication> findAllByCreatedAtAfter(long timestamp);
}

public interface OrderRepository extends CrudRepository<Order, Long> {

    List<Order> findByCustomerId(String customerId);

    void deleteById(Long id);
}
"""


class TestSpringDataRepoDetection:
    def test_spring_data_reads_emitted(self, parser):
        data = _write_and_parse(parser, SPRING_DATA_REPO_SRC)
        orm = data.get("orm_mappings", [])
        spring_reads = [r for r in orm if r.get("kind") == "spring_data_method" and r.get("operation") == "READS"]
        assert len(spring_reads) >= 4, f"Expected >=4 READS, got {len(spring_reads)}: {spring_reads}"

    def test_spring_data_writes_emitted(self, parser):
        data = _write_and_parse(parser, SPRING_DATA_REPO_SRC)
        orm = data.get("orm_mappings", [])
        spring_writes = [r for r in orm if r.get("kind") == "spring_data_method" and r.get("operation") == "WRITES"]
        method_names = [r["method_name"] for r in spring_writes]
        assert "deleteByUserId" in method_names, f"Expected deleteByUserId in WRITES, got: {method_names}"

    def test_spring_data_entity_class_extracted(self, parser):
        data = _write_and_parse(parser, SPRING_DATA_REPO_SRC)
        orm = data.get("orm_mappings", [])
        spring = [r for r in orm if r.get("kind") == "spring_data_method"]
        user_auth_methods = [r for r in spring if r.get("entity_class") == "UserAuthentication"]
        assert len(user_auth_methods) >= 1, f"Expected entity_class=UserAuthentication, got: {[r.get('entity_class') for r in spring]}"

    def test_spring_data_crud_repo_detected(self, parser):
        data = _write_and_parse(parser, SPRING_DATA_REPO_SRC)
        orm = data.get("orm_mappings", [])
        order_methods = [r for r in orm if r.get("kind") == "spring_data_method" and r.get("entity_class") == "Order"]
        assert len(order_methods) >= 1, f"Expected Order entity methods, got: {order_methods}"

    def test_spring_data_class_name_set(self, parser):
        data = _write_and_parse(parser, SPRING_DATA_REPO_SRC)
        orm = data.get("orm_mappings", [])
        spring = [r for r in orm if r.get("kind") == "spring_data_method"]
        for r in spring:
            assert r.get("class_name"), f"class_name missing on {r}"
            assert r.get("method_name"), f"method_name missing on {r}"
            assert r.get("method_path"), f"method_path missing on {r}"
            assert r.get("entity_class"), f"entity_class missing on {r}"
