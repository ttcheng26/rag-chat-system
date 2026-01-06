import pandas as pd
import os
import sys
import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)

def clean_dataframe(df):
    """
    1. 移除全空的欄位。
    2. 移除 'Unnamed' 且內容幾乎全空的垃圾欄位。
    3. 嘗試修正標題列錯位 (Header Misalignment)。
    """
    # 1. 移除全空的欄位
    df = df.dropna(axis=1, how='all')
    
    # 2. 移除名稱是 'Unnamed' 且內容超過 90% 是空的欄位
    cols_to_drop = []
    for col in df.columns:
        col_str = str(col)
        if "Unnamed" in col_str or "nan" == col_str.lower():
            # 計算該欄位的空值比例
            empty_count = df[col].astype(str).replace('', 'nan').replace('nan', pd.NA).isna().sum()
            if empty_count / len(df) > 0.9:
                cols_to_drop.append(col)
    
    if cols_to_drop:
        df = df.drop(columns=cols_to_drop)

    # 3. 標題列修正偵測
    # 如果標題有一半以上是 'Unnamed'，但第一列資料看起來很像標題，就往上提
    unnamed_headers = sum(1 for c in df.columns if "Unnamed" in str(c))
    if unnamed_headers > len(df.columns) / 2 and len(df) > 1:
        new_header = df.iloc[0]
        empty_new_header = new_header.astype(str).replace('', 'nan').replace('nan', pd.NA).isna().sum()
        
        # 如果新標題比舊標題更完整，就替換
        if empty_new_header < unnamed_headers:
            print("偵測到標題列可能錯位，自動修正 Header...")
            df = df[1:] # 移除第一列資料
            df.columns = new_header # 設定為新 Header
            # 再次清洗新標題中可能的 Unnamed
            df = df.loc[:, ~df.columns.astype(str).str.contains('^Unnamed')]

    return df

# ==========================================
# 轉換主程式 (使用標準套件)
# ==========================================
def excel_to_markdown(file_path):
    if not os.path.exists(file_path):
        return f"錯誤: 找不到檔案 {file_path}"

    file_ext = os.path.splitext(file_path)[1].lower()
    markdown_output = ""
    
    try:
        dfs = {}
        
        # 1. 讀取 Excel / ODS
        # pandas 會自動根據副檔名呼叫 openpyxl (xlsx) 或 odfpy (ods)
        if file_ext in ['.xlsx', '.xls', '.ods']:
            dfs = pd.read_excel(file_path, sheet_name=None)
            
        # 2. 讀取 CSV
        elif file_ext == '.csv':
            df = pd.read_csv(file_path)
            dfs = {'Sheet1': df}
            
        else:
            return f"錯誤: 不支援的格式 {file_ext}"
            
        if not dfs: return ""

        # 3. 轉換為 Markdown
        for sheet_name, df in dfs.items():
            # 如果有多個工作表，用分隔線區隔，保持版面乾淨
            if len(markdown_output) > 0:
                markdown_output += "\n\n---\n\n"
            
            # 執行清洗
            df_clean = clean_dataframe(df)
            
            # 轉為字串避免格式錯誤
            df_clean = df_clean.fillna("")
            df_clean = df_clean.astype(str)
          
            # 轉 Markdown (依賴 tabulate 套件)
            try:
                markdown_table = df_clean.to_markdown(index=False)
            except ImportError:
                markdown_table = df_clean.to_string(index=False)
                
            markdown_output += markdown_table
            
        return markdown_output

    except Exception as e:
        return f"處理失敗: {str(e)}"

if __name__ == "__main__":
    # 自動抓取目錄下的所有試算表檔案
    target_files = [f for f in os.listdir('.') if f.endswith(('.xlsx', '.xls', '.ods', '.csv'))]
    
    for f in target_files:
        if f == "excel_convert.py": continue
        
        print(f"正在處理: {f} ...")
        md_result = excel_to_markdown(f)
        
        output_filename = f + ".md"
        with open(output_filename, "w", encoding="utf-8") as out:
            out.write(md_result)
            
        print(f"已儲存至: {output_filename}")