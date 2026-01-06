# ============================================
# vLLM - LLM 推理引擎
# 使用 ISTA-DASLab/gemma-3-27b-it-GPTQ-4b-128g
# ============================================
FROM vllm/vllm-openai:v0.13.0

WORKDIR /app

# 安裝 curl（用於健康檢查）
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# 暴露埠號
EXPOSE 8000

# 使用 ENTRYPOINT 覆蓋原有的設定
ENTRYPOINT ["python3", "-m", "vllm.entrypoints.openai.api_server"]

# 設定預設參數 - 與 run_27b_vllm.sh 一致
CMD ["--host", "0.0.0.0", \
     "--port", "8000", \
     "--model", "ISTA-DASLab/gemma-3-27b-it-GPTQ-4b-128g", \
     "--trust-remote-code", \
     "--dtype", "auto", \
     "--max-model-len", "25000", \
     "--gpu-memory-utilization", "0.52", \
     "--max-num-batched-tokens", "4096", \
     "--kv-cache-dtype", "auto", \
     "--enable-chunked-prefill", \
     "--enforce-eager", \
     "--api-key", "EMPTY"]
