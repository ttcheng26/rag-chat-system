import json
import os
import chromadb
from chromadb import Documents, EmbeddingFunction, Embeddings
from sentence_transformers import SentenceTransformer
from tqdm import tqdm
import torch

# --- 設定區 ---
JSON_PATH = "graph_data_final.json"
MODEL_PATH = "./jina-model"  
DB_PATH = "./chroma_db"      
COLLECTION_NAME = "regulations_rag"

def split_text_by_window(text, chunk_size=800, overlap=100):
    """
    簡單的滑動視窗切分：
    將長字串切成多個長度約 chunk_size 的片段，
    每個片段之間保留 overlap 重疊，以免切斷關鍵詞。
    """
    if len(text) <= chunk_size:
        return [text]
    
    chunks = []
    start = 0
    total_len = len(text)
    
    while start < total_len:
        end = start + chunk_size
        # 截取一段
        chunk = text[start:end]
        chunks.append(chunk)
        
        # 如果已經到底了，就結束
        if end >= total_len:
            break
            
        # 下一段的起點要往前縮 (overlap)，製造重疊
        start += (chunk_size - overlap)
        
    return chunks

class LocalJinaEmbeddingFunction(EmbeddingFunction):
    def __init__(self, model_path):
        self.model = SentenceTransformer(model_path, trust_remote_code=True, device='cpu')

        # 靜態量化 
        try:
            self.model = torch.quantization.quantize_dynamic(
                self.model, {torch.nn.Linear}, dtype=torch.qint8
            )
        except Exception as e:
            print(f"量化失敗: {e}")

    def __call__(self, input: Documents) -> Embeddings:
        # Chroma 會呼叫這個函式來計算向量
        # 我們轉成 list 回傳，並確保是 float 格式
        embeddings = self.model.encode(input).tolist()
        return embeddings

def build_parent_map(graph_data):
    parent_map = {} 
    nodes_by_id = {n['id']: n for n in graph_data['nodes']}
    
    for edge in graph_data['edges']:
        source_id = edge['source']
        target_id = edge['target']
        label = edge['label']
        if label in ["HAS_ITEM", "HAS_ARTICLE"]:
            parent_map[target_id] = source_id
            
    return parent_map, nodes_by_id

def serialize_node(node, parent_map, nodes_by_id):
    node_id = node['id']
    label = node['label']
    props = node['properties']
    
    # --- [新增] 1. 往上追溯最頂層 Document 節點，抓取檔名 ---
    # 目的：解決 112年 vs 113年 內容混淆問題，強制將檔名寫入 Embeddings
    doc_name = ""
    curr_id = node_id
    
    # 設定一個安全迴圈上限
    depth_limit = 10 
    while curr_id in parent_map and depth_limit > 0:
        parent_id = parent_map[curr_id]
        parent_node = nodes_by_id.get(parent_id)
        
        # 如果找到了 Document 類型的節點，就抓它的 name
        if parent_node and parent_node.get('label') == 'Document':
            doc_name = parent_node['properties'].get('name', '')
            break
            
        curr_id = parent_id
        depth_limit -= 1
    # -----------------------------------------------------

    # --- [原有邏輯] 2. 抓取父節點與祖父節點作為上下文 ---
    context_text = ""
    parent_id = parent_map.get(node_id)
    if parent_id:
        parent_node = nodes_by_id.get(parent_id)
        if parent_node:
            p_title = parent_node['properties'].get('title', '') or parent_node['properties'].get('name', '')
            context_text = f"[{p_title}] " + context_text
            grandparent_id = parent_map.get(parent_id)
            if grandparent_id:
                gp_node = nodes_by_id.get(grandparent_id)
                if gp_node:
                    gp_name = gp_node['properties'].get('name', '')
                    context_text = f"[{gp_name}] " + context_text

    # --- [修正內文邏輯] 3. 處理內文 ---
    text_content = ""
    if label == "Document":
        # 🟢 【修正點】：把 "法規名稱" 改成 "文件名稱"
        text_content = f"文件名稱: {props.get('name', '')}"
        
    elif label == "Article":
        text_content = f"{props.get('title', '')} {props.get('content', '')}"
        text_content = text_content.replace("關聯表格資料已轉化為 TableItem 子節點", "")
        
    elif label == "TableItem":
        parts = []
        for k, v in props.items():
            if not v or v.strip() == "---": continue
            clean_key = k.split('_')[0]
            clean_val = str(v).replace('\n', '，').replace('<br>', '，')
            parts.append(f"{clean_key}: {clean_val}")
        text_content = " ".join(parts)

    # --- [修改] 4. 組合最終文字 ---
    # 如果有抓到檔名（代表是子節點），就強制加在最前面
    if doc_name:
        final_text = f"【來源文件：{doc_name}】 {context_text} {text_content}".strip()
    else:
        # 如果沒抓到檔名（代表它自己就是根節點，或是孤兒），就直接用 context + text
        final_text = f"{context_text} {text_content}".strip()
        
    return final_text

# def serialize_node(node, parent_map, nodes_by_id):
#     node_id = node['id']
#     label = node['label']
#     props = node['properties']
    
#     context_text = ""
#     parent_id = parent_map.get(node_id)
#     if parent_id:
#         parent_node = nodes_by_id.get(parent_id)
#         if parent_node:
#             p_title = parent_node['properties'].get('title', '') or parent_node['properties'].get('name', '')
#             context_text = f"[{p_title}] " + context_text
#             grandparent_id = parent_map.get(parent_id)
#             if grandparent_id:
#                 gp_node = nodes_by_id.get(grandparent_id)
#                 if gp_node:
#                     gp_name = gp_node['properties'].get('name', '')
#                     context_text = f"[{gp_name}] " + context_text

#     text_content = ""
#     if label == "Document":
#         text_content = f"法規名稱: {props.get('name', '')}"
#     elif label == "Article":
#         text_content = f"{props.get('title', '')} {props.get('content', '')}"
#         text_content = text_content.replace("關聯表格資料已轉化為 TableItem 子節點", "")
#     elif label == "TableItem":
#         parts = []
#         for k, v in props.items():
#             if not v or v.strip() == "---": continue
#             clean_key = k.split('_')[0]
#             clean_val = str(v).replace('\n', '，').replace('<br>', '，')
#             parts.append(f"{clean_key}: {clean_val}")
#         text_content = " ".join(parts)

#     final_text = f"{context_text} {text_content}".strip()
#     return final_text

class VectorDBBuilder:
    def __init__(self, db_path="./chroma_db", model_path="./jina-model", collection_name="regulations_rag"):
        print(f"初始化 ChromaDB: {db_path}")
        self.client = chromadb.PersistentClient(path=db_path)
        
        print(f"正在載入 Embedding 模型: {model_path}")
        self.ef = LocalJinaEmbeddingFunction(model_path)
        
        # 取得或建立 Collection (不刪除舊資料！)
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=self.ef
        )

    def reset_collection(self):
        """如果想要清空資料庫，呼叫此函式"""
        try:
            self.client.delete_collection(self.collection.name)
            self.collection = self.client.create_collection(
                name=self.collection.name,
                embedding_function=self.ef
            )
            print("資料庫已清空")
        except:
            pass

    def ingest_graph_data(self, graph_data):
        """將單一份圖譜資料寫入資料庫"""
        print("建立節點關聯索引...")
        parent_map, nodes_by_id = build_parent_map(graph_data)

        # 【修正 1】 這裡統一使用 ids, documents, metadatas
        ids = []
        documents = []
        metadatas = []

        nodes = graph_data['nodes']
        if not nodes: return

        print(f"處理 {len(nodes)} 個節點...")
        
        for node in nodes:
            if not node.get('properties'): continue
            
            # 1. 5000字過濾 (針對 Section)
            if node['label'] == 'Section':
                raw_text = node['properties'].get('content') or node['properties'].get('full_content') or node['properties'].get('text') or ""
                if len(str(raw_text)) > 5000:
                    continue

            # 2. 序列化
            serialized_text = serialize_node(node, parent_map, nodes_by_id)
            if not serialized_text.strip():
                continue       
            
            # --- [開始修改] 加入「切片」邏輯 ---
            
            # 【修正 2】 迴圈內統一 append 到 ids, documents, metadatas
            if len(serialized_text) <= 1000:
                # === A. 短節點直接加入 ===
                ids.append(node['id'])
                documents.append(serialized_text)
                
                # 準備 metadata
                source_name = 'unknown'
                for n_id, n_data in nodes_by_id.items():
                     if n_data.get('label') == 'Document':
                         source_name = n_data.get('properties', {}).get('name', 'unknown')
                         break
                meta = {
                    "type": node['label'],
                    "label": node['label'],
                    "original_id": node['id'],
                    "source_doc": source_name,
                    "is_chunked": False
                }
                if node['label'] == 'Article':
                    meta['title'] = node['properties'].get('title', '')[:50]
                metadatas.append(meta)

            else:
                # === B. 長節點進行切分 ===
                print(f"  發現長節點 {node['id']} (長度 {len(serialized_text)})，進行切分...")
                sub_chunks = split_text_by_window(serialized_text, chunk_size=800, overlap=100)
                
                for i, chunk in enumerate(sub_chunks):
                    # 1. ID 加上後綴
                    new_id = f"{node['id']}_part_{i}"
                    ids.append(new_id)
                    
                    # 2. 內容是切分後的小片段
                    documents.append(chunk)
                    
                    # 3. Metadata 複製並標記
                    source_name = 'unknown'
                    for n_id, n_data in nodes_by_id.items():
                         if n_data.get('label') == 'Document':
                             source_name = n_data.get('properties', {}).get('name', 'unknown')
                             break
                    
                    
                    meta = {
                        "type": node['label'],
                        "label": node['label'],
                        "original_id": node['id'],
                        "source_doc": source_name,
                        "chunk_index": i,
                        "is_chunked": True
                    }
                    if node['label'] == 'Article':
                        meta['title'] = node['properties'].get('title', '')[:50]
                    metadatas.append(meta)
            
            # --- [修改結束] ---

        # 【修正 3】 寫入時變數名稱現在對應得上了
        batch_size = 10
        total = len(documents)
        print(f"準備寫入 {total} 筆資料...")
        
        for i in tqdm(range(0, total, batch_size), desc="向量建庫進度"):
            end = min(i + batch_size, total)
            self.collection.add(
                ids=ids[i:end],
                documents=documents[i:end],
                metadatas=metadatas[i:end]
            )

        print(f"已寫入 {total} 筆資料")


if __name__ == "__main__":
    # 這是單檔測試用的
    with open("graph_data_final.json", 'r', encoding='utf-8') as f:
        data = json.load(f)
    builder = VectorDBBuilder()
    builder.reset_collection() # 單檔測試時先清空
    builder.ingest_graph_data(data)