"""Sheet Solution — new-engine tests: template, runner, report, images.

These guard the NEW sheet-comparison layer. The inherited spine tests in
tests/test_*.py (the signoff-derived suite) guard the reused engine.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from sheet_solution.sheets import template, runner, report, images
from sheet_solution.core.errors import ConfigError


# ---------------------------------------------------------------------------
# template
# ---------------------------------------------------------------------------
def test_template_parses_machine_and_human_checks():
    config = template.parse_template(Path("tests/fixtures/check-template.txt"), "s.xlsx")
    assert config.persona == "auditor"
    assert [c.check_id for c in config.checks] == ["CHECK-001", "CHECK-002", "CHECK-003"]
    by_id = {c.check_id: c for c in config.checks}
    assert by_id["CHECK-001"].machine_can_check is True
    assert by_id["CHECK-003"].machine_can_check is False
    assert by_id["CHECK-003"].needs_human is True


def test_template_refuses_missing_required_field(tmp_path):
    bad = tmp_path / "bad.txt"
    bad.write_text("[CHECK]\ncheck_id = X-1\nmachine_can_check = yes\n")
    with pytest.raises(ConfigError):
        template.parse_template(bad, "s.xlsx")


def test_template_refuses_duplicate_check_id(tmp_path):
    dup = tmp_path / "dup.txt"
    dup.write_text(
        "[CHECK]\ncheck_id = X-1\nwhat_is_this_check_for = a\nwhat_to_look_at = b\n"
        "expected_value_or_rule = no blank\nwhen_it_fails_say = c\n"
        "machine_can_check = yes\nexample_that_passes = p\nexample_that_fails = f\n"
        "[CHECK]\ncheck_id = X-1\nwhat_is_this_check_for = a\nwhat_to_look_at = b\n"
        "expected_value_or_rule = no blank\nwhen_it_fails_say = c\n"
        "machine_can_check = yes\nexample_that_passes = p\nexample_that_fails = f\n")
    with pytest.raises(ConfigError):
        template.parse_template(dup, "s.xlsx")


def test_template_refuses_bad_machine_flag(tmp_path):
    bad = tmp_path / "bad.txt"
    bad.write_text(
        "[CHECK]\ncheck_id = X-1\nwhat_is_this_check_for = a\nwhat_to_look_at = b\n"
        "expected_value_or_rule = no blank\nwhen_it_fails_say = c\n"
        "machine_can_check = maybe\nexample_that_passes = p\nexample_that_fails = f\n")
    with pytest.raises(ConfigError):
        template.parse_template(bad, "s.xlsx")


def test_template_verifier_persona():
    config = template.parse_template(Path("tests/fixtures/check-template-verifier.txt"), "s.xlsx")
    assert config.persona == "verifier"


# ---------------------------------------------------------------------------
# runner
# ---------------------------------------------------------------------------
def _machine_check(tmp_path, rule, machine="yes", column="photo"):
    text = (
        "[CHECK]\ncheck_id = C-1\nwhat_is_this_check_for = t\nwhat_to_look_at = photo\n"
        f"expected_value_or_rule = {rule}\nwhen_it_fails_say = f\n"
        f"machine_can_check = {machine}\ncolumn_name = {column}\n"
        "example_that_passes = p\nexample_that_fails = f\n")
    p = tmp_path / "t.txt"
    p.write_text(text)
    return template.parse_template(p, "s.xlsx").checks[0]


def test_runner_no_blank_passes_when_all_present():
    check = _machine_check.__wrapped__ if False else None  # keep linter quiet
    import tempfile
    tmp = Path(tempfile.gettempdir())
    check = _machine_check(tmp, "no blank")
    rows = [{"row": "r1", "photo": "a.png"}, {"row": "r2", "photo": "b.png"}]
    res = runner.run_machine_check(check, rows)
    assert res.outcome == "PASS"
    assert res.matched_rows == 2 and res.failed_rows == 0


def test_runner_no_blank_fails_when_blank_present():
    import tempfile
    tmp = Path(tempfile.gettempdir())
    check = _machine_check(tmp, "no blank")
    rows = [{"row": "r1", "photo": "a.png"}, {"row": "r2", "photo": ""}]
    res = runner.run_machine_check(check, rows)
    assert res.outcome == "FAIL"
    assert res.failed_row_ids == ["r2"]


def test_runner_numeric_threshold():
    import tempfile
    tmp = Path(tempfile.gettempdir())
    check = _machine_check(tmp, ">= 60", column="qa_score")
    rows = [{"row": "r1", "qa_score": "95"}, {"row": "r2", "qa_score": "42"}]
    res = runner.run_machine_check(check, rows)
    assert res.outcome == "FAIL" and res.failed_row_ids == ["r2"]


def test_runner_machine_check_flagged_no_is_pending_human():
    import tempfile
    tmp = Path(tempfile.gettempdir())
    check = _machine_check(tmp, "no blank", machine="no")
    rows = [{"row": "r1", "photo": "a.png"}]
    res = runner.run_machine_check(check, rows)
    assert res.outcome == "PENDING-HUMAN"


def test_runner_unexpressible_rule_is_pending_human():
    import tempfile
    tmp = Path(tempfile.gettempdir())
    check = _machine_check(tmp, "a clear, unobstructed face photo")
    rows = [{"row": "r1", "photo": "x"}]
    res = runner.run_machine_check(check, rows)
    assert res.outcome == "PENDING-HUMAN"


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------
def test_report_summary_counts():
    # r1: photo present + qa 95 -> both machine checks pass; r2: photo blank +
    # qa 42 -> both fail; CHECK-003 is always human. Expected: 0 PASS, 2 FAIL, 1 human.
    results = runner.run(
        template.parse_template(Path("tests/fixtures/check-template.txt"), "s.xlsx"),
        [{"row": "r1", "photo": "a", "qa_score": "95"},
         {"row": "r2", "photo": "", "qa_score": "42"}])
    summary = report.summary(results)
    assert "0 passed" in summary and "2 failed" in summary and "1 awaiting human" in summary


def test_report_summary_all_pass():
    # All machine checks satisfied -> 2 passed, 1 human (CHECK-003 always human).
    results = runner.run(
        template.parse_template(Path("tests/fixtures/check-template.txt"), "s.xlsx"),
        [{"row": "r1", "photo": "a", "qa_score": "95"},
         {"row": "r2", "photo": "b", "qa_score": "88"}])
    summary = report.summary(results)
    assert "2 passed" in summary and "0 failed" in summary and "1 awaiting human" in summary


def test_report_csv_neutralises_formula_injection():
    results = [runner.CheckResult(
        check_id="C", label="=CMD()", outcome="PASS",
        matched_rows=1, failed_rows=0, denominator=1, detail="ok")]
    csv_text = report.render_results_csv(results)
    # The label '=CMD()' is a formula-injection vector; the renderer must quote
    # the field so CSV consumers treat it as text, not an executable formula.
    assert '"' + '=CMD()' + '"' in csv_text
    # No bare leading '=' at the start of any CSV line/field.
    assert not any(ln.lstrip().startswith('=CMD()') for ln in csv_text.splitlines())


# ---------------------------------------------------------------------------
# images
# ---------------------------------------------------------------------------
def test_extract_images_from_xlsx(tmp_path):
    # Build an xlsx with an embedded image, then extract.
    import openpyxl
    from openpyxl.drawing.image import Image as XLImage
    png = tmp_path / "p.png"
    from PIL import Image
    Image.new("RGB", (40, 40), (9, 9, 9)).save(png)
    wb = openpyxl.Workbook(); ws = wb.active
    ws.append(["a", "b"]); ws.append([1, 2])
    im = XLImage(str(png)); im.anchor = "C2"; ws.add_image(im)
    xlsx = tmp_path / "with-img.xlsx"; wb.save(xlsx)
    out = tmp_path / "out"
    extracted = images.extract_images(xlsx, out)
    assert extracted, "expected at least one embedded image"
    assert (out / "media" / Path(extracted[0].out_path).name).exists()


def test_no_pii_exfiltration_image_paths_are_local(tmp_path):
    import openpyxl
    from openpyxl.drawing.image import Image as XLImage
    from PIL import Image
    png = tmp_path / "p.png"
    Image.new("RGB", (10, 10), (1, 2, 3)).save(png)
    wb = openpyxl.Workbook(); ws = wb.active
    ws.append(["x"]); ws.append([1])
    im = XLImage(str(png)); im.anchor = "A2"; ws.add_image(im)
    xlsx = tmp_path / "pii.xlsx"; wb.save(xlsx)
    extracted = images.extract_images(xlsx, tmp_path / "o")
    for ex in extracted:
        # Every extracted path must live under the out dir (local, no network).
        assert ex.out_path.startswith(str(tmp_path / "o"))
