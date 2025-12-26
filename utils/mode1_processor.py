import os
import shutil
from natsort import natsorted
import pandas as pd


class Mode1Processor:
    """
    分類 .dat 並匯出 hq_data.xlsx 與 lq_data.xlsx
    """
    def __init__(self, target_dir):
        self.target_dir = target_dir
        self.q_values = []

    def process_dat_file(self, file_path):
        i_values = []
        with open(file_path, 'r') as f:
            started = False
            skip_next = False  # 新增變數，用於跳過下一行
            for line in f:
                # 新增條件：遇到 Distribution 行
                if 'DISTRIBUTION=TRUE' in line.upper() and 'X' in line.upper() and 'Y' in line.upper():
                    started = False
                    skip_next = True  # 跳過一行
                    
                    continue
                if skip_next:
                    skip_next = False
                    started = True  # 下一行才開始
                    continue
                # 原本的條件：遇到 Q I ERROR 行
                if 'Q' in line.upper() and 'I' in line.upper() and 'ERROR' in line.upper() :
                    started = True
                    continue
                if started:
                    if ',' in line:
                        parts = [p.strip() for p in line.strip().replace('，', ',').split(',')]
                    else:
                        parts = line.split()
                    if len(parts) >= 2:
                        try:
                            q, i = float(parts[0]), float(parts[1])
                        except ValueError:
                            continue
                        if q == 0:
                            continue
                        if q not in self.q_values:
                            self.q_values.append(q)
                        i_values.append(i)
        return i_values

    def export(self, folder, output_name):
        self.q_values = []
        data = {}
        max_len = 0
        for fn in natsorted([f for f in os.listdir(folder) if f.endswith('.dat')]):
            fp = os.path.join(folder, fn)
            if os.path.getsize(fp) == 0:
                print(f"空檔 {fp}，跳過。")
                continue
            iv = self.process_dat_file(fp)
            data[fn] = iv
            max_len = max(max_len, len(iv))

        for k in data:
            data[k] += [None] * (max_len - len(data[k]))

        df = pd.concat([
            pd.DataFrame({'Q': self.q_values[:max_len]}),
            pd.DataFrame(data)
        ], axis=1)
        # 如果是 lq_data，就丟掉最後 5 筆
        if output_name.lower().startswith('lq'):
            if len(df) > 5:
                df = df.iloc[:-5].reset_index(drop=True)
            else:
                # 保險起見，如果總行數小於等於5，就留空 DataFrame
                df = df.iloc[0:0]

        out = os.path.join(self.target_dir, output_name)
        df.to_excel(out, index=False)
        print(f"數據已成功儲存到：{out}")

    def run(self):
        hq = os.path.join(self.target_dir, 'hq')
        lq = os.path.join(self.target_dir, 'lq')
        os.makedirs(hq, exist_ok=True)
        os.makedirs(lq, exist_ok=True)

        # 複製檔案
        for r, _, files in os.walk(self.target_dir):
            for name in files:
                if name.endswith('.dat') and '-' not in name:
                    src = os.path.join(r, name)
                    dest_dir = hq if '1M' in name else lq
                    dst = os.path.join(dest_dir, name)
                    if os.path.abspath(src) != os.path.abspath(dst):
                        shutil.copy2(src, dst)

        # 匯出 Excel
        self.export(hq, 'hq_data.xlsx')
        self.export(lq, 'lq_data.xlsx')