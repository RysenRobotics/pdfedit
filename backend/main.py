import os
import shutil
import uuid
from pathlib import Path

import pymupdf
from fastapi import FastAPI, UploadFile, File, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from schemas import PageData, DocInfo, SaveRequest, UploadResult
from core.extract import extract_page
from core.detect import diagnose
from core.writer import apply_edits
from core.ocr import ocr_page

app = FastAPI(title="PDF 可视编辑器 API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

BASE = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE / "/app/uploads"
OUTPUT_DIR = BASE / "/app/outputs"
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# session: token -> {path, doc, block_map}
SESSIONS: dict[str, dict] = {}


@app.get("/api/health")
def health():
    return {"ok": True}


@app.post("/api/upload", response_model=UploadResult)
async def upload(file: UploadFile = File(...), mode: str = Query("line")):
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(400, "只支持 PDF 文件")

    token = uuid.uuid4().hex
    saved = UPLOAD_DIR / f"{token}.pdf"
    with open(saved, "wb") as f:
        shutil.copyfileobj(file.file, f)

    doc = pymupdf.open(saved)
    info = diagnose(str(saved), file.filename)
    pages: list[PageData] = []
    block_map: dict[str, dict] = {}

    for i, page in enumerate(doc):
        blocks = extract_page(page, i, mode)
        if not blocks and info.doc_type in ("scanned", "mixed"):
            blocks = ocr_page(page, i)   # 扫描页：识别不了字体，只做编辑替换
        pages.append(PageData(page=i, width=page.rect.width,
                              height=page.rect.height, blocks=blocks))
        for b in blocks:
            block_map[b["id"]] = {
                "page": i, "bbox": b["bbox"], "origin": b["origin"],
                "font": b["font"], "size": b["size"], "color": b["color"],
                "can_keep_font": b["can_keep_font"],
            }

    SESSIONS[token] = {"path": str(saved), "doc": doc, "block_map": block_map}

    return UploadResult(token=token, doc_type=info.doc_type,
                        pages=len(pages), page_data=pages)


@app.get("/api/analyze", response_model=DocInfo)
def analyze(token: str):
    s = SESSIONS.get(token)
    if not s:
        raise HTTPException(404, "session 不存在，请重新上传")
    s["doc"].close()
    s["doc"] = pymupdf.open(s["path"])   # 重新打开，避免与渲染争用
    info = diagnose(s["path"], os.path.basename(s["path"]))
    return info


@app.get("/api/page-image/{token}/{page}")
def page_image(token: str, page: int, zoom: float = 1.5):
    """返回某一页的渲染图，前端拿它当背景底图。"""
    s = SESSIONS.get(token)
    if not s:
        raise HTTPException(404, "session 不存在")
    doc = s["doc"]
    if page < 0 or page >= doc.page_count:
        raise HTTPException(404, "页码越界")

    out = OUTPUT_DIR / f"{token}_p{page}.png"
    pix = doc[page].get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
    pix.save(out)
    return FileResponse(out, media_type="image/png")


@app.get("/api/page-size/{token}/{page}")
def page_size(token: str, page: int):
    s = SESSIONS.get(token)
    if not s:
        raise HTTPException(404, "session 不存在")
    r = s["doc"][page].rect
    return {"width": r.width, "height": r.height}


@app.post("/api/save")
def save(req: SaveRequest, token: str):
    s = SESSIONS.get(token)
    if not s:
        raise HTTPException(404, "session 不存在，请重新上传")

    doc: pymupdf.Document = s["doc"]
    apply_edits(doc, req.edits, s["block_map"])

    out_name = f"edited_{token}.pdf"
    out_path = OUTPUT_DIR / out_name
    doc.save(str(out_path), garbage=4, deflate=True)

    # 保存后重新打开，保证后续渲染拿到的是新内容
    doc.close()
    s["doc"] = pymupdf.open(s["path"])   # 原始仍保留，可再次编辑
    return {"ok": True, "download": f"/api/download/{token}"}


@app.get("/api/download/{token}")
def download(token: str):
    out_path = OUTPUT_DIR / f"edited_{token}.pdf"
    if not out_path.exists():
        raise HTTPException(404, "还没有保存过任何修改")
    return FileResponse(out_path, media_type="application/pdf",
                        filename="edited.pdf")


@app.exception_handler(Exception)
async def on_err(request, exc):
    return JSONResponse(status_code=500, content={"detail": str(exc)})
