import pytest
from pydantic import ValidationError

from noc7.providers import EgressBlocked, ProviderConfig, ensure_allowed
from noc7.schema import DataClass


def test_external_provider_defaults_to_synthetic_only():
    minimax = ProviderConfig(name="minimax", kind="openai_compatible", external=True)
    ensure_allowed(minimax, DataClass.SYNTHETIC)
    with pytest.raises(EgressBlocked):
        ensure_allowed(minimax, DataClass.REAL)


def test_external_real_requires_approval_reference():
    with pytest.raises(ValidationError, match="approval_ref"):
        ProviderConfig(name="x", kind="openai_compatible", external=True, allowed_data=["synthetic", "real"])
    ProviderConfig(name="x", kind="openai_compatible", external=True, allowed_data=["synthetic", "real"],
                   approval_ref="docs/decisions/0099-approved.md")


def test_local_provider_may_take_real_data():
    local = ProviderConfig(name="rules", kind="rules", external=False, allowed_data=["synthetic", "real"])
    ensure_allowed(local, DataClass.REAL)
