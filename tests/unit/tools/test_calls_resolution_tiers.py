"""
Unit tests for Phase 2+3 — resolution tier waterfall and confidence scoring
in calls.py.

Covers:
  - Tier 1: self/this/super receiver → confidence 1.00
  - Tier 2: local name → confidence 0.95
  - Tier 3: inferred_obj_type with FQN in imports_map → confidence 0.88
  - Tier 4: inferred_obj_type with short-name fallback → confidence 0.72
  - Tier 5: globally unique short name → confidence 0.90
  - Tier 6: FQN key from qualified import → confidence 0.85
  - Tier 7: FQN path-substring match → confidence 0.70
  - Tier 8: alphabetical-first of multiple candidates → confidence 0.25
  - Tier 9: same-file fallback for obj.method() → confidence 0.08
  - confidence and resolution_tier are always present in the return dict
  - skip_external still suppresses definitionally-external (tier 9) calls
  - return dict structure is unchanged (no removed keys)
"""

import pytest
from codegraphcontext.tools.indexing.resolution.calls import resolve_function_call, _TIER_CONFIDENCE


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _call(called_name, full_name=None, inferred_obj_type=None, context=("caller_fn", None, 1)):
    return {
        "name": called_name,
        "full_name": full_name or called_name,
        "line_number": 5,
        "args": [],
        "inferred_obj_type": inferred_obj_type,
        "context": context,
    }


CALLER = "/repo/Controller.java"


def resolve(call_dict, local_names=None, local_imports=None, imports_map=None, skip_external=False):
    return resolve_function_call(
        call_dict,
        caller_file_path=CALLER,
        local_names=local_names or set(),
        local_imports=local_imports or {},
        imports_map=imports_map or {},
        skip_external=skip_external,
    )


# ---------------------------------------------------------------------------
# Tests: return shape (backward-compat check)
# ---------------------------------------------------------------------------

class TestReturnShape:

    def test_confidence_always_present(self):
        result = resolve(_call("helper"), local_names={"helper"})
        assert result is not None
        assert "confidence" in result

    def test_resolution_tier_always_present(self):
        result = resolve(_call("helper"), local_names={"helper"})
        assert result is not None
        assert "resolution_tier" in result

    def test_legacy_keys_still_present(self):
        """Existing consumers must not break — all original keys must be returned."""
        result = resolve(_call("helper"), local_names={"helper"})
        assert result is not None
        for key in ("caller_name", "caller_file_path", "called_name", "called_file_path",
                    "line_number", "args", "full_call_name", "type"):
            assert key in result, f"Legacy key '{key}' missing from resolve_function_call result"

    def test_file_type_when_no_caller_context(self):
        """A call with context=None must return type='file' (backward compat)."""
        result = resolve(_call("helper", context=None), local_names={"helper"})
        assert result is not None
        assert result["type"] == "file"


# ---------------------------------------------------------------------------
# Tests: Tier 1 — self/this/super
# ---------------------------------------------------------------------------

class TestTier1SelfReceiver:

    def test_this_receiver_resolves_to_caller(self):
        result = resolve(_call("execute", full_name="this.execute"))
        assert result["called_file_path"] == CALLER

    def test_this_receiver_tier_is_1(self):
        result = resolve(_call("execute", full_name="this.execute"))
        assert result["resolution_tier"] == 1

    def test_this_receiver_confidence_is_1(self):
        result = resolve(_call("execute", full_name="this.execute"))
        assert result["confidence"] == _TIER_CONFIDENCE[1]

    def test_super_receiver_resolves_to_caller(self):
        result = resolve(_call("execute", full_name="super.execute"))
        assert result["called_file_path"] == CALLER
        assert result["resolution_tier"] == 1


# ---------------------------------------------------------------------------
# Tests: Tier 2 — local name
# ---------------------------------------------------------------------------

class TestTier2LocalName:

    def test_local_function_resolves_to_caller(self):
        result = resolve(_call("helper"), local_names={"helper"})
        assert result["called_file_path"] == CALLER

    def test_local_function_tier_is_2(self):
        result = resolve(_call("helper"), local_names={"helper"})
        assert result["resolution_tier"] == 2

    def test_local_function_confidence(self):
        result = resolve(_call("helper"), local_names={"helper"})
        assert result["confidence"] == _TIER_CONFIDENCE[2]


# ---------------------------------------------------------------------------
# Tests: Tier 3 — inferred_obj_type + FQN key
# ---------------------------------------------------------------------------

class TestTier3InferredFQN:

    def test_fqn_import_resolves_cross_file(self):
        """When local_imports has the FQN and imports_map[FQN] has exactly 1 path, use Tier 3."""
        imports_map = {
            "BillingService": ["/repo/a/BillingService.java", "/repo/b/BillingService.java"],
            "com.example.acme.billing.BillingService": ["/repo/a/BillingService.java"],
        }
        local_imports = {"BillingService": "com.example.acme.billing.BillingService"}
        call_dict = _call("processPayment", full_name="billingService.processPayment",
                          inferred_obj_type="BillingService")

        result = resolve(call_dict, local_imports=local_imports, imports_map=imports_map)

        assert result is not None
        assert result["called_file_path"] == "/repo/a/BillingService.java"
        assert result["resolution_tier"] == 3
        assert result["confidence"] == _TIER_CONFIDENCE[3]

    def test_tier3_over_tier4_when_fqn_resolves(self):
        """Tier 3 (FQN) must win over Tier 4 (short-name first-match)."""
        imports_map = {
            "BillingService": ["/repo/z/BillingService.java"],  # only 1 — would be Tier 4
            "com.example.acme.billing.BillingService": ["/repo/a/BillingService.java"],
        }
        local_imports = {"BillingService": "com.example.acme.billing.BillingService"}
        call_dict = _call("charge", full_name="bs.charge", inferred_obj_type="BillingService")

        result = resolve(call_dict, local_imports=local_imports, imports_map=imports_map)

        assert result["resolution_tier"] == 3
        assert result["called_file_path"] == "/repo/a/BillingService.java"


# ---------------------------------------------------------------------------
# Tests: Tier 4 — inferred_obj_type + short-name fallback
# ---------------------------------------------------------------------------

class TestTier4InferredShortName:

    def test_short_name_fallback_when_no_fqn_key(self):
        """When no FQN key exists, fall back to short-name first-match (Tier 4)."""
        imports_map = {"WorkService": ["/repo/WorkService.java"]}
        call_dict = _call("doWork", full_name="ws.doWork", inferred_obj_type="WorkService")

        result = resolve(call_dict, imports_map=imports_map)

        assert result["called_file_path"] == "/repo/WorkService.java"
        assert result["resolution_tier"] == 4
        assert result["confidence"] == _TIER_CONFIDENCE[4]


# ---------------------------------------------------------------------------
# Tests: Tier 5 — globally unique short name
# ---------------------------------------------------------------------------

class TestTier5UniqueShortName:

    def test_unique_name_in_imports_map(self):
        imports_map = {"parseRequest": ["/repo/RequestParser.java"]}
        result = resolve(_call("parseRequest"), imports_map=imports_map)

        assert result["called_file_path"] == "/repo/RequestParser.java"
        assert result["resolution_tier"] == 5
        assert result["confidence"] == _TIER_CONFIDENCE[5]


# ---------------------------------------------------------------------------
# Tests: Tier 6 — FQN key from qualified import
# ---------------------------------------------------------------------------

class TestTier6QualifiedImport:

    def test_fqn_direct_lookup_in_imports_map(self):
        """When local_imports[name]=FQN and imports_map[FQN] has 1 path → Tier 6."""
        imports_map = {
            "AuthService": ["/repo/a/AuthService.java", "/repo/b/AuthService.java"],
            "com.example.acme.auth.AuthService": ["/repo/a/AuthService.java"],
        }
        # no inferred_obj_type — pure Tier 6 path via call-site name lookup
        local_imports = {"AuthService": "com.example.acme.auth.AuthService"}
        call_dict = _call("AuthService")  # calling the class as a constructor/factory

        result = resolve(call_dict, local_imports=local_imports, imports_map=imports_map)

        assert result["called_file_path"] == "/repo/a/AuthService.java"
        assert result["resolution_tier"] == 6
        assert result["confidence"] == _TIER_CONFIDENCE[6]


# ---------------------------------------------------------------------------
# Tests: Tier 7 — FQN path-substring match
# ---------------------------------------------------------------------------

class TestTier7PathSubstring:

    def test_fqn_as_path_substring(self):
        """When FQN can't resolve directly but matches as a file-path substring → Tier 7."""
        imports_map = {
            "AuthService": [
                "/opt/repos/myapp/acme.auth/src/main/java/com/example/acme/auth/AuthService.java",
                "/opt/repos/myapp/acme.authv2/src/main/java/com/example/acme/authv2/AuthService.java",
            ]
        }
        local_imports = {"AuthService": "com.example.acme.auth.AuthService"}
        call_dict = _call("AuthService")

        result = resolve(call_dict, local_imports=local_imports, imports_map=imports_map)

        assert "com/example/acme/auth/AuthService" in result["called_file_path"]
        assert result["resolution_tier"] == 7
        assert result["confidence"] == _TIER_CONFIDENCE[7]


# ---------------------------------------------------------------------------
# Tests: Tier 8 — alphabetical-first of multiple candidates
# ---------------------------------------------------------------------------

class TestTier8AlphabeticalFirst:

    def test_multiple_candidates_no_import_hint(self):
        """When multiple paths, no import hint, no obj type → Tier 8 first-match."""
        imports_map = {
            "execute": ["/repo/a/ActionA.java", "/repo/b/ActionB.java"],
        }
        result = resolve(_call("execute"), imports_map=imports_map)

        assert result["called_file_path"] in ("/repo/a/ActionA.java", "/repo/b/ActionB.java")
        assert result["resolution_tier"] == 8
        assert result["confidence"] == _TIER_CONFIDENCE[8]

    def test_tier8_confidence_is_low(self):
        """Tier 8 is a last-resort guess — confidence must be below 0.5."""
        assert _TIER_CONFIDENCE[8] < 0.5


# ---------------------------------------------------------------------------
# Tests: Tier 9 — same-file fallback
# ---------------------------------------------------------------------------

class TestTier9SameFileFallback:

    def test_unresolvable_obj_call_falls_back_to_caller(self):
        """obj.method() with no type info and no imports_map match → same-file fallback."""
        call_dict = _call("execute", full_name="sequence.execute")
        result = resolve(call_dict)

        assert result["called_file_path"] == CALLER
        assert result["resolution_tier"] == 9
        assert result["confidence"] == _TIER_CONFIDENCE[9]

    def test_tier9_confidence_is_very_low(self):
        """Tier 9 is definitionally wrong for obj.method() — confidence must be < 0.2."""
        assert _TIER_CONFIDENCE[9] < 0.2

    def test_skip_external_suppresses_tier9(self):
        """When skip_external=True, unresolvable obj.method() calls must return None."""
        call_dict = _call("execute", full_name="sequence.execute")
        result = resolve(call_dict, skip_external=True)
        assert result is None

    def test_skip_external_does_not_suppress_tier1(self):
        """self.method() is not external — skip_external must not suppress it."""
        call_dict = _call("execute", full_name="this.execute")
        result = resolve(call_dict, skip_external=True)
        assert result is not None

    def test_skip_external_does_not_suppress_tier2(self):
        """Local name resolution is not external — skip_external must not suppress it."""
        result = resolve(_call("helper"), local_names={"helper"}, skip_external=True)
        assert result is not None


# ---------------------------------------------------------------------------
# Tests: tier ordering (lower tier = higher confidence only where monotonic)
# ---------------------------------------------------------------------------

class TestTierConfidenceOrdering:

    def test_tier1_highest_confidence(self):
        """Tier 1 (certain) must have the highest confidence of all tiers."""
        max_conf = max(v for k, v in _TIER_CONFIDENCE.items() if k != 1)
        assert _TIER_CONFIDENCE[1] > max_conf

    def test_tier9_lowest_confidence(self):
        """Tier 9 (same-file fallback) must have the lowest confidence."""
        min_other = min(v for k, v in _TIER_CONFIDENCE.items() if k != 9)
        assert _TIER_CONFIDENCE[9] < min_other

    def test_all_confidences_in_range(self):
        """All confidence values must be in [0.0, 1.0]."""
        for tier, conf in _TIER_CONFIDENCE.items():
            assert 0.0 <= conf <= 1.0, f"Tier {tier} confidence {conf} out of range"
