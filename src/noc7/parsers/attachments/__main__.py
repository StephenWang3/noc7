"""A2 独立调试入口，不修改 A1 负责的 analyze 命令。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ...bundle import BundleError, load_bundle
from ...ocr import RapidOCRLayout, TesseractLayout
from ...providers.attachment_models import ReplayAttachmentProvider
from ...schema.common import DataClass
from ...schema.evidence import MaterialKind, ParseStatus
from ..base import ParseContext, ParserRegistry
from . import DOCXParser, EMLParser, ImageParser, OtherParser, PDFParser


def parse_attachments(bundle, *, ocr=None, vision=None):
    ocr = ocr if ocr is not None else RapidOCRLayout()
    registry = ParserRegistry()
    for parser in (ImageParser(ocr=ocr, vision=vision), PDFParser(ocr=ocr), DOCXParser(), EMLParser(), OtherParser()):
        registry.register(parser)
    return [registry.parse(ParseContext(bundle, material)) for material in bundle.manifest.materials
            if material.kind in {MaterialKind.IMAGE, MaterialKind.PDF, MaterialKind.DOCX, MaterialKind.EMAIL_EML, MaterialKind.OTHER}]


def main(argv=None):
    parser = argparse.ArgumentParser(description="解析工单包附件，输出兼容 A0 的 ParseOutput JSON")
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--out", type=Path, help="输出 JSON；真实数据必须写到仓库外")
    parser.add_argument("--ocr", choices=("rapidocr", "tesseract", "replay"), default="rapidocr")
    parser.add_argument("--replay-dir", type=Path)
    parser.add_argument("--strict", action="store_true", help="待复核状态也返回非零退出码")
    args = parser.parse_args(argv)
    if args.ocr == "replay" and args.replay_dir is None:
        parser.error("--ocr replay 需要 --replay-dir")
    try:
        bundle = load_bundle(args.bundle)
        repo = Path(__file__).resolve().parents[4]
        if args.out and bundle.manifest.data_class is DataClass.REAL and (repo / "pyproject.toml").exists() and args.out.resolve().is_relative_to(repo):
            raise ValueError("真实附件解析结果不能写入源码仓库")
        ocr = {"rapidocr": RapidOCRLayout, "tesseract": TesseractLayout,
               "replay": lambda: ReplayAttachmentProvider(args.replay_dir)}[args.ocr]()
        outputs = parse_attachments(bundle, ocr=ocr)
        result = {"bundle_id": bundle.manifest.bundle_id, "data_class": bundle.manifest.data_class.value,
                  "synthetic_notice": bundle.manifest.synthetic_notice,
                  "validation_scope": "仅合成样本验证，尚未验证真实 PDF/EML" if bundle.manifest.data_class is DataClass.SYNTHETIC else "本机真实材料，不得提交或外发",
                  "bundle_warnings": bundle.warnings,
                  "outputs": [o.model_dump(mode="json") for o in outputs]}
        content = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(content, encoding="utf-8")
        else:
            sys.stdout.write(content)
        bad = {ParseStatus.FAILED, ParseStatus.UNSUPPORTED}
        if args.strict:
            bad.add(ParseStatus.NEEDS_REVIEW)
        return int(any(out.status in bad for out in outputs))
    except (BundleError, ValueError, OSError) as exc:
        print(f"附件解析未完成：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
