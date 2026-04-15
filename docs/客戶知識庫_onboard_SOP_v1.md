# 客戶知識庫 Onboard SOP v1.0
**更新日期：2026-04-17**
**適用版本：CECLAW POC 階段（B70前）**

---

## 1. 客戶需要準備什麼文件

支援格式：PDF、DOCX、XLSX、圖片（PNG/JPG）

建議優先提供：
- 公司 SOP 文件
- 內部 FAQ
- 產品/服務說明書
- 人資政策手冊
- 法務合約範本
- IT 資安政策

不建議上傳：含員工個人資料的文件（姓名/身分證/薪資明細），這類資料不應進入共用知識庫。

---

## 2. 上傳流程

### Step 1：確認 ceclaw-docs 服務正常
```bash
curl -s http://localhost:8010/health
```

### Step 2：上傳文件進行結構化萃取
```bash
curl -X POST http://172.25.0.12:8010/extract \
  -F "file=@/path/to/document.pdf"
```

回傳格式：
```json
{
  "filename": "公司SOP.pdf",
  "doc_type": "技術文件",
  "extracted_data": {
    "標題": "...",
    "主要內容": "..."
  },
  "chunks_stored": 12,
  "text_length": 4823
}
```

### Step 3：確認分類正確
目前支援 7 種分類：合約、財報、HR文件、發票、會議紀錄、技術文件、其他

如果分類錯誤，告知軟工手動指定 doc_type 重新萃取。

### Step 4：文件存入客戶專屬 collection
目前 /extract 存入 `ceclaw_documents`（共用）。
客戶專屬 collection 需軟工手動建立（見下節）。

---

## 3. Collection 命名規則

| 類型 | 命名格式 | 範例 |
|------|---------|------|
| 客戶公司知識庫 | `ceclaw_company_{client_id}` | `ceclaw_company_htc` |
| 客戶部門知識庫 | `ceclaw_dept_{client_id}_{dept}` | `ceclaw_dept_htc_hr` |

`client_id` 規則：全小寫英文，無空格，簡短易識別。

建立新 collection 指令（在 GB10 執行）：
```bash
curl -X PUT "http://192.168.1.91:6333/collections/ceclaw_company_{client_id}" \
  -H "Content-Type: application/json" \
  -d '{
    "vectors": {
      "size": 1024,
      "distance": "Cosine"
    }
  }'
```

---

## 4. Router 查詢此 Collection

⚠️ 已知限制：Router（proxy.py）目前只查詢 `tw_knowledge`，collection 路徑硬寫死（第455行）。客戶專屬 collection 暫時查不到。

**B70前 Workaround：**
使用 ceclaw-legal/hr/finance 等 Agent 的 workspace，把客戶文件放進對應 Agent 的 SOUL.md 或 vault，讓 Hermes file tool 存取。實際做法是把客戶文件用 ceclaw-docs /extract 跑完後，把 extracted_data 複製貼進對應 Agent 的 SOUL.md 知識區段，讓 OpenClaw 直接讀到。

**B70後正式方案：**
修改 `proxy.py` 的 RAG 查詢邏輯，改為動態查詢多個 collection：
```python
# 查詢順序：ceclaw_company_{client_id} → tw_knowledge → tw_laws
collections = [f"ceclaw_company_{client_id}", "tw_knowledge", "tw_laws"]
```
這個修改排在 B70後路線第5項（Router 智慧化）。

---

## 5. 驗證方法

### 確認文件已存入
```bash
curl -s "http://192.168.1.91:6333/collections/ceclaw_company_{client_id}/points/count" \
  -X POST -H "Content-Type: application/json" \
  -d '{}' | python3 -c "import json,sys; d=json.load(sys.stdin); print('筆數:', d['result']['count'])"
```

### 語意搜尋測試
```bash
# 直接打 Qdrant 確認向量存入
curl -s "http://192.168.1.91:6333/collections/ceclaw_company_{client_id}/points/scroll" \
  -X POST -H "Content-Type: application/json" \
  -d '{"limit": 3, "with_payload": true}' \
  | python3 -c "
import json,sys
d=json.load(sys.stdin)
for p in d.get('result',{}).get('points',[]):
    print(p.get('payload',{}).get('title',''))
"
```

### 端對端測試
在 Hermes UI 問一個只有客戶文件才知道答案的問題，確認 Agent 能正確回答。

---

## 已知限制（POC階段）

| 限制 | 說明 | 解法時間 |
|------|------|---------|
| Router 查不到客戶 collection | proxy.py 硬寫死 tw_knowledge | B70後 Router 智慧化 |
| /extract 存入共用 ceclaw_documents | 未做 client_id 隔離 | B70後多租戶架構 |
| 單次上傳無預覽 | P1-4 文件上傳預覽本週六完成 | 週六 |

---

## 版本歷史
| 版本 | 日期 | 說明 |
|------|------|------|
| v1.0 | 2026-04-17 | 初版，POC階段適用 |
