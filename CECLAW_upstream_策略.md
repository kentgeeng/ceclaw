# CECLAW Upstream 維護策略

## 元件策略

| 元件 | 策略 | 說明 |
|------|------|------|
| OpenClaw | 選項 A，永久 fork | Router 已完全替代其路由層，upstream 影響有限 |
| Hermes | 選項 B→C | B70 升級時把 P3 hook 改成 builtin_hooks/ |
| proxy.py | 完全自主 | 不依賴任何 upstream |

## Hermes P3 hook 重構（B70 後優先執行）

現況：直接改 `webapi/routes/chat.py`
目標：移到 `gateway/builtin_hooks/`，不碰 upstream 檔案

重構完成後，Hermes 升級流程：
1. git pull upstream
2. 驗證 hook 掛載點位置
3. 無衝突，直接部署

## 關鍵待辦

- [ ] Hermes v0.8.0 升級時順便重構 P3 hook（B70 搬家同批）


## CDC 驗證 → 客戶 OTA 流程

upstream 新版本 → CDC 測試環境（pop-os + GB10）72小時燒機
驗證項目：P3 hook / RAG 三層 / shared_bridge / vault
→ 通過 → 客戶 OTA：openshell sandbox update --name ceclaw-companyA

CDC 定位：L1/L2 生產節點 + 官方驗證環境（雙重角色）

## 銷售賣點

我們幫你擋 upstream 風險。每個版本在我們自己的環境跑過 72 小時才推給你，你不會是第一個踩坑的人。雲端 SaaS 做不到這個。
