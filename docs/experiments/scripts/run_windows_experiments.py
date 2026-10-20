"""2026-10-19 Windows 實驗驅動腳本：依清單跑我方側任務並記錄耗時。
用法：python run_windows_experiments.py <實驗名> （需在 repo 根目錄、ComfyUI 已啟動）
實驗名：denoise / e1 / e4 / e5 / e6 / e8
"""
import json, subprocess, sys, time, os, pathlib

PY = r"C:\Users\XU\ComfyUI\.venv\Scripts\python.exe"
OUT = pathlib.Path("output/experiments/platform-vs-pipeline-20261019")
IN = OUT / "inputs"
env = dict(os.environ, PYTHONUTF8="1")
log_path = OUT / "timings.jsonl"


def run(tag, args):
    t = time.time()
    p = subprocess.run([PY, *args], capture_output=True, text=True, encoding="utf-8", env=env)
    dt = round(time.time() - t, 2)
    rec = {"tag": tag, "seconds": dt, "rc": p.returncode, "tail": (p.stdout + p.stderr).strip().splitlines()[-2:]}
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(tag, dt, p.returncode, rec["tail"][-1:] )
    return rec


def gen(task, tag, outdir, *extra):
    return run(tag, ["tools_src/generate.py", task, "--config", "local_config.json", *extra, "--output-dir", str(OUT / outdir)])


def main(which):
    if which == "denoise":
        for d in ("1.0", "0.6", "0.3"):
            gen("inpaint", f"denoise-{d}", f"DN/inpaint-d{d}", "--prompt", "a long spear", "--image", str(IN/"A.png"),
                "--mask", str(IN/"M.png"), "--denoise", d)
    elif which == "e1":
        # ComfyUI 對完全相同的請求會直接回傳快取，不會重算；所以固定種子與不同種子交錯執行，
        # 讓每次「固定種子」都真的重新生成。
        for i in range(1, 6):
            gen("concept", f"e1-fixed-{i}", f"E1b/fixed-{i}", "--prompt", "a red potion bottle on a table", "--seed", "12345")
            gen("concept", f"e1-varied-{i}", f"E1b/varied-{i}", "--prompt", "a red potion bottle on a table", "--seed", str(i))
    elif which == "e4":
        gen("icon_asset", "e4-icon", "E4/ours", "--prompt", "a golden coin game icon")
    elif which == "e5":
        words = ["POTION", "START", "開始遊戲", "藥水", "1234"]
        for w in words:
            for s in range(1, 6):
                gen("concept", f"e5-{w}-{s}", f"E5/ours-{w}-{s}", "--prompt", f'a wooden sign that says "{w}"', "--seed", str(s))
    elif which == "e6":
        gen("inpaint", "e6-inpaint", "E6/ours", "--prompt", "red shoulder badge", "--image", str(IN/"A.png"), "--mask", str(IN/"M2.png"))
    elif which == "e8":
        gen("concept", "e8-concept", "E8/ours", "--prompt", "a red potion bottle")


main(sys.argv[1])
