import argparse
from utils.mode1_processor import Mode1Processor
from utils.mode2_merger import Mode2Merger
from utils.mode3_plotter import Mode3Plotter
import os
def main():
    cpu_count = os.cpu_count() or 4
    default_workers = min(4, cpu_count)
    parser = argparse.ArgumentParser(description='一鍵處理 DAT->Excel、合併、繪圖')
    parser.add_argument('--mode', choices=['1','2','3','all'], default='3',
                        help='1=DAT到Excel,2=合併HQ/LQ,3=繪圖,all=全部')
    parser.add_argument('--path', required=True, help='目標資料夾路徑')
    parser.add_argument('--interval',default=10, help='幾個檔案為一組，預設為10')
    parser.add_argument(
        '--plot-mode',
        choices=['simple', 'cluster', 'pick_auto'],
        default='cluster',
        help='繪圖模式：simple=僅平移疊圖, cluster=導數分群疊圖, pick_auto=自動pick Q強度 (新功能)'
    )
    parser.add_argument(
        '--y-axis',
        choices=['linear', 'log'],
        default='log',
        help='Y 軸刻度：linear=線性, log=對數 (預設)'
    )
    parser.add_argument(
        '--x-axis',
        choices=['linear', 'log'],
        default='linear',
        help='X 軸刻度：linear=線性 (預設), log=對數'
    )
    parser.add_argument(
        '--output-dir',
        default='output',
        help='輸出圖片資料夾名稱 (預設為 output)'
    )
    parser.add_argument(
        '--output-name',
        type=str,
        default=None,
        help='輸出圖片檔名（不用副檔名，如 "myplot"），不設定則自動依資料夾命名'
    )
    parser.add_argument(
        '--interactive',
        default=False,
        help='是否啟用互動式繪圖 (預設為 False)'
    )
    parser.add_argument(
        '--derivative',
        type=int,
        choices=[1,2],
        default=2,
        help='導數階數: 1=一次導數, 2=二次導數 (預設=2)'
    )
    parser.add_argument(
        '--diff-step',
        type=float,
        default=0.05,
        help='導數插值間隔 (預設=0.05)'
    )
    parser.add_argument(
        '--flat-threshold',
        type=float,
        default=0.0,
        help='平緩閾值：若導數特徵小於此值則歸類為 Cluster 0'
    )
    parser.add_argument(
        '--sort-peak',
        action='store_true',
        help='是否根據Q=0.5~0.7區間最大值排序每群'
    )
    parser.add_argument(
        '--shift',
        type=float,
        default=0.0,
        help='每條線Y軸平移量 (對數位移倍率，預設 0.0)'
    )
    parser.add_argument(
        '--q-min', type=float, default=0.0,
        help='顯示 Q 軸的最小值 (預設=0.0)'
    )   
    parser.add_argument(
        '--q-max', type=float, default=2.5,
        help='顯示 Q 軸的最大值 (預設=2.0)'
    )
    parser.add_argument(
        '--cluster-colors',
        type=str,
        default=None,
        help='每群的顏色, 逗號分隔（如 "#FF0000,#00FF00,#0000FF" 或 "red,green,blue"），預設用 rainbow colormap'
    )
    parser.add_argument(
        '--save-label',
        action='store_true',
        help='存圖時是否包含 legend 標籤 (加這個參數會存有標籤的圖，不加則沒有)'
    )
    parser.add_argument(
        '--peak-min',
        default='0.5',
        help='選擇最小值的 Q 範圍 (預設=1.6, 例如 1.6,2.0)'
    )
    parser.add_argument(
        '--peak-max',
        default='0.6',
        help='選擇最大值的 Q 範圍 (預設=1.8, 例如 1.6,2.0)'
    )
    parser.add_argument(
        '--cluster-range',
        action='store_true',
        help='是否將分群計算限制在 Peak Min ~ Peak Max 範圍內'
    )
    parser.add_argument(
        '--baseq',
        default=None,
        help='指定baseline的 Q 值，若不指定則採用起漲點'
    )
    parser.add_argument(
        '--pick-qs',
        default=None,
        help='指定要 pick 的 Q 值，用逗號分隔 (例如 0.52,0.75,0.85)。若不指定則使用程式內建預設值。'
    )
    parser.add_argument(
        '--max-workers',
        type=int,
        default=default_workers,
        help='指定多線程的最大 worker 數量，避免佔用過多記憶體。預設為 4 或 CPU 核心數的較小值。'
    )

    args = parser.parse_args()
    CUSTOM_COLOR_MAP = {
        "red": "#fb8072",
        "green": "#8dd3c7",
        "blue": "#80b1d3",
        "purple": "#8A2BE2",
        # 你要的其他顏色
    }
    COLOR_SERIES_DICT = {
        "red": [
            "#E34234", "#FF5349", "#FF6F61", "#E30B17", "#C41E3A", "#D7263D", 
            "#ED2939", "#FD3A4A", "#CB4154", "#B22234", "#F88379"
        ],
        "blue": [
            "#0077BE", "#0E4D92", "#4682B4", "#1F75FE", "#5B5EA6", "#1560BD", 
            "#436B95", "#89CFF0", "#6495ED", "#00308F", "#B0C4DE"
        ],
        "green": [
            "#009150", "#50C878", "#8FBC8F", "#43B48C", "#228B22", "#66B032", 
            "#00A877", "#B2D3C2", "#006400", "#2E8B57", "#3CB371"
        ],
        "purple": [
            "#8A2BE2", "#A569BD", "#6C3483", "#D6A4FF", "#7D3C98", "#9B59B6",
            "#A569BD", "#C39BD3", "#BA55D3", "#8E44AD", "#6C3483"
        ],
        "black": [
            "#111111", "#222222", "#444444", "#555555", "#666666", "#333333", 
            "#777777", "#888888", "#999999", "#000000", "#1A1A1A"
        ],
        "brown": [
            "#8B4513", "#A0522D", "#D2691E", "#DEB887", "#A0522D", "#CD853F", 
            "#8B0000", "#BC8F8F", "#704214", "#C19A6B", "#B87333"
        ]
    }
    # PICK_QS 設定
    if args.pick_qs:
        try:
            PICK_QS = [float(x.strip()) for x in args.pick_qs.split(',')]
        except ValueError:
            print("警告: --pick-qs 格式錯誤，將使用預設值。")
            PICK_QS = [0.5,0.59,0.7185,0.75]
    else:
        # 預設值
        PICK_QS = [0.5,0.59,0.7185,0.75]
    if args.cluster_colors:
        colors = [c.strip() for c in args.cluster_colors.split(',')]
        mapped_colors = [CUSTOM_COLOR_MAP.get(c, c) for c in colors]
        while len(mapped_colors) < 3:
            mapped_colors.append(mapped_colors[-1])
        cluster_colors_for_plotter = ",".join(mapped_colors)
    else:
        cluster_colors_for_plotter = "#009150, #50C878, #8FBC8F, #43B48C"

    # pick_auto 專用的 pick_colors
    color_names = [c.strip() for c in args.cluster_colors.split(',')] if args.cluster_colors else ['purple']
    PICK_N = len(PICK_QS)
    if len(color_names) >= PICK_N:
        pick_colors = color_names[:PICK_N]  # 直接取你輸入的顏色
    else:
        # 不夠才用色階補齊
        pick_colors = []
        for cname in color_names:
            if cname in COLOR_SERIES_DICT:
                pick_colors.extend(COLOR_SERIES_DICT[cname][:PICK_N - len(pick_colors)])
            else:
                pick_colors.append(cname)
        while len(pick_colors) < PICK_N:
            pick_colors.append(pick_colors[-1])

    

    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)

    if args.mode in ('1', 'all'):
        Mode1Processor(args.path, max_workers=args.max_workers).run()
    if args.mode in ('2', 'all'):
        Mode2Merger(args.path).run()
    if args.mode in ('3', 'all'):
        Mode3Plotter(
            args.path,
            interval=args.interval,
            plot_mode=args.plot_mode,
            y_axis=args.y_axis,
            x_axis=args.x_axis,
            output_dir=args.output_dir,
            output_filename=args.output_name,
            interactive=args.interactive,
            derivative_order=args.derivative,
            diff_step=args.diff_step,
            flat_threshold=args.flat_threshold,
            sort_peak=args.sort_peak,
            shift_distance=args.shift,
            display_q_min=args.q_min,
            display_q_max=args.q_max,
            cluster_colors=cluster_colors_for_plotter,
            pick_colors=pick_colors if args.plot_mode == "pick_auto" else None,   # <--- 加這個！
            save_label=args.save_label,
            peak_min=args.peak_min, peak_max=args.peak_max,
            cluster_range=args.cluster_range,
            pick_qs=PICK_QS if args.plot_mode == "pick_auto" else None,
            baseq=args.baseq,
            max_workers=args.max_workers,
        ).run()
if __name__ == '__main__':
    main()
