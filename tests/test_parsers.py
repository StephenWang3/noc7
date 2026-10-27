import pytest
from pydantic import ValidationError

from noc7.bundle import load_bundle
from noc7.parsers import PARSER_OWNERSHIP, ParseContext, ParseOutput, ParserRegistry
from noc7.schema import EvidenceSpan, FieldLocator, IssueCode, MaterialKind, ParseStatus

from .conftest import BUNDLES


def _ctx(material_id="M04", name="SYN-S10"):
    b = load_bundle(BUNDLES / name)
    return ParseContext(bundle=b, material=b.manifest.material(material_id))


def test_every_material_kind_has_an_owner():
    assert set(PARSER_OWNERSHIP) == set(MaterialKind)
    assert set(PARSER_OWNERSHIP.values()) == {"A1", "A2"}


def test_unimplemented_kind_is_reported_not_skipped():
    out = ParserRegistry().parse(_ctx())
    assert out.status is ParseStatus.UNSUPPORTED
    assert out.issues[0].code is IssueCode.MATERIAL_UNSUPPORTED


class _Img:
    name = "test.image@0"
    kinds = frozenset({MaterialKind.IMAGE})

    def parse(self, ctx):
        return ParseOutput(material_id=ctx.material.id, parser=self.name, status=ParseStatus.PARSED,
                           spans=[EvidenceSpan(id=f"{ctx.material.id}/img", material_id=ctx.material.id,
                                               locator={"type": "image_region"}, text="chart", extractor=self.name)])


class _Boom(_Img):
    def parse(self, ctx):
        raise RuntimeError("decoder crashed")


def test_duplicate_registration_is_rejected():
    reg = ParserRegistry()
    reg.register(_Img())
    with pytest.raises(ValueError, match="已由"):
        reg.register(_Boom())


def test_parser_crash_becomes_failed_status():
    reg = ParserRegistry()
    reg.register(_Boom())
    out = reg.parse(_ctx())
    assert out.status is ParseStatus.FAILED and out.issues[0].code is IssueCode.MATERIAL_PARSE_FAILED


def test_registered_parser_output():
    reg = ParserRegistry()
    reg.register(_Img())
    assert reg.parse(_ctx()).spans[0].id == "M04/img"


def test_parser_cannot_emit_spans_for_other_materials():
    with pytest.raises(ValidationError, match="越界"):
        ParseOutput(material_id="M04", parser="x", status=ParseStatus.PARSED,
                    spans=[EvidenceSpan(id="M01/f:cause", material_id="M01", locator=FieldLocator(field_key="cause"),
                                        text="x", extractor="x")])


def test_default_registry_works_before_a1_and_a2_land():
    from noc7.parsers import default_registry

    out = default_registry().parse(_ctx())
    assert out.status in (ParseStatus.UNSUPPORTED, ParseStatus.PARSED, ParseStatus.NEEDS_REVIEW, ParseStatus.FAILED)
