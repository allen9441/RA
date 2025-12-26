# 📌 DAT → Excel → 合併 HQ/LQ → 自動繪圖工具

提供分析流程，從原始 `.dat` 檔案開始，自動完成：

1.  DAT 檔解析 → 輸出 Excel\
2.  HQ / LQ 曲線自動對齊與合併\
3.  多模式繪圖（simple / cluster / pick_auto）\
4.  自動產生高解析 PNG 與分析結果 Excel
------------------------------------------------------------------------

# ⭐ 功能總覽

### 🔧 Mode 1：DAT → Excel

-   自動搜尋、分類 `.dat` 檔\
-   檔名含 `1M` → HQ，其餘 → LQ\
-   解析曲線、跳過 DISTRIBUTION 區塊\
-   輸出：
    -   `hq_data.xlsx`
    -   `lq_data.xlsx`

------------------------------------------------------------------------

### 🔧 Mode 2：合併 HQ + LQ → all_data

-   根據 LQ 有效 Q 區段建立基準\
-   自動計算 HQ → LQ 的 scaling factor\
-   自動對齊、合併兩者\
-   輸出：
    -   `all_data.xlsx`

------------------------------------------------------------------------

### 🔧 Mode 3：繪圖（simple / cluster / pick_auto）

三種可切換繪圖方式：

  模式          描述
  ------------- -----------------------------------
  `simple`      基礎疊圖、可調 shift 與 interval
  `cluster`     導數強度自動分群（3 clusters）
  `pick_auto`   自動 peak picking + baseline 修正

統一支援： - 自動 PNG 輸出\
- 支援互動式視窗（可用 `--interactive True` 開啟）\
- 自訂顏色、排序、取樣間隔、Q 範圍等參數

------------------------------------------------------------------------

# 📦 安裝環境

## 1️⃣ 安裝 Python 套件

``` bash
python -m pip install -r requirements.txt
```

若你沒有 requirements.txt，可用：

``` bash
pip install numpy pandas matplotlib scipy natsort openpyxl
```

------------------------------------------------------------------------

## 2️⃣ TkAgg Backend（interactive 模式需要）

### macOS

``` bash
brew install tcl-tk
export TK_SILENCE_DEPRECATION=1
```

### Ubuntu

``` bash
sudo apt-get install python3-tk
```

### 若遇到錯誤：

    ImportError: Cannot load backend 'TkAgg'

可改用非互動模式：

``` bash
python main.py --interactive False
```

------------------------------------------------------------------------

# 📁 專案結構

    main.py
    utils/
      ├─ mode1_processor.py   # DAT → Excel
      ├─ mode2_merger.py      # HQ/LQ 合併
      └─ mode3_plotter.py     # 繪圖（simple / cluster / pick_auto）
    output/                   # 圖片輸出（自動建立）

------------------------------------------------------------------------

# 🚀 使用方式

## 一鍵執行全部流程（最推薦）

``` bash
python main.py --mode all --path ./G32
```

------------------------------------------------------------------------

## 單獨執行各步驟

### Mode 1：DAT → Excel

``` bash
python main.py --mode 1 --path ./G32
```

### Mode 2：合併 HQ / LQ

``` bash
python main.py --mode 2 --path ./G32
```

### Mode 3：繪圖

``` bash
python main.py --mode 3 --path ./G32
```

------------------------------------------------------------------------

# ⚙ main.py 參數表
| 參數 | 功能 |
|------|------|
| `--mode {1,2,3,all}` | 執行模式 |
| `--path PATH` | 要處理的資料夾 |
| `--interval N` | 每 N 個檔取樣一次 |
| `--plot-mode simple/cluster/pick_auto` | 繪圖模式 |
| `--y-axis log/linear` | Y 軸刻度 |
| `--output-dir DIR` | PNG 輸出資料夾 |
| `--output-name NAME` | 自訂輸出 PNG 名稱 |
| `--interactive {True,False}`| 顯示互動式介面，default False |
| `--derivative {1,2}` | cluster 使用一階/二階導數 |
| `--sort-peak` | 根據峰值排序 |
| `--shift FLOAT` | y 軸平移倍率 |
| `--q-min` / `--q-max` | Q 顯示範圍 |
| `--cluster-colors` | 3 群顏色（逗號分隔，可以色號）Ex： "red,green,blue"|
| `--save-label` | PNG 是否包含 legend |
| `--peak-min` / `--peak-max` | 排序時的峰值搜尋區間 |
| `--pick_qs` | pick_auto 模式要分析的 Q 值 |
| `--cluster-colors` | 如果pick_auto有選， 每個 pick_q 的顏色 |


------------------------------------------------------------------------

# 🧩 Mode 1：DAT → Excel 詳細說明

-   掃描資料夾內所有 `.dat`\
-   分類為：
    -   `hq`（檔名含 `1M`）
    -   `lq`（其餘）\
-   解析曲線：
    -   跳過 DISTRIBUTION 區段
    -   讀取 `(Q, I)` 數據
-   重新對齊 Q 軸並輸出 Excel

輸出：

    hq/hq_data.xlsx
    lq/lq_data.xlsx

------------------------------------------------------------------------

# 🧩 Mode 2：HQ/LQ 合併 → all_data.xlsx

流程：

1.  LQ 從 Q ≥ 0.0024729 開始取用
2.  HQ 取前 10 行後的數據
3.  找到 HQ/LQ 接點（相近 Q）
4.  計算 scaling factor：

$$
\text{scale} = \frac{\text{mean}(|LQ|)}{\text{mean}(|HQ|)}
$$

5.  對 HQ 所有欄位套用 scale
6.  回填至 LQ → 合併成一張表

輸出：

    all_data.xlsx

------------------------------------------------------------------------

# 🧩 Mode 3：繪圖模式說明

------------------------------------------------------------------------

## 🎨 simple 模式

-   每 `interval` 個檔畫一次\
-   可調整：
    -   y-shift
    -   Q 範圍
    -   interval

------------------------------------------------------------------------

## 🎨 cluster 模式（導數分群）

-   計算每條曲線在指定 Q 範圍內的二階導數強度\
-   自動分成 3 群（0, 1, 2）\
-   可互動調整：interval、shift、cluster 過濾、diff step、Q min/max

------------------------------------------------------------------------

## 🎨 pick_auto 模式（自動 peak picking）

對每個 `pick_q`：

1.  搜尋 ±0.06 Q 區間\
2.  找到最高峰 (`PeakQ`, `PeakValue`)\
3.  找斜率開始上升的 baseline\
4.  計算：

$$
\text{AdjustedIntensity} = \text{PeakValue} - \text{BaselineValue}
$$

5.  若 `--sort-peak` → 依 AdjustedIntensity 排序\
6.  自動輸出 Excel：
-  Folder_pickQ_1.2000.xlsx
-  Folder_pickQ_1.3000.xlsx

------------------------------------------------------------------------

# 📤 Mode 3 輸出結果

執行後將產生：

    output/
      FolderName.png
      FolderName_pickQ_XXXX.xlsx

若使用：

    --output-name myplot

則輸出：

    output/myplot.png

------------------------------------------------------------------------

# 🔁 推薦使用流程

``` bash
python main.py --mode all --path ./G32
```

或針對 peak picking：

``` bash
python main.py --mode 3 --plot-mode pick_auto --path ./G32 --sort-peak
```

首次執行需編譯WebUI：

``` bash
python3 -m py_compile streamlit_app.py   
```
啟動WebUI：

``` bash
python -m streamlit run streamlit_app.py 
```