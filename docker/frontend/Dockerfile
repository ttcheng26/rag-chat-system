# ============================================
# Next.js 前端 - 多階段建構
# ============================================

# === Stage 1: 安裝依賴 ===
FROM node:20-alpine AS deps
WORKDIR /app

# 複製 package 檔案
COPY package.json package-lock.json ./

# 安裝依賴
RUN npm ci

# === Stage 2: 建構應用 ===
FROM node:20-alpine AS builder
WORKDIR /app

# 接收建構參數
ARG BACKEND_URL=http://backend:8001
ENV BACKEND_URL=${BACKEND_URL}

# 複製依賴
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# 設定環境變數
ENV NEXT_TELEMETRY_DISABLED=1
ENV NODE_ENV=production

# 建構
RUN npm run build

# === Stage 3: 執行環境 ===
FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

# 接收執行時環境變數
ARG BACKEND_URL=http://backend:8001
ENV BACKEND_URL=${BACKEND_URL}

# 建立非 root 使用者 (安全性)
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# 複製必要檔案
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/next.config.ts ./next.config.ts

# 設定權限
RUN chown -R nextjs:nodejs /app

USER nextjs

EXPOSE 3001

ENV PORT=3001
ENV HOSTNAME="0.0.0.0"

# 啟動
CMD ["npm", "start"]