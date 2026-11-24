// 后端地址：开发时走 vite 代理（见 vite.config.ts），生产可改成绝对地址
const BASE = import.meta.env.VITE_API_BASE ?? ""

export interface TextBlock {
  id: string
  page: number
  text: string
  font: string
  size: number
  color: number
  bbox: [number, number, number, number]
  origin: [number, number]
  mode: "line" | "paragraph"
  can_keep_font: boolean
  is_ocr: boolean
}

export interface PageData {
  page: number
  width: number
  height: number
  blocks: TextBlock[]
}

export interface UploadResult {
  token: string
  doc_type: "native" | "scanned" | "ocr_layer" | "mixed"
  pages: number
  page_data: PageData[]
}

export interface EditItem {
  id: string
  page: number
  old_text: string
  new_text: string
  action: "keep" | "fallback" | "cancel"
  fallback_font: string
}

export async function uploadPdf(file: File, mode: string): Promise<UploadResult> {
  const fd = new FormData()
  fd.append("file", file)
  const r = await fetch(`${BASE}/api/upload?mode=${mode}`, { method: "POST", body: fd })
  if (!r.ok) throw new Error((await r.json()).detail ?? "上传失败")
  return r.json()
}

export function pageImageUrl(token: string, page: number): string {
  return `${BASE}/api/page-image/${token}/${page}`
}

export async function saveEdits(token: string, filename: string, edits: EditItem[]) {
  const r = await fetch(`${BASE}/api/save?token=${token}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ filename, edits }),
  })
  if (!r.ok) throw new Error((await r.json()).detail ?? "保存失败")
  return r.json()
}

export function downloadUrl(token: string): string {
  return `${BASE}/api/download/${token}`
}
