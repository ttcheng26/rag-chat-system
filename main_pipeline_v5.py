import os
import sys
import json
import hashlib
import shutil 

# --- import funciton modules ---
import parsing_v2 as parser      # ODT -> MD
import graph_chunker_v6 as chunker  # MD -> JSON
import build_vectordb_v3 as db_builder # JSON -> ChromaDB
import pdf_convert                  # PDF -> MD 
import excel_convert                # Excel/ODS -> MD
import docx_convert

# --- 設定區 ---
DATA_DIR = "./data_files"
PROCESSED_DIR = "./processed_data" 
TEMP_DATA_DIR = os.path.join(PROCESSED_DIR, "temp_data")

def process_single_file(filepath, builder):
    filename = os.path.basename(filepath)
    file_ext = os.path.splitext(filename)[1].lower()
    
    print(f"\n========================================")
    print(f"開始處理: {filename}")
    print(f"========================================")

    md_content = ""
    
    # --- 1. 解析階段 (Parsing) ---
    try:
        # A. 如果是 PDF
        if file_ext == '.pdf':
            print("偵測到 PDF，啟動 pdf_convert 引擎...")
            md_content = pdf_convert.smart_process_pdf(filepath)

        # B. 如果是 Word (Doc/Docx)
        elif file_ext == '.docx':
                    print(f"偵測到 DOCX，啟動 docx_convert...")
                    md_content = docx_convert.parse_docx_to_markdown(filepath)

        # C. 如果是 ODT
        elif file_ext == '.odt':
            print("偵測到 ODT 檔，開始解析")
            md_content = parser.parse_full_document(filepath)


        # D. [新增] 如果是 Excel / ODS / CSV
        elif file_ext in ['.xlsx', '.xls', '.ods', '.csv']:
            print("偵測到試算表檔案，啟動 excel_convert 引擎...")
            md_content = excel_convert.excel_to_markdown(filepath)
            
            # 簡單檢查回傳是否為錯誤訊息
            if md_content.startswith("錯誤") or md_content.startswith("處理失敗"):
                print(md_content)
                return
            
        else:
            print(f"不支援的格式: {file_ext}")
            return

        # 檢查解析結果
        if not md_content:
            print("解析結果為空，跳過後續步驟。")
            return

        print(f"解析完成 (長度: {len(md_content)} 字)")
        
        # 備份 Markdown 
        md_filename = os.path.join(PROCESSED_DIR, filename + ".md")
        with open(md_filename, "w", encoding="utf-8") as f:
            f.write(md_content)

    except Exception as e:
        print(f"解析階段發生錯誤: {e}")
        import traceback
        traceback.print_exc()
        return

    # --- 2. 切分階段 (Chunking) ---
    try:
        print("正在進行結構化切分 (Chunking)...")
        # 去掉副檔名作為文件標題
        doc_title = os.path.splitext(filename)[0]
        graph_data = chunker.parse_markdown_to_graph(md_content, doc_name=doc_title)
        
        print(f"切分完成: {len(graph_data['nodes'])} 個節點")

        # 備份 JSON
        json_filename = os.path.join(PROCESSED_DIR, filename + ".json")
        with open(json_filename, "w", encoding="utf-8") as f:
            json.dump(graph_data, f, ensure_ascii=False, indent=2)

    except Exception as e:
        print(f"切分階段發生錯誤: {e}")
        return

    # --- 3. ID 處理 ---
    # 因為我們要呼叫 builder.ingest_graph_data，所以要在傳入前先把 ID 弄成唯一的
    try:
        # print("正在為節點生成唯一 ID...")
        file_hash = hashlib.md5(filename.encode()).hexdigest()[:6]
        id_mapping = {}

        for node in graph_data['nodes']:
            old_id = node['id']
            # 格式: hash_原ID (例如: a1b2c_sec_01)
            new_id = f"{file_hash}_{old_id}"
            node['id'] = new_id
            id_mapping[old_id] = new_id
        
        # 更新邊 (Edge) 的 source/target
        for edge in graph_data['edges']:
            edge['source'] = id_mapping.get(edge['source'], edge['source'])
            edge['target'] = id_mapping.get(edge['target'], edge['target'])

    except Exception as e:
        print(f"ID 處理失敗: {e}")
        return

    # --- 4. 建庫階段 (Ingestion) ---
    # 回歸 V3 邏輯：直接交給模組處理，模組內有 batch_size=10 的保護機制
    try:
        print("正在寫入向量資料庫 (ChromaDB)...")
        builder.ingest_graph_data(graph_data)
        print("寫入成功！")

    except Exception as e:
        print(f"建庫階段發生錯誤: {e}")

def main():
    # 建立必要資料夾
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        print(f"已建立資料夾: {DATA_DIR}，請將檔案放入此處。")
        return
    
    if not os.path.exists(PROCESSED_DIR):
        os.makedirs(PROCESSED_DIR)
    
    if not os.path.exists(TEMP_DATA_DIR):
        os.makedirs(TEMP_DATA_DIR)

    # 0. 詢問是否重置資料庫
    reset = input("是否重置資料庫 (刪除舊資料)? (y/n): ").strip().lower()
    if reset == 'y':
        print("正在清除舊資料庫內容...")
        db_folder = "./chroma_db"
        
        if os.path.exists(db_folder):
            for filename in os.listdir(db_folder):
                file_path = os.path.join(db_folder, filename)
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.unlink(file_path) # 刪除檔案
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path) # 刪除子資料夾
                except Exception as e:
                    print(f"略過佔用檔: {filename}")
        
        print("資料庫內容清理完成")

    print("初始化 VectorDB Builder...")
    builder = db_builder.VectorDBBuilder()
    
    # 支援的副檔名 
    supported_exts = ('.odt', '.docx', '.pdf', '.xlsx', '.xls', '.ods', '.csv')
    files = [f for f in os.listdir(DATA_DIR) if f.lower().endswith(supported_exts)]
    
    if not files:
        print(f"資料夾 {DATA_DIR} 內沒有支援的檔案")
        return

    print(f"發現 {len(files)} 個檔案，準備開始批次處理...")

    for f in files:
        full_path = os.path.join(DATA_DIR, f)
        process_single_file(full_path, builder)

    print("\n所有檔案處理完成！")

if __name__ == "__main__":
    main()