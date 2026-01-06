# ============================================
# RAG Backend - FastAPI 服務
# ============================================
FROM python:3.11-slim

WORKDIR /app

# 安裝系統依賴（PDF處理、OCR支援、OpenCV依賴）
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-chi-tra \
    tesseract-ocr-chi-sim \
    tesseract-ocr-eng \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

# 複製依賴檔案
COPY docker/backend/requirements.txt .

# 安裝 Python 依賴
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 複製所有 Python 程式碼
COPY rag_server.py .
COPY query_rag_v3.py .
COPY build_vectordb_v3.py .
COPY main_pipeline_v5.py .
COPY parsing_v2.py .
COPY graph_chunker_v6.py .
COPY pdf_convert.py .
COPY docx_convert.py .
COPY excel_convert.py .

# 建立必要目錄
RUN mkdir -p /app/chroma_db /app/data_files /app/processed_data 

# 暴露埠號
EXPOSE 8001

# 啟動命令
CMD ["python", "rag_server.py"]