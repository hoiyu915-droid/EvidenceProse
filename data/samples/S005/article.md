# LitTraceQA：答案對，不代表整條證據鏈都對

## 一句話總結

LitTraceQA 是一個要求系統同時交出「相關論文＋定位證據＋最終答案」三段可查證紀錄的文獻問答基準，並將三段分開評分、joint success 採嚴格聯集判定，用來揭穿「答案聽起來對，但論文找錯、證據也對不上」這種常見的假陽性。

## 內容

### 這篇論文想解決什麼問題

現有的科學文獻問答基準大多只看「答案對不對」，或是乾脆先把來源論文餵給模型，跳過「自己去找對論文」這一關。LitTraceQA（Liu, Wang, Shi, Xue, Ke, Cai, Choi, Wu, Shi & Czarnecki, 2026）的立場是：一個可信賴的系統必須先從論文池裡找到對的論文，再定位到論文裡具體的證據，最後才產生一個「主張可以被查核」的答案。答案正確、但論文找錯，或論文對了、證據卻牛頭不對馬嘴，都不算真正解決了「literature-grounded QA」這個任務。

### 任務怎麼定義

給定一個研究問題 q 與一個論文中繼資料池 P，系統要回傳三個連動的輸出：
- 相關論文的正式識別碼（canonical paper IDs）
- 支持答案的證據位置（evidence locations，包含論文、證據型態、頁碼，表格與圖另外附物件 ID）
- 依照要求格式產生的答案（自由文字、選擇題，或結構化表格）

任務依三個正交的схема軸切分：task family（hidden-source single-paper／multi-paper）、primary evidence type（表格、圖、文字段落、公式或演算法、引用脈絡）、answer type（free-form／MC／table）。公開開發集（public development split）用完整 schema，含 free-form 答案；較大的本地標註集合（local annotation collection）目前只收 MC 與 structured table 兩種答案格式，方便自動化查核。

### 五種證據類型，不是只有文字段落

LitTraceQA 特別強調科學論文閱讀常見的五種證據來源：表格（比較不同論文回報的數字）、圖（讀圖表趨勢）、文字段落（方法或設定描述）、公式或演算法（形式化流程）、引用脈絡（論文如何定位自己與前人研究的關係）。這個設計是刻意的：如果把科學論文 QA 簡化成「找一段文字」，會漏掉表格、圖、公式這些同樣關鍵、但性質完全不同的證據型態。

### 資料是怎麼建構出來的

公開開發集有 55 題，其中 26 題是 hidden-source single-paper（不直接告訴你答案在哪篇論文），29 題是 multi-paper，涵蓋全部五種證據類型。

較大的本地標註集合則用「generate–ground–challenge」流程從 27,487 篇近期 ML／CV／NLP 論文中生成、驗證與篩選：
1. 開放書生成器（open-book generator）讀論文文字，產生問題、gold papers、typed evidence、答案；
2. 自動化 grounding 檢查驗證證據確實屬於宣稱的論文、且文字或數值可在論文原文中找到；
3. 同一個問題再丟給沒有拿到論文內容的 closed-book challenger 模型（GPT、Claude、Gemma）測試——如果光靠模型記憶就能穩定猜對，這題會被篩掉。

去除跨檢查點重複問題後，最終本地集合有 4,978 題不重複問題，涵蓋 4,859 篇不重複 gold papers、8,612 個論文—問題連結，平均每題 1.73 篇論文、2.62 個證據項目。

### 這批資料長什麼樣子

- 題目範疇：64.85% 是 multi-paper（需要跨論文對齊證據），35.15% 是 single-paper。
- 答案格式：60.8% 選擇題，39.2% 結構化表格（本地集合不含 free-form）。
- 主證據類型：表格 26.9%、圖 22.7%、文字段落 18.7%、公式／演算法 16.5%、引用脈絡 15.2%。
- 證據項目本身更混合：文字段落證據項目占 43.5%、表格 16.1%、引用脈絡 14.6%、公式／演算法 13.2%、圖 12.6%——代表就算主標籤是「表格題」，答案往往還是需要輔助文字才能確認。
- Closed-book 難度標籤：61.9% 的題目是三個 challenger 模型全部答錯，38.1% 是剛好有一個答對。這個比例記錄的是「建構資料時，用來篩掉可被模型記憶猜中的題目」的 hardness metadata，不是有論文可查（RAG）情境下的模型排行榜表現，兩者不能混為一談。
- 來源分布：8,612 個 gold-paper 連結中，ICCV 2025 占 48.6%，其次是 NAACL 2025（11.3%）與 ACL 2025（10.7%），其餘來自 ICLR、ICML、CVPR、ECCV、NeurIPS、EMNLP；作者自陳這是目前收集的偏斜、不是刻意的領域聚焦定論。
- 其他稽核發現：918 組 gold-paper set 重複、72 筆（1.4%）證據項目少於兩個，這些被作者列為 release 前需要處理的資料平衡問題，而非個別題目的正確性問題。

### 怎麼評分——三段分開算，joint success 是嚴格聯集

LitTraceQA 主張三段分開評分，而不是把它們平均成一個總分：
- 論文檢索：question-level precision／recall／F1（macro 平均），若系統回傳排序列表可另外報 Recall@K、MRR、MAP、nDCG。
- 證據定位：對照論文＋證據型態＋頁碼＋（表格用 table ID、圖用 figure ID）的粗粒度 exact match，可再輔以 precision／recall／F1。
- 答案正確性：選擇題用準確率，自由文字用 exact match，結構化表格用 row-level F1 加 cell accuracy。

Joint success 要求三段全部正確，是嚴格的邏輯 AND，不是三個分數的平均——這點論文特別強調，因為一個「答案對、論文卻找錯」的系統，並沒有真正解決 grounded QA。

論文另外提供一組 oracle 診斷階梯，用來拆解失敗發生在哪一段：
- End-to-end：只給問題和論文池，測完整能力；
- Oracle paper：直接給 gold papers，只測證據定位與答案；
- Oracle evidence：連 gold evidence 都給，只測最後一步答案生成。

這三層設定不是額外的模型成績，而是拿來定位「系統到底是找錯論文、找錯證據，還是證據對了但還是答錯」的診斷工具。

### 論文自己承認的限制

作者在文中列出五項發布前還沒完成的事項：證據定位欄位需要正規化（目前 locator 欄位彈性太大，不利跨型態自動評分）；需要定義正式的 public／hidden split；需要交代論文文字與標註的授權與再散布狀態；需要補上人工審查或專家抽查程序（目前主要靠自動化生成、grounding 檢查與 challenger 驗證）；需要用同一套三段指標實測 retrieval-augmented baseline 系統。換句話說，這篇論文目前的定位是「benchmark-development paper ＋ 公開開發集」，而不是已經走完全部發布治理流程的正式 benchmark release。

### 為什麼這個設計值得注意

多數科學 QA 基準把「找對論文」「找到證據」「答對」三件事混在一起算分，容易讓「答案聽起來合理但沒有可查證來源」的系統被高估。LitTraceQA 把三段拆開、要求嚴格聯集才算成功，等於是把「答案正確」與「證據可追溯」兩件事分開檢驗，這個評分設計對任何要用 LLM 做文獻檢索與問答輔助的應用場景（包含 RAG 系統）都是可以直接借鏡的診斷框架。

### 證據分級

🟢 任務定義、schema、三段評分協定、oracle 診斷階梯：屬於論文自行定義的方法論設計，並非需要外部驗證的實證主張。
🟡 4,978 題本地集合的統計數字（比例、證據型態分布、venue 分布、closed-book 難度標籤）：來自作者自陳的資料集稽核，屬於同一團隊的自我報告，尚未經外部或第三方複核；作者本人也承認這批資料距離正式 release 還有多項待完成工作（locator 正規化、official split、授權文件、人工品管、baseline 實測），本文據此如實呈現「benchmark-development 階段」的定位，而非已完工的公開基準。
🟡 公開開發集（55 題）的規模與組成：作者提供，供社群本地驗證用，尚無獨立第三方使用結果可供對照。

## 引用來源

Liu, X., Wang, Y., Shi, P., Xue, B., Ke, X., Cai, S., Choi, K., Wu, D., Shi, F., & Czarnecki, K. (2026). LitTraceQA: A Benchmark for Multi-Stage Grounding and Verification in Scientific Question Answering. *arXiv:2608.07370v1*.

> 最後更新：20260811
