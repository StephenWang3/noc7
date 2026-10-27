import io
from email.message import EmailMessage

from docx import Document
from PIL import Image
import pymupdf
import pytest

from noc7.ocr import LayoutResult, RapidOCRLayout
from noc7.parsers import ParseOutput, ParserRegistry, default_registry
from noc7.parsers.attachments import DOCXParser, EMLParser, ImageParser, PDFParser
from noc7.parsers.attachments.image import chart_spans
from noc7.providers import ProviderConfig, ProviderKind
from noc7.schema.common import DataClass
from noc7.schema.evidence import ChartReading, ImageSubtype, MaterialKind, ParseStatus, SpanRole, TableReading
from noc7.schema.issues import IssueCode

from .conftest import fixture_ctx


class FakeOCR:
    name = "test.layout@1"
    config = ProviderConfig(name=name, kind=ProviderKind.LOCAL, external=False,
                            allowed_data=[DataClass.SYNTHETIC, DataClass.REAL])

    def __init__(self, blocks=()):
        self.result = LayoutResult(blocks=list(blocks))

    def read(self, image, data_class):
        return self.result


@pytest.fixture(scope="module")
def images():
    ocr = RapidOCRLayout()
    parser = ImageParser(ocr=ocr)
    return {name: parser.parse(fixture_ctx(name, mid)) for name, mid in (("SYN-S10", "M04"), ("SYN-X01", "M03"))}


def test_actual_offline_qos_stats(images):
    out = images["SYN-S10"]
    assert out.status is ParseStatus.PARSED
    assert out.subtype is ImageSubtype.QOS_CHART
    charts = [s for s in out.spans if isinstance(s.reading, ChartReading)]
    observed = {r.series: (r.max, r.avg, r.min) for s in charts for r in s.reading.series}
    assert observed == {"EF": (1.4, .20, 0), "AF41": (3.1, .46, 0), "AF31": (6.2, 1.03, 0),
                        "AF21": (9.6, 1.68, 0), "AF11": (14.3, 2.75, 0), "BE": (21.8, 4.76, 0)}
    for s in charts:
        assert (s.reading.x_start, s.reading.x_end) == ("01:55", "02:47")
        assert not s.reading.timezone_shown
        assert s.reading.series[0].first_nonzero is None
        assert s.derived_from and set(s.derived_from) <= {x.id for x in out.spans}
        assert s.locator.bbox and s.quality >= .85
    assert ParseOutput.model_validate_json(out.model_dump_json()) == out


def test_actual_long_document_regions_and_table(images):
    out = images["SYN-X01"]
    assert out.subtype is ImageSubtype.DOCUMENT_COMPOSITE
    assert out.status is ParseStatus.NEEDS_REVIEW
    sections = [s for s in out.spans if "section:" in s.id]
    assert len(sections) == 4
    tables = [s.reading for s in out.spans if isinstance(s.reading, TableReading)]
    assert len(tables) == 1 and len(tables[0].rows) == 3
    text = " ".join(s.text for s in out.spans)
    assert all(key in text for key in ("2025-03-14", "20Mbps", "23.92", "22.79"))


def test_real_ocr_is_offline(monkeypatch):
    import socket
    def forbid(*args, **kwargs):
        raise AssertionError("本地 OCR 不得联网")
    monkeypatch.setattr(socket.socket, "connect", forbid)
    from PIL import ImageDraw
    image = Image.new("RGB", (400, 90), "white")
    ImageDraw.Draw(image).text((20, 20), "SYNTHETIC 123", fill="black", font_size=30)
    assert RapidOCRLayout().read(image, DataClass.REAL).blocks


def test_text_pdf_pages_and_bbox():
    out = PDFParser().parse(fixture_ctx("SYN-P04", "M03"))
    assert out.status is ParseStatus.PARSED
    assert {s.locator.page for s in out.spans} == {1, 2}
    assert all(s.locator.bbox for s in out.spans)
    assert any("市政道路施工" in s.text for s in out.spans)
    assert any("3.21 km" in s.text for s in out.spans)


@pytest.mark.parametrize("rotation", [0, 90])
def test_scanned_pdf_projection(make_ctx, rotation):
    doc = pymupdf.open()
    page = doc.new_page(width=300, height=200)
    buf = io.BytesIO()
    Image.new("RGB", (300, 200), "white").save(buf, format="PNG")
    page.insert_image(page.rect, stream=buf.getvalue())
    page.set_rotation(rotation)
    ctx = make_ctx(doc.tobytes(), MaterialKind.PDF)
    doc.close()
    ocr = FakeOCR([{"text": "合成扫描正文", "bbox": (20, 30, 100, 60), "quality": .70}])
    out = PDFParser(ocr=ocr).parse(ctx)
    assert out.status is ParseStatus.NEEDS_REVIEW
    s = out.spans[0]
    assert s.role is SpanRole.OCR_TEXT and s.locator.page == 1
    if rotation == 0:
        assert s.locator.bbox == pytest.approx((9.6, 14.4, 48, 28.8), abs=.1)
    else:
        assert s.locator.bbox[1] > 150
    assert 0 <= s.locator.bbox[0] < s.locator.bbox[2] <= 300
    assert 0 <= s.locator.bbox[1] < s.locator.bbox[3] <= 200


def test_pdf_partial_ocr_failure_preserves_other_page(make_ctx):
    doc = pymupdf.open()
    doc.new_page().insert_text((30, 40), "SYNTHETIC preserved page")
    doc.new_page()
    ctx = make_ctx(doc.tobytes(), MaterialKind.PDF)
    class Boom(FakeOCR):
        def read(self, image, data_class):
            raise RuntimeError("OCR unavailable")
    out = PDFParser(ocr=Boom()).parse(ctx)
    assert out.status is ParseStatus.NEEDS_REVIEW
    assert out.spans[0].locator.page == 1
    assert IssueCode.MATERIAL_PARSE_FAILED in {i.code for i in out.issues}


def test_actual_scanned_pdf_local_ocr(make_ctx):
    from PIL import ImageDraw
    image = Image.new("RGB", (800, 250), "white")
    ImageDraw.Draw(image).text((40, 50), "SYNTHETIC REPAIR\nService up 17:20 UTC", font_size=40, fill="black")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=125)
    page.insert_image(page.rect, stream=buffer.getvalue())
    ctx = make_ctx(doc.tobytes(), MaterialKind.PDF)
    out = PDFParser().parse(ctx)
    assert any("17:20" in s.text for s in out.spans)
    assert all(s.role is SpanRole.OCR_TEXT and s.locator.page == 1 for s in out.spans)


def test_encrypted_pdf_has_clear_failure(make_ctx):
    doc = pymupdf.open()
    doc.new_page()
    data = doc.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw="synthetic-owner", user_pw="synthetic-user")
    out = default_registry().parse(make_ctx(data, MaterialKind.PDF))
    assert out.status is ParseStatus.FAILED and "加密" in out.issues[0].message


def test_docx_cells_and_injection():
    out = DOCXParser().parse(fixture_ctx("SYN-P03", "M04"))
    assert any(s.id == "M04/tbl:0:1:1" and s.text == "-32.5 dBm" for s in out.spans)
    assert any(isinstance(s.reading, TableReading) for s in out.spans)
    instruction = [s for s in out.spans if "自动关闭工单" in s.text]
    assert instruction
    assert any(i.code is IssueCode.EMBEDDED_INSTRUCTION and instruction[0].id in i.evidence_refs for i in out.issues)


def test_docx_embedded_image_is_not_silently_lost(make_ctx):
    doc = Document()
    doc.add_paragraph("合成正文")
    image = io.BytesIO()
    Image.new("RGB", (80, 40), "white").save(image, format="PNG")
    image.seek(0)
    doc.add_picture(image)
    data = io.BytesIO()
    doc.save(data)
    out = DOCXParser().parse(make_ctx(data.getvalue(), MaterialKind.DOCX))
    assert out.status is ParseStatus.NEEDS_REVIEW
    assert out.spans[0].text == "合成正文"
    assert IssueCode.MATERIAL_UNSUPPORTED in {i.code for i in out.issues}


def test_eml_fixture_headers_body_and_signature():
    out = EMLParser().parse(fixture_ctx("SYN-P02", "M03"))
    assert out.status is ParseStatus.PARSED
    body = next(s for s in out.spans if s.role is SpanRole.ORIGINAL and s.locator.part == "body")
    assert "06 Oct 2026 14:39 UTC" in body.text
    assert "third-party civil works" in body.text
    assert any(s.role is SpanRole.SIGNATURE for s in out.spans)


def test_eml_literal_escape_compatibility_is_explicit(make_ctx):
    data = fixture_ctx("SYN-P02", "M03").read_bytes().replace(b"\r\n", b"\\r\\n")
    out = EMLParser().parse(make_ctx(data, MaterialKind.EMAIL_EML))
    assert out.status is ParseStatus.NEEDS_REVIEW
    assert "字面量转义换行" in out.issues[0].message
    assert any("06 Oct 2026 14:39 UTC" in s.text for s in out.spans)


def test_eml_mime_charset_alternative_and_attachment(make_ctx, tmp_path):
    mail = EmailMessage()
    mail["From"] = "noc@example.com"
    mail["Subject"] = "合成恢复通知"
    mail["Date"] = "Tue, 06 Oct 2026 17:30:00 +0000"
    mail.set_content("当前消息：17:20 UTC 恢复\n> 历史引用\n-- \n合成签名", charset="gb18030", cte="base64")
    mail.add_alternative("<p>重复的 HTML 消息</p>", subtype="html")
    mail.add_attachment(b"%PDF-synthetic", maintype="application", subtype="pdf", filename="../../unsafe.pdf")
    out = EMLParser().parse(make_ctx(mail.as_bytes(), MaterialKind.EMAIL_EML))
    assert out.status is ParseStatus.NEEDS_REVIEW
    assert any("合成恢复通知" in s.text for s in out.spans)
    assert any("当前消息" in s.text for s in out.spans)
    assert not any("重复的 HTML" in s.text for s in out.spans)
    assert any(s.role is SpanRole.QUOTED for s in out.spans)
    assert any(s.role is SpanRole.SIGNATURE for s in out.spans)
    assert any(i.code is IssueCode.MATERIAL_UNSUPPORTED and "unsafe.pdf" in i.message for i in out.issues)
    assert {p.name for p in tmp_path.iterdir()} == {"input.bin"}


def test_eml_html_table_and_quoted_table(make_ctx):
    mail = EmailMessage()
    mail["Subject"] = "合成 HTML 邮件"
    mail.set_content("<p>合成正文</p><blockquote><table><tr><th>编号</th></tr><tr><td>SYN-1</td></tr></table></blockquote>"
                     "<script>fetch('https://attacker.example')</script>", subtype="html")
    out = EMLParser().parse(make_ctx(mail.as_bytes(), MaterialKind.EMAIL_EML))
    tables = [s for s in out.spans if isinstance(s.reading, TableReading)]
    assert tables[0].role is SpanRole.QUOTED
    assert not any("fetch(" in s.text for s in out.spans)


def test_eml_forwarded_message_attachment_not_silently_skipped(make_ctx):
    inner = EmailMessage()
    inner["Subject"] = "合成历史邮件"
    inner.set_content("历史附件正文")
    outer = EmailMessage()
    outer["Subject"] = "合成转发邮件"
    outer.set_content("当前正文")
    outer.add_attachment(inner)
    out = EMLParser().parse(make_ctx(outer.as_bytes(), MaterialKind.EMAIL_EML))
    assert out.status is ParseStatus.NEEDS_REVIEW
    assert any("message/rfc822" in i.message for i in out.issues)


@pytest.mark.parametrize("kind,data", [(MaterialKind.PDF, b"bad pdf"), (MaterialKind.DOCX, b"bad zip"),
                                      (MaterialKind.IMAGE, b"bad png"), (MaterialKind.EMAIL_EML, b"bad eml")])
def test_corrupt_input_reports_failure(make_ctx, kind, data):
    out = default_registry().parse(make_ctx(data, kind))
    assert out.status is ParseStatus.FAILED
    assert out.issues[0].code is IssueCode.MATERIAL_PARSE_FAILED


def test_empty_and_low_quality_image_do_not_claim_success(make_ctx):
    data = io.BytesIO()
    Image.new("RGB", (100, 100), "white").save(data, format="PNG")
    ctx = make_ctx(data.getvalue(), MaterialKind.IMAGE)
    out = ImageParser(ocr=FakeOCR()).parse(ctx)
    assert out.status is ParseStatus.NEEDS_REVIEW and not out.spans
    out = ImageParser(ocr=FakeOCR([{"text": "不清晰", "bbox": (0, 0, 50, 50), "quality": .4}])).parse(ctx)
    assert out.status is ParseStatus.NEEDS_REVIEW and out.spans[0].needs_review


def test_unknown_attachment_explicitly_unsupported(make_ctx):
    out = default_registry().parse(make_ctx(b"unknown", MaterialKind.OTHER))
    assert out.status is ParseStatus.UNSUPPORTED


def test_ids_and_readings_stable(images):
    first = images["SYN-S10"]
    second = default_registry().parse(fixture_ctx("SYN-S10", "M04"))
    assert first == second


def test_chart_does_not_guess_missing_table():
    ctx = fixture_ctx("SYN-S10", "M04")
    assert chart_spans(ctx, LayoutResult(blocks=[{"text": "packet loss EF BE", "bbox": (0, 0, 100, 20), "quality": .99}]), "test") == []
