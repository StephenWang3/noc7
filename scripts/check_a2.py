"""用现有合成工单包复现 A2 验收；只读 fixtures/bundles，不修改 A0 样本。"""
from __future__ import annotations

import argparse
import json
from importlib.metadata import version
from pathlib import Path

from noc7.bundle import load_bundle
from noc7.ocr import RapidOCRLayout, TesseractLayout
from noc7.parsers import ParseContext
from noc7.parsers.attachments.__main__ import parse_attachments
from noc7.parsers.attachments.image import ImageParser, open_image
from noc7.providers.attachment_models import image_digest, read_layout
from noc7.schema.common import DataClass
from noc7.schema.evidence import ChartReading, MaterialKind, ParseStatus, TableReading

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {"EF": [1.4, .20, 0], "AF41": [3.1, .46, 0], "AF31": [6.2, 1.03, 0],
            "AF21": [9.6, 1.68, 0], "AF11": [14.3, 2.75, 0], "BE": [21.8, 4.76, 0]}


def stats(out):
    return {r.series: [r.max, r.avg, r.min] for s in out.spans if isinstance(s.reading, ChartReading)
            for r in s.reading.series}


def main():
    parser = argparse.ArgumentParser(description="生成仅限合成附件的验收记录")
    parser.add_argument("--out", type=Path, default=ROOT / "evals/a2/verification.json")
    parser.add_argument("--compare-tesseract", action="store_true", help="需本机已装 Tesseract 与中英文语言包")
    parser.add_argument("--record-replay", type=Path, help="可选：把合成 PNG 的本地 OCR 结果录制到指定目录")
    args = parser.parse_args()
    ocr = RapidOCRLayout()
    result = {"validation_scope": "仅合成材料；尚未用真实 PDF/EML 验证；未调用外部模型",
              "versions": {p: version(p) for p in ("rapidocr-onnxruntime", "onnxruntime", "pymupdf", "python-docx", "pillow")},
              "materials": [], "qos": {"expected": EXPECTED}}
    failed = False
    for path in sorted((ROOT / "fixtures/bundles").iterdir()):
        bundle = load_bundle(path)
        if bundle.manifest.data_class is not DataClass.SYNTHETIC:
            raise ValueError("验收脚本只允许合成材料")
        outputs = parse_attachments(bundle, ocr=ocr)
        for out in outputs:
            material = bundle.manifest.material(out.material_id)
            result["materials"].append({"bundle_id": bundle.manifest.bundle_id, "material_id": out.material_id,
                "sha256": material.sha256, "kind": material.kind.value, "status": out.status.value,
                "subtype": out.subtype.value if out.subtype else None, "span_count": len(out.spans),
                "located_span_count": sum(getattr(s.locator, "bbox", None) is not None or s.locator.type in ("doc_block", "email_message") for s in out.spans),
                "table_count": sum(isinstance(s.reading, TableReading) for s in out.spans),
                "issues": [i.code.value for i in out.issues]})
            failed = failed or out.status in (ParseStatus.FAILED, ParseStatus.UNSUPPORTED)
            if path.name == "SYN-S10" and material.kind is MaterialKind.IMAGE:
                observed = stats(out)
                result["qos"].update(observed=observed, matched_values=sum(
                    v == EXPECTED[k][i] for k, values in observed.items() if k in EXPECTED for i, v in enumerate(values)),
                    expected_values=18, first_nonzero="未测量，留空", timezone_shown=False)
                failed = failed or observed != EXPECTED
                if args.compare_tesseract:
                    baseline = ImageParser(ocr=TesseractLayout()).parse(ParseContext(bundle, material))
                    result["tesseract_baseline"] = {"status": baseline.status.value, "observed": stats(baseline),
                        "note": "未读出的统计留空；不将 OCR 的 218 自动改成 21.8"}
            if args.record_replay and material.kind is MaterialKind.IMAGE:
                image = open_image(bundle.read_bytes(material.id))
                layout = read_layout(ocr, image, DataClass.SYNTHETIC)
                args.record_replay.mkdir(parents=True, exist_ok=True)
                (args.record_replay / f"{image_digest(image)}.ocr.json").write_text(layout.model_dump_json(indent=2) + "\n", encoding="utf-8")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"合成附件验收记录已写入 {args.out}；{'存在失败' if failed else '通过'}")
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
