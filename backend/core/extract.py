"""把 PDF 每页拆成“按行”或“按段落”的可编辑文字块。

PDF 里没有天然的“段落”概念，结构只有 block -> line -> span：
- 按行  = 把同一 line 里的多个 span 合并成一行（默认，碎片少又精确）
- 按段落 = 把同一 block 里的所有 line 合并成一段

每个块都记录 bbox / origin / font / size / color，回写时才能原位对齐。
"""
import uuid
import pymupdf


def _span_color_int(color: int) -> int:
    return color


def _font_usable(font: str) -> bool:
    """子集嵌入字体名形如 'AAAAAA+Helvetica'，缺字时无法扩展，需 fallback。"""
    return not font.startswith("AAAAAA")

def _flip_bbox(bbox, page_height):
    x0, y0, x1, y1 = bbox
    return [x0, page_height - y1, x1, page_height - y0]

def extract_page(page: pymupdf.Page, page_index: int, mode: str = "line") -> list:
    blocks_out = []
    page_height = page.rect.height
    for block in page.get_text("dict")["blocks"]:
        if block["type"] != 0:      # 跳过图片块
            continue

        if mode == "paragraph":
            lines = block["lines"]
            text = " ".join(
                span["text"]
                for line in lines
                for span in line["spans"]
            ).strip()
            if not text:
                continue
            first = lines[0]["spans"][0]
            x0, y0, x1, y1 = block["bbox"]
            blocks_out.append({
                "id": uuid.uuid4().hex,
                "page": page_index,
                "text": text,
                "font": first["font"],
                "size": round(first["size"], 2),
                "color": first["color"],
                "bbox": _flip_bbox([x0, y0, x1, y1], page_height),
                "origin": list(first["origin"]),
                "mode": "paragraph",
                "can_keep_font": _font_usable(first["font"]),
                "is_ocr": False,
            })
        else:
            for line in block["lines"]:
                text = "".join(span["text"] for span in line["spans"]).strip()
                if not text:
                    continue
                first = line["spans"][0]
                x0, y0, x1, y1 = line["bbox"]
                blocks_out.append({
                    "id": uuid.uuid4().hex,
                    "page": page_index,
                    "text": text,
                    "font": first["font"],
                    "size": round(first["size"], 2),
                    "color": first["color"],
                    "bbox": _flip_bbox([x0, y0, x1, y1], page_height),
                    "origin": list(first["origin"]),
                    "mode": "line",
                    "can_keep_font": _font_usable(first["font"]),
                    "is_ocr": False,
                })

    return blocks_out
