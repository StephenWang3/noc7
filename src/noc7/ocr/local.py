"""完全离线的 OCR：RapidOCR 随 wheel 的 ONNX 模型；Tesseract 用系统语言包。"""
from __future__ import annotations

import csv
import io
import math
import subprocess
from threading import Lock

from PIL import Image

from ..providers import ProviderConfig, ProviderKind, ensure_allowed
from ..schema.common import DataClass
from .base import LayoutBlock, LayoutResult


def _config(name: str) -> ProviderConfig:
    return ProviderConfig(name=name, kind=ProviderKind.LOCAL, external=False,
                          allowed_data=[DataClass.SYNTHETIC, DataClass.REAL])


class RapidOCRLayout:
    name = "local.rapidocr-onnx@1"

    def __init__(self) -> None:
        self.config = _config(self.name)
        self._engine = None
        self._lock = Lock()

    def read(self, image: Image.Image, data_class: DataClass) -> LayoutResult:
        ensure_allowed(self.config, data_class)
        import numpy as np
        from rapidocr_onnxruntime import RapidOCR

        # 长图切片，保留重叠区，但每个文字中心只归一片；不整图缩小到文字不可辨。
        rgb = image.convert("RGB")
        blocks = []
        with self._lock:
            if self._engine is None:
                self._engine = RapidOCR(intra_op_num_threads=1, inter_op_num_threads=1)
            step, overlap = 1280, 160
            for start in range(0, rgb.height, step):
                top, bottom = max(0, start - overlap), min(rgb.height, start + step + overlap)
                crop = rgb.crop((0, top, rgb.width, bottom))
                # RapidOCR 接收 OpenCV BGR 数组。
                result, _ = self._engine(np.asarray(crop)[:, :, ::-1].copy())
                for polygon, text, score in result or []:
                    xs, ys = zip(*polygon)
                    cx = (min(ys) + max(ys)) / 2 + top
                    if not start <= cx < min(start + step, rgb.height):
                        continue
                    bbox = (max(0, math.floor(min(xs))), max(0, math.floor(min(ys)) + top),
                            min(rgb.width, math.ceil(max(xs))), min(rgb.height, math.ceil(max(ys)) + top))
                    if text.strip() and bbox[0] < bbox[2] and bbox[1] < bbox[3]:
                        blocks.append(LayoutBlock(text=text, bbox=bbox, quality=float(score)))
        return LayoutResult(blocks=sorted(blocks, key=lambda b: (b.bbox[1], b.bbox[0], b.text)))


class TesseractLayout:
    name = "local.tesseract@1"

    def __init__(self, language: str = "chi_sim+eng", executable: str = "tesseract") -> None:
        self.config = _config(self.name)
        self.language, self.executable = language, executable

    def read(self, image: Image.Image, data_class: DataClass) -> LayoutResult:
        ensure_allowed(self.config, data_class)
        buf = io.BytesIO()
        image.convert("RGB").save(buf, format="PNG")
        result = subprocess.run([self.executable, "stdin", "stdout", "-l", self.language,
                                 "--psm", "11", "tsv"], input=buf.getvalue(),
                                capture_output=True, timeout=90, check=False)
        if result.returncode:
            raise RuntimeError("Tesseract 运行失败，请检查程序与语言包安装")
        groups: dict[tuple, list] = {}
        for word in csv.DictReader(io.StringIO(result.stdout.decode("utf-8")), delimiter="\t", quoting=csv.QUOTE_NONE):
            if word["level"] != "5" or not word.get("text", "").strip():
                continue
            key = tuple(word[k] for k in ("page_num", "block_num", "par_num", "line_num"))
            groups.setdefault(key, []).append(word)
        blocks = []
        for words in groups.values():
            x0 = min(int(w["left"]) for w in words)
            y0 = min(int(w["top"]) for w in words)
            x1 = max(int(w["left"]) + int(w["width"]) for w in words)
            y1 = max(int(w["top"]) + int(w["height"]) for w in words)
            blocks.append(LayoutBlock(text=" ".join(w["text"] for w in words), bbox=(x0, y0, x1, y1),
                                      quality=sum(max(0, float(w["conf"])) for w in words) / len(words) / 100))
        return LayoutResult(blocks=sorted(blocks, key=lambda b: (b.bbox[1], b.bbox[0])))
