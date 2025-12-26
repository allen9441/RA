import pandas as pd
import matplotlib.pyplot as plt
import argparse

parser = argparse.ArgumentParser(description="Peak Value Scatter Plotter (origin vs sorted)")
parser.add_argument('--file', type=str, required=True, help='Excel 檔案路徑')
parser.add_argument('--sheet', type=str, required=True, help='Excel sheet 名稱')
parser.add_argument('--colors', type=str, default='red,blue,green,orange', help='逗號分隔的顏色')
parser.add_argument('--marker_size', type=float, default=5, help='點的大小 (預設 5)')
args = parser.parse_args()

file_path = args.file
sheet_name = args.sheet
colors = [c.strip() for c in args.colors.split(',') if c.strip()] if args.colors else None
marker_size = args.marker_size

df = pd.read_excel(file_path, sheet_name=sheet_name)
peak_cols = df.columns[df.columns.str.contains('peak', case=False, regex=True)]

# --------- 第一張圖：原始順序 ---------
plt.figure(figsize=(14, 5))
for i, col in enumerate(peak_cols):
    color = colors[i] if colors and i < len(colors) else None
    plt.scatter(df.index, df[col], label=f"{col} (time)", color=color, s=marker_size)
plt.xlabel('Index (time)')
plt.ylabel('Value')
plt.title(f'Scatter Plot (time) - {sheet_name}')
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.show()

# --------- 第二張圖：各自排序 ---------
plt.figure(figsize=(14, 5))
for i, col in enumerate(peak_cols):
    y_sorted = df[col].sort_values().values
    x_sorted = range(len(y_sorted))
    color = colors[i] if colors and i < len(colors) else None
    plt.scatter(x_sorted, y_sorted, label=f"{col} (sort peak)", color=color, s=marker_size)
plt.xlabel('Index (Sorted)')
plt.ylabel('Value')
plt.title(f'Scatter Plot (peak) - {sheet_name}')
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.show()
