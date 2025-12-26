import os
import pandas as pd
import numpy as np


class Mode2Merger:
    """
    合併 hq_data.xlsx 與 lq_data.xlsx 並輸出 all_data.xlsx
    """
    def __init__(self, target_dir, lq_start_x=0.0024729):
        self.target_dir = target_dir
        self.lq_start_x = lq_start_x

    def run(self):
        hq_file_path = os.path.join(self.target_dir, 'hq_data.xlsx')
        lq_file_path = os.path.join(self.target_dir, 'lq_data.xlsx')
        output_file_path = os.path.join(self.target_dir, 'all_data.xlsx')
        try:
        # 讀取資料
            hq_data = pd.read_excel(hq_file_path, skiprows=10)
            lq_data = pd.read_excel(lq_file_path)

        # 確認資料不為空
            if hq_data.empty and not lq_data.empty:
                lq_data.to_excel(output_file_path, index=False)
                print(f"HQ 為空，直接複製 LQ 成為 all_data.xlsx")
                return
            if lq_data.empty and not hq_data.empty:
                # HQ 可能要保留原始 X；跳過前 10 行剛好拿到完整
                hq_data.to_excel(output_file_path, index=False)
                print(f"LQ 為空，直接複製 HQ 成為 all_data.xlsx")
                return
            if hq_data.empty and lq_data.empty:
                raise ValueError("HQ 和 LQ 都是空的，無法合併。")

            # 篩選 lq_data 中大於等於 lq_start_x_value 的數據
            lq_x_values = lq_data.iloc[:, 0]
            trimmed_lq_data = lq_data[lq_x_values >= self.lq_start_x].copy()  # 確保是副本

            if trimmed_lq_data.empty:
                raise ValueError("lq_data 中沒有大於或等於指定 lq_start_x_value 的數據。")

            # 重置索引，確保從 0 開始
            trimmed_lq_data.reset_index(drop=True, inplace=True)

            # 找到 hq_data 的第一個 X 值
            hq_first_x_value = hq_data.iloc[0, 0]

            # 找到 trimmed_lq_data 中最接近且小於等於 hq_first_x_value 的索引
            lq_x_values_trimmed = trimmed_lq_data.iloc[:, 0]
            if (lq_x_values_trimmed <= hq_first_x_value).any():
                closest_index = lq_x_values_trimmed[lq_x_values_trimmed <= hq_first_x_value].idxmax()
            else:
                raise ValueError("trimmed_lq_data 中找不到小於或等於 hq_data 第一個 X 值的匹配項目。")

            # 確保 hq_data 有足夠行數進行匹配
            num_rows_hq = len(hq_data)
            rows_to_consider = len(trimmed_lq_data) - closest_index  # 要考慮算平均的行數
            lq_last_x_value = trimmed_lq_data.iloc[-1, 0]  # Low Q 最後一個 Q 值
            hq_end_index = hq_data.iloc[:, 0][hq_data.iloc[:, 0] <= lq_last_x_value].idxmax()

            # 如果 trimmed_lq_data 行數不足，擴充行數
            if num_rows_hq > rows_to_consider:
                additional_rows = num_rows_hq - rows_to_consider
                empty_data = pd.DataFrame(
                    np.nan, index=range(additional_rows), columns=trimmed_lq_data.columns
                )
                trimmed_lq_data = pd.concat([trimmed_lq_data, empty_data], ignore_index=True)

            # 按列計算倍率並調整 hq_data
            adjusted_hq_data = hq_data.copy()
            num = 1
            for col in range(1, hq_data.shape[1]):  # 跳過第一列 (X 列)
                lq_col = trimmed_lq_data.iloc[closest_index:closest_index + num_rows_hq, col]  # 當前列
                hq_col = adjusted_hq_data.iloc[:hq_end_index, col]  # 當前列

                # 計算該列的倍率
                lq_avg = lq_col.abs().mean()
                hq_avg = hq_col.abs().mean()
                scaling_factor = lq_avg / hq_avg if hq_avg != 0 else 1
                if num < 5:
                    print(lq_avg,hq_avg,scaling_factor,num)
                num += 1
                # 調整 hq_data 的該列
                adjusted_hq_data.iloc[:, col] *= scaling_factor

            # 替換 X 列（第一列）
            adjusted_hq_data.iloc[:, 0] = hq_data.iloc[:, 0]

            # 合併資料
            end_index = closest_index + num_rows_hq
            trimmed_lq_data.iloc[closest_index:end_index, :] = adjusted_hq_data.values

            # 儲存結果
            trimmed_lq_data.to_excel(output_file_path, index=False)
            print(f"合併成功，結果已保存到：{output_file_path}")

        except FileNotFoundError as e:
            print(f"錯誤：找不到檔案 - {e.filename}")
        except ValueError as e:
            print(f"錯誤：{e}")
        except Exception as e:
            print(f"發生未知錯誤：{e}")