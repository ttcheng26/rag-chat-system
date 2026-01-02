import re
import json
import os

def uniquify_headers(headers):
    counts = {}
    
    # 統計出現次數
    for h in headers:
        clean_h = h.strip()
        if not clean_h: clean_h = "Col" # 空白表頭給預設值
        counts[clean_h] = counts.get(clean_h, 0) + 1
    
    new_headers = []
    current_counts = {}
    
    # 生成唯一 Key
    for h in headers:
        clean_h = h.strip()
        if not clean_h: clean_h = "Col"
        
        current_counts[clean_h] = current_counts.get(clean_h, 0) + 1
        
        # 如果有名稱重複，加上 _1, _2
        if counts[clean_h] > 1: 
            new_headers.append(f"{clean_h}_{current_counts[clean_h]}")
        else: 
            # 這裡直接回傳 clean_h，它包含了 (千元)
            new_headers.append(clean_h)
            
    return new_headers

def looks_like_header(cols):
    # 1. 欄位太少通常不是正規表格
    if len(cols) < 2: return False
    
    # 2. 關鍵字加分 (包含常見表頭詞彙)
    header_keywords = [
        "名稱", "金額", "單位", "日期", "編號", "備註", "說明", "合計", "總計", 
        "數量", "項目", "年度", "摘要", "歸屬", "來源", "成果", "對象", "預算",
        "內容", "執行", "辦理", "地點"
    ]
    
    keyword_hits = sum(1 for c in cols if any(k in c for k in header_keywords))
    
    # 3. 數字含量檢查 & 年份豁免檢查
    digit_cols = 0
    year_cols = 0 
    
    for c in cols:
        clean_c = c.strip()
        # 檢查是否包含數字
        if re.search(r'\d', c):
            digit_cols += 1
    
            # 條件：純數字，且介於 100-120 (民國年) 或 2020-2030 (西元年)
            if re.match(r'^(1[0-1][0-9]|202[0-9])$', clean_c):
                year_cols += 1

    # --- 判定邏輯 A (標準) ---
    # 有關鍵字，且「純數字欄位」不過半
    if keyword_hits > 0 and digit_cols < len(cols) / 2:
        return True

    # --- 判定邏輯 B (年份豁免條款) ---
    if keyword_hits > 0 and (digit_cols - year_cols) < len(cols) / 2:
        return True
        
    # --- 判定邏輯 C (全文字表頭) ---
    if all(len(c) < 60 for c in cols) and digit_cols == 0:
        if not any("違反" in c or "處新臺幣" in c for c in cols):
            return True
            
    return False

def determine_doc_type(content):
    """簡單判斷文件類型，決定使用哪種 Regex"""
    preview = content[:1000]
    if re.search(r'第\s*[0-9一二三四五六七八九十百]+\s*[條]', preview):
        return "REGULATION"
    if re.search(r'\n\s*1\.\d', preview):
        return "PLAN"
    return "GENERAL"

def parse_markdown_to_graph(md_content, doc_name="未命名文件"):
    nodes = [] 
    edges = [] 
    
    # 建立根節點
    doc_id = "doc_01"
    nodes.append({
        "id": doc_id,
        "label": "Document",
        "properties": {
            "name": doc_name,
            "full_content": md_content[:300] + "..." 
        }
    })
    
    lines = md_content.split('\n')
    
    current_section_id = None 
    current_section_title = "未命名章節"
    current_text_buffer = [] 

    # --- [新增函式] 用來結算章節內容 ---
    def finalize_section_content(section_id, text_buffer):
        if not section_id: return
        
        # 找出目前節點
        target_node = next((n for n in nodes if n['id'] == section_id), None)
        if not target_node: return

        # 檢查這個 section 是否有連到 TableItem (即是否有子表格數據)
        child_items = [e for e in edges if e['source'] == section_id and e['label'] == 'HAS_ITEM']
        
        if child_items:
            # 【策略：父節點輕量化】
            # 如果有子表格，父節點只存摘要，避免 token 爆炸
            title = target_node['properties'].get('title', '未知標題')
            item_count = len(child_items)
            
            summary = f"**章節摘要**\n"
            summary += f"標題：{title}\n"
            summary += f"統計：本章節包含 {item_count} 筆細項數據 (TableItem)。\n"
            summary += "說明：詳細數據內容（如金額、廠商名稱、數值）已拆分至子節點，請檢索與此節點連結的 TableItem 以獲取精確資訊。"
            
            target_node['properties']['content'] = summary
        else:
            # 【策略：純文字保留】
            # 如果沒有表格，就保留完整的段落文字
            target_node['properties']['content'] = "\n".join(text_buffer)

    def extract_long_text(properties, parent_item_id):
        """檢查屬性，如果太長則獨立成 Article 節點"""
        for k, v in properties.items():
            if len(v) > 50: 
                detail_node_id = f"{parent_item_id}_detail_{k}"
                nodes.append({
                    "id": detail_node_id,
                    "label": "Article", 
                    "properties": {
                        "title": f"{current_section_title} > {k}",
                        "content": v 
                    }
                })
                edges.append({"source": current_section_id, "target": detail_node_id, "label": "HAS_ARTICLE"})
    
    # =================================================================
    
    doc_type = determine_doc_type(md_content)
    print(f"文件類型判定: {doc_type}")

    if doc_type == "REGULATION":
        section_pattern = re.compile(
            r'^\s*(#+\s*)?[\*]*('
            r'第\s*[0-9一二三四五六七八九十百]+\s*[條]|'
            r'附表|總說明|'
            r'主旨|說明|擬辦|依據|公告事項|受文者'
            r')'
        )
    else:
        section_pattern = re.compile(
            r'^\s*(#+\s*)?[\*]*('
            r'[壹貳參肆伍陸柒捌玖拾]+、|'
            r'[一二三四五六七八九十]+、|'
            r'（[一二三四五六七八九十]+）|'
            r'\(\s*[一二三四五六七八九十]+\s*\)|'
            r'Q\.|A\.|問[:：]|答[:：]|'
            r'\d+\.\d+(\.\d+)*\s+|'
            r'\d+\.\s+'
            r')'
        )
    
    table_row_pattern = re.compile(r'^\|(.*)\|$')
    
    current_table_headers = []
    table_item_count = 0
    last_row_values = {} 

    for line in lines:
        line = line.strip()
        if not line: 
            last_row_values = {}
            continue
        
        # --- A. 偵測段落標題 ---
        match_section = section_pattern.match(line)
        is_markdown_header = line.startswith("#")
        is_valid_section = False
        if match_section:
            is_valid_section = True
        elif is_markdown_header and len(line) < 30:
            is_valid_section = True

        if is_valid_section:
            # 結算上一個章節
            if current_section_id:
                finalize_section_content(current_section_id, current_text_buffer)
            
            raw_title = line.replace("#", "").replace("*", "").strip()
            current_section_id = f"sec_{len(nodes)}"
            current_section_title = raw_title 
            current_text_buffer = [line]
            current_table_headers = []
            last_row_values = {}
            
            nodes.append({
                "id": current_section_id, "label": "Article",
                "properties": { "title": raw_title, "content": "" }
            })
            edges.append({"source": doc_id, "target": current_section_id, "label": "HAS_ARTICLE"})
            continue

        # --- B. 表格處理 ---
        match_table = table_row_pattern.match(line)
        if match_table:
            row_content = match_table.group(1)
            if not re.search(r'[^\|\-\s]', line): continue

            cols = [c.strip() for c in row_content.split('|')]
            if len(cols) > 1 and cols[0] == '': cols.pop(0)
            if len(cols) > 0 and cols[-1] == '': cols.pop()

            if not current_section_id:
                current_section_id = "sec_table_list"
                current_section_title = "表格列表"
                nodes.append({
                    "id": current_section_id, "label": "Section",
                    "properties": { "title": current_section_title, "content": "" }
                })
                edges.append({"source": doc_id, "target": current_section_id, "label": "HAS_ARTICLE"})

            is_new_header = False
            if not current_table_headers and looks_like_header(cols):
                is_new_header = True
            
            if is_new_header:
                current_table_headers = uniquify_headers(cols)
                current_text_buffer.append(line)
                last_row_values = {}
            else:
                filled_cols = []
                for i, val in enumerate(cols):
                    if not val and i in last_row_values:
                        val = last_row_values[i]
                    filled_cols.append(val)
                for i, val in enumerate(filled_cols):
                    if val: last_row_values[i] = val
                cols = filled_cols
                
                # ✅ 強制合併 <br> (不拆分)
                item_id = f"item_{table_item_count}"
                table_item_count += 1
                props = {}
                for i, val in enumerate(cols):
                    if i < len(current_table_headers):
                        key = current_table_headers[i]
                    else:
                        key = f"Col_{i+1}"
                    props[key] = val.replace("<br>", "\n")
                
                nodes.append({ "id": item_id, "label": "TableItem", "properties": props })
                edges.append({ "source": current_section_id, "target": item_id, "label": "HAS_ITEM" })
                
                extract_long_text(props, item_id)
            
            if current_section_id: current_text_buffer.append(line)
            continue
            
        # --- C. 一般內文 ---
        if current_section_id:
            current_text_buffer.append(line)
        else:
            current_section_id = "sec_intro"
            current_section_title = "前言/摘要"
            nodes.append({
                "id": current_section_id, "label": "Article",
                "properties": {"title": current_section_title, "content": ""}
            })
            edges.append({"source": doc_id, "target": current_section_id, "label": "HAS_ARTICLE"})
            current_text_buffer.append(line)

    # 最後結算當前章節
    if current_section_id:
        finalize_section_content(current_section_id, current_text_buffer)

    return {"nodes": nodes, "edges": edges}

if __name__ == "__main__":
    input_md_file = "期末執行成果報告-113資安跨域_審後版1224.docx.md"
    try:
        with open(input_md_file, "r", encoding="utf-8") as f:
            md_content = f.read()

        print("正在執行切分測試...")
        result = parse_markdown_to_graph(md_content, doc_name="測試文件")

        output_json = "test_output.json"
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        print(f"切分完成！結果已儲存至: {output_json}")
        print(f"節點總數: {len(result['nodes'])}")

        table_items = [n for n in result['nodes'] if n['label'] == 'TableItem']
        print(f"TableItem 節點數: {len(table_items)}")
        

    except Exception as e:
        print(f"測試失敗: {e}")