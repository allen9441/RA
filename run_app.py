import os
import sys
import multiprocessing
import streamlit.web.cli as stcli

def resolve_path(path):
    if getattr(sys, "frozen", False):
        basedir = sys._MEIPASS
    else:
        basedir = os.path.dirname(__file__)
    return os.path.join(basedir, path)

if __name__ == "__main__":
    multiprocessing.freeze_support()

    # 如果參數裡帶有 --cli-mode，就切換到執行原本的 main.py，而不是啟動 streamlit
    if len(sys.argv) > 1 and sys.argv[1] == "--cli-mode":
        import main
        # 移除 --cli-mode 這個參數，讓 argparse 正常解析
        sys.argv.pop(1)
        sys.exit(main.main())

    app = resolve_path("streamlit_app.py")

    sys.argv = [
        "streamlit",
        "run",
        app,
        "--global.developmentMode=false",
    ]
    sys.exit(stcli.main())
