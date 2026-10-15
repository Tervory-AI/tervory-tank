"""Workspace rules for Matters, Review, and feeds. No network."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_page_rules_hide_drafts_and_keys() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed on this job")
    subprocess.check_call(
        [node, "--experimental-strip-types", "tests/zenas_page_rules.mjs"],
        cwd=ROOT,
    )


def test_review_requires_the_reviewer_role_and_admission_number() -> None:
    access = (ROOT / "workspace" / "app" / "review" / "access.ts").read_text(encoding="utf-8")
    sign = (ROOT / "workspace" / "app" / "api" / "zenas" / "documents" / "[id]" / "reviews" / "route.ts").read_text(encoding="utf-8")
    assert 'role !== "reviewer"' in access
    assert "admission_no" in access
    assert "jurisdiction" in access
    assert "admissionNo" in sign
    assert "reviewerMay" in sign
    matters = (ROOT / "workspace" / "app" / "api" / "zenas" / "rules.ts").read_text(encoding="utf-8")
    assert 'doc.state !== "released"' in matters
