<template>
  <div class="editor">
    <!-- 顶部工具条 -->
    <div class="toolbar">
      <label class="tb-item">
        粒度
        <select v-model="mode" :disabled="loading" @change="reload">
          <option value="line">按行</option>
          <option value="paragraph">按段落</option>
        </select>
      </label>

      <label class="tb-item file-btn">
        上传 PDF
        <input type="file" accept="application/pdf" @change="onFile" :disabled="loading" />
      </label>

      <span class="tb-item doc-type" v-if="token">
        类型：<b>{{ docType }}</b>
        <span class="hint" v-if="docTypeHint">（{{ docTypeHint }}）</span>
      </span>

      <div class="spacer" />

      <template v-if="pages.length">
        <button @click="prev" :disabled="cur === 0">‹ 上一页</button>
        <span class="tb-item">第 {{ cur + 1 }} / {{ pages.length }} 页</span>
        <button @click="next" :disabled="cur === pages.length - 1">下一页 ›</button>
        <button class="primary" @click="save" :disabled="saving || dirtyCount === 0">
          {{ saving ? "保存中…" : `保存修改（${dirtyCount}）` }}
        </button>
        <a v-if="download" :href="download" class="dl">下载</a>
      </template>
    </div>

    <div class="warn" v-if="warn">{{ warn }}</div>

    <!-- 编辑区：页图做背景，文字块叠加 -->
    <div class="stage" v-if="pages.length" ref="stage">
      <div class="page-wrap" :style="pageWrapStyle">
        <img :src="bgUrl" class="bg" :style="bgStyle" @load="onImgLoad" />

        <div
          v-for="b in currentBlocks"
          :key="b.id"
          class="block"
          :class="{
            editing: editing?.id === b.id,
            dirty: isDirty(b.id),
            nofont: !b.can_keep_font,
          }"
          :style="blockStyle(b)"
          @dblclick="startEdit(b)"
          :title="b.can_keep_font ? '双击编辑' : '字体为子集，修改后需近似字体替代'"
        >
          {{ displayText(b) }}
        </div>

        <!-- 就地编辑输入框 -->
        <textarea
          v-if="editing"
          ref="inputEl"
          class="editor-input"
          :style="inputStyle"
          v-model="draft"
          @blur="commit"
          @keydown.esc.prevent="cancelEdit"
          @keydown.enter.ctrl.prevent="commit"
        />
      </div>
    </div>

    <div class="empty" v-else>
      <p>上传一个 PDF 开始编辑</p>
      <p class="sub">按行/按段落呈现 · 双击文字块就地修改 · 尽量保留原字体与背景</p>
    </div>

    <!-- 字体 fallback 确认弹窗 -->
    <div class="modal-mask" v-if="fallbackAsk" @click.self="cancelFallback">
      <div class="modal">
        <h4>原字体无法完整保留</h4>
        <p>该文字块用的是子集嵌入字体，新字符可能显示异常。请选择：</p>
        <div class="opts">
          <button @click="resolveFallback('fallback')">用近似字体替代（推荐）</button>
          <button @click="resolveFallback('keep')">仍尝试保留原字体</button>
          <button class="ghost" @click="resolveFallback('cancel')">取消本次编辑</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, reactive, nextTick, onUnmounted } from "vue"
import {
  uploadPdf, pageImageUrl, saveEdits, downloadUrl,
  type PageData, type TextBlock, type EditItem,
} from "./api"

const mode = ref<"line" | "paragraph">("line")
const token = ref<string | null>(null)
const filename = ref("")
const docType = ref("")
const pages = ref<PageData[]>([])
const cur = ref(0)
const loading = ref(false)
const saving = ref(false)
const download = ref<string | null>(null)
const warn = ref("")

// 当页渲染图自然尺寸（CSS px），用于把 PDF 点坐标映射到屏幕
const imgW = ref(0)
const imgH = ref(0)

// 编辑态
const editing = ref<TextBlock | null>(null)
const draft = ref("")
const inputEl = ref<HTMLTextAreaElement | null>(null)

// 改动表：id -> 新文本 / 动作
const changes = reactive<Record<string, { text: string; action: EditItem["action"]; fallback_font: string }>>({})

const currentPage = computed(() => pages.value[cur.value] ?? null)
const currentBlocks = computed(() => currentPage.value?.blocks ?? [])

const scale = computed(() => {
  const p = currentPage.value
  return p && imgW.value ? imgW.value / p.width : 1
})

const bgUrl = computed(() => (token.value ? pageImageUrl(token.value, cur.value) : ""))

const bgStyle = computed(() => ({ width: imgW.value + "px", height: imgH.value + "px" }))
const pageWrapStyle = computed(() => ({
  width: imgW.value ? imgW.value + "px" : "auto",
  height: imgH.value ? imgH.value + "px" : "auto",
}))

const dirtyCount = computed(() => Object.keys(changes).length)

const docTypeHint = computed(() => {
  const map: Record<string, string> = {
    native: "原生文字版，可保留字体",
    scanned: "纯扫描件，编辑将用近似字体",
    ocr_layer: "含 OCR 文字层，结果可能不准",
    mixed: "混合文档，按页分别处理",
  }
  return map[docType.value] ?? ""
})

function displayText(b: TextBlock) {
  return changes[b.id]?.text ?? b.text
}
function isDirty(id: string) {
  return id in changes
}

// PDF 点 -> 屏幕像素。PDF 原点在左下，页面图原点在左上，y 要翻转
function blockStyle(b: TextBlock) {
  const s = scale.value
  const ph = currentPage.value!.height
  const [x0, y0, x1, y1] = b.bbox
  const color = "#" + (b.color >>> 0).toString(16).padStart(6, "0").slice(-6)
  return {
    left: x0 * s + "px",
    top: (ph - y1) * s + "px",
    width: Math.max((x1 - x0) * s, 8) + "px",
    height: Math.max((y1 - y0) * s, 6) + "px",
    fontSize: b.size * s + "px",
    color,
    fontFamily: b.can_keep_font ? cssFont(b.font) : "sans-serif",
    lineHeight: "1.1",
  }
}

// 把 PDF 字体名转成 CSS font-family，去掉子集前缀
function cssFont(f: string) {
  return "'" + f.replace(/^[A-Za-z0-9]{6}\+/, "").replace(/["']/g, "") + "', sans-serif"
}

const inputStyle = computed(() => {
  if (!editing.value) return {}
  const st: any = blockStyle(editing.value)
  return { ...st, height: "auto", minHeight: st.height }
})

// ---- 图片尺寸测量：拿到真实渲染尺寸后才算 scale，保证叠加对齐 ----
function onImgLoad(e: Event) {
  const img = e.target as HTMLImageElement
  imgW.value = img.clientWidth
  imgH.value = img.clientHeight
}

// ---- 文件与翻页 ----
async function onFile(e: Event) {
  const f = (e.target as HTMLInputElement).files?.[0]
  if (!f) return
  filename.value = f.name
  await doUpload(f)
}

async function reload() {
  if (!lastFile) return
  await doUpload(lastFile)
}
let lastFile: File | null = null

async function doUpload(f: File) {
  lastFile = f
  loading.value = true
  warn.value = ""
  try {
    const res = await uploadPdf(f, mode.value)
    token.value = res.token
    docType.value = res.doc_type
    pages.value = res.page_data
    cur.value = 0
    download.value = null
    Object.keys(changes).forEach((k) => delete changes[k])
    editing.value = null
    imgW.value = 0
    if (res.doc_type === "scanned") {
      warn.value = "检测到扫描件：文字由 OCR 识别，编辑后会用近似字体重绘，无法还原原字体。"
    } else if (res.doc_type === "mixed") {
      warn.value = "混合文档：部分页为扫描页，那些页编辑将使用近似字体。"
    }
  } catch (err: any) {
    warn.value = err.message ?? "上传失败"
  } finally {
    loading.value = false
  }
}

function prev() {
  if (cur.value > 0) { cur.value--; editing.value = null; imgW.value = 0 }
}
function next() {
  if (cur.value < pages.value.length - 1) { cur.value++; editing.value = null; imgW.value = 0 }
}

// ---- 就地编辑 ----
function startEdit(b: TextBlock) {
  editing.value = b
  draft.value = displayText(b)
  nextTick(() => inputEl.value?.focus())
}

function cancelEdit() {
  editing.value = null
}

async function commit() {
  const b = editing.value
  if (!b) return
  editing.value = null
  const text = draft.value.trim()
  if (!text || text === b.text) {
    // 恢复原样：删掉改动
    if (text === b.text) delete changes[b.id]
    return
  }
  if (!b.can_keep_font) {
    pending = { b, text }
    fallbackAsk.value = true
    return
  }
  changes[b.id] = { text, action: "keep", fallback_font: "helv" }
}

// ---- fallback 弹窗 ----
const fallbackAsk = ref(false)
let pending: { b: TextBlock; text: string } | null = null

function resolveFallback(act: "fallback" | "keep" | "cancel") {
  if (pending) {
    if (act === "cancel") {
      delete changes[pending.b.id]
    } else {
      changes[pending.b.id] = {
        text: pending.text,
        action: act,
        fallback_font: "helv",
      }
    }
  }
  fallbackAsk.value = false
  pending = null
}
function cancelFallback() {
  fallbackAsk.value = false
  pending = null
}

// ---- 保存 ----
async function save() {
  if (!token.value) return
  saving.value = true
  warn.value = ""
  try {
    const edits: EditItem[] = Object.entries(changes).map(([id, c]) => {
      const b = allBlocks().find((x) => x.id === id)!
      return {
        id,
        page: b.page,
        old_text: b.text,
        new_text: c.text,
        action: c.action,
        fallback_font: c.fallback_font,
      }
    })
    await saveEdits(token.value, filename.value, edits)
    download.value = downloadUrl(token.value)
  } catch (err: any) {
    warn.value = err.message ?? "保存失败"
  } finally {
    saving.value = false
  }
}

function allBlocks(): TextBlock[] {
  return pages.value.flatMap((p) => p.blocks)
}

onUnmounted(() => { /* session 由后端 TTL 清理 */ })
</script>

<style scoped>
.editor { display: flex; flex-direction: column; height: 100vh; font-family: system-ui, sans-serif; }
.toolbar {
  display: flex; align-items: center; gap: 12px; padding: 10px 16px;
  background: #1f2937; color: #f9fafb; flex-wrap: wrap;
}
.tb-item { display: inline-flex; align-items: center; gap: 6px; font-size: 13px; }
.tb-item select, .file-btn input { margin-left: 4px; }
.file-btn { cursor: pointer; background: #374151; padding: 5px 10px; border-radius: 6px; }
.file-btn input { display: none; }
.spacer { flex: 1; }
.toolbar button {
  background: #374151; color: #f9fafb; border: none; padding: 6px 12px;
  border-radius: 6px; cursor: pointer; font-size: 13px;
}
.toolbar button:disabled { opacity: .45; cursor: not-allowed; }
.toolbar button.primary { background: #2563eb; }
.dl { color: #93c5fd; font-size: 13px; }
.hint { color: #9ca3af; }
.doc-type b { color: #fbbf24; }
.warn { background: #fef3c7; color: #92400e; padding: 8px 16px; font-size: 13px; }

.stage { flex: 1; overflow: auto; background: #525659; padding: 24px; }
.page-wrap { position: relative; margin: 0 auto; background: #fff; box-shadow: 0 2px 12px rgba(0,0,0,.4); }
.bg { display: block; user-select: none; -webkit-user-drag: none; }

.block {
  position: absolute; white-space: pre; cursor: text; padding: 0 1px;
  box-sizing: border-box; overflow: hidden;
  text-shadow: 0 0 2px rgba(255,255,255,.6);
}
.block:hover { outline: 1px dashed #3b82f6; background: rgba(59,130,246,.08); }
.block.dirty { outline: 1px solid #f59e0b; background: rgba(245,158,11,.12); }
.block.nofont { outline: 1px dotted #ef4444; }
.block.editing { visibility: hidden; }

.editor-input {
  position: absolute; margin: 0; padding: 0 1px; border: 2px solid #2563eb;
  outline: none; resize: none; background: #fff; box-sizing: border-box;
  font-family: inherit; line-height: 1.1; color: #111;
  box-shadow: 0 1px 4px rgba(0,0,0,.3);
}

.empty { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; color: #6b7280; }
.empty .sub { font-size: 13px; color: #9ca3af; }

.modal-mask { position: fixed; inset: 0; background: rgba(0,0,0,.45); display: flex; align-items: center; justify-content: center; }
.modal { background: #fff; padding: 22px 26px; border-radius: 10px; max-width: 420px; }
.modal h4 { margin: 0 0 8px; }
.modal p { color: #4b5563; font-size: 14px; margin: 0 0 16px; }
.modal .opts { display: flex; flex-direction: column; gap: 8px; }
.modal .opts button { padding: 9px; border: none; border-radius: 6px; background: #2563eb; color: #fff; cursor: pointer; }
.modal .opts button.ghost { background: #e5e7eb; color: #374151; }
</style>
