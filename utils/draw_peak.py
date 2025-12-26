import pandas as pd
import matplotlib.pyplot as plt
import argparse

parser = argparse.ArgumentParser(description="Compare one peak across multiple samples (sheets)")
parser.add_argument('--file', type=str, required=True, help='Excel 檔案路徑')
parser.add_argument('--peak', type=str, required=True, help='peak 欄位名（例 peak(011)）')
parser.add_argument('--sheets', type=str, required=True, help='逗號分隔的 sheet 名單（例: sample1,sample2,sample3,sample4）')
parser.add_argument('--colors', type=str, default='red,blue,green,orange', help='逗號分隔的顏色')
parser.add_argument('--marker_size', type=float, default=5, help='點的大小 (預設 5)')
args = parser.parse_args()

file_path = args.file
peak_col = args.peak
sheet_names = [s.strip() for s in args.sheets.split(',')]
colors = [c.strip() for c in args.colors.split(',') if c.strip()] if args.colors else None
marker_size = args.marker_size

# --- 第一張圖：時間軸/原始順序 ---
plt.figure(figsize=(14, 6))
for i, sheet in enumerate(sheet_names):
    df = pd.read_excel(file_path, sheet_name=sheet)
    if peak_col not in df.columns:
        print(f'警告：{sheet} 沒有 {peak_col} 欄位，跳過')
        continue
    y = df[peak_col].values
    x = df.index   # 預設 index。如果你的 x 軸其實是某個時間欄位，改成 df['Time'] or df.iloc[:,0]
    color = colors[i] if colors and i < len(colors) else None
    plt.scatter(x, y, label=sheet, color=color, s=marker_size)

plt.xlabel('Index (time)')
plt.ylabel(peak_col)
plt.title(f"{peak_col} vs Sample (time)")
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.show()

# --- 第二張圖：每個樣品自己排序 ---
plt.figure(figsize=(14, 6))
for i, sheet in enumerate(sheet_names):
    df = pd.read_excel(file_path, sheet_name=sheet)
    if peak_col not in df.columns:
        continue
    y = df[peak_col].sort_values().values
    x = range(len(y))
    color = colors[i] if colors and i < len(colors) else None
    plt.scatter(x, y, label=sheet, color=color, s=marker_size)

plt.xlabel('Index (sorted)')
plt.ylabel(peak_col)
plt.title(f"{peak_col} vs Sample (sorted)")
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.show()
