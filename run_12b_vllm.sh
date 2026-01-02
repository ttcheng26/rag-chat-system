#!/bin/bash

# 確保進入虛擬環境
source ~/myrag/myvenv/bin/activate

# 啟動 vLLM (黃金參數版)
MODEL_NAME="RedHatAI/gemma-3-12b-it-FP8-dynamic"

vllm serve $MODEL_NAME \
  --trust-remote-code \
  --dtype auto \
  --max-model-len 8192 \
  --gpu-memory-utilization 0.85 \
  --max-num-batched-tokens 8192 \
  --enable-chunked-prefill \
  --enforce-eager \
  --api-key EMPTY
