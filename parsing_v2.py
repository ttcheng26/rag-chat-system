import re
import sys
from odf.opendocument import load
from odf.table import Table, TableRow, TableCell
from odf.text import P, H, List, ListItem, Section
from odf import teletype

# --- 工具函式 ---

def get_odf_attr(element, local_name):
    if not hasattr(element, 'attributes') or not element.attributes:
        return None
    for key, value in element.attributes.items():
        key_name = key[1] if isinstance(key, tuple) else key
        if key_name == local_name:
            return str(value)
    return None

def get_cell_text_with_newlines(cell):
    paragraphs = []
    for child in cell.childNodes:
        if child.qname[1] in ('p', 'h'):
            text = teletype.extractText(child).strip()
            if text: paragraphs.append(text)
    if not paragraphs:
        text = teletype.extractText(cell).strip()
        if text: paragraphs.append(text)
    return "<br>".join(paragraphs)

def is_cell_empty(text):
    if not text: return True
    clean = re.sub(r'(<br>|[\s\u3000\xa0])+', '', str(text))
    return len(clean) == 0

# --- 表格處理 ---

def process_table_node(table_node):
    # get all rows from the table
    rows = table_node.getElementsByType(TableRow)
    if not rows: return "" 

    # initial variables
    grid = []
    occupied = {}
    current_row_idx = 0

    for row in rows:
        valid_cells = [c for c in row.childNodes if c.qname[1] == 'table-cell']
        current_col_idx = 0
        row_data = []

        # fill contents from occupied cells
        def fill_occupied():
            nonlocal current_col_idx
            while (current_row_idx, current_col_idx) in occupied:
                row_data.append(occupied[(current_row_idx, current_col_idx)])
                current_col_idx += 1

        fill_occupied()

        for cell in valid_cells:
            n_rows = int(get_odf_attr(cell, "number-rows-spanned") or 1)
            n_cols = int(get_odf_attr(cell, "number-columns-spanned") or 1)
            n_rept = int(get_odf_attr(cell, "number-columns-repeated") or 1)
            text_content = get_cell_text_with_newlines(cell)

            for _ in range(n_rept):

                fill_occupied() # double check

                for r in range(n_rows):
                    for c in range(n_cols):
                        if r == 0 and c == 0: pass
                        else: occupied[(current_row_idx + r, current_col_idx + c)] = text_content
                for _ in range(n_cols):
                    row_data.append(text_content)
                    current_col_idx += 1

        while (current_row_idx, current_col_idx) in occupied:
             row_data.append(occupied[(current_row_idx, current_col_idx)])
             current_col_idx += 1

        grid.append(row_data)
        current_row_idx += 1

    if not grid: return ""

    # 向下填充空白儲存格
    for r in range(2, len(grid)):
        for c in range(len(grid[r])):
            if c >= len(grid[r-1]): continue
            curr = grid[r][c]
            parent = grid[r-1][c]
            if is_cell_empty(curr) and not is_cell_empty(parent):
                should_fill = True
                for check_col in range(c):
                    if check_col >= len(grid[r-1]) or grid[r][check_col] != grid[r-1][check_col]:
                        should_fill = False
                        break
                if should_fill: grid[r][c] = parent

    cleaned_grid = []
    for row in grid:
        cleaned_row = []
        for cell_text in row:
            # 將實體換行 (\n) 替換為 HTML 換行 (<br>) 或直接移除
            # 這樣才能確保 Markdown 表格不會斷成兩行
            safe_text = str(cell_text).replace('\n', '<br>').replace('\r', '')
            cleaned_row.append(safe_text)
        cleaned_grid.append(cleaned_row)
    grid = cleaned_grid  

    md_output = "\n"
    if grid:
        headers = grid[0]
        md_output += "| " + " | ".join(headers) + " |\n"
        md_output += "| " + " | ".join(["---"] * len(headers)) + " |\n"
        for row in grid[1:]:
            if len(row) < len(headers): row += [""] * (len(headers) - len(row))
            row = row[:len(headers)]
            md_output += "| " + " | ".join(row) + " |\n"
    
    return md_output + "\n"


def recursive_parse(node):
    """
    遞迴解析所有節點，包含 Section, List, Paragraph, Table
    """
    results = []
    
    tag_name = node.qname[1]
    
    if tag_name == 'h': # 標題
        level = get_odf_attr(node, "outline-level") or "1"
        text = teletype.extractText(node).strip()
        if text: results.append(f"\n{'#' * int(level)} {text}\n")
        
    elif tag_name == 'p': # 段落
        text = teletype.extractText(node).strip()
        if text: results.append(f"{text}\n")
        
    elif tag_name == 'table': # 表格
        results.append(process_table_node(node))
        
    elif tag_name in ('list', 'list-item', 'section'): 
        for child in node.childNodes:
            results.extend(recursive_parse(child))
            
    # 處理其他可能的容器 (例如 draw:text-box 等)
    elif hasattr(node, 'childNodes'):
        for child in node.childNodes:
            results.extend(recursive_parse(child))
            
    return results

def parse_full_document(file_path):
    print(f"Loading and Parsing: {file_path} ...", file=sys.stderr)
    doc = load(file_path)
    full_text = []
    
    # Start Recursive Parsing from header text
    for node in doc.text.childNodes:
        full_text.extend(recursive_parse(node))
            
    return "".join(full_text)

# --- 測試單一文件區塊 ---
if __name__ == "__main__":
    file_path = ".....odt" 

    try:
        final_markdown = parse_full_document(file_path)
        
        output_filename = "parsed_result_v6_full.md"
        with open(output_filename, "w", encoding="utf-8") as f:
            f.write(final_markdown)
        print(f"\n完整內容已儲存至: {output_filename}", file=sys.stderr)


    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"\n發生錯誤: {e}", file=sys.stderr)

