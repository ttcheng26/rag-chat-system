#!/bin/bash
# 確保進入虛擬環境
source ~/myrag/myvenv/bin/activate

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