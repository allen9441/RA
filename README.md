## 目錄 README.md


# 一鍵處理 DAT→Excel、合併 HQ/LQ、繪圖工具

提供一個命令列介面（CLI），可依序或分別執行：

1. **模式1**：將 `.dat` 檔案分類至 `hq`、`lq` 資料夾，並匯出 `hq_data.xlsx`、`lq_data.xlsx`。  
2. **模式2**：讀取 `hq_data.xlsx`、`lq_data.xlsx`，計算並應用縮放因子，輸出 `all_data.xlsx`。  
3. **模式3**：載入 `all_data.xlsx`，並以互動式視窗繪製分群曲線圖。  


### 安裝環境
```bash
pyton -m pip install -r requirements.txt
````

### 結構

````
main.py              # CLI 入口
utils/               # 模式處理器模組
  mode1_processor.py
  mode2_merger.py
  mode3_plotter.py
````

### 使用範例

````bash
# 預設繪圖模式（mode3）
python main.py --path ./G32

# 所有步驟
python main.py --mode all --path ./G32

# 只轉檔與匯出 Excel
python main.py --mode 1 --path ./G32

# 只合併 HQ/LQ
python main.py --mode 2 --path ./G32

# 自訂繪圖間隔
python main.py --mode 3 --path ./G32 --interval 20
````

---

## `utils/mode1_processor.py`


# Mode1Processor

負責：將資料夾中的 `.dat` 檔案分類並匯出 Excel

## 類別
````python
class Mode1Processor:
    def __init__(self, target_dir: str): ...
    def run(self): ...  # 建立 hq/lq，輸出 hq_data.xlsx, lq_data.xlsx
````

## 用法

````python
from utils.mode1_processor import Mode1Processor
proc = Mode1Processor("./G32")
proc.run()
````

### 主要參數

* `target_dir`: 要處理的資料夾路徑，程式會在該目錄下建立 `hq`、`lq` 子資料夾並輸出 `.xlsx` 檔案。


---

## `utils/mode2_merger.py` 

# Mode2Merger
負責：讀取 `hq_data.xlsx`、`lq_data.xlsx`，計算 HQ 欄位縮放因子，合併輸出 `all_data.xlsx`

## 類別
````python
class Mode2Merger:
    def __init__(self, target_dir: str): ...
    def run(self): ...  # 讀取、計算、輸出 all_data.xlsx
````

## 用法

````python
from utils.mode2_merger import Mode2Merger
merger = Mode2Merger("./G32")
merger.run()
````

### 流程

1. 跳過 `hq_data.xlsx` 前 10 行載入 HQ 資料。
2. 篩選 LQ 資料中大於等於預設 X 值（`0.0024729`）。
3. 計算每欄位的縮放因子並調整 HQ 數值。
4. 合併後儲存 `all_data.xlsx`。



---

## `utils/mode3_plotter.py` 
# Mode3Plotter

負責：載入 `all_data.xlsx`，並以互動式視窗繪製二階導數分群曲線圖。

## 類別
````python
class Mode3Plotter:
    def __init__(self, target_dir: str, interval: int = 10): ...
    def run(self): ...  # 啟動互動視窗
````

## 用法

````python
from utils.mode3_plotter import Mode3Plotter
plotter = Mode3Plotter("./G32", interval=10)
plotter.run()
````

### 交互控制

* **Interval**：取樣間隔，決定每隔多少欄位畫一次曲線。
* **Shift**：垂直偏移倍數，用於分離曲線。
* **Cluster**：輸入群組編號（0–2）只顯示該群曲線。
* **1st Deriv／2nd Deriv**：切換一階或二階導數分群。
* **Q Start**、**Q End**、**Diff Step**：定義分群時的 Q 區間和差分步長。


