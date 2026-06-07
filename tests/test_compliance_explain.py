"""Tests for compliance check explanation builder."""

from __future__ import annotations

from forge.utils.compliance_explain import build_check_explanations


def test_build_check_explanations_links_rule_ids():
    compliance = {
        "results": [
            {
                "module": "dengbao_2.0",
                "items": [
                    {
                        "rule_id": "db-acs-001",
                        "status": "fail",
                        "title": "身份鉴别",
                        "detail": "缺少 MFA",
                    },
                    {
                        "check_id": "chk-2",
                        "status": "pass",
                        "title": "审计",
                        "detail": "日志完整",
                    },
                ],
            }
        ]
    }
    explanations = build_check_explanations(compliance)
    assert len(explanations) == 2
    assert explanations[0]["rule_id"] == "db-acs-001"
    assert "FAIL" in explanations[0]["explanation"]
    assert explanations[1]["rule_id"] == "chk-2"


def test_build_check_explanations_empty_results():
    assert build_check_explanations({}) == []
    assert build_check_explanations({"results": []}) == []
