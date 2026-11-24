# PDF 可视编辑器（FastAPI + Vue3）

上传 PDF → 按行/按段落显示在页面上 → 双击就地编辑 → 回写并下载，尽量保留原字体与背景色。

## 启动
```bash
docker compose up --build
```
- 前端 http://localhost:5173  后端文档 http://localhost:8000/docs （后端端口未对外映射，仅在容器网络内）
- 本机开发：后端 `cd backend && pip install -r requirements.txt && uvicorn backend.main:app --reload --port 8000`（在项目根目录执行）；
  前端 `cd frontend && npm install && npm run dev`，vite 代理默认指向 `http://localhost:8000`，docker 内指向 `http://backend:8000`（见 vite.config.ts）。

## 已验证
- 后端上传/分析/页图/保存/下载全链路测试通过；编辑 `1001.00 → 2048.00` 回写后旧文本消失、新文本可搜到。
- 前端因沙盒网络限制**未做浏览器实测**，首次运行请重点检查叠加层对齐。

## 已知限制
- 会话存在进程内存里，重启即失效；单点写入，多进程需换 Redis。
- 子集嵌入字体缺字时只能近似替代；回写单块超长文本不会自动换行。
- 扫描件 OCR 需容器内安装 tesseract 及 chi_sim/eng 语言包，当前 Dockerfile 未包含。
- 保存后再次保存基于原始文件，只保留最后一次的编辑。
