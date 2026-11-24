"""把前端的编辑结果回写到 PDF。

策略：
1. 用 redact 把原文字块区域涂成背景色（先采样该块周边底色，尽量贴合原背景）
2. 用原 font / size / color / origin 在同位置重绘新文字
3. action=fallback 时用近似内置字体；action=cancel 跳过
"""
import pymupdf
from schemas import EditItem


def _sample_bg(page: pymupdf.Page, rect: pymupdf.Rect):
    """在文字块左上角外侧取一小块像素，估算背景色。取不到就返回白。"""
    try:
        pad = 2
        sample = pymupdf.Rect(rect.x0 + 1, rect.y0 - 3 - pad, rect.x0 + 12, rect.y0 - 3)
        if sample.y1 <= 0:
            sample = pymupdf.Rect(rect.x1 + 1, rect.y0, rect.x1 + 12, rect.y1)
        pix = page.get_pixmap(clip=sample, colorspace=pymupdf.csRGB)
        n = pix.width * pix.height
        if n == 0:
            return (1, 1, 1)
        r = sum(pix.samples[i] for i in range(0, len(pix.samples), 3)) / n / 255
        g = sum(pix.samples[i + 1] for i in range(0, len(pix.samples), 3)) / n / 255
        b = sum(pix.samples[i + 2] for i in range(0, len(pix.samples), 3)) / n / 255
        return (max(0, min(1, r)), max(0, min(1, g)), max(0, min(1, b)))
    except Exception:
        return (1, 1, 1)


def apply_edits(doc: pymupdf.Document, edits: list[EditItem], block_map: dict) -> str:
    """block_map: {block_id: {bbox, origin, font, size, color, page}} 由 session 提供。"""
    for e in edits:
        if e.action == "cancel":
            continue
        meta = block_map.get(e.id)
        if not meta:
            continue

        page = doc[meta["page"]]
        rect = pymupdf.Rect(meta["bbox"])
        bg = _sample_bg(page, rect)

        # 1) 覆盖原文字
        page.add_redact_annot(rect, fill=bg)
        page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE)

        # 2) 选字体名
        if e.action == "fallback":
            fontname = e.fallback_font or "helv"
        else:
            fontname = meta["font"] if meta["can_keep_font"] else "helv"

        # 3) 原色
        c = meta["color"]
        color = ((c >> 16 & 255) / 255, (c >> 8 & 255) / 255, (c & 255) / 255)

        # 4) 基线起点：用 bbox 左下角微调，比 origin 更稳
        point = (rect.x0, rect.y1 - 2)
        try:
            page.insert_text(
                point, e.new_text,
                fontname=fontname,
                fontsize=meta["size"],
                color=color,
            )
        except Exception:
            # 字体含子集前缀或不支持时，退到内置字体
            page.insert_text(point, e.new_text, fontname="helv", fontsize=meta["size"], color=color)

    return fontname
