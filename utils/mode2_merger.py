import os
import pandas as pd
import numpy as np


class Mode2Merger:
    """
    合併 hq_data.csv 與 lq_data.csv 並輸出 all_data.csv
    """
    def __init__(self, target_dir, lq_start_x=0.0024729):
        self.target_dir = target_dir
        self.lq_start_x = lq_start_x

    def run(self):
        hq_file_path = os.path.join(self.target_dir, 'hq_data.csv')
        lq_file_path = os.path.join(self.target_dir, 'lq_data.csv')
        output_file_path = os.path.join(self.target_dir, 'all_data.csv')
        try:
        # 讀取資料
            hq_data = pd.read_csv(hq_file_path, skiprows=10)
            lq_data = pd.read_csv(lq_file_path)

        # 確認資料不為空
            if hq_data.empty and not lq_data.empty:
                self._preprocess_and_save(lq_data, output_file_path)
                print(f"HQ 為空，處理並複製 LQ 成為 all_data.csv")
                return
            if lq_data.empty and not hq_data.empty:
                # HQ 可能要保留原始 X；跳過前 10 行剛好拿到完整
                self._preprocess_and_save(hq_data, output_file_path)
                print(f"LQ 為空，處理並複製 HQ 成為 all_data.csv")
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
            
            # 使用 Pandas 向量化運算取代迴圈
            # 取得數值資料區域 (跳過第一列的 X)
            lq_subset = trimmed_lq_data.iloc[closest_index:closest_index + num_rows_hq, 1:]
            hq_subset = adjusted_hq_data.iloc[:hq_end_index, 1:]
            
            # 計算平均值
            # 加上 .values 避免因index不同而導致廣播失敗
            lq_avg = lq_subset.abs().mean(axis=0).values
            hq_avg = hq_subset.abs().mean(axis=0).values
            
            # 避免除以零，產生 scaling_factor 向量
            # 使用 np.where，當 hq_avg == 0 時回傳 1
            scaling_factors = np.where(hq_avg != 0, lq_avg / hq_avg, 1)
            
            # 印出前 4 筆觀察
            for i in range(min(4, len(scaling_factors))):
                print(lq_avg[i], hq_avg[i], scaling_factors[i], i+1)
            
            # 使用廣播機制更新數值 (跳過 X 列)
            adjusted_hq_data.iloc[:, 1:] *= scaling_factors

            # 替換 X 列（第一列）
            adjusted_hq_data.iloc[:, 0] = hq_data.iloc[:, 0]

            # 合併資料
            end_index = closest_index + num_rows_hq
            trimmed_lq_data.iloc[closest_index:end_index, :] = adjusted_hq_data.values

            # 儲存結果
            self._preprocess_and_save(trimmed_lq_data, output_file_path)
            print(f"合併成功，處理後結果已保存到：{output_file_path}")

        except FileNotFoundError as e:
            print(f"錯誤：找不到檔案 - {e.filename}")
        except ValueError as e:
            print(f"錯誤：{e}")
        except Exception as e:
            print(f"發生未知錯誤：{e}")

    def _preprocess_and_save(self, df, output_file_path):
        """
        對合併後的資料進行預處理：
        1. 刪除最後 20 筆資料
        2. 將每筆資料數值平移（加上最小值的絕對值）並過濾小於 1e-6 的值
        這原本在 mode3 中進行，現在移到產出 csv 前。
        """
        if len(df) > 20:
            df = df.iloc[:-20].copy()
        else:
            df = df.copy()
            
        orig = df.iloc[:, 1:]
        adjusted_y = orig.add(orig.min().abs()).where(lambda d: d >= 1e-6)
        df.iloc[:, 1:] = adjusted_y
        
        df.to_csv(output_file_path, index=False)
