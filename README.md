# 📚 RAG Knowledge Base System

> 一套基於 **vLLM + ChromaDB + Next.js** 的RAG (Retrieval-Augmented Generation) 知識庫系統，支援多格式文件上傳、智慧問答與即時串流回覆。

![Architecture](https://img.shields.io/badge/Architecture-Microservices-blue)
![LLM](https://img.shields.io/badge/LLM-Gemma--3--27B-green)
![VectorDB](https://img.shields.io/badge/VectorDB-ChromaDB-orange)
![Frontend](https://img.shields.io/badge/Frontend-Next.js%2015-black)

---

## 📋 目錄

- [系統架構](#-系統架構)
- [功能特色](#-功能特色)
- [技術堆疊](#-技術堆疊)
- [快速開始](#-快速開始)
- [系統需求](#-系統需求)
- [部署指南](#-部署指南)
- [API 文件](#-api-文件)
- [專案結構](#-專案結構)
- [設定說明](#-設定說明)
- [常見問題](#-常見問題)

---

## 🏗️ 系統架構

```
┌─────────────────────────────────────────────────────────────┐
│                         使用者瀏覽器                          │
│                      http://localhost:3001                    │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Frontend (Next.js 15)                      │
│                     Container: rag-frontend                  │
│                        Port: 3001                            │
│  • React 18 + TypeScript                                     │
│  • Tailwind CSS                                              │
│  • SSE (Server-Sent Events) 串流接收                          │
└─────────────────────────────┬───────────────────────────────┘
                              │ HTTP / SSE
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Backend (FastAPI)                          │
│                     Container: rag-backend                   │
│                        Port: 8001                            │
│  • RAG Pipeline (query_rag_v3.py)                            │
│  • 文件轉換 (PDF/DOCX/Excel/ODS/ODT)                          │
│  • ChromaDB 向量儲存                                          │
│  • Jina Embedding Model                                      │
└─────────────────────────────┬───────────────────────────────┘
                              │ OpenAI Compatible API
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      vLLM Server                             │
│                     Container: rag-vllm                      │
│                        Port: 8000                            │
│  • Model: ISTA-DASLab/gemma-3-27b-it-GPTQ-4b-128g            │
│  • GPU Accelerated (NVIDIA)                                  │
│  • OpenAI Compatible API                                     │
└─────────────────────────────────────────────────────────────┘
```

---

## ✨ 功能特色

### 🔍 智慧問答
- **RAG 檢索增強生成**：結合向量搜尋與關鍵字搜尋的混合檢索策略
- **智慧關鍵字提取**：使用 LLM 自動從問題中提取搜尋關鍵字
- **進階重排序 (Reranking)**：多維度評分機制確保最相關內容優先
- **即時串流回覆**：透過 SSE 實現打字機效果的即時回應

### 📁 文件管理
- **多格式支援**：PDF、DOCX、XLSX、XLS、ODS、ODT、CSV
- **批次上傳**：支援最多 10 個檔案同時上傳
- **智慧 OCR**：掃描版 PDF 自動觸發 AI 視覺辨識
- **檔案刪除**：同步清除實體檔案與向量資料庫記錄

### 📊 文件處理 Pipeline
- **結構化切分 (Chunking)**：圖結構切分保留文件層次關係
- **表格智慧處理**：完整保留表格結構轉為 Markdown
- **來源追蹤**：每個 chunk 標記來源文件名稱

### 🎯 特殊功能
- **演講稿生成**：偵測「演講/致詞/講稿」關鍵字自動切換寫作模式
- **年份過濾**：自動識別查詢年份並過濾相關文件

---

## 🛠️ 模型以及版本

| 類別 | 技術 | 版本 |
|------|------|------|
| **LLM 推理** | vLLM | v0.13.0 |
| **語言模型** | Gemma-3-27B-GPTQ | 4-bit 量化 |
| **向量資料庫** | ChromaDB | v1.3.5 |
| **Embedding** | Jina Embeddings | sentence-transformers |
| **後端框架** | FastAPI | v0.123.0 |
| **前端框架** | Next.js | v15.5.9 |
| **容器化** | Docker Compose | v3.8 |
| **GPU 支援** | NVIDIA CUDA | 12.x |

---

## 🚀 快速設定

### 1️⃣ 前置準備

```bash
# 確認 Docker 與 Docker Compose 已安裝
docker --version
docker compose version

# 確認 NVIDIA Container Toolkit (GPU 支援)
nvidia-smi
docker run --rm --gpus all nvidia/cuda:12.0-base nvidia-smi
```

### 2️⃣ 複製專案

```bash
git clone <repository-url>
cd myrag
```

### 3️⃣ 準備 Embedding 模型

```bash
# 下載 Jina Embedding 模型至 ./jina-model 目錄
# 或使用您現有的模型
ls ./jina-model/
# 應包含: config.json, model.safetensors, tokenizer.json 等
```

### 4️⃣ 啟動服務

```bash
# 建構並啟動所有容器 (首次建構約需 15-30 分鐘)
docker compose up -d --build

# 觀看即時日誌
docker compose logs -f
```

### 5️⃣ 檢查服務狀態

```bash
# 確認所有容器運行中
docker compose ps

# 預期輸出:
# NAME            STATUS                   PORTS
# rag-vllm        healthy                  0.0.0.0:8000->8000/tcp
# rag-backend     healthy                  0.0.0.0:8001->8001/tcp
# rag-frontend    running                  0.0.0.0:3001->3001/tcp
```

### 6️⃣ 開始使用

開啟瀏覽器訪問：**http://localhost:3001**

---

## 💻 系統需求

### 硬體需求

| 項目 | 最低需求 | 建議配置 |
|------|----------|----------|
| **GPU** | NVIDIA RTX 3090 (24GB) | NVIDIA A100 (40GB+) |
| **VRAM** | 24GB | 40GB+ |
| **RAM** | 32GB | 64GB+ |
| **儲存空間** | 100GB SSD | 500GB NVMe SSD |
| **CPU** | 8 cores | 16+ cores |

### 軟體需求

- **作業系統**：Ubuntu 20.04+ / RHEL 8+
- **Docker**：24.0+
- **Docker Compose**：v2.20+
- **NVIDIA Driver**：535+
- **CUDA**：12.0+
- **NVIDIA Container Toolkit**：已安裝並設定

---

## 📦 部署指南

### Docker Compose 部署 (推薦)

#### 步驟 1：設定環境變數

```bash
# 建立 .env 檔案 (可選，已有預設值)
cat > .env << EOF
VLLM_MODEL=ISTA-DASLab/gemma-3-27b-it-GPTQ-4b-128g
VLLM_API_BASE=http://vllm:8000/v1
VLLM_API_KEY=EMPTY
CHROMA_DB_PATH=/app/chroma_db
EMBEDDING_MODEL_PATH=/app/jina-model
MAX_CONTEXT_CHARS=20000
EOF
```

#### 步驟 2：建構映像檔

```bash
# 建構所有服務 (首次約 15-30 分鐘)
docker compose build

# 或單獨建構特定服務
docker compose build backend
docker compose build frontend
docker compose build vllm
```

#### 步驟 3：啟動服務

```bash
# 背景啟動
docker compose up -d

# 等待 vLLM 模型載入 (可能需要 5-10 分鐘)
docker compose logs -f vllm
```

#### 步驟 4：驗證部署

```bash
# 測試 vLLM 健康狀態
curl http://localhost:8000/health

# 測試 Backend 健康狀態
curl http://localhost:8001/health

# 測試 RAG 問答
curl -X POST http://localhost:8001/stream-chat \
  -H "Content-Type: application/json" \
  -d '{"message": "你好"}'
```

### 服務管理命令

```bash
# 查看服務狀態
docker compose ps

# 查看日誌
docker compose logs -f              # 所有服務
docker compose logs -f backend      # 僅後端
docker compose logs -f vllm         # 僅 vLLM

# 重啟服務
docker compose restart backend
docker compose restart frontend

# 停止服務
docker compose down

# 完全清除 (包含 volumes)
docker compose down -v
```

---

## 📡 API 文件

### 基礎資訊

- **Base URL**: `http://localhost:8001`
- **Content-Type**: `application/json`

### 端點列表

#### `GET /health`
健康檢查

**Response:**
```json
{
  "status": "healthy",
  "service": "rag-backend"
}
```

---

#### `GET /files`
取得知識庫檔案列表

**Response:**
```json
{
  "files": ["文件1.pdf", "文件2.docx", "表格.xlsx"]
}
```

---

#### `POST /upload`
上傳檔案至知識庫

**Request:**
- Content-Type: `multipart/form-data`
- Body: `file` (binary)

**Response:**
```json
{
  "message": "檔案已接收，正在背景處理: example.pdf",
  "filename": "example.pdf",
  "status": "processing"
}
```

---

#### `GET /upload-status?filename={filename}`
查詢檔案處理狀態

**Parameters:**
- `filename` (required): URL 編碼的檔案名稱

**Response:**
```json
{
  "status": "completed",  // processing | completed | error | unknown
  "message": "處理完成！"
}
```

---

#### `DELETE /files?filename={filename}`
刪除檔案

**Parameters:**
- `filename` (required): URL 編碼的檔案名稱

**Response:**
```json
{
  "message": "檔案 example.pdf 已刪除",
  "filename": "example.pdf"
}
```

---

#### `POST /stream-chat`
RAG 問答 (串流回應)

**Request:**
```json
{
  "message": "請說明112年度的執行成果",
  "session_id": "optional-session-id",
  "temperature": 0.0,
  "max_tokens": 4096
}
```

**Response (SSE):**
```
data: {"type": "search_results", "has_knowledge": true, "knowledge_count": 15, ...}

data: {"type": "chunk", "content": "根據", ...}

data: {"type": "chunk", "content": "文件", ...}

data: [DONE]
```

---

## 📁 專案結構

```
myrag/
├── 📄 docker-compose.yml      # Docker 編排設定
├── 📄 .env                    # 環境變數設定
├── 📄 .dockerignore           # Docker 忽略規則
├── 📄 requirements.txt        # Python 依賴 (本機開發用)
│
├── 🐍 rag_server.py           # FastAPI 主程式
├── 🐍 query_rag_v3.py         # RAG 查詢邏輯
├── 🐍 build_vectordb_v3.py    # 向量資料庫建構
├── 🐍 main_pipeline_v5.py     # 文件處理管線
├── 🐍 graph_chunker_v6.py     # 圖結構切分器
│
├── 🐍 pdf_convert.py          # PDF 轉換器 (含 OCR)
├── 🐍 docx_convert.py         # DOCX 轉換器
├── 🐍 excel_convert.py        # Excel/ODS 轉換器
├── 🐍 parsing_v2.py           # ODT 解析器
├── 🐍 file_convert.py         # 檔案轉換入口
│
├── 📁 docker/                 # Docker 設定
│   ├── backend/
│   │   ├── Dockerfile         # 後端映像檔
│   │   └── requirements.txt   # 後端依賴
│   ├── frontend/
│   │   └── (Dockerfile 在 tainan-frontEnd_run/)
│   └── vllm/
│       └── Dockerfile         # vLLM 映像檔
│
├── 📁 tainan-frontEnd_run/    # Next.js 前端
│   ├── Dockerfile             # 前端映像檔
│   ├── package.json           # Node.js 依賴
│   ├── next.config.ts         # Next.js 設定
│   ├── app/
│   │   └── page.tsx           # 主頁面元件
│   └── components/            # UI 元件
│
├── 📁 jina-model/             # Embedding 模型 (需自行準備)
│   ├── config.json
│   ├── model.safetensors
│   └── tokenizer.json
│
├── 📁 chroma_db/              # 向量資料庫儲存
├── 📁 data_files/             # 上傳的原始檔案
├── 📁 processed_data/         # 處理後的中間檔案
│
└── 📁 Gemma3/                 # LLM 模型快取 (自動下載)
```

---

## ⚙️ 設定說明

### 環境變數 (.env)

| 變數名稱 | 說明 | 預設值 |
|----------|------|--------|
| `VLLM_MODEL` | vLLM 使用的模型名稱 | `ISTA-DASLab/gemma-3-27b-it-GPTQ-4b-128g` |
| `VLLM_API_BASE` | vLLM API 端點 | `http://vllm:8000/v1` |
| `VLLM_API_KEY` | API 金鑰 | `EMPTY` |
| `CHROMA_DB_PATH` | ChromaDB 儲存路徑 | `/app/chroma_db` |
| `EMBEDDING_MODEL_PATH` | Embedding 模型路徑 | `/app/jina-model` |
| `MAX_CONTEXT_CHARS` | 最大上下文字元數 | `20000` |

### Docker Compose 設定

#### vLLM 服務參數

```yaml
# docker/vllm/Dockerfile CMD 參數
--max-model-len 25000        # 最大序列長度
--gpu-memory-utilization 0.95 # GPU 記憶體使用率
--max-num-batched-tokens 4096 # 批次 token 數
--kv-cache-dtype fp8         # KV Cache 資料型態
```

#### Volume 掛載

```yaml
volumes:
  - ./chroma_db:/app/chroma_db       # 向量資料庫持久化
  - ./data_files:/app/data_files     # 上傳檔案持久化
  - ./processed_data:/app/processed_data  # 處理結果持久化
  - ./jina-model:/app/jina-model     # Embedding 模型
  - ~/.cache/huggingface:/root/.cache/huggingface  # 模型快取
```

---

## ❓ 常見問題

### Q1: vLLM 啟動失敗，顯示 CUDA out of memory

**A:** 調整 `docker/vllm/Dockerfile` 中的參數：
```dockerfile
--gpu-memory-utilization 0.85  # 降低 GPU 使用率
--max-model-len 16000          # 減少序列長度
```

### Q2: 檔案上傳後一直顯示「處理中」

**A:** 
1. 檢查後端日誌：`docker compose logs -f backend`
2. 確認 `jina-model` 目錄內有正確的模型檔案
3. 大型 PDF 處理可能需要 1-5 分鐘

### Q3: 前端無法連接後端

**A:** 
1. 確認後端健康狀態：`curl http://localhost:8001/health`
2. 檢查 CORS 設定是否正確
3. 確認防火牆未阻擋 8001 埠

### Q4: 如何更換 LLM 模型？

**A:** 
1. 修改 `docker/vllm/Dockerfile` 中的 `--model` 參數
2. 更新 `.env` 中的 `VLLM_MODEL`
3. 重新建構：`docker compose build vllm && docker compose up -d`

### Q5: 如何增加支援的檔案格式？

**A:** 
1. 在對應的轉換器 (`*_convert.py`) 中新增處理邏輯
2. 更新 `main_pipeline_v5.py` 中的 `supported_exts`
3. 重新建構後端：`docker compose build backend`

### Q6: 如何備份資料？

**A:** 備份以下目錄：
```bash
tar -czvf rag-backup.tar.gz chroma_db/ data_files/ processed_data/
```

---

## 📄 授權條款

本專案採用 MIT 授權條款。詳見 [LICENSE](LICENSE) 檔案。

---

## 🤝 貢獻指南

1. Fork 本專案
2. 建立功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交變更 (`git commit -m 'Add some AmazingFeature'`)
4. 推送至分支 (`git push origin feature/AmazingFeature`)
5. 開啟 Pull Request

---

## 📞 聯絡資訊

如有任何問題或建議，歡迎透過 Issue 提出。

---

<div align="center">

**Built with ❤️ using vLLM, ChromaDB, and Next.js**

</div>
