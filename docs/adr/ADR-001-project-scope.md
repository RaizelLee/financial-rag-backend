# ADR-001：P2 第一版範圍

## 目標
建立一個能根據財報回答問題，並引用正確頁碼的 RAG API。

## 第一版使用者
想快速從指定公司財報中尋找證據的人。

## 第一版輸入
一家公司、一個年度、一份文字型財報 PDF。

## 第一版輸出
答案、引用原文、PDF 頁碼、公司、期間和單位。

## 成功條件
1. 能解析一份真實財報。
2. 能保留每段文字的頁碼。
3. 能回答至少 10 個測試問題。
4. 回答必須有來源。
5. 資料不足時不能亂答。

## 暫時不做
Agent、MCP、GraphRAG、Text2SQL、OCR、投資建議、
多公司、前端 UI、Kubernetes。

PDF
→ parser
→ page/section metadata
→ chunks
→ embeddings
→ vector database
→ retrieval
→ answer with citation
→ evaluation