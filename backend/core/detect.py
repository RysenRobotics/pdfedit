"""判断 PDF 是原生文字版、纯扫描件、双层 OCR 还是混合文档。

用三个信号组合，避免把扫描件当文本提取（会拿到空内容）：
1. 可见字符数
2. 文本块覆盖面积占比
3. 图片覆盖面积占比
4. 是否存在不可见文本层（render_mode=3，典型双层 OCR）
"""
import pymupdf
from schemas import DocInfo


def _classify_page(page: pymupdf.Page):
    text = page.get_text("text")
    char_count = len(text.strip())

    page_area = page.rect.width * page.rect.height or 1
    text_area = 0.0
    for b in page.get_text("blocks"):
        if b[6] == 0:  # 文本块
            x0, y0, x1, y1 = b[:4]
            text_area += max(0, x1 - x0) * max(0, y1 - y0)

    # 图片面积用页面里渲染出的绘图对象估算，比 extract_image 更贴近“视觉占比”
    image_area = 0.0
    for info in page.get_image_info(xrefs=True):
        image_area += info["bbox"].get_area() if hasattr(info["bbox"], "get_area") else 0

    has_invisible_ocr = False
    try:
        for span in page.get_texttrace():
            if span.get("type") == 3:
                has_invisible_ocr = True
                break
    except Exception:
        pass

    text_ratio = text_area / page_area
    img_ratio = min(image_area / page_area, 1.0)

    # 有足够可见字符 + 没有不可见文本层 => 原生文字版。
    # 面积占比只作辅助：稀疏页面（标题页/封面）文字占比很低但仍是文本型，
    # 所以不拿它当硬门槛，避免误判。
    if char_count >= 40 and not has_invisible_ocr:
        return "native"
    if char_count >= 40 and has_invisible_ocr:
        return "ocr_layer"
    if char_count < 40 and img_ratio > 0.4:
        return "scanned"
    return "native" if char_count >= 40 else "scanned"


def diagnose(path: str, filename: str) -> DocInfo:
    doc = pymupdf.open(path)
    types = set()
    for page in doc:
        types.add(_classify_page(page))
    doc.close()

    if types == {"native"}:
        doc_type = "native"
    elif types == {"scanned"}:
        doc_type = "scanned"
    elif types == {"ocr_layer"}:
        doc_type = "ocr_layer"
    else:
        doc_type = "mixed"

    return DocInfo(filename=filename, doc_type=doc_type, pages=len(types) or 0)
