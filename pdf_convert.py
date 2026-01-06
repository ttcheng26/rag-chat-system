import fitz  
import sys
import os
import base64
import pymupdf4llm  
from openai import OpenAI

# --- 設定區 ---
API_BASE = os.getenv("VLLM_API_BASE", "http://localhost:8000/v1")
API_KEY = os.getenv("VLLM_API_KEY", "EMPTY")
MODEL_NAME = os.getenv("VLLM_MODEL", "ISTA-DASLab/gemma-3-27b-it-GPTQ-4b-128g")

print(f"PDF Converter Config: Base={API_BASE}, Model={MODEL_NAME}")

client = OpenAI(base_url=API_BASE, api_key=API_KEY)


#  判斷 PDF 類型 
def check_pdf_has_text(pdf_path, threshold=50):
    """
    檢查 PDF 是否包含可提取的文字
    回傳: (是否有字, 文字頁數, 總頁數)
    """
    try:
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        text_pages = 0
        
        print(f" 檢查 PDF 內容 (共 {total_pages} 頁)...")
        
        for i, page in enumerate(doc):
            # 抽樣檢查前 10 頁即可，避免大檔案檢查太久
            if i >= 10: break 
            
            text = page.get_text().strip()
            # 計算有效字符 (排除空白)
            valid_chars = len("".join(text.split()))
            
            if valid_chars > threshold:
                text_pages += 1
        
        # 簡單判斷：如果前 10 頁有一半以上有字，就當作是文字版
        check_limit = min(total_pages, 10)
        has_text = text_pages > (check_limit / 2)
        
        return has_text, text_pages, total_pages
        
    except Exception as e:
        print(f" 檢查 PDF 失敗: {e}")
        return False, 0, 0


#  文字提取pymupdf4llm)
def extract_text_from_pdf(pdf_path):

    print(" 執行文字提取 (pymupdf4llm)...")
    try:
        # 這行指令會直接把整份 PDF 轉成 Markdown 格式的字串
        md_text = pymupdf4llm.to_markdown(pdf_path)
        return md_text
    except Exception as e:
        print(f" 提取失敗: {e}")
        return ""


#  掃描圖 OCR 
def encode_image_base64(pix):
    img_data = pix.tobytes("png")
    return base64.b64encode(img_data).decode("utf-8")

def process_pdf_with_gemma(pdf_path):

    print(" 執行 AI 視覺辨識 ...")
    doc = fitz.open(pdf_path)
    full_markdown = []
    
    # 修改 Prompt，讓 OCR 的輸出格式跟 pymupdf4llm 一致
    prompt = """
    你是一個文件數位化專家。請將這張圖片的內容轉換為 Markdown 格式。
    
    【輸出規則】：
    1. **標題**：請辨識圖片中的標題，並使用 Markdown '#' 標記 (例如 # 壹、計畫緣起)。
    2. **表格**：若圖片中有表格，請務必轉換為 Markdown Table (| 欄位 | 欄位 |)。
    3. **內文**：保持段落完整，不要隨意斷句。
    4. **排除**：忽略頁眉、頁尾的頁碼或無意義裝飾。
    5. **語言**：請使用繁體中文。
    
    請直接輸出內容，不要有開場白或結尾。
    """

    for i, page in enumerate(doc):
        page_num = i + 1
        print(f"   正在辨識第 {page_num} 頁...")
        
        # 轉為圖片 (高解析度以利辨識)
        pix = page.get_pixmap(dpi=400)
        base64_image = encode_image_base64(pix)
        
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}},
                        ],
                    }
                ],
                max_tokens=2048,
                temperature=0.0
            )
            content = response.choices[0].message.content
            full_markdown.append(content)
            # 加入分頁符號，保持格式一致
            full_markdown.append(f"\n\n\n\n")
            
        except Exception as e:
            print(f"    第 {page_num} 頁辨識失敗: {e}")
            
    return "".join(full_markdown)


def smart_process_pdf(file_path, force_ocr=False):
    # 1. 先檢查有沒有字
    has_text, _, _ = check_pdf_has_text(file_path)
    
    # 2. 決定路徑
    if has_text and not force_ocr:
        print(" 判定為【原生電子檔】")
        return extract_text_from_pdf(file_path)
    else:
        print(" 判定為【掃描/圖片檔】")
        return process_pdf_with_gemma(file_path)

if __name__ == "__main__":
    # 測試用
    input_file = "3-新任總統數位政見.pdf" 
    output_file = input_file + ".md"
    
    # 模擬參數 (你可以改為 True 來測試 OCR 模式)
    FORCE_OCR = False 
    
    try:
        if not os.path.exists(input_file):
            print(f"❌ 找不到檔案: {input_file}")
            sys.exit(1)
            
        final_md = smart_process_pdf(input_file, force_ocr=FORCE_OCR)
        
        if final_md:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(final_md)
            print(f"\n 轉換完成！Markdown 已儲存至: {output_file}")
        else:
            print("轉換結果為空。")
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"發生錯誤: {e}")
