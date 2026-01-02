import re
import os
from docx import Document
from docx.document import Document as _Document
from docx.oxml.text.paragraph import CT_P
from docx.oxml.table import CT_Tbl
from docx.table import _Cell, Table
from docx.text.paragraph import Paragraph

def iter_block_items(parent):
    """遍歷 DOCX 區塊 (保持不變)"""
    if isinstance(parent, _Document):
        parent_elm = parent.element.body
    elif isinstance(parent, _Cell):
        parent_elm = parent._tc
    else:
        raise ValueError("Unsupported parent type")

    for child in parent_elm.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, parent)
        elif isinstance(child, CT_Tbl):
            yield Table(child, parent)

def extract_table_content(table):
    """表格轉 Markdown (保持不變)"""
    md_lines = []
    rows_data = []
    for row in table.rows:
        row_cells = []
        for cell in row.cells:
            cell_text = "<br>".join([p.text.strip() for p in cell.paragraphs if p.text.strip()])
            cell_text = cell_text.replace("|", "&#124;") 
            row_cells.append(cell_text)
        rows_data.append(row_cells)

    if not rows_data: return ""

    header = rows_data[0]
    header = [h if h else " " for h in header] 
    
    md_lines.append("| " + " | ".join(header) + " |")
    md_lines.append("| " + " | ".join(["---"] * len(header)) + " |")

    for row in rows_data[1:]:
        processed_row = [c if c else " " for c in row]
        md_lines.append("| " + " | ".join(processed_row) + " |")

    return "\n".join(md_lines)

def parse_docx_to_markdown(file_path):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"找不到檔案: {file_path}")

    doc = Document(file_path)
    md_output = []
    
    # 使用迭代器按順序讀取內容
    for block in iter_block_items(doc):
        
        # === 處理段落 ===
        if isinstance(block, Paragraph):
            text = block.text.strip()
            if not text: continue
                
            style_name = block.style.name
            
            # 簡單判斷標題
            if 'Heading' in style_name:
                md_output.append(f"\n## {text}\n")
            elif len(text) < 30 and not re.search(r'[，。；]', text):
                md_output.append(f"\n## {text}\n")
            else:
                md_output.append(f"{text}\n")

        # === 處理表格 ===
        elif isinstance(block, Table):
            md_table = extract_table_content(block)
            if md_table:
                md_output.append(f"\n{md_table}\n")

    return "\n".join(md_output)

if __name__ == "__main__":
    # 測試用
    input_file = ".....docx" 

    md = parse_docx_to_markdown(input_file)
    print(f"解析完成")
