#!/bin/bash

# 確保進入虛擬環境
source ~/myrag/myvenv/bin/activate

# 啟動 vLLM (黃金參數版)
# vllm serve ISTA-DASLab/gemma-3-27b-it-GPTQ-4b-128g \
#   --trust-remote-code \
#   --dtype auto \
#   --max-model-len 15000 \
#   --gpu-memory-utilization 0.9 \
#   --max-num-batched-tokens 2048 \
#   --enable-chunked-prefill \
#   --enforce-eager \
#   --api-key EMPTY

vllm serve ISTA-DASLab/gemma-3-27b-it-GPTQ-4b-128g \
  --trust-remote-code \
  --dtype auto \
  --max-model-len 25000 \
  --gpu-memory-utilization 0.95 \
  --max-num-batched-tokens 4096 \
  --kv-cache-dtype fp8 \
  --enable-chunked-prefill \
  --enforce-eager \
  --api-key EMPTY