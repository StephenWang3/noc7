from __future__ import annotations

import io
import re

from PIL import Image

from ...ocr import LayoutBlock, LayoutResult, RapidOCRLayout
from ...providers.attachment_models import read_layout, describe_image
from ...schema.evidence import ChartReading, ChartSeriesStat, ImageRegionLocator, ImageSubtype, MaterialKind, SpanRole, TableReading
from ..base import ParseContext
from .common import QUALITY_THRESHOLD, finish, read_limited, span


def open_image(data: bytes) -> Image.Image:
    with Image.open(io.BytesIO(data)) as image:
        if getattr(image, "n_frames", 1) > 1:
            raise ValueError("多帧图片暂不支持，请拆分为独立材料后导入")
        if image.width * image.height > 25_000_000:
            raise ValueError("图片超过 2500 万像素本地解析上限")
        image.load()
        # 保持文件中像素坐标，不做隐式 EXIF 旋转。
        return image.convert("RGB")


def union(blocks: list[LayoutBlock]) -> tuple[int, int, int, int]:
    return (min(b.bbox[0] for b in blocks), min(b.bbox[1] for b in blocks),
            max(b.bbox[2] for b in blocks), max(b.bbox[3] for b in blocks))


def rows(blocks: list[LayoutBlock]) -> list[list[LayoutBlock]]:
    result: list[list[LayoutBlock]] = []
    for b in sorted(blocks, key=lambda b: ((b.bbox[1] + b.bbox[3]) / 2, b.bbox[0])):
        center = (b.bbox[1] + b.bbox[3]) / 2
        if result:
            last = result[-1]
            previous = sum((x.bbox[1] + x.bbox[3]) / 2 for x in last) / len(last)
            tolerance = max(4, min(b.bbox[3] - b.bbox[1], last[0].bbox[3] - last[0].bbox[1]) * 0.55)
            if abs(center - previous) <= tolerance:
                last.append(b)
                continue
        result.append([b])
    return [sorted(r, key=lambda b: b.bbox[0]) for r in result]


def classify(layout: LayoutResult, image: Image.Image) -> ImageSubtype:
    text = " ".join(b.text for b in layout.blocks).lower()
    compact = re.sub(r"\s+", "", text)
    if re.search(r"packet\s*loss|丢包", text) and re.search(r"\b(?:EF|AF[1-4][1-3]|BE)\b", text, re.I):
        return ImageSubtype.QOS_CHART
    if any(t in compact for t in ("deliveryconfirmation", "acceptancetest", "交付确认", "验收", "确认书")):
        return ImageSubtype.DOCUMENT_COMPOSITE
    if re.search(r"(?:ping|traceroute|tracert|destination|ttl=|bytes from|命令提示符)", text):
        return ImageSubtype.TERMINAL_SCREENSHOT
    if re.search(r"site\s*photo|现场照片", text) and image.height < image.width * 1.5:
        return ImageSubtype.SITE_PHOTO
    if image.height > image.width * 1.8 and len(layout.blocks) >= 10:
        return ImageSubtype.DOCUMENT_COMPOSITE
    return ImageSubtype.OTHER


def chart_spans(ctx: ParseContext, layout: LayoutResult, name: str):
    """只转录可见统计表；不用曲线像素推断精确均值、首非零或时区。"""
    grouped = rows(layout.blocks)
    headers = None
    header_y = -1
    for row in grouped:
        labels = " ".join(b.text for b in row).lower()
        if all(re.search(p, labels) for p in (r"class|类别", r"max|最大", r"avg|平均", r"min|最小")):
            headers, header_y = row, max(b.bbox[3] for b in row)
            break
    if headers is None:
        return []
    # 读取列顺序，避免把 Min/Max 互换的表误读。
    labels = [re.sub(r"\s+", "", b.text.lower()) for b in headers]
    if len(labels) != 4 or not re.search(r"class|类别", labels[0]):
        return []
    mapping = []
    for label in labels[1:]:
        mapping.append(next((key for key, pattern in (("max", r"max|最大"), ("avg", r"avg|平均"),
                                                      ("min", r"min|最小")) if re.search(pattern, label)), ""))
    if set(mapping) != {"max", "avg", "min"}:
        return []
    text = " ".join(b.text for b in layout.blocks)
    if not re.search(r"%|percent|百分", text, re.I):
        return []  # 单位不明不猜成百分比。
    times = []
    for row in grouped:
        # 横轴标签应在同一行，排除标题、正文中的时间。
        values = re.findall(r"\b(?:[01]\d|2[0-3]):[0-5]\d\b", " ".join(b.text for b in row))
        if len(values) >= 2:
            times = values
            break
    output = []
    seen = set()
    for row in grouped:
        if min(b.bbox[1] for b in row) < header_y - 2:
            continue
        line = " ".join(b.text for b in row)
        match = re.fullmatch(r"\s*(EF|AF[1-4][1-3]|BE|CS[0-7])\s+"
                             r"(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)\s*", line, re.I)
        if not match or match[1].upper() in seen:
            continue
        values = dict(zip(mapping, map(float, match.groups()[1:])))
        if not (0 <= values["min"] <= values["avg"] <= values["max"] <= 100):
            continue
        series = match[1].upper()
        seen.add(series)
        quality = min(b.quality for b in [*headers, *row])
        reading = ChartReading(metric="丢包率", unit="%", x_start=times[0] if times else None,
                               x_end=times[-1] if times else None,
                               timezone_shown=bool(re.search(r"UTC|GMT|时区", text, re.I)),
                               series=[ChartSeriesStat(series=series, **values)])
        output.append(span(ctx, f"img:chart:{series}", f"统计表原文：{line}",
                           ImageRegionLocator(bbox=union(row)), name, role=SpanRole.VISUAL_OBSERVATION,
                           reading=reading, quality=quality, needs_review=quality < QUALITY_THRESHOLD,
                           derived_from=[f"{ctx.material.id}/img:r{i}" for i, b in enumerate(layout.blocks)
                                         if b in row or b in headers]))
    return output


def document_spans(ctx: ParseContext, layout: LayoutResult, name: str, image: Image.Image):
    """按可见标题分区并保留验收表，区域含义是材料类型，不是故障结论。"""
    grouped = rows(layout.blocks)
    result = []
    headings = []
    for row in grouped:
        text = " ".join(b.text for b in row)
        compact = re.sub(r"\s+", "", text.lower())
        if any(key in compact for key in ("deliveryconfirmation", "acceptancetestrecord", "sitephoto:",
                                          "speedtest-", "交付确认", "验收测试", "现场照片")):
            headings.append((union(row)[1], text))
    for i, (top, heading) in enumerate(headings):
        bottom = headings[i + 1][0] if i + 1 < len(headings) else image.height
        result.append(span(ctx, f"img:section:{i}", "区域标题（OCR）：“" + heading + "”；区域内容与本次故障的关系待审核",
                           ImageRegionLocator(bbox=(0, top, image.width, bottom)), name,
                           role=SpanRole.VISUAL_OBSERVATION, quality=0.7, needs_review=True))
    for i, header in enumerate(grouped):
        labels = [re.sub(r"\s+", "", b.text.lower()) for b in header]
        if len(labels) != 3 or labels != ["testitem", "result", "verdict"]:
            continue
        body = []
        blocks = list(header)
        last_bottom = union(header)[3]
        for row in grouped[i + 1:]:
            if len(row) != len(header) or union(row)[1] - last_bottom > 60:
                break
            body.append([b.text for b in row])
            blocks.extend(row)
            last_bottom = union(row)[3]
        if body:
            quality = min(b.quality for b in blocks)
            result.append(span(ctx, f"img:table:{i}", "\n".join(" | ".join(r) for r in [[b.text for b in header], *body]),
                               ImageRegionLocator(bbox=union(blocks)), name,
                               role=SpanRole.VISUAL_OBSERVATION, quality=quality,
                               needs_review=quality < QUALITY_THRESHOLD,
                               reading=TableReading(headers=[b.text for b in header], rows=body)))
    return result


class ImageParser:
    name = "a2.image@0.1"
    kinds = frozenset({MaterialKind.IMAGE})

    def __init__(self, ocr=None, vision=None):
        self.ocr = ocr if ocr is not None else RapidOCRLayout()
        self.vision = vision

    def parse(self, ctx: ParseContext):
        image = open_image(read_limited(ctx))
        layout = read_layout(self.ocr, image, ctx.bundle.manifest.data_class)
        subtype = classify(layout, image)
        spans = [span(ctx, f"img:r{i}", b.text, ImageRegionLocator(bbox=b.bbox), self.ocr.name,
                      role=SpanRole.OCR_TEXT, quality=b.quality, needs_review=b.quality < QUALITY_THRESHOLD)
                 for i, b in enumerate(layout.blocks)]
        readings = chart_spans(ctx, layout, self.name) if subtype is ImageSubtype.QOS_CHART else []
        spans.extend(readings)
        if subtype is ImageSubtype.DOCUMENT_COMPOSITE:
            spans.extend(document_spans(ctx, layout, self.name, image))
        notes = ["图片坐标为文件像素坐标。规则分类；OCR 分数不等于业务结论置信度。"]
        if self.vision is not None:
            observation = describe_image(self.vision, image, ctx.bundle.manifest.data_class)
            subtype = observation.subtype
            for i, region in enumerate(observation.regions):
                spans.append(span(ctx, f"img:vision:{i}", region.text, ImageRegionLocator(bbox=region.bbox),
                                  self.vision.name, role=SpanRole.VISUAL_OBSERVATION, reading=region.reading,
                                  quality=region.quality, needs_review=region.needs_review or region.quality < QUALITY_THRESHOLD))
        if subtype is ImageSubtype.QOS_CHART:
            notes.append("统计来自可见表格；未测量曲线像素，first_nonzero 留空，不能等同起障时间。")
        if subtype is ImageSubtype.DOCUMENT_COMPOSITE:
            notes.append("文档/照片/测速拼图按 OCR 区域保留；历史交付信息不自动证明本次故障已恢复或已定责。")
        # 图例有六类却只读出五类也不能标记为完整。
        legend = set(re.findall(r"\b(?:EF|AF[1-4][1-3]|BE|CS[0-7])\b", " ".join(b.text for b in layout.blocks), re.I))
        read_series = {s.series for s in spans if isinstance(s.reading, ChartReading) for s in s.reading.series}
        incomplete = subtype is ImageSubtype.QOS_CHART and (not read_series or not {s.upper() for s in legend} <= read_series)
        return finish(ctx, self.name, spans, subtype=subtype,
                      review=subtype in (ImageSubtype.OTHER, ImageSubtype.SITE_PHOTO) or incomplete,
                      note=" ".join(notes))
