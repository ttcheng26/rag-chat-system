# Tainan Frontend 專案

這是一個基於 Next.js 15 的前端專案，使用 TypeScript 和 React 18 開發，提供聊天介面功能。

## 系統需求

- Node.js 18.0 或更高版本
- npm 或 yarn 套件管理工具

## 快速開始

### 1. 安裝相依套件

專案會根據 `package.json` 自動安裝所需的 node_modules：

```bash
npm install
```

### 2. 程式碼編譯

執行 build 指令來編譯 TypeScript 和打包程式碼：

```bash
npm run build
```

### 3. 正式執行

編譯完成後，使用以下指令啟動生產環境伺服器：

```bash
npm start
```

伺服器將在 `http://localhost:3001` 上運行。

### 開發模式（選用）

如果需要在開發環境下運行並啟用熱重載：

```bash
npm run dev
```

## 專案結構

```
tainan-frontEnd_run/
├── app/                    # Next.js App Router 頁面
│   ├── chat/              # 聊天頁面
│   ├── layout.tsx         # 根佈局
│   └── page.tsx           # 首頁
├── components/            # React 元件
│   └── chat.tsx          # 聊天介面元件
├── lib/                   # 工具函式和 API 客戶端
│   ├── api.ts            # API 通訊模組
│   └── utils.ts          # 工具函式
├── public/               # 靜態資源
├── package.json          # 專案相依套件設定
└── next.config.ts        # Next.js 配置檔
```

## API 使用說明

### 後端 API 位置

**重要**: 本專案使用 `'use client'` 進行客戶端渲染，所有 API 呼叫都在瀏覽器中執行。

實際使用的 API 位置為：

```typescript
const API_BASE_URL = ' ';
```

⚠️ **注意事項**:
- `lib/api.ts` 中的 `http://localhost:8081` 並未實際使用
- 客戶端元件（使用 `'use client'`）的 API 呼叫會在瀏覽器執行
- 請在各個頁面或元件中直接定義 `API_BASE_URL`
- 生產環境請使用完整的域名，避免使用 `localhost`

### API 端點

#### 1. 健康檢查（Health Check）

檢查後端服務是否正常運作：

```typescript
const checkConnection = async () => {
  try {
    const response = await fetch(`${API_BASE_URL}/health`);
    const isConnected = response.ok;
    console.log('後端連線狀態:', isConnected);
  } catch (error) {
    console.error('連線失敗:', error);
  }
};
```

#### 2. 串流聊天訊息（Stream Chat）

使用 fetch API 呼叫串流端點：

```typescript
// 建立 AbortController 用於取消請求
const abortController = new AbortController();

const response = await fetch(`${API_BASE_URL}/stream-chat`, {
  method: 'POST',
  headers: { 
    'Content-Type': 'application/json',
    'Accept': 'text/event-stream',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive'
  },
  body: JSON.stringify({
    message: '你好，這是我的問題',
    session_id: sessionId || undefined,      // 選用：會話 ID
    temperature: 0.1,                        // 溫度參數（0.0-1.0）
    max_tokens: 5000,                        // 最大回應長度
    top_k: 5,                                // Top-K 採樣參數
    use_web_search: true,                    // 是否使用網路搜尋
    use_vllm: true                           // 是否使用 vLLM 引擎
  }),
  signal: abortController.signal             // 用於取消請求
});

// 處理 Server-Sent Events (SSE) 串流回應
const reader = response.body?.getReader();
const decoder = new TextDecoder();

while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  
  const chunk = decoder.decode(value);
  console.log('收到訊息片段:', chunk);
  
  // 解析 SSE 格式的資料
  const lines = chunk.split('\n');
  for (const line of lines) {
    if (line.startsWith('data: ')) {
      const data = line.slice(6);
      if (data === '[DONE]') {
        console.log('串流結束');
        break;
      }
      try {
        const json = JSON.parse(data);
        console.log('解析後的資料:', json);
      } catch (e) {
        console.log('文字內容:', data);
      }
    }
  }
}

// 取消請求（如需要）
// abortController.abort();
```

### 請求參數說明

#### StreamChatRequest（串流請求格式）
```typescript
{
  message: string;              // 必填：使用者訊息內容
  session_id?: string;          // 選用：會話 ID，用於延續對話
  temperature?: number;         // 選用：溫度參數 (0.0-1.0)，預設 0.1
  max_tokens?: number;          // 選用：最大回應 token 數，預設 5000
  top_k?: number;               // 選用：Top-K 採樣參數，預設 5
  use_web_search?: boolean;     // 選用：是否啟用網路搜尋，預設 true
  use_vllm?: boolean;           // 選用：是否使用 vLLM 引擎，預設 true
}
```

#### StreamChunk（串流回應格式）
```typescript
{
  type: 'init' | 'chunk' | 'end' | 'error' | 'search_results';
  session_id?: string;          // 會話 ID
  content?: string;             // 訊息內容片段
  error?: string;               // 錯誤訊息
  timestamp: string;            // 時間戳記
  
  // 搜尋結果相關欄位（當 type='search_results' 時）
  has_knowledge?: boolean;      // 是否有知識庫結果
  knowledge_count?: number;     // 知識庫結果數量
  has_map_info?: boolean;       // 是否有地圖資訊
  map_locations_count?: number; // 地圖位置數量
  nearby_places_count?: number; // 附近地點數量
  has_web_search?: boolean;     // 是否有網路搜尋結果
  web_search_count?: number;    // 網路搜尋結果數量
  
  knowledge_context?: any[];    // 知識庫內容
  map_info?: any;               // 地圖資訊
  web_search_results?: any[];   // 網路搜尋結果
}
```

#### SearchResults（搜尋結果彙整）
```typescript
{
  has_knowledge: boolean;       // 是否有知識庫結果
  knowledge_count: number;      // 知識庫結果數量
  has_map_info: boolean;        // 是否有地圖資訊
  map_locations_count: number;  // 地圖位置數量
  nearby_places_count: number;  // 附近地點數量
  has_web_search: boolean;      // 是否有網路搜尋結果
  web_search_count: number;     // 網路搜尋結果數量
  knowledge_context?: any[];    // 知識庫內容
  map_info?: any;               // 地圖資訊
  web_search_results?: any[];   // 網路搜尋結果
}
```

#### Message（訊息格式）
```typescript
{
  id: string;                   // 訊息 ID
  role: 'user' | 'assistant';   // 訊息角色
  content: string;              // 訊息內容
  timestamp: Date;              // 時間戳記
}
```

#### Headers 說明
```typescript
{
  'Content-Type': 'application/json',      // JSON 格式請求
  'Accept': 'text/event-stream',           // 接受 SSE 串流回應
  'Cache-Control': 'no-cache',             // 禁用快取
  'Connection': 'keep-alive'               // 保持連線
}
```

## 主要技術棧

- **框架**: Next.js 15.5.9 (App Router)
- **UI 框架**: React 18.3.1
- **語言**: TypeScript 5
- **樣式**: Tailwind CSS 4
- **聊天 UI**: @llamaindex/chat-ui 0.6.1
- **圖示**: Lucide React 0.542.0

## 可用指令

```bash
npm run dev      # 開發模式運行（預設 port 3001）
npm run build    # 編譯專案
npm start        # 生產模式運行（預設 port 3001）
npm run lint     # 執行程式碼檢查
```

## 連接埠與 API 說明

- **前端**：預設運行在 **port 3001**
- **後端 API**：`https://tainan-chatplus.ofido.tw/api`

### 修改前端 Port

如需修改前端 port，請編輯 `package.json` 中的相關指令：

```json
{
  "scripts": {
    "dev": "next dev --turbopack -p 3001",
    "start": "next start -p 3001"
  }
}
```

### 修改後端 API 位置

在您的頁面或元件中修改 `API_BASE_URL`：

```typescript
// 例如：app/chat/page.tsx
const API_BASE_URL = 'https://your-api-domain.com/api';
```

## 注意事項

1. **客戶端 API 呼叫**: 本專案使用 `'use client'`，所有 API 請求都在瀏覽器執行，請使用完整的域名而非 `localhost`
2. **後端服務**: 確保後端 API 服務已在 `https://tainan-chatplus.ofido.tw/api` 上運行
3. **CORS 設定**: 後端需正確設定 CORS，允許前端域名的請求
4. **環境變數**: 建議使用 `.env.local` 檔案來管理 API 端點：
   ```env
   NEXT_PUBLIC_API_BASE_URL=https://tainan-chatplus.ofido.tw/api
   ```
   然後在程式碼中使用：
   ```typescript
   const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL;
   ```
5. **串流請求取消**: 使用 `AbortController` 來取消進行中的串流請求
6. **錯誤處理**: 建議實作完整的錯誤處理機制，包含網路錯誤、逾時等情況

## 疑難排解

### 套件安裝失敗

```bash
# 清除快取重新安裝
rm -rf node_modules package-lock.json
npm install
```

### 連接後端 API 失敗

1. 檢查後端服務是否正在運行
2. 確認 `lib/api.ts` 中的 `API_BASE_URL` 設定正確
3. 檢查網路防火牆設定

### 編譯錯誤

```bash
# 清除 Next.js 快取
rm -rf .next
npm run build
```

## 授權

此專案為私有專案 (private: true)

## 聯絡資訊

如有問題或需要技術支援，請聯繫專案維護人員。
