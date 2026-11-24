"""扫描件 OCR：识别文字与位置，字体无法识别，仅完成编辑替换。"""
import uuid
import pymupdf


def ocr_page(page: pymupdf.Page, page_index: int, dpi: int = 200) -> list:
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return []

    pix = page.get_pixmap(dpi=dpi, alpha=False)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    data = pytesseract.image_to_data(img, lang="chi_sim+eng",
                                     output_type=pytesseract.Output.DICT)

    scale = 72.0 / dpi  # 像素 -> PDF 点
    rows: dict[int, list] = {}
    for i, text in enumerate(data["text"]):
        if not str(text).strip() or int(data["conf"][i] or -1) < 40:
            continue
        top = data["top"][i]
        rows.setdefault(top // 8, []).append(i)

    blocks = []
    for key, idxs in rows.items():
        idxs.sort(key=lambda i: data["left"][i])
        parts = [str(data["text"][i]).strip() for i in idxs]
        text = " ".join(parts)
        if not text:
            continue
        x0 = min(data["left"][i] for i in idxs) * scale
        y0 = min(data["top"][i] for i in idxs) * scale
        x1 = max(data["left"][i] + data["width"][i] for i in idxs) * scale
        y1 = max(data["top"][i] + data["height"][i] for i in idxs) * scale
        h = max(1, y1 - y0)
        blocks.append({
            "id": uuid.uuid4().hex,
            "page": page_index,
            "text": text,
            "font": "OCR",
            "size": round(h * 0.8, 2),
            "color": 0,
            "bbox": [x0, y0, x1, y1],
            "origin": [x0, y1 - 2],
            "mode": "ocr",
            "can_keep_font": False,   # 字体识别不了，编辑时让用户选近似字体或取消
            "is_ocr": True,
        })
    return blocks
