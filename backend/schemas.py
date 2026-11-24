from pydantic import BaseModel
from typing import List, Literal, Optional


class TextBlock(BaseModel):
    """前端一个可编辑的文字块（默认一行）"""
    id: str
    page: int
    text: str
    font: str
    size: float
    color: int
    # PDF 用户单位坐标（1pt = 1/72 inch），左上角原点系下的 bbox
    bbox: List[float]          # [x0, y0, x1, y1]
    origin: List[float]        # 基线起点 [x, y]，回写时用
    mode: Literal["line", "paragraph"] = "line"
    can_keep_font: bool = True   # 字体是否可原样保留（False 则需 fallback）
    is_ocr: bool = False


class PageData(BaseModel):
    page: int
    width: float
    height: float
    blocks: List[dict]   # extract_page 直接产出 dict，前端按 TextBlock 结构消费


class UploadResult(BaseModel):
    token: str
    doc_type: Literal["native", "scanned", "ocr_layer", "mixed"]
    pages: int
    page_data: List[PageData]


class DocInfo(BaseModel):
    filename: str
    doc_type: Literal["native", "scanned", "ocr_layer", "mixed"]
    pages: int


class EditItem(BaseModel):
    id: str
    page: int
    old_text: str
    new_text: str
    action: Literal["keep", "fallback", "cancel"] = "keep"
    fallback_font: str = "helv"   # PyMuPDF 内置别名：helv(无衬线) / tiem(衬线)


class SaveRequest(BaseModel):
    filename: str
    edits: List[EditItem]
