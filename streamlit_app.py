import streamlit as st
import subprocess
import sys
import os

st.set_page_config(page_title="X-Ray Data Processor", layout="wide")

st.title("X-Ray Data Processor GUI")

# Initialize session state for browser
if 'browser_cwd' not in st.session_state:
    st.session_state.browser_cwd = os.getcwd()

def get_subdirs(path):
    try:
        return [d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d)) and not d.startswith('.')]
    except Exception:
        return []

# 1. Path Selection
st.header("Step 1: 資料夾路徑")

# Browser UI
st.markdown("### 資料夾瀏覽器")
col_path, col_up = st.columns([0.85, 0.15])

with col_path:
    st.code(st.session_state.browser_cwd)

with col_up:
    if st.button("上一層"):
        st.session_state.browser_cwd = os.path.dirname(st.session_state.browser_cwd)
        st.rerun()

subdirs = sorted(get_subdirs(st.session_state.browser_cwd))
col_sel, col_go = st.columns([0.85, 0.15])

with col_sel:
    selected_subdir = st.selectbox("進入子資料夾", ["(選擇資料夾)"] + subdirs, label_visibility="collapsed")

with col_go:
    if st.button("進入") and selected_subdir != "(選擇資料夾)":
        st.session_state.browser_cwd = os.path.join(st.session_state.browser_cwd, selected_subdir)
        st.rerun()

# Confirm selection
if st.button("確認選擇此資料夾"):
    st.session_state.selected_target = st.session_state.browser_cwd

# Final Path Input (Editable)
target_dir = st.text_input(
    "目標資料夾路徑 (可手動修改)", 
    value=st.session_state.get('selected_target', os.getcwd()),
    help="輸入要處理的資料夾完整路徑。 | 可使用上方瀏覽器選擇，或直接貼上路徑。"
)

st.markdown("---")

# 2. Mode Selection
st.header("Step 2: 執行模式")
mode = st.radio(
    "選擇模式", 
    ["1. DAT轉Excel (Mode 1)", "2. 合併HQ/LQ (Mode 2)", "3. 繪圖與分析 (Mode 3)", "All (全部執行)"],
)
mode_map = {
    "1. DAT轉Excel (Mode 1)": "1",
    "2. 合併HQ/LQ (Mode 2)": "2",
    "3. 繪圖與分析 (Mode 3)": "3",
    "All (全部執行)": "all"
}
selected_mode = mode_map[mode]

st.markdown("---")

# 3. Parameters
st.header("Step 3: 參數設定")

col1, col2 = st.columns(2)

with col1:
    st.subheader("一般設定")
    interval = st.text_input(
        "Interval (間隔)", "30",
        help="每隔幾個檔案畫一條線，避免圖表過於擁擠。 | 預設值：30"
    )
    output_dir = st.text_input(
        "Output Dir (輸出目錄)", "output",
        help="輸出圖片或 Excel 檔案存放的資料夾名稱。 | 預設值：output"
    )
    output_name = st.text_input(
        "Output Name (輸出檔名, 選填)", "",
        help="指定輸出的檔名 (不含副檔名)。 | 若留空，則自動使用資料夾名稱作為檔名。"
    )

with col2:
    st.subheader("開關選項")
    interactive = st.checkbox(
        "Interactive (互動式視窗)", value=False, 
        help="若勾選，程式會嘗試開啟獨立的 Matplotlib 視窗顯示圖表。"
    )
    sort_peak = st.checkbox(
        "Sort Peak (依峰值排序)", value=False,
        help="是否根據指定 Q 範圍內的峰值強度，重新排序圖例順序。"
    )
    save_label = st.checkbox(
        "Save Label (存圖含標籤)", value=False,
        help="存檔圖片時是否包含圖例 (Legend)。若檔案過多建議關閉以避免遮擋。"
    )

# Mode 3 specific
if selected_mode in ["3", "all"]:
    st.subheader("繪圖詳細設定 (Mode 3)")
    
    c1, c2, c3 = st.columns(3)
    with c1:
        plot_mode = st.selectbox(
            "Plot Mode", ["cluster", "simple", "pick_auto"],
            help="cluster: 自動根據導數特徵分群疊圖 | simple: 一般平移疊圖 | pick_auto: 自動抓取特定 Q 值的峰值強度並輸出報表"
        )
        y_axis = st.selectbox(
            "Y Axis", ["log", "linear"],
            help="Y 軸 (強度) 的顯示刻度。"
        )
        x_axis = st.selectbox(
            "X Axis", ["linear", "log"],
            help="X 軸 (Q 值) 的顯示刻度。"
        )
    with c2:
        derivative = st.selectbox(
            "Derivative Order", ["2", "1"],
            help="導數階數，僅用於 Cluster 模式的分群計算。 | 預設值：2 (二次導數)"
        )
        diff_step = st.text_input(
            "Diff Step", "0.05",
            help="導數計算的插值間隔。數值越大越平滑(抗雜訊)，數值越小越敏感。 | 預設值：0.1"
        )
        flat_threshold = st.text_input(
            "Flat Threshold", "0.0",
            help="平緩閾值。若導數特徵小於此值，將被獨立分到 Cluster 0 (Flat)。設為 0.0 代表不啟用。 | 建議嘗試 0.001 ~ 0.01"
        )
        shift = st.text_input(
            "Shift", "0.0",
            help="每條曲線的垂直平移量 (在 log 刻度下代表倍率)。 | 預設值：0.0 (不平移)"
        )
    with c3:
        q_min = st.text_input(
            "Q Min", "0.0",
            help="X 軸 (Q 值) 顯示範圍的最小值。 | 預設值：0.0"
        )
        q_max = st.text_input(
            "Q Max", "2.5",
            help="X 軸 (Q 值) 顯示範圍的最大值。 | 預設值：2.5"
        )
    
    c4, c5 = st.columns(2)
    with c4:
        peak_min = st.text_input(
            "Peak Min (Sort)", "0.5",
            help="用於排序或分群計算的 Q 值範圍下限。 | 預設值：0.5"
        )
        peak_max = st.text_input(
            "Peak Max (Sort)", "0.6",
            help="用於排序或分群計算的 Q 值範圍上限。 | 預設值：0.6"
        )
        baseq = st.text_input(
            "Base Q (Optional)", "",
            help="指定扣除 Baseline 的 Q 值位置。 | 若留空，程式會自動偵測起漲點作為 Baseline。"
        )
        cluster_range = st.checkbox(
            "Cluster within Peak Range", value=True,
            help="若勾選，分群計算將僅針對 Peak Min ~ Peak Max 範圍內的導數特徵，而非整條譜線。建議Range / Step >= 5"
        )
    with c5:
        cluster_colors = st.text_input(
            "Cluster Colors (comma separated)", "",
            help="指定分群顏色 (用逗號分隔，如 red,green,blue)。 | 預設值：自動配色 (Rainbow)"
        )
        pick_qs = st.text_input(
            "Pick Qs (comma separated)", "0.5,0.59,0.7185,0.75",
            help="指定要自動抓峰的 Q 值列表 (用逗號分隔)。僅用於 pick_auto 模式。 | 預設值：0.5, 0.59, 0.7185, 0.75"
        )

st.markdown("---")

# 4. Run
st.header("Step 4: 執行")

if st.button("開始執行"):
    if not os.path.exists(target_dir):
        st.error(f"找不到路徑: {target_dir}")
    else:
        cmd = [sys.executable, "main.py"]
        cmd.extend(["--mode", selected_mode])
        cmd.extend(["--path", target_dir])
        cmd.extend(["--interval", interval])
        cmd.extend(["--output-dir", output_dir])
        
        if output_name:
            cmd.extend(["--output-name", output_name])
            
        if selected_mode in ["3", "all"]:
            cmd.extend(["--plot-mode", plot_mode])
            cmd.extend(["--y-axis", y_axis])
            cmd.extend(["--x-axis", x_axis])
            cmd.extend(["--derivative", derivative])
            cmd.extend(["--diff-step", diff_step])
            cmd.extend(["--flat-threshold", flat_threshold])
            cmd.extend(["--shift", shift])
            cmd.extend(["--q-min", q_min])
            cmd.extend(["--q-max", q_max])
            cmd.extend(["--peak-min", peak_min])
            cmd.extend(["--peak-max", peak_max])
            
            if cluster_colors:
                cmd.extend(["--cluster-colors", cluster_colors])
            if baseq:
                cmd.extend(["--baseq", baseq])
            if pick_qs:
                cmd.extend(["--pick-qs", pick_qs])
            
            if interactive:
                cmd.extend(["--interactive", "True"])
            if sort_peak:
                cmd.append("--sort-peak")
            if save_label:
                cmd.append("--save-label")
            if cluster_range:
                cmd.append("--cluster-range")

        st.info(f"執行指令: {' '.join(cmd)}")
        
        # Run process
        with st.spinner("執行中..."):
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = process.communicate()
            
            if stdout:
                st.text_area("執行輸出 (Output)", stdout, height=300)
            if stderr:
                st.error("錯誤輸出 (Error):")
                st.text(stderr)
            
            if process.returncode == 0:
                st.success("執行成功！")
                
                # Try to display result image if exists
                if output_name:
                    img_path = os.path.join(output_dir, f"{output_name}.png")
                else:
                    folder_name = os.path.basename(os.path.normpath(target_dir))
                    img_path = os.path.join(output_dir, f"{folder_name}.png")
                
                if os.path.exists(img_path):
                    st.image(img_path, caption="Result Plot")
            else:
                st.error("執行失敗")
