import os
import pandas as pd
import numpy as np
import matplotlib
try:
    import tornado
    matplotlib.use('WebAgg')
except ImportError:
    matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.widgets import TextBox, RadioButtons
from matplotlib.cm import get_cmap
from scipy.stats import mode
from matplotlib.colors import to_rgb, to_hex
import concurrent.futures

# --- Helper Functions for ProcessPoolExecutor ---
def _smooth(y, win=5):
    """輕度平滑避免雜訊；win<=1 時不平滑"""
    if win <= 1 or len(y) < win:
        return y
    k = np.ones(win) / win
    return np.convolve(y, k, mode='same')

def _find_start_of_rise(x_in, y_in, peak_idx):
    if peak_idx <= 0:
        return 0
    y_s = _smooth(y_in, win=5)
    dy = np.gradient(y_s, x_in)
    start_idx = None
    for k in range(0, peak_idx):
        if dy[k] <= 0 and dy[k + 1] > 0:
            start_idx = k + 1
    if start_idx is None:
        start_idx = int(np.nanargmin(y_s[:peak_idx + 1]))
    return start_idx

def _pick_auto_worker(col_name, x, y_col, q_center, pick_half_width, baseq_info):
    """
    baseq_info: (base_q_fixed, base_val_fixed) if baseq is set, else None
    """
    mask_win = (x >= q_center - pick_half_width) & (x <= q_center + pick_half_width)
    x_in = x[mask_win]
    y_in = y_col[mask_win]

    if len(x_in) == 0:
        return np.nan, np.nan, np.nan, np.nan, np.nan

    y_s = _smooth(y_in, win=5)
    peak_idx = int(np.nanargmax(y_s))
    peak_q = x_in[peak_idx]
    peak_val = y_in[peak_idx]

    start_idx = _find_start_of_rise(x_in, y_in, peak_idx)
    base_q = x_in[start_idx]
    base_val = y_in[start_idx]
    
    if baseq_info is not None:
        base_q, base_val = baseq_info

    adjusted = peak_val - base_val
    if not np.isnan(adjusted) and adjusted < 0:
        adjusted = 0.0

    return peak_q, peak_val, base_q, base_val, adjusted

def _cluster_worker(col, xs, ys, qs, qe, dq, derivative_order):
    if len(xs) < 3:
        return col, 0
    qg = np.arange(qs, qe + dq / 2, dq)
    
    if len(qg) < 3:
        return col, 0

    yg = np.interp(qg, xs, ys)
    deriv = np.gradient(yg, qg) if derivative_order == 1 else np.gradient(np.gradient(yg, qg), qg)
    return col, np.nanmax(np.abs(deriv))


class Mode3Plotter:
    """
    交互式繪圖：提供 simple（簡易平移疊圖）和 cluster（導數分群疊圖）兩種模式。
    """
    def __init__(self, target_dir, output_dir, interactive, interval=30, 
                plot_mode='cluster',y_axis='log',x_axis='linear',derivative_order=2,
                diff_step=0.05, flat_threshold=0.0,
                sort_peak=False,shift_distance=0.0,display_q_min=0.0, display_q_max=2.0,
                cluster_colors=None,save_label=False,peak_min=0.5, peak_max=0.6,
                cluster_range=False,
                pick_qs=None,output_filename=None,pick_colors=None,baseq=None,
                max_workers=None):
        self.target_dir = target_dir
        self.max_workers = max_workers
        self.output_dir = output_dir
        self.interactive = interactive
        self.interval = int(interval)
        self.plot_mode = plot_mode  # 'simple' or 'cluster'
        self.derivative_order = derivative_order
        self.diff_step = float(diff_step)
        self.flat_threshold = float(flat_threshold)
        self.sort_peak = sort_peak
        self.shift_distance = shift_distance
        
        if self.flat_threshold > 0:
            self.num_clusters = 4
        else:
            self.num_clusters = 3
            
        # 設定 Y 軸刻度
        self.y_axis = y_axis
        self.x_axis = x_axis
        # 預設的 Q 顯示範圍
        self.display_q_min = display_q_min
        self.display_q_max = display_q_max
        # cluster 模式的顏色設定
        self.cluster_colors_arg = cluster_colors
        # 是否在存圖時包含 legend 標籤
        self.save_label = save_label
        # 預設的峰值範圍
        self.peak_min = float(peak_min)
        self.peak_max = float(peak_max)
        self.cluster_range = cluster_range
        # 載入資料（兩種模式共用，預處理已在 mode2 進行）
        fp = os.path.join(self.target_dir, 'all_data.csv')
        df = pd.read_csv(fp)
        self.df_raw = df
        self.x = df.iloc[:,0].values
        self.adjusted_y = df.iloc[:,1:]
        # 如果有指定 pick_qs，則只取這個 Q 範圍
        self.q_start = min(self.x)
        self.q_end   = max(self.x)
        #  pick_auto 模式的 Q 作圖
        self.pick_qs = pick_qs
        # 顏色設定
        self.pick_colors = pick_colors
        # 輸出檔名設定
        self.output_filename = output_filename
        self.baseq = baseq


        # cluster 模式額外結構
        if self.plot_mode in ('cluster', 'pick_auto'):
            self.sec_metrics = {}
            self.df_res = pd.DataFrame({'Column': self.adjusted_y.columns})
            self.df_res['Cluster'] = 0
            self.shift_values = {i: i*0.4 for i in range(self.num_clusters)}
            if self.cluster_colors_arg:
                colors = [c.strip() for c in self.cluster_colors_arg.split(',')]
                while len(colors) < self.num_clusters:
                    colors.append(colors[-1])
                self.cluster_colors = {i: colors[i] for i in range(self.num_clusters)}
            else:
                # rainbow fallback
                cmap = get_cmap('rainbow')
                self.cluster_colors = {i: cmap(i/self.num_clusters) for i in range(self.num_clusters)}

    def run(self):
        fig, ax = plt.subplots(figsize=(14,8))
        plt.subplots_adjust(bottom=0.25)

        if self.plot_mode == 'simple':
            self._setup_simple_ui(fig, ax)
            self._draw_simple(ax, self.interval)
        elif self.plot_mode == 'pick_auto':
            self._draw_pick_auto(ax)   # << 新增這一行
        else:
            self._setup_cluster_ui(fig, ax)
            self._compute_and_cluster()
            self._draw_cluster(ax, self.interval)
        
        # --- 自動存圖 ---
        # 結束互動前，複製一張純主圖
        folder_name = os.path.basename(os.path.normpath(self.target_dir))
        fig2, ax2 = plt.subplots(figsize=(14,8))
        # 把主 ax 的所有 Line2D 複製過去
        for line in ax.get_lines():
            ax2.plot(
                line.get_xdata(),
                line.get_ydata(),
                color=line.get_color(),
                linewidth=line.get_linewidth(),
                label=line.get_label()
            )
        # 複製所有 scatter（Collection）
        for col in ax.collections:
            offsets = col.get_offsets()
            if offsets.size == 0:
                continue
            # scatter 的顏色可能是陣列，也可能是單一色，這裡用 facecolor 取第一個
            facecolor = col.get_facecolor()[0] if len(col.get_facecolor()) else (0,0,0,1)
            ax2.scatter(offsets[:,0], offsets[:,1], color=facecolor, s=col.get_sizes(), alpha=facecolor[3])
        # 複製座標設定
        ax2.set_xlim(ax.get_xlim())
        ax2.set_ylim(ax.get_ylim())
        ax2.set_xscale(ax.get_xscale())
        ax2.set_yscale(ax.get_yscale())
        ax2.set_xlabel(ax.get_xlabel())
        ax2.set_ylabel(ax.get_ylabel())
        ax2.set_title(ax.get_title())
        ax2.grid(True)
        # 複製圖例 會太長不建議打開
        # handles, labels = ax.get_legend_handles_labels()
        # ax2.legend(handles, labels, loc='upper right', fontsize='small')
        if self.save_label:
            handles, labels = ax.get_legend_handles_labels()
            if self.plot_mode == 'pick_auto':
                ax2.xaxis.set_visible(False)
                ax2.legend(handles, labels , loc='upper left',bbox_to_anchor=(0.05, 0.95))
            else:
                ax2.legend(handles, labels, loc='upper right', fontsize='small')
        # 存檔
        if self.output_filename:
            out2 = os.path.join(self.output_dir, f"{self.output_filename}.png")
            out_html = os.path.join(self.output_dir, f"{self.output_filename}.html")
        else:
            out2 = os.path.join(self.output_dir, f"{folder_name}.png")
            out_html = os.path.join(self.output_dir, f"{folder_name}.html")
        fig2.savefig(out2, bbox_inches='tight', dpi=600)
        plt.close(fig2)
        print("已儲存：", out2)

        # 產出 Plotly 互動式網頁圖表
        try:
            import plotly.graph_objects as go
            from matplotlib.colors import to_hex

            fig_plotly = go.Figure()
            # 複製 Lines
            for line in ax.get_lines():
                label = line.get_label()
                if label.startswith('_'): continue
                color = to_hex(line.get_color())
                fig_plotly.add_trace(go.Scatter(
                    x=line.get_xdata(), y=line.get_ydata(), mode='lines',
                    name=label, line=dict(color=color)
                ))
            # 複製 Scatter
            for col in ax.collections:
                offsets = col.get_offsets()
                if offsets.size == 0: continue
                facecolor = col.get_facecolor()[0] if len(col.get_facecolor()) else (0,0,0,1)
                color_hex = to_hex(facecolor)
                label = col.get_label()
                if label.startswith('_'): label = None
                fig_plotly.add_trace(go.Scatter(
                    x=offsets[:,0], y=offsets[:,1], mode='markers',
                    name=label, marker=dict(color=color_hex, size=8)
                ))

            fig_plotly.update_layout(
                title=ax.get_title(),
                xaxis_title=ax.get_xlabel(),
                yaxis_title=ax.get_ylabel(),
                xaxis_type="log" if ax.get_xscale() == "log" else "linear",
                yaxis_type="log" if ax.get_yscale() == "log" else "linear",
                template="plotly_white"
            )
            fig_plotly.write_html(out_html)
            print("已儲存互動式網頁圖表：", out_html)
        except Exception as e:
            print("產出 Plotly 圖表失敗:", e)

        # --- 是否開啟互動圖 ---
        if self.interactive:
            plt.show()

    # --- 簡易模式方法 ---------------------------------------------
    def _draw_simple(self, ax, interval):
        ax.clear()
        # 先在 x, adjusted_y 裡做 Q 範圍篩選
        mask = (self.x >= self.q_start) & (self.x <= self.q_end)
        x = self.x[mask]
        # 同理對每條 y 作過濾
        filtered_y = self.adjusted_y.loc[mask, :]
        cols = filtered_y.columns[::interval]
        cmap = get_cmap("rainbow")
        colors = cmap(np.linspace(0,1,len(cols)))

        for idx, col in enumerate(cols):
            y = filtered_y[col].values * (10**(self.shift_distance * idx))
            ax.plot(x, y, color=colors[idx], label=col)
        title_name = os.path.basename(os.path.normpath(self.target_dir))
        ax.set_yscale(self.y_axis)
        ax.set_xscale(self.x_axis)
        ax.set_title(f"Simple Plot {title_name} (Interval={self.interval}, Shift={self.shift_distance})")
        ax.set_xlabel(f"q ({self.x_axis})"); ax.set_ylabel(f"Intensity {self.y_axis}")
        ax.grid(True); ax.legend(loc='upper right'); plt.draw()
        ax.set_xlim(left=self.display_q_min)
    def _setup_simple_ui(self, fig, ax):
        # Interval
        ax_int = plt.axes([0.1,0.02,0.1,0.05])
        self.tb_int = TextBox(ax_int, "Interval", initial=str(self.interval))
        def submit_interval(text):
            try:
                val = int(text)
                if val >= 1:
                    self.interval = val
            except ValueError:
                pass
            # 重畫
            self._draw_simple(ax, self.interval)
        self.tb_int.on_submit(submit_interval)

        # Shift
        ax_sh = plt.axes([0.3,0.02,0.1,0.05])
        self.tb_sh = TextBox(ax_sh, "Shift", initial=str(self.shift_distance))
        def submit_shift(text):
            try:
                self.shift_distance = float(text)
            except ValueError:
                pass
            self._draw_simple(ax, self.interval)
        self.tb_sh.on_submit(submit_shift)

        ax_qs = plt.axes([0.5,0.02,0.1,0.05])
        # Q Start
        self.tb_qs = TextBox(ax_qs, "Q Start", initial="0.0")
        def submit_qs(text):
            try:
                self.q_start = float(text)
            except ValueError:
                pass
            self._draw_simple(ax, self.interval)
        self.tb_qs.on_submit(submit_qs)

        # Q End
        ax_qe = plt.axes([0.7,0.02,0.1,0.05])
        self.tb_qe = TextBox(ax_qe, "Q End", initial=str(max(self.x)))
        def submit_qe(text):
            try:
                self.q_end = float(text)
            except ValueError:
                pass
            self._draw_simple(ax, self.interval)
        self.tb_qe.on_submit(submit_qe)


    # --- pick_auto 模式方法 ---------------------------------------
    # def _draw_pick_auto(self, ax, xtick_num=10):
    #     columns = list(self.adjusted_y.columns)
    #     pick_qs = self.pick_qs if self.pick_qs is not None else []
    #     pick_half_width = 0.06

    #     x = self.x
    #     ydata = self.adjusted_y

    #     y_matrix = []  # shape: [len(pick_qs), len(columns)]

    #     for q_center in pick_qs:
    #         peak_qs = []
    #         for col in columns:
    #             mask = (x >= q_center - pick_half_width) & (x <= q_center + pick_half_width)
    #             x_in = x[mask]
    #             y_in = ydata[col][mask].values
    #             if len(y_in) == 0:
    #                 peak_qs.append(np.nan)
    #             else:
    #                 max_idx = np.nanargmax(y_in)
    #                 peak_qs.append(x_in[max_idx])
    #         valid_qs = [q for q in peak_qs if not np.isnan(q)]
    #         if not valid_qs:
    #             unified_q = np.nan
    #         else:
    #             unified_q = float(mode(valid_qs, keepdims=True).mode[0])

    #         y_at_q_list = []
    #         for col in columns:
    #             y_col = ydata[col].values
    #             idx = np.abs(x - unified_q).argmin()
    #             y_at_q = y_col[idx]
    #             y_at_q_list.append(y_at_q)
    #         min_y = np.nanmin(y_at_q_list)
    #         y_pick = [y - min_y for y in y_at_q_list]
    #         y_matrix.append(y_pick)

    #     # --- 畫全部點 ---
    #     for i, q in enumerate(pick_qs):
    #         y = y_matrix[i]
    #         # 根據 pick_colors 決定顏色
    #         if hasattr(self, 'pick_colors') and self.pick_colors and len(self.pick_colors) > 0:
    #             if i < len(self.pick_colors):
    #                 color = self.pick_colors[i]
    #             else:
    #                 color = self.pick_colors[-1]  # 不夠時用最後一個顏色延續
    #         else:
    #             color = 'purple'  # 沒有指定時預設紫色
    #         if self.sort_peak:
    #             # 如果要排序，先對 y 做排序, 這裡的 y 是每個 column 在 unified_q 的值
    #             folder_name = os.path.basename(os.path.normpath(self.target_dir))
    #             sort_idx = np.argsort(y)
    #             sorted_columns = [columns[j] for j in sort_idx]
    #             sorted_y = [y[j] for j in sort_idx]
    #             ax.scatter(range(len(sorted_columns)), sorted_y, color=color, s=10, alpha=0.8, label=f"PickQ={q:.4f}")
    #             df_out = pd.DataFrame({
    #                 'File': sorted_columns,
    #                 'Intensity': sorted_y
    #             })
    #             out_name = f"{folder_name}_pickQ_{q:.4f}.xlsx"
    #             df_out.to_excel(os.path.join(self.output_dir, out_name), index=False)
    #         else:
    #             ax.scatter(range(len(columns)), y, color=color, s=10, alpha=0.8, label=f"PickQ={q:.4f}")
                

    #     ax.set_yscale(self.y_axis)
    #     ax.set_ylabel("Intensity")
    #     # ax.xaxis.set_visible(False)
    #     ax.set_xlim(0, len(columns)-1)
    #     ax.set_title("Pick Q Intensity vs File (pick_auto)")
    #     ax.grid(True)
    #     ax.legend()
        # 畫布 show
        # plt.draw()
        # plt.tight_layout()
        # plt.show()

    # --- 改良版 pick_auto 會扣掉baseline 方法 -----------------------------------    
    def _draw_pick_auto(self, ax, xtick_num=10):
        """
        pick_auto:
        對每個 pick_q 視窗(±pick_half_width)，每個檔案找最高點與起漲點，
        計算 Adjusted = PeakValue - BaselineValue (>= 0)，
        以 Adjusted 做排序(若 self.sort_peak)，畫散點並輸出 Excel。
        """
        import numpy as np
        import pandas as pd

        columns = list(self.adjusted_y.columns)
        pick_qs = self.pick_qs if self.pick_qs is not None else []
        pick_half_width = 0.06

        baseq = self.baseq
        x = self.x
        ydata = self.adjusted_y

    # ---- 主流程：為每個 pick_q 建資料，然後畫圖/輸出 ----
        # 預先計算 baseq 索引 (如果有的話)
        base_idx = None
        base_q_val = None
        if baseq is not None:
            base_idx = (np.abs(x - float(baseq))).argmin()
            base_q_val = x[base_idx]

        for i, q_center in enumerate(pick_qs):
            # 每檔案的結果容器
            peak_q_list, peak_val_list = [], []
            base_q_list, base_val_list = [], []
            adjusted_list = []

            # 準備 tasks
            tasks = []
            for col in columns:
                y_col = ydata[col].values
                baseq_info = None
                if base_idx is not None:
                    baseq_info = (base_q_val, y_col[base_idx])
                
                tasks.append((col, x, y_col, q_center, pick_half_width, baseq_info))

            # 1) 視窗內找最高點與起漲點；使用 ProcessPoolExecutor
            with concurrent.futures.ProcessPoolExecutor(max_workers=self.max_workers) as executor:
                futures = [executor.submit(_pick_auto_worker, *t) for t in tasks]
                for future in futures:
                    pq, pv, bq, bv, adj = future.result()
                    peak_q_list.append(pq)
                    peak_val_list.append(pv)
                    base_q_list.append(bq)
                    base_val_list.append(bv)
                    adjusted_list.append(adj)

            # 2) 畫圖（以 Adjusted 排序或原順序）
            #    顏色：沿用 self.pick_colors 設定，否則預設紫色
            if hasattr(self, 'pick_colors') and self.pick_colors and len(self.pick_colors) > 0:
                color = self.pick_colors[i] if i < len(self.pick_colors) else self.pick_colors[-1]
            else:
                color = 'purple'

            # 排序索引
            if self.sort_peak:
                # 由大到小排序
                sort_idx = np.argsort(np.asarray(adjusted_list))
            else:
                sort_idx = np.arange(len(columns))

            sorted_columns = [columns[j] for j in sort_idx]
            sorted_adj     = [adjusted_list[j] for j in sort_idx]
            sorted_peak_q  = [peak_q_list[j]   for j in sort_idx]
            sorted_peak_v  = [peak_val_list[j] for j in sort_idx]
            sorted_base_q  = [base_q_list[j]   for j in sort_idx]
            sorted_base_v  = [base_val_list[j] for j in sort_idx]

            # 若是對數軸，避免 0 導致報錯：0 -> 很小正數(僅用於繪圖)
            y_plot = np.array(sorted_adj, dtype=float)
            if self.y_axis == 'log':
                y_plot = np.where(y_plot <= 0, 1e-12, y_plot)

            ax.scatter(range(len(sorted_columns)), y_plot, color=color, s=10, alpha=0.8,
                    label=f"PickQ={q_center:.4f}")

            # 3) 輸出 Excel
            folder_name = os.path.basename(os.path.normpath(self.target_dir))
            df_out = pd.DataFrame({
                'File':              sorted_columns,
                'PickCenter':        [q_center] * len(sorted_columns),
                'BaselineQ':         sorted_base_q,
                'BaselineValue':     sorted_base_v,
                'PeakQ':             sorted_peak_q,
                'PeakValue':         sorted_peak_v,
                'AdjustedIntensity': sorted_adj  # = PeakValue - BaselineValue (>=0)
            })
            out_name = f"{folder_name}_pickQ_{q_center:.4f}.xlsx"
            df_out.to_excel(os.path.join(self.output_dir, out_name), index=False)

        # 4) 軸設定
        ax.set_yscale(self.y_axis)
        ax.set_ylabel("Adjusted Intensity (Peak - Baseline)")
        ax.set_xlim(0, len(columns) - 1)
        ax.set_title("Pick Q Adjusted Intensity vs File (pick_auto)")
        ax.grid(True)
        ax.legend()


        
    # --- cluster 模式方法 ------------------------------------------
    def _compute_and_cluster(self):
        if self.cluster_range:
            qs = self.peak_min
            qe = self.peak_max
        else:
            qs = self.q_start
            qe = self.q_end
        
        dq = float(self.tb_step.text)  # Diff Step 仍然保留
        self.sec_metrics.clear()
        
        mask = (self.x >= qs) & (self.x <= qe)
        xs = self.x[mask]
        
        # 準備 tasks
        tasks = []
        for col in self.adjusted_y.columns:
            ys = self.adjusted_y[col][mask].values
            tasks.append((col, xs, ys, qs, qe, dq, self.derivative_order))

        # 使用多進程平行計算導數 (CPU-bound)
        with concurrent.futures.ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            # starmap 在 Python 3.10+ 的 Executor 中未直接支援，用 submit loop
            futures = [executor.submit(_cluster_worker, *t) for t in tasks]
            
            for future in futures:
                col, metric = future.result()
                self.sec_metrics[col] = metric

        vals = list(self.sec_metrics.values())
        
        if not vals:
            print("Warning: No metrics calculated.")
            return

        vmin, vmax = min(vals), max(vals)
        print(f"Cluster Metrics (Range {qs:.3f}-{qe:.3f}): Min={vmin:.6f}, Max={vmax:.6f}")

        # Flat Threshold
        if self.flat_threshold > 0:
            flat_cols = [k for k, v in self.sec_metrics.items() if v < self.flat_threshold]
            signal_cols = [k for k, v in self.sec_metrics.items() if v >= self.flat_threshold]
            
            newc = {}
            # Assign Cluster 0 to Flat
            for k in flat_cols:
                newc[k] = 0
            
            # Assign Cluster 1, 2, 3 to Signal
            if signal_cols:
                sig_vals = [self.sec_metrics[k] for k in signal_cols]
                sv_min, sv_max = min(sig_vals), max(sig_vals)
                
                if sv_min == sv_max:
                    for k in signal_cols:
                        newc[k] = 1
                else:
                    bins = np.linspace(sv_min, sv_max, 4) 
                    bins[-1] += 1e-8
                    for k in signal_cols:
                        v = self.sec_metrics[k]
                        # digitize returns 1, 2, 3
                        idx = np.digitize(v, bins)
                        # Clamp to 1~3 just in case
                        idx = max(1, min(idx, 3))
                        newc[k] = idx
        else:
            if vmin == vmax:
                # if all values identical, assigning to cluster 0
                newc = {k: 0 for k in self.sec_metrics}
            else:
                bins = np.linspace(vmin, vmax, self.num_clusters+1)
                bins[-1] += 1e-8
                newc = {k:min(max(np.digitize(v,bins)-1,0),self.num_clusters-1) 
                        for k,v in self.sec_metrics.items()}
            
        self.df_res['Cluster'] = self.df_res['Column'].map(newc)
        # 顯示統計
        import pandas as pd
        stats = [{'Cluster':c,
                    'Count':len([k for k,v in newc.items() if v==c]),
                    'Min':min([self.sec_metrics[k] for k,v in newc.items() if v==c]) if c in newc.values() else None,
                    'Max':max([self.sec_metrics[k] for k,v in newc.items() if v==c]) if c in newc.values() else None}
                    for c in range(self.num_clusters)]
        print(pd.DataFrame(stats))

        # 輸出分群結果到 Excel
        self._export_clustered_data()

    def _export_clustered_data(self):
        """
        將分群後的數據匯出到 Excel
        格式：
        - Index: Q value
        - Columns: MultiIndex (Cluster, File)
        - Data: 原始強度
        """
        # Q 軸作為 Index
        q_col = self.df_raw.iloc[:, 0]

        # 如果有啟用 sort_peak，則依照 Cluster -> Peak Value 排序
        # 否則依照 Cluster -> Column Name 排序
        
        res = self.df_res.copy()
        
        if self.sort_peak:
            # 計算每個 column 在 Q 範圍的peak
            q_min, q_max = self.peak_min, self.peak_max
            peak_dict = {}
            for col in self.adjusted_y.columns:
                mask = (self.x >= q_min) & (self.x <= q_max)
                yvals = self.adjusted_y[col][mask].values
                if len(yvals) == 0:
                    peak = float('-inf')
                else:
                    peak = np.nanmax(yvals)
                peak_dict[col] = peak
            
            # 將 Peak 加入排序
            res['Peak'] = res['Column'].map(peak_dict)
            res = res.sort_values(by=['Cluster', 'Peak'])
        else:
            res = res.sort_values(by=['Cluster', 'Column'])

        # 建立 MultiIndex Columns: (Cluster, File)
        # 匯出的是 df_raw 的數據，其 Columns 對應 res['Column']
        # df_raw 的第0列是Q，第1列開始是數據
        
        # 依序取出需要的 columns
        sorted_cols = res['Column'].tolist()
        sorted_clusters = res['Cluster'].tolist()
        
        # 從 df_raw 提取數據
        # df_raw columns: ['X', 'File1', 'File2', ...]
        # 檢查 sorted_cols 是否都在 df_raw 中
        valid_cols = [c for c in sorted_cols if c in self.df_raw.columns]
        
        if not valid_cols:
            print("警告: 無法對應原始數據欄位，略過匯出。")
            return

        data_subset = self.df_raw[valid_cols]
        
        # MultiIndex columns
        multi_index = pd.MultiIndex.from_tuples(
            zip(sorted_clusters, valid_cols), 
            names=['Cluster', 'File']
        )
        data_subset.columns = multi_index
        
        # 將 Q 值作為 Index
        export_df = data_subset.copy()
        export_df.index = q_col
        export_df.index.name = 'Q'
        
        folder_name = os.path.basename(os.path.normpath(self.target_dir))
        out_name = f"{folder_name}_clustered.xlsx"
        out_path = os.path.join(self.output_dir, out_name)
        
        try:
            export_df.to_excel(out_path)
            print(f"分群數據已成功匯出至: {out_path}")
        except Exception as e:
            print(f"匯出 Excel 失敗: {e}")

    def _draw_cluster(self, ax, interval):
        interval = int(interval)
        ax.clear()
        txt = self.tb_filter.text.strip()
        sid = int(txt) if (txt.isdigit() and 0 <= int(txt) < self.num_clusters) else None

        # 只用顯示用的 Q 範圍
        disp_q_min, disp_q_max = self.display_q_min, self.display_q_max
        display_mask = (self.x >= disp_q_min) & (self.x <= disp_q_max)
        x_sub = self.x[display_mask]

        if self.sort_peak:
            # 排序的區間直接寫死
            q_min, q_max = self.peak_min, self.peak_max
            peak_dict = {}
            for col in self.adjusted_y.columns:
                mask = (self.x >= q_min) & (self.x <= q_max)
                yvals = self.adjusted_y[col][mask].values
                if len(yvals) == 0:
                    peak = float('-inf')
                else:
                    peak = np.nanmax(yvals)
                peak_dict[col] = peak

            sorted_columns_by_cluster = {}
            draw_counts = []
            for c in range(self.num_clusters):
                cluster_cols = self.df_res[self.df_res['Cluster'] == c]['Column']
                sorted_cols = sorted(cluster_cols, key=lambda col: peak_dict[col])
                sorted_columns_by_cluster[c] = sorted_cols
                N = len(sorted_cols)
                if N == 0:
                    draw_counts.append(0)
                else:
                    draw_counts.append(1 + (N - 1) // interval)
            n_draws = min(draw_counts)
            if n_draws == 0:
                return

            for c in range(self.num_clusters):
                sorted_cols = sorted_columns_by_cluster[c]
                N = len(sorted_cols)
                if N < 1 or n_draws == 0:
                    continue
                sample_indices = np.linspace(0, N-1, n_draws).round().astype(int)
                sample_indices = np.unique(sample_indices)
                for draw_idx, idx in enumerate(sample_indices):
                    col = sorted_cols[idx]
                    if sid is not None and c != sid:
                        continue
                    y = self.adjusted_y[col].values
                    y_sub = y[display_mask]
                    shift = 10 ** (self.shift_values[c] + self.shift_distance * draw_idx)
                    ax.plot(x_sub, y_sub * shift, color=self.cluster_colors[c], label=col)

        else:
            cols = self.df_res['Column'][::interval]
            clus = self.df_res['Cluster'][::interval]
            for idx, (col, c) in enumerate(zip(cols, clus)):
                if sid is not None and c != sid:
                    continue
                y = self.adjusted_y[col].values
                y_sub = y[display_mask]
                shift = 10 ** (self.shift_values[c] + self.shift_distance * idx)
                ax.plot(x_sub, y_sub * shift, color=self.cluster_colors[c], label=col)
        ax.set_yscale(self.y_axis); ax.set_xscale(self.x_axis)
        ax.set_xlabel(f'q ({self.x_axis})'); ax.set_ylabel(f'Intensity {self.y_axis}')
        title_name = os.path.basename(os.path.normpath(self.target_dir))
        title = f"Cluster Plot {title_name} ({self.derivative_order}nd Deriv, Interval={interval})"
        if sid is not None: title += f" - Cluster {sid}"
        ax.set_title(title); ax.grid(True); ax.legend(loc='upper right', fontsize='small')
        ax.set_xlim(left=self.display_q_min)
        plt.draw()
        


    def _setup_cluster_ui(self, fig, ax):
        # Interval
        ax_int = plt.axes([0.05, 0.10, 0.05, 0.05])
        self.tb_int = TextBox(ax_int, 'Interval', initial=str(self.interval),label_pad=0.1)
        self.tb_int.on_submit(lambda t: self._draw_cluster(ax, int(t)))

        # Shift
        ax_sh = plt.axes([0.15, 0.10, 0.05, 0.05])
        self.tb_sh = TextBox(ax_sh, 'Shift', initial=str(self.shift_distance),label_pad=0.1)
        def submit_shift(text):
            try:
                self.shift_distance = float(text)
            except ValueError:
                pass
            self._draw_cluster(ax, int(self.tb_int.text))
        self.tb_sh.on_submit(submit_shift)

        # Cluster
        ax_fl = plt.axes([0.25, 0.10, 0.05, 0.05])
        self.tb_filter = TextBox(ax_fl, 'Cluster', initial='',label_pad=0.1)
        self.tb_filter.on_submit(lambda t: self._draw_cluster(ax, int(self.tb_int.text)))

        # Diff Step
        ax_st = plt.axes([0.35, 0.10, 0.05, 0.05])
        self.tb_step = TextBox(ax_st, 'Diff Step', initial=str(self.diff_step),label_pad=0.1)
        self.tb_step.on_submit(lambda _: (self._compute_and_cluster(), self._draw_cluster(ax, int(self.tb_int.text))))

        # 顯示Q範圍
        # 顯示 Q Min
        ax_qmin = plt.axes([0.45, 0.10, 0.05, 0.05])
        self.tb_qmin = TextBox(ax_qmin, 'Q min', initial=str(self.display_q_min),label_pad=0.1)
        def submit_qmin(text):
            try:
                self.display_q_min = float(text)
            except ValueError:
                pass
            self._draw_cluster(ax, int(self.tb_int.text))
        self.tb_qmin.on_submit(submit_qmin)

        # 顯示 Q Max
        ax_qmax = plt.axes([0.55, 0.10, 0.05, 0.05])
        self.tb_qmax = TextBox(ax_qmax, 'Q max', initial=str(self.display_q_max),label_pad=0.1)
        def submit_qmax(text):
            try:
                self.display_q_max = float(text)
            except ValueError:
                pass
            self._draw_cluster(ax, int(self.tb_int.text))
        self.tb_qmax.on_submit(submit_qmax)

        # Flat Threshold
        ax_flat = plt.axes([0.65, 0.10, 0.05, 0.05])
        self.tb_flat = TextBox(ax_flat, 'Flat Thr', initial=str(self.flat_threshold),label_pad=0.1)
        def submit_flat(text):
            try:
                val = float(text)
                self.flat_threshold = val
                
                if self.flat_threshold > 0:
                    self.num_clusters = 4
                else:
                    self.num_clusters = 3
                
                self.shift_values = {i: i*0.4 for i in range(self.num_clusters)}
                
                if self.cluster_colors_arg:
                    colors = [c.strip() for c in self.cluster_colors_arg.split(',')]
                    while len(colors) < self.num_clusters:
                        colors.append(colors[-1])
                    self.cluster_colors = {i: colors[i] for i in range(self.num_clusters)}
                else:
                    cmap = get_cmap('rainbow')
                    self.cluster_colors = {i: cmap(i/self.num_clusters) for i in range(self.num_clusters)}
                
                self._compute_and_cluster()
                self._draw_cluster(ax, int(self.tb_int.text))
            except ValueError:
                pass
        self.tb_flat.on_submit(submit_flat)
