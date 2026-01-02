import os
import subprocess

def convert_to_odt(input_file, output_dir=None):
    """
    將 doc, docx轉為 odt
    :param input_file: 來源檔案路徑
    :param output_dir: (選填) 指定輸出資料夾，若不填則存於原資料夾
    """
    input_path = os.path.abspath(input_file)
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    
    # [修改] 決定輸出資料夾
    if output_dir:
        directory = os.path.abspath(output_dir)
        if not os.path.exists(directory):
            os.makedirs(directory)
    else:
        directory = os.path.dirname(input_path)
    
    target_odt = os.path.join(directory, base_name + ".odt")
    
    # 如果目標已經存在，直接回傳 (快取機制)
    if os.path.exists(target_odt):
        print(f"    轉檔快取已存在: {target_odt}")
        return target_odt

    print(f" 正在處理: {input_file} ...")

    # 1. 使用 LibreOffice 將 DOC/DOCX 轉為 ODT
    try:
        cmd = [
            'soffice', '--headless', '--convert-to', 'odt',
            '--outdir', directory, input_path
        ]
        # 執行指令
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        if os.path.exists(target_odt):
            print(f" 成功轉換為: {target_odt}")
            return target_odt
        else:
            print(" 轉換失敗，找不到輸出檔案。")
            return None

    except Exception as e:
        print(f"❌ LibreOffice 轉換錯誤: {e}")
        return None

if __name__ == "__main__":
    pass

# import os
# import subprocess

# def convert_to_odt(input_file):
#     """
#     將 doc, docx轉為 odt
#     """
#     input_path = os.path.abspath(input_file)
#     directory = os.path.dirname(input_path)
#     base_name = os.path.splitext(os.path.basename(input_path))[0]
#     ext = os.path.splitext(input_path)[1].lower()
    
#     target_odt = os.path.join(directory, base_name + ".odt")
    
#     # 如果目標已經存在，直接回傳
#     if os.path.exists(target_odt):
#         return target_odt

#     print(f"🔄 正在處理: {input_file} ...")

#     # 1. 使用 LibreOffice 將 DOC/DOCX 轉為 ODT
#     # 支援格式: .doc, .docx, .rtf, .txt 等
#     try:
#         cmd = [
#             'soffice', '--headless', '--convert-to', 'odt',
#             '--outdir', directory, input_path
#         ]
#         # 執行指令
#         subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        

            
#         if os.path.exists(target_odt):
#             print(f"✅ 成功轉換為: {target_odt}")
#             return target_odt
#         else:
#             print("❌ 轉換失敗，找不到輸出檔案。")
#             return None

#     except Exception as e:
#         print(f"❌ LibreOffice 轉換錯誤: {e}")
#         return None

# # --- 測試 ---
# if __name__ == "__main__":
#     # 測試檔案 (請換成你有的檔案)
#     convert_to_odt("首都圈黃金廊帶推動方案-推動策略(三)_數位發展部_彙整1，再請補充各計畫概要V1.docx")
#     pass