import re
import json
import os

# ==========================================
# 1. 輔助函式：表頭處理
# ==========================================
def uniquify_headers(headers):
    counts = {}
    for h in headers:
        clean_h = h.strip()
        if not clean_h: clean_h = "Col"
        counts[clean_h] = counts.get(clean_h, 0) + 1
    
    new_headers = []
    current_counts = {}
    for h in headers:
        clean_h = h.strip()
        if not clean_h: clean_h = "Col"
        current_counts[clean_h] = current_counts.get(clean_h, 0) + 1
        
        if counts[clean_h] > 1: 
            new_headers.append(f"{clean_h}_{current_counts[clean_h]}")
        else: 
            new_headers.append(clean_h)
    return new_headers

def looks_like_header(cols):
    if len(cols) < 2: return False
    header_keywords = [
        "名稱", "金額", "單位", "日期", "編號", "備註", "說明", "合計", "總計", 
        "數量", "內容", "項目", "年度", "來源", "預算", "執行", "成果", "效益",
        "摘要", "類別", "性質", "對象", "地點", "時間", "職稱", "姓名", "票種", "條件"
    ]
    score = 0
    for c in cols:
        val = c.strip()
        if any(k in val for k in header_keywords):
            score += 1
        # 表頭通常不會是純數字 (除非是年份，但年份通常有上下文)
        if re.match(r'^\d+$', val):
            score -= 1
            
    if score >= 2 or (len(cols) > 0 and score / len(cols) > 0.3):
        return True
    return False

# ==========================================
# 2. 輔助函式：文件類型判斷 
# ==========================================
def determine_doc_type(content):
    # 簡單啟發式：如果有 "第 X 條"，通常是法規/標準
    if re.search(r'第\s*[0-9一二三四五六七八九十百]+\s*[條]', content[:5000]):
        return "REGULATION"
    return "GENERAL"

def get_section_pattern(doc_type):
    if doc_type == "REGULATION":
        # 法規類：第 X 條, 附表, 總說明...
        return re.compile(
            r'^\s*(#+\s*)?[\*]*('
            r'第\s*[0-9一二三四五六七八九十百]+\s*[條]|'
            r'附表|總說明|'
            r'主旨|說明|擬辦|依據|公告事項|受文者'
            r')'
        )
    else:
        # 一般計畫書：壹、貳、一、二、1.1 ...
        return re.compile(
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

# ==========================================
# 3. 主程式：Markdown 切分
# ==========================================
def parse_markdown_to_graph(md_content, doc_name="unknown"):
    nodes = []
    edges = []
    
    # 1. 建立 Document 根節點
    doc_id = "doc_01"
    clean_full_content = md_content[:20000] 
    
    nodes.append({
        "id": doc_id,
        "label": "Document",
        "properties": {
            "name": doc_name,
            "full_content": clean_full_content
        }
    })
    
    # 2. 判斷文件類型與切分規則
    doc_type = determine_doc_type(md_content)
    print(f"[{doc_name}] 文件類型判定: {doc_type}")
    section_pattern = get_section_pattern(doc_type)
    
    lines = md_content.split('\n')
    
    current_section_id = None
    current_section_title = ""
    current_text_buffer = []
    
    section_counter = 0
    item_counter = 0
    
    # 表格處理狀態
    in_table = False
    current_headers = []
    last_row_values = {} 
    
    def finalize_section_content(sec_id, buffer):
        if not sec_id or not buffer: return
        content = "\n".join(buffer).strip()
        if content:
            # 找到該節點並更新 content
            for n in nodes:
                if n['id'] == sec_id:
                    n['properties']['content'] = content
                    break
    
    for line in lines:
        line_strip = line.strip()
        
        # --- A. 偵測標題 (Heading) & 自定義 Pattern ---
        # 優先權 1: Markdown 標題 (#)
        md_header_match = re.match(r'^(#{1,6})\s+(.*)', line_strip)
        
        # 優先權 2: Regex Pattern (第X條, 一、...)
        pattern_match = section_pattern.match(line_strip)
        
        is_new_section = False
        new_title = ""
        
        if md_header_match:
            is_new_section = True
            new_title = md_header_match.group(2).strip()
        elif pattern_match:
            is_new_section = True
            new_title = line_strip # 使用整行作為標題
            
        if is_new_section:
            # 1. 先結算上一個章節
            if current_section_id:
                finalize_section_content(current_section_id, current_text_buffer)
                current_text_buffer = []
            
            # 2. 建立新章節
            section_counter += 1
            new_sec_id = f"sec_{section_counter}"
            current_section_id = new_sec_id
            current_section_title = new_title
            
            nodes.append({
                "id": new_sec_id,
                "label": "Article", 
                "properties": {
                    "title": new_title,
                    "content": "" # 待填
                }
            })
            
            edges.append({
                "source": doc_id,
                "target": new_sec_id,
                "label": "HAS_ARTICLE"
            })
            
            current_text_buffer.append(line)
            continue
            
        # --- B. 偵測表格 (Table) ---
        if line_strip.startswith("|"):
            cols = [c.strip() for c in line_strip.split("|")[1:-1]]
            
            # 判斷是否為分隔線
            if all(re.match(r'^[\s\-:]+$', c) for c in cols):
                continue
                
            if not in_table:
                if looks_like_header(cols):
                    in_table = True
                    current_headers = uniquify_headers(cols)
                    last_row_values = {} 
                    current_text_buffer.append(f"\n[表格: {', '.join(current_headers)}]\n")
                else:
                    current_text_buffer.append(line)
            else:
                if len(cols) != len(current_headers):
                    continue
                
                filled_cols = []
                for i, val in enumerate(cols):
                    final_val = val
                    
                    if not val and i in last_row_values:
                        parent_val = last_row_values[i].strip()
                        
                        # 1. 純數據檢查 (數字、金額、百分比) -> 禁止繼承
                        is_data_value = re.match(r'^[\d,.]+%?$', parent_val)
                        
                        # 2. 無效符號 -> 禁止繼承
                        is_empty_indicator = parent_val in ["-", "---", "N/A", "NA", "無", ".", ""]

                        should_fill = False
                        
                        if is_empty_indicator:
                            should_fill = False
                        elif not is_data_value:
                            # 文字、帶單位數字 (如 "114年", "100元", "入園費") -> 填滿
                            should_fill = True
                        else:
                            # 純數據 (如 "112", "3000")
                            if i == 0:
                                # 第 1 欄通常是序號 -> 填滿
                                should_fill = True
                            else:
                                # 其他欄位 -> 禁止填滿 (防止幻覺)
                                should_fill = False
                        
                        if should_fill:
                            final_val = parent_val
                            
                    filled_cols.append(final_val)
                
                last_row_values = {i: v for i, v in enumerate(filled_cols) if v}
                
                # 建立 TableItem
                item_counter += 1
                item_id = f"item_{item_counter}"
                
                props = {}
                if current_section_title:
                    props["section_context"] = current_section_title
                    
                for h, v in zip(current_headers, filled_cols):
                    props[h] = v
                    
                nodes.append({
                    "id": item_id,
                    "label": "TableItem",
                    "properties": props
                })
                
                # 建立連結
                target_source = current_section_id if current_section_id else doc_id
                edges.append({
                    "source": target_source,
                    "target": item_id,
                    "label": "HAS_ITEM"
                })
                    
            continue 
            
        else:
            if in_table:
                in_table = False
                current_text_buffer.append("\n(關聯表格資料已轉化為 TableItem 子節點)\n")
            
            if not line_strip: continue
            
        # --- C. 一般內文 ---
        if current_section_id:
            current_text_buffer.append(line)
        else:
            # 前言處理
            current_section_id = "sec_intro"
            current_section_title = "前言/摘要"
            nodes.append({
                "id": current_section_id, "label": "Article",
                "properties": {"title": current_section_title, "content": ""}
            })
            edges.append({"source": doc_id, "target": current_section_id, "label": "HAS_ARTICLE"})
            current_text_buffer.append(line)

    if current_section_id:
        finalize_section_content(current_section_id, current_text_buffer)

    return {"nodes": nodes, "edges": edges}

if __name__ == "__main__":
    print("Graph Chunker v6 Loaded.")