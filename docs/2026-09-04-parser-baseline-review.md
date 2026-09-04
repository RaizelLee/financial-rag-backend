# 2026-09-04 財報 PDF Parser Baseline 複習

> 目的：這份文件不是記錄「今天產生了哪些檔案」，而是幫助我理解今天解決了什麼問題、程式如何運作、有哪些限制，以及我是否能不靠 AI 說明與修改它。

## 一、今天完成了什麼

今天完成的是 P2 Financial Report RAG Backend 的第一個工程里程碑：

> 將一份真實財報逐頁檢查，提取可用文字，保留來源與頁碼，辨認不能直接解析的頁面，並輸出可供後續 chunking 使用的結構化資料。

使用的財報為台積電 2025 年合併財務報表，共 85 頁。

實際結果：

| 項目 | 結果 |
|---|---:|
| PDF 總頁數 | 85 |
| 可直接提取文字的頁數 | 71 |
| 無可用文字層的頁數 | 14 |
| 偵測到金額格式的頁數 | 55 |
| 需要 OCR 或替代 parser 的頁面 | 1–14 |

目前建立的主要輸出：

| 檔案 | 用途 |
|---|---|
| `scripts/parser_spike.py` | 執行逐頁解析與診斷 |
| `artifacts/parsed_pages.json` | 完整 85 頁的本機解析結果，不上傳 Git |
| `artifacts/parser_sample.json` | 代表性頁面，供人工檢查 |
| `artifacts/parser_summary.json` | 解析統計與問題頁面摘要 |
| `docs/parser-spike-notes.md` | 工程結果、限制與決策紀錄 |

## 二、它在完整 RAG 系統中的位置

完整的 RAG 流程是：

```text
PDF
→ parsing
→ text normalization
→ chunking
→ embedding
→ vector database
→ retrieval
→ LLM answer
→ citation
→ evaluation
```

今天只完成最前面的 parsing baseline。

今天沒有做：

- Chunking
- Embedding
- Vector database
- LLM 問答
- OCR
- 表格結構重建
- RAG evaluation

這樣安排的原因是：如果 PDF 解析結果本身不可靠，後面的 embedding、retrieval 和 LLM 都只是在放大錯誤。

## 三、Parser 到底做了什麼

Parser 對每一頁執行以下步驟：

```text
開啟 PDF
→ 逐頁讀取
→ 嘗試提取文字
→ 計算文字長度與文字區塊
→ 檢查一般圖片物件
→ 尋找可能的財務金額
→ 判斷頁面解析狀態
→ 保存來源、頁碼、文字、metadata 和 diagnostics
```

每一頁輸出的概念結構如下：

```json
{
  "source_id": "TSMC_2025Q4_Consolidated_Financial_Statements_C",
  "pdf_page": 52,
  "text": "提取到的原始文字",
  "metadata": {
    "company": "台灣積體電路製造股份有限公司",
    "reporting_period": "2025FY",
    "currency": "TWD",
    "default_unit": "thousand"
  },
  "extraction_status": "text_extracted",
  "diagnostics": {
    "text_chars": 1000,
    "text_blocks": 30,
    "image_count": 0,
    "contains_amounts": true,
    "amount_count": 20
  }
}
```

### `source_id`

識別資料來自哪一份文件。未來同時加入不同公司或年度時，不能只靠頁碼判斷來源。

### `pdf_page`

保存原始 PDF 頁碼。未來 LLM 回答問題時，必須能引用證據頁面。

### `text`

實際提取出的文字。後續 chunking 處理的是這個欄位。

### `metadata`

描述這段資料的附加資訊，例如公司、期間、幣別、預設單位及是否為合併報表。

Metadata 有兩個主要用途：

1. 在檢索前過濾錯誤公司或年度。
2. 產生引用與數值背景，避免只回答一個沒有單位的數字。

### `extraction_status`

目前有兩種狀態：

- `text_extracted`：本頁有可提取文字。
- `needs_ocr_or_alternative_parser`：本頁沒有可用文字層。

### `diagnostics`

Diagnostics 是用來除錯與評估資料品質，不是直接提供給使用者的答案。

## 四、今天遇到的問題與真正原因

### 問題一：最初的 JSON 前十頁全部是空字串

最初觀察：

```json
{
  "pdf_page": 1,
  "text": ""
}
```

一開始可能誤以為整份 PDF 都不能解析，但真正原因是：

- PDF 有 85 頁。
- 第 1–14 頁沒有正常文字層。
- 第 15–85 頁具有可提取文字。
- 原本 sample 使用 `pages[:10]`，剛好只輸出不能解析的前十頁。

因此，問題不是「整份 PDF 都壞掉」，而是「抽樣策略只看了沒有文字層的範圍」。

### 問題二：`image_count = 0`，頁面看起來卻不是空白

PDF 頁面可以包含不同物件：

- 真正的文字物件
- 一般圖片物件
- 向量繪圖路徑
- 表單或其他 PDF 物件

因此：

```text
text_chars = 0
image_count = 0
```

不等於頁面是空白。文字可能被轉成向量路徑畫在頁面上，人類看得到，但一般文字 parser 無法把它當作字元提取。

### 問題三：第一版 sample 沒有看到財務金額

改成 `extractable_pages[:10]` 後，sample 是第 15–24 頁。這些頁面主要是：

- 公司沿革
- IFRS 準則
- 會計政策
- 金融工具定義

它們本來就不是主要金額頁面。

這表示 parser 可以工作，但 sample 沒有驗證真正重要的財務數字。

後來改成代表性頁面：

```text
15, 18, 31, 38, 52, 54, 58, 62, 67, 71
```

其中包含：

- 第 31 頁：現金及約當現金
- 第 52 頁：營業收入
- 第 58 頁：每股盈餘
- 其他包含複雜表格與大量金額的頁面

這次修正的重點不是 parser 演算法，而是改善 QA sample 的代表性。

## 五、金額偵測 Regex 的用途與限制

目前使用 regular expression 尋找以下格式：

```text
3,809,054,272
86,642,964
66.26
```

用途是快速找出「可能含有財務金額」的頁面，方便人工 QA。

它不能證明：

- 這個數字一定是金額。
- 數字屬於哪一個財務項目。
- 數字屬於哪一年。
- 數字的單位一定是仟元。
- 數字是否為正確欄位。

因此：

> 偵測到數字，不等於理解數字。

Regex 是 diagnostics，不是財務表格解析器。

## 六、為什麼「文字提取成功」仍不代表資料可靠

財報中的一般敘述文字通常可以正常解析，但表格可能失去：

- 欄與列的關係
- 年度與數值的對應
- 表格標題
- 跨行公司名稱
- 單位與數值的對應

例如 parser 可能取得：

```text
114年度 113年度
3,809,054,272 2,894,307,699
```

但必須確認數字順序真的分別對應 114 年與 113 年。

財務 RAG 最危險的錯誤不一定是「完全找不到數字」，而是：

> 找到一個真實數字，卻把它配到錯誤年度、公司、項目、幣別或單位。

## 七、為什麼今天不立刻做 OCR

第 1–14 頁沒有正常文字層，其中包含重要的主要財務報表。

但 baseline 階段先不加入 OCR，原因是：

1. OCR 會增加安裝與部署複雜度。
2. OCR 可能把 `0`、`O`、小數點、負號或括號辨識錯誤。
3. 表格 OCR 仍不保證保留列與欄的關係。
4. 第 15–85 頁已足以完成第一條 text-based RAG pipeline。
5. 先建立 baseline，之後才有數據判斷 OCR 改善多少。

工程決策：

```text
現在：使用第 15–85 頁完成 text RAG baseline
之後：針對第 8–14 頁加入 targeted OCR／table extraction
```

不是永遠不做 OCR，而是避免在尚未跑通 baseline 前擴張範圍。

## 八、程式各區塊應該能怎麼解釋

### 1. Paths

```python
PROJECT_ROOT = Path(__file__).resolve().parents[1]
```

用途：從 script 自己的位置找到專案根目錄，因此不需要依賴目前 PowerShell 停在哪個資料夾。

### 2. Document metadata

集中定義公司、期間、幣別和報表類型，讓每一頁都能帶有相同文件背景。

### 3. `AMOUNT_PATTERN`

用 regex 尋找帶千分位逗號或小數點的數值，只供 diagnostics 與 sample 選擇。

### 4. `write_json()`

集中管理 JSON 輸出：

- 自動建立父資料夾
- 使用 UTF-8
- 保留繁體中文
- 使用縮排方便人工閱讀

### 5. `extract_pages()`

核心 parser function：逐頁提取文字、圖片與 blocks，建立 page-level dictionary。

### 6. `create_sample_pages()`

從完整頁面中選擇代表性頁面，供人工 QA。它不是 ingestion 的資料來源。

### 7. `create_summary()`

計算解析統計：總頁數、成功頁面、問題頁面、含金額頁面。

### 8. `main()`

負責組合整個流程：

```text
extract
→ create sample
→ create summary
→ write three JSON files
→ print results
```

## 九、三個 JSON 為什麼要分開

### `parsed_pages.json`

完整資料，用於下一階段 chunking。它很大、可重新產生，因此不提交 Git。

### `parser_sample.json`

小型、具代表性的 QA 證據，讓 reviewer 不必打開完整 85 頁資料就能檢查品質。

### `parser_summary.json`

提供數量化結果，證明 parser 不只是「看起來有執行」，而是有統計成功與失敗範圍。

## 十、Git 與資料安全決策

應提交：

- Parser code
- 小型 sample
- Summary
- ADR
- Data card
- Parser notes
- README
- `.env.example`
- Dependency file

不應提交：

- `.env`
- API key
- 原始 PDF
- 完整 `parsed_pages.json`
- Virtual environment
- Qdrant storage

原因：原始資料與 generated artifacts 可重新建立；Git 應保存程式、決策與可驗證的小型證據。

## 十一、我今天實際做出的判斷

雖然 AI 協助提供程式與分析方式，但我今天至少做了以下重要判斷：

1. 實際執行 parser，而不是只閱讀程式。
2. 發現輸出的文字全空，並提供 diagnostics。
3. 質疑 sample 為什麼完全沒有財務金額。
4. 驗證不能只看程式成功執行，還要看資料內容。
5. 決定暫時不讓 OCR 擴張 baseline 範圍。
6. 將 generated data、source PDF 與 Git 證據分開管理。

其中「發現 JSON 沒有金額」是很重要的 QA 行為。這代表我不是只確認程式沒有 exception，而是開始檢查輸出是否符合業務目的。

## 十二、閉卷複習題

在不看答案的情況下，口頭回答：

1. 為什麼最初輸出的前十頁都是空字串？
2. 為什麼 `image_count = 0` 不代表頁面是空白？
3. `source_id` 和 `pdf_page` 對未來 RAG 有什麼用途？
4. Metadata 和原始文字有什麼不同？
5. Regex 找到金額後，為什麼仍不能直接回答財務問題？
6. 為什麼第 18 頁的文字可提取，表格卻仍不可靠？
7. 為什麼今天不立刻導入 OCR？
8. `parsed_pages.json`、`parser_sample.json`、`parser_summary.json` 各自有什麼用途？
9. 為什麼不能把完整 `parsed_pages.json` 當作品集主要證據？
10. Parser 完成後，下一步為什麼是 chunking，而不是直接問 LLM？

達標標準：至少能不看文件回答 8 題，而且回答不只是一句名詞。

## 十三、閉卷答案重點

1. 因為 PDF 第 1–14 頁無正常文字層，而 sample 原本只取前十頁。
2. PDF 內容也可能由向量繪圖路徑或其他物件構成。
3. 用於來源追蹤、metadata filtering 和答案引用。
4. 原始文字是內容；metadata 描述公司、期間、頁碼、幣別與報表背景。
5. Regex 不知道數字對應的年度、項目、單位與表格欄位。
6. 純文字提取通常不能保存二維表格的 row-column structure。
7. 先完成 text baseline，避免增加 OCR 錯誤與部署複雜度。
8. 分別用於完整處理、人工 QA、數量化摘要。
9. 它很大、可重新產生，而且沒有清楚呈現工程判斷。
10. 必須先把長文字切成可檢索、仍保留來源語意的 chunks。

## 十四、我應該能獨立完成的小修改

明天開始 chunking 前，不看 AI 產生的新程式，嘗試完成一個修改：

> 在 `parser_summary.json` 增加 `extraction_success_rate`。

計算方式：

```text
可提取文字頁數 ÷ 總頁數
71 ÷ 85 ≈ 0.8353
```

輸出可以是：

```json
{
  "extraction_success_rate": 0.8353
}
```

完成步驟：

1. 找到 `create_summary()`。
2. 使用現有的 `extractable_pages` 與 `pages`。
3. 將結果四捨五入到小數點後四位。
4. 重新執行 parser。
5. 檢查 summary 是否更新。

這個小修改的目的不是增加功能，而是確認我能讀懂並改動今天的程式。

## 十五、面試時可以怎麼說

### 一分鐘版本

> 我使用 PyMuPDF 對一份 85 頁的台積電合併財務報表做 parser spike。最初前十頁全部回傳空字串，我沒有直接假設整份文件不可用，而是增加逐頁 diagnostics，最後發現這是一份混合型 PDF：前 14 頁沒有可提取文字層，後 71 頁可以正常提取。我保留 source ID、PDF page、公司、期間、幣別與單位等 metadata，並將完整輸出、QA sample 與統計摘要分開。另一個重要發現是，文字 parser 可以取得財務金額，但不一定保留表格的年度與欄位關係，所以我把 OCR 和 table extraction 延後，先建立 text-based RAG baseline，後續再用 evaluation 驗證 targeted parsing 的改善。

### 面試追問：最大的風險是什麼？

> 最大風險不是完全找不到數字，而是找到真實數字後，將它配到錯誤年度、公司、單位或表格欄位。因此後續除了 retrieval 指標，也需要針對數值、引用頁面和 abstention 設計測試。

### 面試追問：為什麼不用 OCR 處理全部頁面？

> 因為 71 頁已有文字層，全文件 OCR 會增加成本、延遲與辨識錯誤。比較合理的方式是先完成 baseline，再只對缺少文字層且確實重要的頁面做 targeted OCR。

## 十六、15 分鐘複習流程

每次複習只做：

1. 3 分鐘：畫出 PDF → parser → JSON → chunking 的流程。
2. 4 分鐘：口述今天三個問題及根因。
3. 4 分鐘：打開 `parser_spike.py`，逐個 function 說明輸入與輸出。
4. 4 分鐘：回答任選兩個面試問題。

## 十七、今天的真正達標線

不是背下全部程式碼，而是能做到：

- 說明 parser 在 RAG 中的位置。
- 解釋為什麼前 14 頁無法提取。
- 說明三個 JSON 的差異。
- 解釋 metadata 和 diagnostics。
- 說明「抓到數字」不等於「理解表格」。
- 說明延後 OCR 的工程取捨。
- 能在沒有 AI 重新生成整份程式的情況下，完成一個小修改。

達到這些條件後，今天的成果才真正從「AI 幫我完成」轉變為「我能理解、驗證並延伸的工程成果」。
