'use client';

import { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

const API_BASE_URL = "/api";

export default function Home() {
  const MarkdownComponent = ReactMarkdown.default || ReactMarkdown;
  const GfmPlugin = remarkGfm.default || remarkGfm;
  // 登入相關狀態
  const [token, setToken] = useState('');           // 存放在記憶體中的通行證
  const [isLoggedIn, setIsLoggedIn] = useState(false); // 判斷是否已登入
  const [role, setRole] = useState(''); // 目前登入者的身分 (root 或 user)
  const [username, setUsername] = useState('');     // 登入框輸入的帳號
  const [password, setPassword] = useState('');     // 登入框輸入的密碼
  const [loginError, setLoginError] = useState(''); // 登入失敗顯示的錯誤訊息

  const [input, setInput] = useState('');
  const [messages, setMessages] = useState(''); 
  const [progressMsg, setProgressMsg] = useState('');
  const [status, setStatus] = useState('閒置中');

  // 控制按鈕鎖定用
  const [isGenerating, setIsGenerating] = useState(false);

  const [files, setFiles] = useState([]); 
  const [uploading, setUploading] = useState(false);
  const [showKnowledge, setShowKnowledge] = useState(false);
  const [deleting, setDeleting] = useState(null); 

  const [showModal, setShowModal] = useState(false);
  const [modalMessage, setModalMessage] = useState('');
  const [modalType, setModalType] = useState('info'); 

  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [fileToDelete, setFileToDelete] = useState('');

  const [sessionId, setSessionId] = useState('');

  

  const showAlert = (message, type = 'info') => {
    setModalMessage(message);
    setModalType(type);
    setShowModal(true);
    setTimeout(() => setShowModal(false), 3000);
  };

  const fetchFiles = async () => {
    try {
      const res = await authFetch(`${API_BASE_URL}/files`);
      const data = await res.json();
      if (data.files) setFiles(data.files);
    } catch (e) {
      console.error("無法取得檔案列表", e);
    }
  };

  useEffect(() => {
    // 頁面載入時產生隨機 ID
    setSessionId(`session-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`);
    // 檢查 localStorage 有沒有存過的 Token
    const savedToken = localStorage.getItem('access_token');
    const savedRole = localStorage.getItem('user_role');
    if (savedToken) {
      setToken(savedToken);
      if (savedRole) setRole(savedRole);
      setIsLoggedIn(true);
      fetchFiles(); 
    }
  }, []);

  useEffect(() => {
    if (isLoggedIn && token) {
        fetchFiles();
    }
  }, [isLoggedIn, token]);

  // === 登入處理 ===
  const handleLogin = async (e) => {
    e.preventDefault(); // 防止表單重新整理
    setLoginError('');
    setStatus('登入中...');

    // 準備要傳給後端的資料
    const formData = new URLSearchParams();
    formData.append('username', username);
    formData.append('password', password);

    try {
      const res = await fetch(`${API_BASE_URL}/token`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: formData,
      });

      if (!res.ok) throw new Error('帳號或密碼錯誤');

      const data = await res.json();
      const accessToken = data.access_token;

      const userRole = data.role;

      // 登入成功：存入 LocalStorage + 更新狀態
      localStorage.setItem('access_token', accessToken);
      localStorage.setItem('user_role', userRole);
      setToken(accessToken);
      setRole(userRole);
      setIsLoggedIn(true);
      setStatus('登入成功');
      
      // 登入後馬上更新檔案列表
      fetchFiles(); 

    } catch (err) {
      setLoginError(err.message);
      setStatus('登入失敗');
    }
  };

  // === 登出處理 ===
  const handleLogout = () => {
    localStorage.removeItem('access_token'); // 清除瀏覽器紀錄
    localStorage.removeItem('user_role');
    setToken('');
    setRole('');
    setIsLoggedIn(false);
    setFiles([]);     // 清空檔案列表 
    setMessages('');  // 清空對話 
    setUsername('');
    setPassword('');
    setStatus('已登出');
  };

  // 以後上傳或刪除，改用 authFetch 取代原本的 fetch
  const authFetch = async (url, options = {}) => {
    const headers = {
      ...options.headers,
      'Authorization': `Bearer ${token}`, // 自動加上通行證
    };
    return fetch(url, { ...options, headers });
  };

  const handleUpload = async (e) => {
    if (!e.target.files || e.target.files.length === 0) return;
  
    if (!isLoggedIn) {
      showAlert('請先登入', 'error');
      return;
    }

    const selectedFiles = Array.from(e.target.files);

    if (selectedFiles.length > 10) {
      showAlert('最多只能同時上傳 10 個檔案', 'error');
      e.target.value = '';
      return;
    }

    setUploading(true);
    setStatus(`正在上傳 ${selectedFiles.length} 個檔案...`);
    
    let successCount = 0;
    let failCount = 0;
    const uploadedFiles = [];

    for (const file of selectedFiles) {
      const formData = new FormData();
      formData.append('file', file);

      try {
        const res = await authFetch(`${API_BASE_URL}/upload`, {
          method: 'POST',
          body: formData,
        });
        
        if (res.ok) {
          const data = await res.json();
          uploadedFiles.push(data.filename);
          successCount++;
          setStatus(`⏳ 已上傳 ${successCount}/${selectedFiles.length} 個檔案，處理中...`);
        } else {
          if (res.status === 401) throw new Error("憑證過期");
          failCount++;
        }
      } catch (error) {
        console.error(`上傳 ${file.name} 失敗:`, error);
        if (error.message.includes("憑證過期")) {
                handleLogout(); // 自動登出
                showAlert("憑證過期，請重新登入", "error");
                return; // 停止後續上傳
        }
        failCount++;
      }
    }

    if (uploadedFiles.length > 0) {
      pollAllFilesStatus(uploadedFiles, selectedFiles.length);
    } else {
      setUploading(false);
      setStatus('閒置中');
      showAlert('所有檔案上傳失敗', 'error');
    }

    e.target.value = '';
  };

  const pollAllFilesStatus = (filenames, totalCount) => {
    let completedCount = 0;
    let errorCount = 0;
    const fileStatus = {};
    
    filenames.forEach(f => fileStatus[f] = 'processing');

    const checkAllStatus = async () => {
      let allDone = true;
      
      for (const filename of filenames) {
        if (fileStatus[filename] === 'processing') {
          try {
            const statusRes = await fetch(`${API_BASE_URL}/upload-status?filename=${encodeURIComponent(filename)}`);
            const statusData = await statusRes.json();
            
            if (statusData.status === 'completed') {
              fileStatus[filename] = 'completed';
              completedCount++;
            } else if (statusData.status === 'error') {
              fileStatus[filename] = 'error';
              errorCount++;
            } else if (statusData.status === 'unknown') {
              const filesRes = await fetch(`${API_BASE_URL}/files`);
              const filesData = await filesRes.json();
              if (filesData.files && filesData.files.includes(filename)) {
                fileStatus[filename] = 'completed';
                completedCount++;
              } else {
                allDone = false;
              }
            } else {
              allDone = false;
            }
          } catch (err) {
            allDone = false;
          }
        }
      }
      
      const processingCount = filenames.filter(f => fileStatus[f] === 'processing').length;
      setStatus(`⏳ 處理中: ${completedCount}/${totalCount} 完成, ${processingCount} 處理中...`);
      
      if (allDone || (completedCount + errorCount >= filenames.length)) {
        setUploading(false);
        fetchFiles();
        
        if (errorCount === 0) {
          setStatus('✅ 全部處理完成！');
          showAlert(`成功上傳並處理 ${completedCount} 個檔案！`, 'success');
        } else {
          setStatus(`⚠️ ${completedCount} 個成功, ${errorCount} 個失敗`);
          showAlert(`${completedCount} 個檔案成功, ${errorCount} 個失敗`, 'info');
        }
      } else {
        setTimeout(checkAllStatus, 3000);
      }
    };

    checkAllStatus();
  };

  const confirmDelete = (filename) => {
    setFileToDelete(filename);
    setShowDeleteConfirm(true);
  };

  const handleDelete = async () => {
    if (!fileToDelete) return;
    
    setShowDeleteConfirm(false);
    setDeleting(fileToDelete);
    
    try {
      const res = await authFetch(`${API_BASE_URL}/files?filename=${encodeURIComponent(fileToDelete)}`, {
        method: 'DELETE',
      });
      
      if (res.ok) {
        showAlert(`檔案「${fileToDelete}」已刪除`, 'success');
        fetchFiles();
      } else {
        if (res.status === 401) {
          handleLogout();
          showAlert("登入逾時，請重新登入", "error");
          return;
        }
        if (res.status === 403) {
          showAlert("權限不足：只有管理員(root)可以刪除檔案", "error");
          return;
        }
        const data = await res.json();
        showAlert(`刪除失敗: ${data.detail || '未知錯誤'}`, 'error');
      }
    } catch (error) {
      console.error('刪除失敗:', error);
      showAlert('刪除失敗，請檢查後端是否開啟', 'error');
    } finally {
      setDeleting(null);
      setFileToDelete('');
    }
  };

  const sendMessage = async () => {
    // 防連點檢查
    if (!input || isGenerating) return;
    
    setIsGenerating(true);
    setMessages('');
    setProgressMsg('正在分析您的問題......');
    setStatus('請求中...');

    try {
      const response = await fetch(`${API_BASE_URL}/stream-chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'text/event-stream',
        },
        body: JSON.stringify({
          message: input,
          session_id: sessionId, // 使用動態生成的 session ID
        }),
      });

      if (!response.ok) throw new Error('連線失敗');
      if (!response.body) throw new Error('沒有回傳 Body');

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      setStatus('接收串流中...');

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        // const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n');
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const dataStr = line.slice(6);
            
            if (dataStr === '[DONE]') {
              setStatus('完成');
              break;
            }

            try {
              const data = JSON.parse(dataStr);
              
              if (data.type === 'chunk' && data.content) {
                setMessages(prev => prev + data.content);
                setProgressMsg('');
              } 
              else if (data.type === 'progress') {
                setProgressMsg(data.content);
                setStatus(data.content); 
              }
              else if (data.type === 'search_results') {
                console.log('收到搜尋結果:', data);
              }
              else if (data.error) {
                console.error('API 錯誤:', data.error);
                setMessages(prev => prev + `\n[錯誤]: ${data.error}`);
              }
            } catch (e) {}
          }
        }
      }
    } catch (error) {
      console.error(error);
      setStatus('發生錯誤');
    } finally {
      // 無論成功失敗，一定要解鎖
      setIsGenerating(false);
      setProgressMsg('');
    }
  };

  if (!isLoggedIn) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-100 font-sans">
        <div className="bg-white p-8 rounded-xl shadow-lg w-full max-w-md">
          <h1 className="text-2xl font-bold mb-6 text-center text-gray-800">登入</h1>
          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="block text-gray-700 mb-2">帳號</label>
              <input type="text" value={username} onChange={(e) => setUsername(e.target.value)} className="w-full border p-2 rounded focus:ring-2 focus:ring-blue-500 outline-none text-black" placeholder="請輸入帳號" />
            </div>
            <div>
              <label className="block text-gray-700 mb-2">密碼</label>
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="w-full border p-2 rounded focus:ring-2 focus:ring-blue-500 outline-none text-black" placeholder="請輸入密碼" />
            </div>
            {loginError && <div className="text-red-500 text-sm text-center">{loginError}</div>}
            <button type="submit" className="w-full bg-blue-600 text-white py-2 rounded hover:bg-blue-700 transition">登入</button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-4xl mx-auto font-sans relative">
      <div className="absolute top-4 right-4">
         <button onClick={handleLogout} className="text-sm text-gray-500 hover:text-red-500 underline">
            登出 ({username || 'User'})
         </button>
      </div>

      {/* Toast 通知 */}
      {showModal && (
        <div className="fixed top-4 right-4 z-50 animate-slide-in">
          <div className={`flex items-center gap-3 px-4 py-3 rounded-lg shadow-lg border ${
            modalType === 'success' ? 'bg-green-50 border-green-200' :
            modalType === 'error' ? 'bg-red-50 border-red-200' :
            'bg-blue-50 border-blue-200'
          }`}>
            <span className="text-2xl">
              {modalType === 'success' && '✅'}
              {modalType === 'error' && '❌'}
              {modalType === 'info' && 'ℹ️'}
            </span>
            <div className="flex-1">
              <p className={`font-medium ${
                modalType === 'success' ? 'text-green-800' :
                modalType === 'error' ? 'text-red-800' : 'text-blue-800'
              }`}>
                {modalType === 'success' && '操作成功！'}
                {modalType === 'error' && '發生錯誤'}
                {modalType === 'info' && '提示'}
              </p>
              <p className={`text-sm ${
                modalType === 'success' ? 'text-green-600' :
                modalType === 'error' ? 'text-red-600' : 'text-blue-600'
              }`}>{modalMessage}</p>
            </div>
            <button onClick={() => setShowModal(false)} className="text-gray-400 hover:text-gray-600">✕</button>
          </div>
        </div>
      )}

      {/* 刪除確認對話框 */}
      {showDeleteConfirm && (
        <div 
          className="fixed inset-0 flex items-center justify-center z-50"
          style={{ backgroundColor: 'rgba(0, 0, 0, 0.3)' }}
          onClick={() => setShowDeleteConfirm(false)}
        >
          <div 
            className="bg-white rounded-lg shadow-xl p-5 max-w-sm w-full mx-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-2 mb-3">
              <span className="text-xl">🗑️</span>
              <h3 className="text-lg font-bold text-gray-800">確認刪除</h3>
            </div>
            <p className="text-gray-600 text-sm mb-4">
              確定要刪除「<span className="font-medium text-red-600 break-all">{fileToDelete}</span>」嗎？
            </p>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowDeleteConfirm(false)}
                className="px-4 py-1.5 text-sm rounded font-medium text-gray-700 bg-gray-100 hover:bg-gray-200"
              >
                取消
              </button>
              <button
                onClick={handleDelete}
                className="px-4 py-1.5 text-sm rounded font-medium text-white bg-red-500 hover:bg-red-600"
              >
                刪除
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 標題 */}
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">談參資料 Chat API 測試</h1>
       {/* {role === 'root' && (
          <button 
            onClick={() => setShowKnowledge(!showKnowledge)}
            className="text-sm bg-gray-200 px-3 py-1 rounded hover:bg-gray-300 text-gray-700"
          >
            {showKnowledge ? '隱藏知識庫' : '管理知識庫'}
          </button>
        )} */}
        <button 
          onClick={() => setShowKnowledge(!showKnowledge)}
          className="text-sm bg-gray-200 px-3 py-1 rounded hover:bg-gray-300 text-gray-700"
        >
          {showKnowledge ? '隱藏知識庫' : '管理知識庫'}
        </button>
      </div>

      {/* 知識庫管理 */}
      {showKnowledge && (
        <div className="mb-8 p-6 bg-white border rounded-xl shadow-sm">
          <h2 className="text-xl font-semibold mb-4 text-gray-700 flex items-center gap-2">
            📚 知識庫文件列表
            {uploading && <span className="text-sm text-blue-500 font-normal animate-pulse">(正在處理中...)</span>}
          </h2>
          
          <div className="flex gap-4 mb-4">
            <label className={`cursor-pointer text-white px-4 py-2 rounded shadow transition ${uploading ? 'bg-gray-400 cursor-not-allowed' : 'bg-blue-500 hover:bg-blue-600'}`}>
              <span>📤 上傳新文件 (最多10個)</span>
              <input 
                type="file" 
                className="hidden" 
                onChange={handleUpload} 
                disabled={uploading}
                multiple
                accept=".pdf,.doc,.docx,.xls,.xlsx,.odt,.ods"
              />
            </label>
          </div>

          <div className="bg-gray-50 rounded-lg p-4">
            <h3 className="text-sm font-medium text-gray-500 mb-2">目前已索引檔案 ({files.length})：</h3>
            <ul className="grid grid-cols-1 gap-2 max-h-80 overflow-y-auto">
              {files.length > 0 ? (
                files.map((f, i) => (
                  <li key={i} className="flex items-center justify-between text-gray-700 bg-white p-3 rounded border border-gray-100 hover:border-gray-300">
                    <div className="flex items-center gap-2 flex-1 min-w-0">
                      <span className="text-green-500">📄</span>
                      <span className="truncate text-sm" title={f}>{f}</span>
                    </div>
                    {role === 'root' && (
                      <button
                        onClick={() => confirmDelete(f)}
                        disabled={deleting === f}
                        className={`ml-2 px-3 py-1 text-sm rounded transition ${
                          deleting === f 
                            ? 'bg-gray-200 text-gray-400 cursor-not-allowed' 
                            : 'bg-red-100 text-red-600 hover:bg-red-200'
                        }`}
                      >
                        {deleting === f ? '刪除中...' : '🗑️ 刪除'}
                      </button>
                    )}
                  </li>
                ))
              ) : (
                <li className="text-gray-400 text-sm p-2">暫無檔案，請上傳文件。</li>
              )}
            </ul>
          </div>
        </div>
      )}
      
      {/* 輸入區 */}
      <div className="flex gap-2 mb-4">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="請問需要幫您生成甚麼呢?"
          // 鎖定狀態
          disabled={isGenerating}
          className={`border p-2 flex-1 rounded text-black transition-colors ${
            isGenerating ? 'bg-gray-100 cursor-not-allowed' : 'bg-white'
          }`}
          onKeyDown={(e) => e.key === 'Enter' && sendMessage()}
        />
        <button 
          onClick={sendMessage}
          // 鎖定狀態
          disabled={isGenerating}
          className={`px-4 py-2 rounded text-white transition-colors ${
            isGenerating 
              ? 'bg-gray-400 cursor-not-allowed' 
              : 'bg-blue-500 hover:bg-blue-600'
          }`}
        >
          {isGenerating ? '生成中...' : '送出'}
        </button>
      </div>

      <div className="text-sm text-gray-500 mb-2">狀態: {status}</div>

      <div className="border p-4 rounded bg-gray-50 min-h-[200px] text-black leading-relaxed overflow-auto">
        {messages ? (
          <MarkdownComponent  
              remarkPlugins={[GfmPlugin]} 
              components={{
                strong: ({node, ...props}) => <strong className="font-bold" {...props} />,
                ul: ({node, ...props}) => <ul className="list-disc pl-5 my-2" {...props} />,
                li: ({node, ...props}) => <li className="mb-1" {...props} />,
                p: ({node, ...props}) => <p className="mb-2" {...props} />,
            }}
          >
            {messages}
          </MarkdownComponent>
        ) : (
          <div className={`text-gray-400 flex items-center gap-2 ${isGenerating ? 'animate-pulse' : ''}`}>
             {isGenerating ? (
               <>
                 <span>{progressMsg || '正在產生回應...'}</span>
               </>
             ) : (
               '等待回應...'
             )}
          </div>
        )}
      </div>
    </div>
  );
}
