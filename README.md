# Enterprise RAG Knowledge Base System (Gemma-27B Edition)

這是一套RAG (Retrieval-Augmented Generation) 知識庫問答系統。
整合了 **vLLM** 高效推論引擎、**ChromaDB** 向量資料庫與 **Next.js** 前端介面，並採用客製化的圖譜切分技術 (Graph Chunking) 與多樣性重排序 (Diversity Reranking) 機制，解決長文件檢索的精準度問題。

## 功能特色

* **高效能推論**：內建 `vLLM` 引擎，部署 `Gemma-3-27B-IT (GPTQ)` 量化模型，在 GPU 上實現快速回應。
* **高精度檢索**：
    * **混合搜尋**：結合語意向量 (Vector) 與關鍵字 (Keyword) 搜尋。
    * **智慧重排序**：內建多樣性過濾 (Diversity Filter)，避免單一文件佔據所有上下文。
    * **意圖識別**：自動偵測「績效/成果」類問題，優先權重相關報告數據。
* **結構化建庫**：支援 PDF、Word、Excel 自動解析，採用圖譜式切分與上下文補強技術。
* **串流回應**：前端支援 Server-Sent Events (SSE) 文字串流，提供類似 ChatGPT 的即時體驗。

## 系統架構

系統由三個 Docker 容器微服務組成：

| 服務 | 容器名稱 | 端口 | 說明 |
| :--- | :--- | :--- | :--- |
| **Frontend** | `rag-frontend` | **3001** | Next.js 使用者介面 |
| **Backend** | `rag-backend` | **8001** | FastAPI 後端，負責 RAG 邏輯與 ChromaDB 操作 |
| **LLM Engine** | `rag-vllm` | **8080** | vLLM 伺服器 (內部溝通 port 8000) |

---

## 下載與安裝執行 (Installation & Execution)

### 1. 環境先決條件 (Prerequisites)
在開始之前，請確保主機滿足以下要求：
* **作業系統**: Linux (推薦 Ubuntu 20.04/22.04)
* **GPU**: NVIDIA GPU (VRAM 建議 **24GB** 以上，如 RTX 3090/4090 或 A6000)
* **驅動程式**: 已安裝 NVIDIA Driver 與 **NVIDIA Container Toolkit** (以支援 Docker 調用 GPU)。
* **Docker**: Docker Engine 24.0+ 與 Docker Compose。

### 2. 專案設定
* 取得專案後
```
git clone <您的 Git Repository 網址>
cd rag-chat-system
```

* 請建立 `.env` 設定檔：

```bash
# 建立環境變數檔
touch .env

#請將以下內容填入 .env
# --- LLM 設定 ---
# 指定 vLLM 內部服務位置
VLLM_API_BASE=http://vllm:8000/v1
VLLM_API_KEY=EMPTY
# 使用的模型名稱 (需與 docker-compose 內一致)
VLLM_MODEL=ISTA-DASLab/gemma-3-27b-it-GPTQ-4b-128g

# --- RAG 與路徑設定 ---
CHROMA_DB_PATH=/app/chroma_db
# 使用 HuggingFace 線上模型 ID (系統會自動下載並 Cache)
EMBEDDING_MODEL_PATH=jinaai/jina-embeddings-v3
# 上下文長度限制
MAX_CONTEXT_CHARS=20000
```

### 3. 啟動服務
執行以下指令啟動所有容器。 注意：首次啟動時，系統會自動下載 Gemma-27B 模型 (約 20GB) 與 Jina Embedding 模型，請依網路速度耐心等待。
```
docker compose up -d
```
* 檢查狀態：請確保 rag-vllm 服務狀態變為 (healthy)。
```
docker compose ps
docker compose logs -f vllm
```
### 4. 建立知識庫

#### 快速上傳大批檔案
服務啟動後，資料庫預設是空的。請依照以下步驟匯入資料。
* 準備檔案：將你的 PDF、Word、Excel 檔案放入專案根目錄的 data_files/ 資料夾。
* 執行建庫腳本：進入後端容器執行自動化建庫。
```
# 進入後端容器執行建庫主程式
docker compose exec backend python main_pipeline_v5.py
```

### 5. 重啟後端
由於 rag-backend 在啟動時會將資料庫索引載入記憶體，在外部執行完建庫後，必須重啟後端服務，讓它讀取最新的資料。
```
docker compose restart backend
```

完成上述步驟後，即可透過瀏覽器訪問系統：

使用者介面: http://localhost:3001

### 常用維護指令
* 查看後端日誌 (除錯用)：
```
docker compose logs -f backend
```
* 停止服務
```
docker compose down
```
* 清理所有資料 (慎用)： 若需徹底重來（包含移除資料庫），請刪除 chroma_db 資料夾內容
```
sudo rm -rf chroma_db/*
```
