# TOOLS.md - Local Notes

## Web Search & Fetch

### 搜尋即時資訊
使用 web_search tool：
- 天氣、股價、新聞、任何需要搜尋的查詢

### 讀取任意網頁內容
使用 web_fetch tool，可抓取任意 URL：
- 新聞全文、文件、API 回應、任何公開網頁
- URL 透過 CECLAW Router proxy 存取，sandbox 無法直連外網
- 格式：web_fetch("https://任意網址")

### 重要
無法取得即時資訊時，必須告知用戶，嚴禁編造數據。
