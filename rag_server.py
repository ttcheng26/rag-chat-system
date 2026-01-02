import json
import re
import time
import os
import shutil
from fastapi import FastAPI, Request, UploadFile, File, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
from urllib.parse import unquote
# === 引用您原始的套件 ===
import chromadb
from openai import OpenAI
from sentence_transformers import SentenceTransformer
import numpy as np

import query_rag_v3 as my_rag
import main_pipeline_v5 as pipeline
import build_vectordb_v3 as db_builder

from dotenv import load_dotenv
load_dotenv()

processing_status = {}

def process_file_background(file_location: str, filename: str):
    """背景處理檔案"""
    try:
        processing_status[filename] = {"status": "processing", "message": "正在處理中..."}
        pipeline.process_single_file(file_location, rag_builder)
        processing_status[filename] = {"status": "completed", "message": "處理完成！"}
    except Exception as e:
        processing_status[filename] = {"status": "error", "message": str(e)}

# 確保資料夾存在
if not os.path.exists(pipeline.DATA_DIR):
    os.makedirs(pipeline.DATA_DIR)

# --- 設定區  ---
DB_PATH = os.getenv("CHROMA_DB_PATH", "./chroma_db")
COLLECTION_NAME = "regulations_rag"
MODEL_PATH = os.getenv("EMBEDDING_MODEL_PATH", "./jina-model")

LLM_MODEL = os.getenv("VLLM_MODEL", "ISTA-DASLab/gemma-3-27b-it-GPTQ-4b-128g")
API_BASE = os.getenv("VLLM_API_BASE", "http://localhost:8000/v1")
API_KEY = os.getenv("VLLM_API_KEY", "EMPTY")

MAX_CONTEXT_CHARS = int(os.getenv("MAX_CONTEXT_CHARS", "20000"))
# LLM_MODEL = "RedHatAI/gemma-3-12b-it-FP8-dynamic"


# --- 初始化  ---
print(f"正在載入 Embedding 模型: {MODEL_PATH} ...")
embed_model = SentenceTransformer(MODEL_PATH, trust_remote_code=True, device='cpu')

print(f"連接向量資料庫: {DB_PATH}")
chroma_client = chromadb.PersistentClient(path=DB_PATH)
collection = chroma_client.get_collection(name=COLLECTION_NAME)

print(f"連接 vLLM: {LLM_MODEL}")
llm_client = OpenAI(base_url=API_BASE, api_key=API_KEY)

print("初始化 RAG 建庫引擎...")
rag_builder = db_builder.VectorDBBuilder(db_path=DB_PATH, model_path=MODEL_PATH)

# --- FastAPI App 設定 ---
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    temperature: Optional[float] = 0.0 # 您的原始碼設 0.0
    max_tokens: Optional[int] = 1024   # 您的原始碼設 1024

# ==========================================
# 檔案管理 API
# ==========================================
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "rag-backend"}

@app.get("/files")
def list_files():
    """列出目前知識庫中的檔案"""
    try:
        files = []
        if os.path.exists(pipeline.DATA_DIR):
            for f in os.listdir(pipeline.DATA_DIR):
                if not f.startswith('.'):
                    files.append(f)
        return {"files": files}
    except Exception as e:
        return {"error": str(e)}

@app.delete("/files")
def delete_file(filename: str = Query(..., description="要刪除的檔案名稱")):
    """刪除檔案並從向量資料庫移除"""
    decoded_filename = unquote(filename)
    print(f"[刪除] 準備刪除檔案: {decoded_filename}")
    
    try:
        file_path = os.path.join(pipeline.DATA_DIR, decoded_filename)
        
        # 1. 刪除實體檔案
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"[刪除] 已刪除檔案: {file_path}")
        else:
            print(f"[刪除] 檔案不存在: {file_path}")
            raise HTTPException(status_code=404, detail="檔案不存在")
        
        # 2. 從向量資料庫刪除相關資料
        doc_name_without_ext = os.path.splitext(decoded_filename)[0]
        
        try:
            # 嘗試用完整檔名查詢
            results = collection.get(
                where={"source_doc": {"$eq": decoded_filename}},
                include=[]
            )
            
            # 如果找不到，嘗試用不含副檔名的名稱
            if not results['ids']:
                results = collection.get(
                    where={"source_doc": {"$eq": doc_name_without_ext}},
                    include=[]
                )
            
            if results['ids']:
                collection.delete(ids=results['ids'])
                print(f"[刪除] 已從向量資料庫刪除 {len(results['ids'])} 筆資料")
            else:
                print(f"[刪除] 向量資料庫中未找到相關資料")
                
        except Exception as db_err:
            print(f"[刪除] 向量資料庫刪除警告: {db_err}")
        
        # 3. 清除處理狀態記錄
        if decoded_filename in processing_status:
            del processing_status[decoded_filename]
        
        return {"message": f"檔案 {decoded_filename} 已刪除", "filename": decoded_filename}
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"[刪除] 失敗: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload")
async def upload_file(file: UploadFile = File(...), background_tasks: BackgroundTasks = BackgroundTasks()):
    """上傳檔案並自動觸發 RAG 建庫流程（非同步）"""
    try:
        file_location = os.path.join(pipeline.DATA_DIR, file.filename)
        
        # 1. 儲存檔案
        with open(file_location, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        print(f"[上傳] 檔案已儲存: {file_location}")
        
        # 2. 設定初始狀態
        processing_status[file.filename] = {"status": "processing", "message": "檔案已接收，開始處理..."}
        print(f"[上傳] 設定狀態: {file.filename} -> processing")
        
        # 3. 背景執行 RAG 建庫
        if background_tasks:
            background_tasks.add_task(process_file_background, file_location, file.filename)
        else:
            # 同步執行作為備案
            import threading
            thread = threading.Thread(target=process_file_background, args=(file_location, file.filename))
            thread.start()
        
        return {
            "message": f"檔案已接收，正在背景處理: {file.filename}", 
            "filename": file.filename, 
            "status": "processing"
        }
    except Exception as e:
        print(f"[上傳] 處理失敗: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/upload-status")
def get_upload_status(filename: str = Query(..., description="檔案名稱")):
    """查詢檔案處理狀態"""
    # URL 解碼
    decoded_filename = unquote(filename)
    print(f"[查詢狀態] 原始: {filename}")
    print(f"[查詢狀態] 解碼後: {decoded_filename}")
    print(f"[查詢狀態] 目前狀態字典: {list(processing_status.keys())}")
    
    if decoded_filename in processing_status:
        return processing_status[decoded_filename]
    
    # 如果找不到狀態，檢查檔案是否已存在
    file_path = os.path.join(pipeline.DATA_DIR, decoded_filename)
    if os.path.exists(file_path):
        return {"status": "completed", "message": "檔案已存在"}
    
    return {"status": "unknown", "message": "找不到此檔案的處理記錄"}


@app.post("/stream-chat")
async def stream_chat(request: ChatRequest):
    
    async def event_generator():
        query = request.message
        print(f"\n[API] 收到問題: {query}")

        # === Step 0: 智慧提取關鍵字 ===
        core_keywords = my_rag.get_keywords_via_llm(query)
        expanded_keywords = my_rag.expand_keywords_by_intent(query, core_keywords)
        expanded_keywords = expanded_keywords[:8]
        
        # === Step 1: 向量搜尋 ===
        query_vec = embed_model.encode([query]).tolist()
        vector_results = collection.query(
            query_embeddings=query_vec,
            n_results=150,
            include=['documents', 'metadatas', 'distances']
        )
        
        candidates_map = {}
        if vector_results['documents']:
            for i, doc_id in enumerate(vector_results['ids'][0]):
                candidates_map[doc_id] = {
                    "doc": vector_results['documents'][0][i],
                    "meta": vector_results['metadatas'][0][i],
                    "distance": vector_results['distances'][0][i],
                    "source": "vector"
                }

        # === Step 2: 關鍵字強制搜尋 ===
        if expanded_keywords:
            for kw in expanded_keywords:
                try:
                    kw_results = collection.get(
                        where_document={"$contains": kw},
                        limit=50,
                        include=['documents', 'metadatas']
                    )
                    
                    if kw_results['ids']:
                        for i, doc_id in enumerate(kw_results['ids']):
                            if doc_id not in candidates_map:
                                candidates_map[doc_id] = {
                                    "doc": kw_results['documents'][i],
                                    "meta": kw_results['metadatas'][i],
                                    "distance": None, 
                                    "source": "keyword"
                                }
                except Exception as e:
                    pass

        combined_docs = [v["doc"] for v in candidates_map.values()]
        combined_metas = [v["meta"] for v in candidates_map.values()]
        combined_dists = [v["distance"] for v in candidates_map.values()]
        
        # === Step 3: 重排序 (Rerank) ===
        reranked_results = my_rag.advanced_reranker(
            query, combined_docs, combined_metas, combined_dists, 
            top_n=60,
            decay_rate=0.98,
            keywords=core_keywords
        )

        # === Step 4: 拼圖重組 (Merge) ===
        reranked_results = my_rag.group_and_merge_results(reranked_results)
        
        # === Step 5: Scope Guard (年份過濾) ===
        year_match = re.search(r"\b(1[0-9]{2})\b", query)
        if year_match and "報告" in query and ("中" in query or "依據" in query or "根據" in query):
            y = year_match.group(1)
            reranked_results = [
                r for r in reranked_results
                if y in ((r.get("meta", {}) or {}).get("source_doc", ""))
            ]

        # === Step 6: 構建 Context & 準備回傳前端所需的「搜尋結果」格式 ===
        context_str = ""
        current_char_count = 0
        knowledge_context = [] # 收集給前端顯示用

        print("\n--- 參考資料來源 ---")
        for i, res in enumerate(reranked_results):
            meta = res['meta']
            doc_content = res['doc']
            doc_name = meta.get('source_doc', '未知')
            node_type = meta.get('type', meta.get('label', '未知'))
            

            title = meta.get('title', doc_name)
            # 這裡簡單處理，讓前端顯示標題和一點點內容
            knowledge_context.append({
                "title": title[:30],
                "content": doc_content[:100] + "...",
                "source": doc_name
            })


            # 檢查 Token 上限 (維持您的邏輯: continue 而非 break)
            if current_char_count + len(doc_content) > MAX_CONTEXT_CHARS:
                continue 

            if i < 5:    
                print(f" {i+1}. {doc_name} (分數: {res['score']:.3f})")
            
            if node_type == 'MergedTable':
                context_str += f"{doc_content}\n\n"
            else:
                context_str += f"【來源文件：{doc_name}】\n{doc_content}\n\n"
                
            current_char_count += len(doc_content)

        search_result_chunk = {
            "type": "search_results",
            "session_id": request.session_id,
            "has_knowledge": len(knowledge_context) > 0,
            "knowledge_count": len(knowledge_context),
            "knowledge_context": knowledge_context,
            "timestamp": str(time.time())
        }
        yield f"data: {json.dumps(search_result_chunk, ensure_ascii=False)}\n\n"


        if not context_str:
            print("未選入任何資料。")
            # 這裡可以選擇直接回傳「無資料」，或者讓 LLM 自由發揮，照您原本邏輯是 continue (loop)，這裡我們讓它往下跑生成空內容的回應
            context_str = "沒有找到相關資料。"

        # === Step 7: 生成回應  ===
        is_speech_request = any(kw in query for kw in ["演講", "致詞", "講稿", "致辭", "發言稿"])

        if is_speech_request:
            print("偵測到演講稿需求...")
            prompt = f"""
<role>
你現在是某政府機關或大型企業的「幕僚長」，正在為你的首長撰寫一篇公開場合的致詞稿。
</role>

<context>
{context_str}
</context>

<style_guide>
1. **語氣設定**：穩健、自信、大器。這是要「唸出來」的稿子，請使用口語連接詞（如「各位貴賓」、「我們看到」、「這代表著」），避免生硬的公文語句。
2. **數據轉化**：將冰冷的數據轉化為故事。例如不要說「成長20%」，要說「我們成功創造了兩成的顯著成長」。
3. **格式禁忌**：**絕對禁止**使用 Markdown 標題符號 (#) 或列點符號 (-/1.)。整篇稿子必須是純文字段落。
4. **篇幅控制**：約 800 字，適合 3-5 分鐘的演說。
</style_guide>

<structure>
1. **開場 (15%)**：向在場貴賓（依據問題情境推斷）致意，點出今日主題的重要性與願景。
2. **本文 (70%)**：
   - 引用 <context> 中的具體成果（如廠商名、產值、獲獎紀錄）作為政績/業績證明。
   - 將分散的數據串聯成一個推動產業發展的故事。
   - **注意**：只能引用資料裡有的事實，不可捏造。
3. **結語 (15%)**：重申核心價值，並提出對未來的期許 (Call to Action)，以高昂的語氣結尾。
</structure>

<user_instruction>
演講主題：{query}
請依據上述架構，撰寫一份完整的逐字演講稿：
</user_instruction>
"""

        else:
            # 一般 QA 模式
            prompt = f"""
<role>
你是一位隸屬於高層決策單位的「首席情報分析師」。你的任務是基於檢索到的內部資料，提供精確、證據導向的分析報告。
</role>

<context>
{context_str}
</context>

<rules>
1. **絕對證據原則**：所有回答必須嚴格基於 <context> 內容。若資料中未提及，請直接回答「資料庫中無相關資訊」，禁止自行腦補或使用外部知識。
2. **數據精確性**：引用數據時（金額、人數、百分比），必須與原文完全一致，保留小數點與單位。
3. **實體完整性**：提到廠商、機構或專案名稱時，請列出全名，並在首次出現時使用 **粗體** 標示。
4. **排除無效資訊**：若表格數據為 "-" 或 "NA"，代表無數據，請勿將其視為 "0" 或納入統計。
5. **時間敏感度**：若資料包含多個年份（如 112年、113年），請務必在回答中標註年份。
6. **數據邏輯檢核**：若原文表格中包含「總計」或「合計」，請優先引用該數值。若你需要加總多個年份的數字，請務必先進行數學驗算；若驗算結果與原文總數不符，請回答「原文數據與總計有出入」，禁止自行修正或腦補。
</rules>

<output_format>
請直接回答使用者的問題，無需開場白（如"你好"、"根據資料"），並依照以下格式輸出：

### 🎯 核心結論
(用 2-3 句話直接回答問題的重點結論)

### 📊 詳細分析
* **[分類標題 1]**：具體說明，包含廠商名單與關鍵數據。
* **[分類標題 2]**：具體說明，包含廠商名單與關鍵數據。
(請根據內容自動分類，每個重點一段，條理分明)

### 💡 綜合評估
(總結該議題的價值、趨勢或缺口)
</output_format>

<user_query>
{query}
</user_query>
"""

        try:
            # 使用串流 (Stream) 回傳給前端，但參數照舊
            stream = llm_client.chat.completions.create(
                model=LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=4096,
                stream=True 
            )

            for chunk in stream:
                content = chunk.choices[0].delta.content
                if content:
                    # 包裝成前端要的格式 (Yellow highlight)
                    resp_chunk = {
                        "type": "chunk",
                        "content": content,
                        "session_id": request.session_id,
                        "timestamp": str(time.time())
                    }
                    yield f"data: {json.dumps(resp_chunk, ensure_ascii=False)}\n\n"

            # 結束訊號
            yield f"data: [DONE]\n\n"

        except Exception as e:
            print(f"LLM 生成失敗: {e}")
            err_chunk = {
                "type": "error", 
                "error": str(e), 
                "timestamp": str(time.time())
            }
            yield f"data: {json.dumps(err_chunk, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)