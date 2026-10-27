"""附件审核提出的角色、消息定位和闸门传播回归。全部内容为合成。"""
import io
import json
from dataclasses import replace
from email.message import EmailMessage

from PIL import Image
import pymupdf
import pytest

from noc7.parsers import ParserRegistry
from noc7.parsers.attachments import EMLParser, PDFParser
from noc7.parsers.attachments.__main__ import main, parse_attachments
from noc7.providers import EgressBlocked, ProviderConfig, ProviderKind
from noc7.schema.common import DataClass
from noc7.schema.evidence import MaterialKind, ParseStatus, SpanRole, TableReading


def parse_mail(make_ctx, content, subtype="plain"):
    mail = EmailMessage()
    mail["Subject"] = "合成审核回归"
    mail.set_content(content, subtype=subtype)
    return EMLParser().parse(make_ctx(mail.as_bytes(), MaterialKind.EMAIL_EML))


@pytest.mark.parametrize("content,expected", [
    ("> 历史记录：17:20 已恢复\n当前反馈：18:00 仍未恢复", "18:00 仍未恢复"),
    ("当前反馈\nFrom: 本次测试源\n故障时间：18:10", "18:10"),
    ("Best regards, 故障时间：18:20", "18:20"),
    ("Kind regards, 故障时间：18:30", "18:30"),
    ("Disclaimer 故障时间：18:40", "18:40"),
    ("Best regards,\n故障时间：18:50", "18:50"),
])
def test_current_message_returns_to_original(make_ctx, content, expected):
    out = parse_mail(make_ctx, content)
    evidence = next(s for s in out.spans if expected in s.text)
    assert out.status is ParseStatus.PARSED
    assert evidence.role is SpanRole.ORIGINAL
    assert evidence.locator.message_index == 0 and evidence.id.startswith("M03/msg:0:")
    if "From:" in content:
        assert not any(s.role is SpanRole.QUOTED for s in out.spans)


def test_only_quotes_increment_signature_stays_current(make_ctx):
    out = parse_mail(make_ctx, "> 旧观测一\n当前反馈一\n> 旧观测二\nBest regards,\n当前反馈二")
    quotes = [s for s in out.spans if s.role is SpanRole.QUOTED]
    assert [s.locator.message_index for s in quotes] == [1, 2]
    signature = next(s for s in out.spans if s.role is SpanRole.SIGNATURE)
    assert signature.locator.message_index == 0 and signature.id.startswith("M03/msg:0:")
    for evidence in out.spans:
        if "当前反馈" in evidence.text:
            assert evidence.role is SpanRole.ORIGINAL and evidence.locator.message_index == 0


def test_forward_headers_require_group_and_do_not_capture_following_body(make_ctx):
    out = parse_mail(make_ctx, "From: noc@example.com\nSubject: 合成历史头\n当前反馈：仍未恢复")
    quoted = next(s for s in out.spans if s.role is SpanRole.QUOTED)
    assert "From:" in quoted.text and "Subject:" in quoted.text
    current = next(s for s in out.spans if "仍未恢复" in s.text)
    assert current.role is SpanRole.ORIGINAL and current.locator.message_index == 0


def test_html_tables_share_quote_groups_with_body(make_ctx):
    out = parse_mail(make_ctx, "<p>&gt; 纯文本引用</p><p>当前正文</p>"
        "<blockquote><p>历史甲</p><table><tr><th>甲</th></tr><tr><td>17:20</td></tr></table>"
        "<blockquote><p>嵌套甲</p></blockquote></blockquote>"
        "<p>当前表</p><table><tr><td>本次</td></tr></table>"
        "<blockquote><p>历史乙</p><table><tr><td>乙</td></tr></table></blockquote>", "html")
    for label, expected_index in (("历史甲", 2), ("历史乙", 3)):
        body = next(s for s in out.spans if s.locator.part == "body" and label in s.text)
        table = next(s for s in out.spans if isinstance(s.reading, TableReading)
                     and s.reading.headers == ["甲" if label == "历史甲" else "乙"])
        assert body.role is table.role is SpanRole.QUOTED
        assert body.locator.message_index == table.locator.message_index == expected_index
        assert table.id.startswith(f"M03/msg:{expected_index}:tbl:")
    current = next(s for s in out.spans if isinstance(s.reading, TableReading) and s.reading.headers == ["本次"])
    assert current.role is SpanRole.ORIGINAL and current.locator.message_index == 0
    assert next(s for s in out.spans if "嵌套甲" in s.text).locator.message_index == 2


def test_empty_quoted_html_table_does_not_crash(make_ctx):
    out = parse_mail(make_ctx, "<p>当前正文</p><blockquote><table><tr><td></td></tr></table></blockquote>", "html")
    assert out.status is ParseStatus.PARSED


def test_pdf_egress_rejection_fails_whole_material_and_cli(make_ctx, monkeypatch, capsys):
    # 只有运行时合成 PDF 被标记为 real；不使用或保存真实工单。
    with pymupdf.open() as doc:
        doc.new_page().insert_text((30, 40), "SYNTHETIC text layer")
        image = io.BytesIO()
        Image.new("RGB", (100, 100), "white").save(image, format="PNG")
        page = doc.new_page()
        page.insert_image(page.rect, stream=image.getvalue())
        ctx = make_ctx(doc.tobytes(), MaterialKind.PDF)
    manifest = ctx.bundle.manifest.model_copy(update={"data_class": DataClass.REAL,
                                                     "materials": [ctx.material]})
    bundle = replace(ctx.bundle, manifest=manifest)
    ctx = replace(ctx, bundle=bundle)

    class ExternalOCR:
        name = "test.external"
        config = ProviderConfig(name=name, kind=ProviderKind.OPENAI_COMPATIBLE, external=True)
        calls = 0

        def read(self, image, data_class):
            self.calls += 1
            raise AssertionError("真实分级不应进入外部 OCR")

    ocr = ExternalOCR()
    parser = PDFParser(ocr=ocr)
    with pytest.raises(EgressBlocked, match="禁止把 real"):
        parser.parse(ctx)
    registry = ParserRegistry()
    registry.register(parser)
    out = registry.parse(ctx)
    assert out.status is ParseStatus.FAILED and not out.spans
    assert "EgressBlocked" in out.issues[0].message and "禁止把 real" in out.issues[0].message
    assert ocr.calls == 0
    monkeypatch.setattr("noc7.parsers.attachments.__main__.load_bundle", lambda *args: bundle)
    monkeypatch.setattr("noc7.parsers.attachments.__main__.parse_attachments",
                        lambda b, **kwargs: parse_attachments(b, ocr=ocr))
    assert main(["unused"]) == 1  # 默认模式也必须失败，无需 --strict。
    assert json.loads(capsys.readouterr().out)["outputs"][0]["status"] == "failed"
