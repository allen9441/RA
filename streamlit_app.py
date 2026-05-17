import streamlit as st
import subprocess
import sys
import os
import zipfile
import shutil
import tempfile

st.set_page_config(page_title="X-Ray Data Processor", layout="wide")

st.title("X-Ray Data Processor GUI")

# Initialize RA_data directory
RA_DATA_DIR = os.path.join(os.getcwd(), "RA_data")
os.makedirs(RA_DATA_DIR, exist_ok=True)

def get_subdirs(path):
    try:
        return [d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d)) and not d.startswith('.')]
    except Exception:
        return []

# 1. Path Selection
st.header("Step 1: 資料夾管理與選擇")

col_upload, col_select = st.columns(2)

with col_upload:
    st.subheader("上傳新的資料夾壓縮檔 (ZIP)")
    uploaded_file = st.file_uploader("上傳 ZIP 後將自動解壓縮至資料庫", type=["zip"])
    
    if uploaded_file is not None:
        if st.button("上傳並解壓縮"):
            with st.spinner("解壓縮中..."):
                # Save uploaded zip temporarily
                temp_zip = os.path.join(RA_DATA_DIR, "temp_uploaded.zip")
                with open(temp_zip, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                
                # Extract zip
                extract_dir = os.path.join(RA_DATA_DIR, "temp_extract")
                os.makedirs(extract_dir, exist_ok=True)
                with zipfile.ZipFile(temp_zip, 'r') as zip_ref:
                    zip_ref.extractall(extract_dir)
                
                # Check if there is a single top-level directory inside the zip
                extracted_items = os.listdir(extract_dir)
                if len(extracted_items) == 1 and os.path.isdir(os.path.join(extract_dir, extracted_items[0])):
                    src_dir = os.path.join(extract_dir, extracted_items[0])
                    folder_name = extracted_items[0]
                else:
                    src_dir = extract_dir
                    # Use the uploaded file name as folder name (without .zip)
                    folder_name = os.path.splitext(uploaded_file.name)[0]
                
                target_path = os.path.join(RA_DATA_DIR, folder_name)
                
                # Handle existing folder
                if os.path.exists(target_path):
                    shutil.rmtree(target_path)
                    
                shutil.move(src_dir, target_path)
                
                # Cleanup
                if os.path.exists(extract_dir):
                    shutil.rmtree(extract_dir)
                os.remove(temp_zip)
                
                st.success(f"成功上傳並建立資料夾：{folder_name}")
                st.rerun()

with col_select:
    st.subheader("選擇要處理的資料夾")
    subdirs = sorted(get_subdirs(RA_DATA_DIR))
    
    if not subdirs:
        st.info("資料庫目前為空，請先上傳 ZIP 檔案。")
        selected_target = None
    else:
        selected_folder = st.selectbox("選擇 RA_data 內的資料夾", subdirs)
        selected_target = os.path.join(RA_DATA_DIR, selected_folder)
        st.success(f"已選擇資料夾：{selected_folder}")
        
target_dir = selected_target if selected_target else ""

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
    cpu_count = os.cpu_count() or 4
    default_workers = min(4, cpu_count)
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
    max_workers = st.slider(
        "Max Workers (最大線程數)", 
        min_value=1, max_value=cpu_count, value=default_workers, step=1,
        help="控制多線程處理的併發數量。數值越高可能越快，但會佔用更多記憶體。"
    )

with col2:
    st.subheader("開關選項")
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

if 'output_zip_path' not in st.session_state:
    st.session_state.output_zip_path = None

if st.button("開始執行"):
    if not target_dir or not os.path.exists(target_dir):
        st.error(f"找不到路徑: {target_dir}")
    else:
        # Save output in target directory's output folder
        real_output_dir = os.path.join(target_dir, output_dir)
        os.makedirs(real_output_dir, exist_ok=True)
        
        cmd = [sys.executable]
        if getattr(sys, "frozen", False):
            cmd.append("--cli-mode")
        else:
            cmd.append("main.py")

        cmd.extend(["--mode", selected_mode])
        cmd.extend(["--path", target_dir])
        cmd.extend(["--interval", interval])
        cmd.extend(["--output-dir", real_output_dir])
        cmd.extend(["--max-workers", str(max_workers)])

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
            if sort_peak:
                cmd.append("--sort-peak")
            if save_label:
                cmd.append("--save-label")
            if cluster_range:
                cmd.append("--cluster-range")

        st.info("開始處理資料，這可能需要一點時間...")

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
                
                # Copy CSV files to output directory for downloading if they exist
                for csv_file in ["hq_data.csv", "lq_data.csv", "all_data.csv"]:
                    src_csv = os.path.join(target_dir, csv_file)
                    if os.path.exists(src_csv):
                        try:
                            shutil.copy(src_csv, os.path.join(real_output_dir, csv_file))
                        except Exception as e:
                            st.warning(f"無法複製 {csv_file}: {e}")
                
                # 先刪除 target_dir 中可能殘留的舊 zip，避免被一起打包
                folder_name_for_zip = os.path.basename(os.path.normpath(target_dir))
                output_zip_path = os.path.join(target_dir, f"{folder_name_for_zip}_results.zip")
                if os.path.exists(output_zip_path):
                    os.remove(output_zip_path)

                # 也清理 real_output_dir 中可能殘留的 zip
                for f in os.listdir(real_output_dir):
                    if f.endswith('_results.zip'):
                        try:
                            os.remove(os.path.join(real_output_dir, f))
                        except Exception:
                            pass

                # 先打包到暫存目錄，再移動到 target_dir，
                # 確保 zip 檔案不在被打包的來源目錄中
                with tempfile.TemporaryDirectory() as tmpdir:
                    tmp_zip_base = os.path.join(tmpdir, f"{folder_name_for_zip}_results")
                    shutil.make_archive(tmp_zip_base, 'zip', real_output_dir)
                    shutil.move(f"{tmp_zip_base}.zip", output_zip_path)

                st.session_state.output_zip_path = output_zip_path
                
                # Try to display result image/html if exists
                if output_name:
                    img_path = os.path.join(real_output_dir, f"{output_name}.png")
                    html_path = os.path.join(real_output_dir, f"{output_name}.html")
                else:
                    folder_name = os.path.basename(os.path.normpath(target_dir))
                    img_path = os.path.join(real_output_dir, f"{folder_name}.png")
                    html_path = os.path.join(real_output_dir, f"{folder_name}.html")
                
                # If interactive html exists, show it via components.html, otherwise show image
                if os.path.exists(html_path):
                    import streamlit.components.v1 as components
                    with open(html_path, 'r', encoding='utf-8') as f:
                        html_data = f.read()
                    st.markdown("### 互動式圖表")
                    components.html(html_data, height=600, scrolling=True)
                elif os.path.exists(img_path):
                    st.image(img_path, caption="Result Plot")
            else:
                st.error("執行失敗")

if st.session_state.get('output_zip_path') and os.path.exists(st.session_state.output_zip_path):
    with open(st.session_state.output_zip_path, "rb") as fp:
        btn = st.download_button(
            label="下載處理結果 (ZIP)",
            data=fp,
            file_name=os.path.basename(st.session_state.output_zip_path),
            mime="application/zip"
        )
