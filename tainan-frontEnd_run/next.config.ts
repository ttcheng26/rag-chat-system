import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // 1. 忽略 ESLint 檢查
  eslint: {
    ignoreDuringBuilds: true,
  },
  // 2. 忽略 TypeScript 型別錯誤
  typescript: {
    ignoreBuildErrors: true,
  },

  // 3. API 轉發設定 - 使用環境變數
  async rewrites() {
    // Docker 環境中使用 backend 服務名稱，本機開發用 localhost
    const backendUrl = process.env.BACKEND_URL || 'http://backend:8001';
    
    return [
      {
        source: '/api/:path*',
        destination: `${backendUrl}/:path*`,
      },
    ];
  },
  // 4. 增加 API 超時時間
  experimental: {
    proxyTimeout: 300000, // 5 分鐘
  },
};

export default nextConfig;