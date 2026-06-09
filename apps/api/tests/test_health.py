"""
CargoIQ API — Health check tests.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

# Patch supabase before importing app
with patch("supabase.create_client", return_value=MagicMock()):
    from main import app

client = TestClient(app)


def test_root():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "CargoIQ API"
    assert data["status"] == "operational"


def test_health():
    with patch("apps.api.core.supabase_client.get_supabase_admin") as mock_admin:
        mock_admin.return_value.table.return_value.select.return_value.limit.return_value.execute.return_value = MagicMock()
        response = client.get("/health")
        assert response.status_code in (200, 503)


def test_compliance_shield_vat_sacu():
    """Test SACU VAT calculation (no markup)."""
    from apps.api.services.compliance_service import check_sacu_vat
    result = check_sacu_vat({
        "origin_country": "ZA",
        "invoice_value": 10000,
        "currency": "ZAR"
    })
    assert result.result == "pass"
    assert result.detail["is_sacu_origin"] is True
    assert result.detail["markup_applied_pct"] == 0.0


def test_compliance_shield_vat_non_sacu():
    """Test non-SACU VAT calculation (10% markup applied)."""
    from apps.api.services.compliance_service import check_sacu_vat
    result = check_sacu_vat({
        "origin_country": "CN",
        "invoice_value": 10000,
        "currency": "USD"
    })
    assert result.result == "pass"
    assert result.detail["is_sacu_origin"] is False
    assert result.detail["markup_applied_pct"] == 10.0
    assert result.detail["calculated_atv_pre_duties"] == 11000.0


def test_hs_code_validator_valid():
    from apps.api.services.compliance_service import check_hs_code_format
    result = check_hs_code_format({"hs_code_primary": "84713000"})
    assert result.result == "pass"


def test_hs_code_validator_invalid_7_digits():
    from apps.api.services.compliance_service import check_hs_code_format
    result = check_hs_code_format({"hs_code_primary": "8471300"})
    assert result.result == "fail"
    assert result.penalty_risk is True


def test_hs_code_validator_missing():
    from apps.api.services.compliance_service import check_hs_code_format
    result = check_hs_code_format({"hs_code_primary": None})
    assert result.result == "hold"
    assert result.penalty_risk is True
