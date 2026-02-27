import os
import shutil
import concurrent.futures
from natsort import natsorted
import pandas as pd


def _parse_dat_file(file_path):
    q_vals = []
    i_vals = []
    with open(file_path, 'r') as f:
        started = False
        skip_next = False
        for line in f:
            if 'DISTRIBUTION=TRUE' in line.upper() and 'X' in line.upper() and 'Y' in line.upper():
                started = False
                skip_next = True
                continue
            if skip_next:
                skip_next = False
                started = True
                continue
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
                    if q not in q_vals:
                        q_vals.append(q)
                    i_vals.append(i)
    return q_vals, i_vals


class Mode1Processor:
    """
    分類 .dat 並匯出 hq_data.csv 與 lq_data.csv
    """
    def __init__(self, target_dir, max_workers=None):
        self.target_dir = target_dir
        self.max_workers = max_workers
        self.q_values = []

    def export(self, folder, output_name):
        self.q_values = []
        data = {}
        max_len = 0
        
        dat_files = natsorted([f for f in os.listdir(folder) if f.endswith('.dat')])
        valid_files = [f for f in dat_files if os.path.getsize(os.path.join(folder, f)) > 0]
        
        # 使用 ProcessPoolExecutor 並行讀取檔案，避開 GIL
        with concurrent.futures.ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            file_paths = [os.path.join(folder, fn) for fn in valid_files]
            results = list(executor.map(_parse_dat_file, file_paths))
            
        for fn, (q_vals, iv) in zip(valid_files, results):
            data[fn] = iv
            for q in q_vals:
                if q not in self.q_values:
                    self.q_values.append(q)
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
        df.to_csv(out, index=False)
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

        # 匯出 CSV
        self.export(hq, 'hq_data.csv')
        self.export(lq, 'lq_data.csv')
