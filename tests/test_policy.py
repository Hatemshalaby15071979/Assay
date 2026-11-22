"""Phase A — one policy schema, three input formats, fail-closed validation."""
from __future__ import annotations

import pytest

from tests.conftest import REPO
from sheet_solution.core.errors import ConfigError
from sheet_solution.core.policy import load_policy, validate_policy
from sheet_solution.core.policy import yaml_lite

EXAMPLES = REPO / "examples"


def _base_raw():
    return {
        "version": 1,
        "defaults": {"on_unresolved": "propose", "confirm_required": True},
        "checks": [{
            "id": "C1", "column": "score", "rule": "numeric_range",
            "params": {"min": 60}, "severity": "high",
            "on_fail": {"actions": ["tag_row"], "confirm_required": True},
        }],
        "compatibility": {"required_columns": ["id"],
                          "allowed_values": {"status": ["ok", "bad"]}},
    }


# --- three formats -> one schema -------------------------------------------
def test_three_formats_normalise_to_identical_policy():
    j = validate_policy(load_policy(EXAMPLES / "policy.example.json"))
    y = validate_policy(load_policy(EXAMPLES / "policy.example.yaml"))
    c = validate_policy(load_policy(EXAMPLES / "policy-sheet.example.csv"))
    assert j.to_raw() == y.to_raw() == c.to_raw()


def test_version_defaults_when_omitted():
    raw = _base_raw()
    del raw["version"]
    p = validate_policy(raw)
    assert p.version == 1


def test_echo_mentions_all_rules_and_defaults():
    p = validate_policy(_base_raw())
    text = p.echo()
    assert "on_unresolved: propose" in text
    assert "C1" in text and "numeric_range" in text and "tag_row" in text


# --- fail-closed validation -------------------------------------------------
@pytest.mark.parametrize("mutate", [
    lambda r: r.update(version=2),
    lambda r: r.update(unexpected="x"),
    lambda r: r.update(defaults={"on_unresolved": "guess"}),
    lambda r: r["defaults"].update(confirm_required="yes"),
    lambda r: r["checks"][0].update(rule="not_a_rule"),
    lambda r: r["checks"][0].update(severity="critical"),
    lambda r: r["checks"][0]["on_fail"].update(actions=["delete_everything"]),
    lambda r: r["checks"].append(dict(r["checks"][0])),  # duplicate id
    lambda r: r.update(compatibility={"unknown": 1}),
])
def test_validator_rejects_bad_policies(mutate):
    raw = _base_raw()
    mutate(raw)
    with pytest.raises(ConfigError):
        validate_policy(raw)


def test_validator_rejects_non_mapping():
    with pytest.raises(ConfigError):
        validate_policy([1, 2, 3])


def test_checks_must_be_a_list():
    raw = _base_raw()
    raw["checks"] = {"id": "C1"}
    with pytest.raises(ConfigError):
        validate_policy(raw)


# --- YAML subset is safe ----------------------------------------------------
@pytest.mark.parametrize("text", [
    "---\nversion: 1",
    "version: 1\nanchor: &x 1",
    "version: 1\nalias: *x",
    "version: 1\ntag: !!python/object 1",
    "version: 1\nmerge:\n  <<: 1",
    "version: 1\nflow: [unclosed",
    "version: 1\nversion: 2",
    "version: 1\n\tbad: tab",
])
def test_yaml_lite_rejects_unsafe_or_ambiguous(text):
    with pytest.raises(ConfigError):
        yaml_lite.loads(text)


def test_yaml_lite_parses_supported_scalars():
    data = yaml_lite.loads(
        "a: 1\nb: 2.5\nc: true\nd: false\ne: null\nf: [x, y]\ng: {k: v}\nh: 'quoted'\n")
    assert data == {
        "a": 1, "b": 2.5, "c": True, "d": False, "e": None,
        "f": ["x", "y"], "g": {"k": "v"}, "h": "quoted"}


def test_yaml_lite_parses_multiline_flow_sequence():
    data = yaml_lite.loads(
        "version: 1\nchecks:\n  - id: C1\n    on_fail:\n"
        "      actions: [tag_row,\n"
        "                flag_for_human]\n")
    assert data["checks"][0]["on_fail"]["actions"] == ["tag_row", "flag_for_human"]


def test_yaml_lite_parses_multiline_flow_mapping():
    data = yaml_lite.loads(
        "version: 1\nparams: {min: 60,\n"
        "         max: 100}\n")
    assert data["params"] == {"min": 60, "max": 100}


def test_yaml_lite_rejects_truly_unterminated_multiline_flow():
    with pytest.raises(ConfigError, match="unterminated flow value"):
        yaml_lite.loads("version: 1\nflow: [a,\n  b\n")


def test_compose_file_is_not_a_policy(tmp_path):
    p = tmp_path / "docker-compose.yml"
    p.write_text(
        "services:\n  run:\n    command: [\"run\",\n"
        "              \"--out\", \"/out\"]\n")
    with pytest.raises(ConfigError, match="does not look like an Assay policy"):
        load_policy(p)


# --- CLI parse-policy -------------------------------------------------------
def test_cli_parse_policy_echoes(tmp_path):
    import subprocess
    import sys
    out = subprocess.run(
        [sys.executable, "-m", "sheet_solution", "parse-policy",
         "--policy", str(EXAMPLES / "policy.example.json")],
        capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert "policy version: 1" in out.stdout
    assert "QA-THRESHOLD" in out.stdout
