import chromadb
from openai import OpenAI
from sentence_transformers import SentenceTransformer
import numpy as np
import re
import json
import os
from dotenv import load_dotenv

# 載入環境變數
load_dotenv()

# --- 設定區 (改用環境變數) ---
DB_PATH = os.getenv("CHROMA_DB_PATH", "./chroma_db")
COLLECTION_NAME = "regulations_rag"
MODEL_PATH = os.getenv("EMBEDDING_MODEL_PATH", "./jina-model")

LLM_MODEL = os.getenv("VLLM_MODEL", "ISTA-DASLab/gemma-3-27b-it-GPTQ-4b-128g")
API_BASE = os.getenv("VLLM_API_BASE", "http://localhost:8000/v1")
API_KEY = os.getenv("VLLM_API_KEY", "EMPTY")

MAX_CONTEXT_CHARS = int(os.getenv("MAX_CONTEXT_CHARS", "20000"))

# 初始化 LLM Client (全域使用)
llm_client = OpenAI(base_url=API_BASE, api_key=API_KEY)

def get_keywords_via_llm(query):
    """
    【智慧核心 - 通用版】
    使用 LLM 提取搜尋關鍵字，並賦予其「聯想潛在數據指標」的能力。
    """
    system_prompt = """你是一個精準的 RAG 搜尋優化專家。
你的任務是將使用者的模糊問題，轉換為 3-8 個精確的資料庫搜尋關鍵字。

【關鍵策略】：
1. **提取實體**：抓出問題中的專有名詞（如：計畫名稱、廠商名、地名）。
2. **數據聯想 (最重要)**：
   - 如果使用者問「成果」、「亮點」、「績效」、「成效」：
     你**必須**聯想該領域常見的**量化指標詞彙**。
     - 例如問「產業亮點」 -> 需包含：產值, 金額, 成長率, 家數, 投資額
     - 例如問「教育成效」 -> 需包含：人數, 滿意度, 及格率
     - 例如問「資安表現」 -> 需包含：事件數, 攔截率, 認證數
   - 不要只輸出「亮點」這個空泛的詞，要輸出「具體的指標名稱」。

3. **格式要求**：只輸出關鍵字，用逗號分隔，不要有任何解釋。

範例輸入："請問資安跨域計畫的年度執行亮點有哪些?"
範例輸出：資安跨域計畫, 年度亮點, 產值, 投資金額, 成長率, 輔導家數, 億元

範例輸入："112年的預算執行狀況如何?"
範例輸出：112年, 預算, 執行率, 決算數, 經費, 達成率
"""

    try:
        response = llm_client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query}
            ],
            temperature=0.0, # 稍微給一點創意空間讓它聯想
            max_tokens=100
        )
        content = response.choices[0].message.content.strip()
        
        # 清洗結果
        keywords = [k.strip() for k in re.split(r'[,，、\n]+', content) if k.strip()]
        
        # 移除太短的廢字
        keywords = [k for k in keywords if len(k) > 1]
        
        print(f"擴展關鍵字: {keywords}")
        return keywords

    except Exception as e:
        print(f"LLM 提取關鍵字失敗: {e}")
        # 保底機制：如果 LLM 掛了，至少回傳原始字詞
        return [query]


def expand_keywords_by_intent(query, core_keywords):
    expanded = list(core_keywords)
    
    # 針對年份做簡單處理 (Regex 抓取 112, 113, 2024 等)
    year_matches = re.findall(r'\d{3,4}', query)
    if year_matches:
        expanded.extend(year_matches)

    # 針對「錢」的通用符號擴充 (不限產業)
    if any(k in query for k in ["金額", "經費", "預算", "產值", "營收"]):
        expanded.extend(["元", "千元", "億元", "%"])

    return list(set(expanded))

def calculate_keyword_score(query_keywords, text):
    if not text: return 0
    score = 0
    for kw in query_keywords:
        if kw in text:
            score += (len(kw) ** 2) 
    
    # 數據意圖加分
    if any(k in ["多少", "金額", "經費", "預算", "費用"] for k in query_keywords):
        digit_count = sum(c.isdigit() for c in text)
        if digit_count > 0: score += 5.0
        if any(u in text for u in ["元", "億", "萬", "人"]): score += 5.0
    return score

def advanced_reranker(query, documents, metadatas, distances, top_n=30, decay_rate=0.95, keywords=[]):
    temp_scores = []
    is_asking_result = any(k in query for k in ["成果", "績效", "亮點", "成效", "產出"])
    
    # 1. 基礎計分
    for i, (doc, meta, dist) in enumerate(zip(documents, metadatas, distances)):
        
        # 防呆檢查：若資料庫回傳 dist 為 None
        if dist is None:
            sim_score = 0.0
            safe_dist = 1.0
        else:
            sim_score = 1 - dist 
            safe_dist = dist
            
        norm_vector = max(0, min(1, sim_score))
        
        # 關鍵字加分 (確保 doc 也不為 None)
        safe_doc = doc if doc else ""
        kw_score = calculate_keyword_score(keywords, safe_doc)
        norm_kw = min(1.0, kw_score / 15.0) 
        
        # 綜合分數 (關鍵字權重 0.3, 向量 0.7)
        base_score = (norm_vector * 0.7) + (norm_kw * 0.3)
        
        safe_meta = meta if meta else {}
        doc_name = safe_meta.get("doc_name", "unknown")

        if is_asking_result:
            if any(x in doc_name for x in ["績效", "成果", "結案", "報告"]):
                base_score += 0.15  # 加分：讓報告書浮上來
            elif any(x in doc_name for x in ["計畫書", "手冊", "格式"]):
                base_score -= 0.05  # 扣分：這些通常是行政流程文件

        temp_scores.append({
            "index": i,
            "doc": safe_doc,
            "meta": safe_meta,
            "distance": safe_dist,
            "base_score": base_score,
            "doc_name": doc_name
        })

    # 2. 多樣性過濾 (Diversity Filter)
    # 先依照分數高低排序
    temp_scores.sort(key=lambda x: x["base_score"], reverse=True)

    final_results = []
    seen_docs = {}
    
    # 設定：同一份文件最多允許幾個 Chunk 排在最前面？
    MAX_CHUNKS_HEAD = 3 
    
    deferred_queue = [] # 被降權的候補區

    for item in temp_scores:
        d_name = item['doc_name']
        current_count = seen_docs.get(d_name, 0)
        
        if current_count < MAX_CHUNKS_HEAD:
            # 名額內：保持原分，直接錄取
            item['final_score'] = item['base_score']
            final_results.append(item)
            seen_docs[d_name] = current_count + 1
        else:
            # 超額：進入候補區，並給予懲罰 (Penalty)
            item['final_score'] = item['base_score'] * 0.5 
            deferred_queue.append(item)
    
    # 將降權後的項目加回來
    final_results.extend(deferred_queue)
    
    # 再次根據 final_score 排序
    final_results.sort(key=lambda x: x['final_score'], reverse=True)
    for res in final_results:
        res['score'] = res['final_score']
    # 取前 N 名
    return final_results[:top_n]

def group_and_merge_results(candidates):
    """
    1. 將屬於同一份文件 (source_doc) 的 TableItem 分組。
    2. 自動把散落的表格列合併成一個完整的表格字串。
    3. 解決 top_k 截斷導致列表不完整的問題。
    """
    if not candidates: return []
    
    # 1. 分組 (Group by source_doc)
    grouped = {} # Key: source_doc, Value: list of items
    non_table_items = []
    
    for item in candidates:
        # 檢查是否為 TableItem (或之前標記為 TableItem 的節點)
        node_type = item['meta'].get('type', item['meta'].get('label', ''))
        
        if node_type == 'TableItem':
            doc_name = item['meta'].get('source_doc', 'unknown')
            if doc_name not in grouped:
                grouped[doc_name] = []
            grouped[doc_name].append(item)
        else:
            non_table_items.append(item)
            
    final_results = []
    
    # 把非表格的直接加回來
    final_results.extend(non_table_items)
    
    # 2. 處理每一組表格資料
    for doc_name, items in grouped.items():
        # 如果只有一筆，沒什麼好合併的，直接加
        if len(items) == 1:
            final_results.extend(items)
            continue
            
        # 嘗試依 ID 排序 (假設 ID 格式包含數字，如 item_20, item_21)
        # 這能讓合併後的表格順序正確
        def get_id_num(x):
            try:
                original_id = x['meta'].get('original_id', '')
                match = re.search(r'item_(\d+)', original_id)
                return int(match.group(1)) if match else 999999
            except:
                return 999999
        
        items.sort(key=get_id_num)
        
        # 3. 合併成一個大的 Markdown 表格字串
        # max_score = max(item['score'] for item in items)
        max_score = max(item.get('score', 0.0) for item in items)
        best_meta = items[0]['meta'] # 借用第一筆的 metadata
        
        merged_doc_content = ""
        
        for item in items:
            # 移除重複的【來源文件：...】標籤 (如果有的話)，讓閱讀更順暢
            content = item['doc']
            # 簡單的正則移除開頭的標籤，避免合併後重複出現多次
            content = re.sub(r'^【來源文件：.*?】\s*', '', content)
            merged_doc_content += f"{content}\n"
            
        # 加上來源標籤一次就好
        full_content = f"【來源文件：{doc_name}】 (合併表格資料)\n{merged_doc_content}"
        
        merged_item = {
            "doc": full_content,
            "score": max_score, # 讓合併後的表格排在前面
            "meta": best_meta,
            "debug_info": f"[Merged {len(items)} Items] MaxScore: {max_score:.3f}"
        }
        # 標記為合併類型
        merged_item['meta']['type'] = 'MergedTable'
        
        final_results.append(merged_item)
        
    # 重新對所有結果排序 (包含 Article 和 MergedTable)
    final_results.sort(key=lambda x: x['score'], reverse=True)
    
    return final_results

def main():
    print(f"正在載入 Embedding 模型: {MODEL_PATH} ...")
    embed_model = SentenceTransformer(MODEL_PATH, trust_remote_code=True, device='cpu')
    
    print(f"連接向量資料庫: {DB_PATH}")
    client = chromadb.PersistentClient(path=DB_PATH)
    collection = client.get_collection(name=COLLECTION_NAME)
    
    print(f"系統準備就緒！連接 vLLM: {LLM_MODEL}")
    print("=" * 50)
    
    while True:
        query = input("\n請輸入問題 (輸入 'q' 離開): ").strip()
        if query.lower() == 'q':
            break
        if not query:
            continue
            
        print("正在搜尋相關文件...")
        
        # === Step 0: 智慧提取關鍵字 ===
        core_keywords = get_keywords_via_llm(query)
        expanded_keywords = expand_keywords_by_intent(query, core_keywords)
        expanded_keywords = expanded_keywords[:8]
        
        # === Step 1: 向量搜尋 ===
        query_vec = embed_model.encode([query]).tolist()
        vector_results = collection.query(
            query_embeddings=query_vec,
            n_results=100, # 擴大搜尋範圍，確保碎片都有被撈到
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
                    pass # 忽略錯誤

        combined_docs = [v["doc"] for v in candidates_map.values()]
        combined_metas = [v["meta"] for v in candidates_map.values()]
        combined_dists = [v["distance"] for v in candidates_map.values()]
        
        # === Step 3: 重排序 (Rerank) ===
        reranked_results = advanced_reranker(
            query, combined_docs, combined_metas, combined_dists, 
            top_n=50,       # 【關鍵】這裡取多一點 (50)，給後面的合併邏輯足夠的原料
            decay_rate=0.98,
            keywords=core_keywords
        )

        # === Step 4: 拼圖重組 (Merge Fragmentation) ===
        # 這是解決「9個項目只出現8個」的關鍵步驟
        reranked_results = group_and_merge_results(reranked_results)
        
        # === Step 5: Scope Guard (年份過濾) ===
        year_match = re.search(r"\b(1[0-9]{2})\b", query)
        if year_match and "報告" in query and ("中" in query or "依據" in query or "根據" in query):
            y = year_match.group(1)
            reranked_results = [
                r for r in reranked_results
                if y in ((r.get("meta", {}) or {}).get("source_doc", ""))
            ]
            print(f"🔒 Scope guard 啟動：限定 {y} 年相關文件")

        # === Step 6: 構建 Context ===
        context_str = ""
        current_char_count = 0
        
        print("\n--- 參考資料來源(取前5筆) ---")
        for i, res in enumerate(reranked_results):
            meta = res['meta']
            doc_content = res['doc']
            doc_name = meta.get('source_doc', '未知')
            node_type = meta.get('type', meta.get('label', '未知'))
            
            # 顯示來源標題
            if node_type == 'MergedTable':
                source_display = f"{doc_name} > [合併表格資料]"
            elif node_type == 'TableItem':
                source_display = f"{doc_name} > [表格]"
            else:
                title = meta.get('title', '').split('\n')[0]
                source_display = f"{doc_name} > {title[:15]}"
            
            # 檢查 Token 上限
            if current_char_count + len(doc_content) > MAX_CONTEXT_CHARS:
                continue 

            if i < 5:    
                print(f" {i+1}. {source_display} (分數: {res['score']:.3f}) {res['debug_info']}")
                print("-" * 35)
            
            # 如果已經是 MergedTable，doc_content 裡面已經有來源標頭了，就不用重複加
            if node_type == 'MergedTable':
                context_str += f"{doc_content}\n\n"
            else:
                context_str += f"【來源文件：{doc_name}】\n{doc_content}\n\n"
                
            current_char_count += len(doc_content)

        if not context_str:
            print("未選入任何資料。")
            continue

        # === Step 7: 生成回應 (Prompt) ===
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

        print("AI 正在思考中...")
        try:
            response = llm_client.chat.completions.create(
                model=LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=2048 
            )
            answer = response.choices[0].message.content
            print("\n" + "="*20 + " 回答 " + "="*20)
            print(answer)
            print("="*46)
        except Exception as e:
            print(f"❌ LLM 生成失敗: {e}")

if __name__ == "__main__":
    main()
