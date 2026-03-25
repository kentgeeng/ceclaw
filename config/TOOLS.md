# TOOLS.md - Local Notes

## Web Search & Fetch

### 【強制規則】需要即時資訊時，你必須主動呼叫工具

以下情況**禁止**直接回答，**必須**先呼叫工具取得資料：
- 天氣、氣溫、降雨
- 股價、匯率、指數
- 新聞、最新事件
- 任何可能過期的數據

嚴禁編造即時數據。無法取得時，必須明確告知用戶。

---

### web_search — 搜尋即時資訊

使用時機：天氣、股價、新聞、任何需要搜尋的查詢

範例：
- 用戶問「台北天氣」→ 立刻呼叫 web_search("台北天氣")
- 用戶問「台積電股價」→ 立刻呼叫 web_search("台積電 股價")

---

### web_fetch — 讀取指定網頁內容

使用時機：已知 URL，需要抓取完整內容

常用 URL：
- 天氣：`https://wttr.in/taipei?format=3`
- 台北詳細天氣：`https://wttr.in/taipei?format=j1`

範例：
- 用戶問「台北現在幾度」→ 立刻呼叫 web_fetch("https://wttr.in/taipei?format=3")
- 用戶問「幫我查一下這個網頁」→ 立刻呼叫 web_fetch(用戶給的 URL)

---

### 重要

- 取得結果後，用繁體中文整理回覆用戶
- 無法取得即時資訊時，必須告知用戶，嚴禁編造數據
- 外網存取透過 CECLAW Router proxy，POC 階段全開放
