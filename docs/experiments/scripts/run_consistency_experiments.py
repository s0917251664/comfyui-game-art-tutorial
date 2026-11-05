"""2026-10-19 角色一致性補測（E3b）：同一張騎士圖 A.png、同樣 5 個姿勢，比較不同流程。
流程：flux2_edit（文字編修）、style_lock（外觀鎖定，SDXL）、Qwen-Image-Edit 三參考。
用法（repo 根目錄、ComfyUI 已啟動）：python run_consistency_experiments.py <flux2|stylelock|qwen>
"""
import json, os, pathlib, subprocess, sys, time

PY = r"C:\Users\XU\ComfyUI\.venv\Scripts\python.exe"
OUT = pathlib.Path("output/experiments/platform-vs-pipeline-20261019")
IN = OUT / "inputs"
env = dict(os.environ, PYTHONUTF8="1")
POSES = {
    1: "wide stance, both arms raised above the head holding the sword up high",
    2: "standing, both arms raised straight overhead holding the sword up",
    3: "jumping in the air with knees bent, both arms raised overhead holding the sword",
    4: "leaping sideways, one arm raised high holding the sword above the head",
    5: "lunging forward, one arm raised high holding the sword",
}


def run(tag, args):
    t = time.time()
    p = subprocess.run([PY, *args], capture_output=True, text=True, encoding="utf-8", env=env)
    rec = {"tag": tag, "seconds": round(time.time() - t, 1), "rc": p.returncode,
           "tail": (p.stdout + p.stderr).strip().splitlines()[-2:]}
    with open(OUT / "timings_consistency.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(tag, rec["seconds"], rec["rc"], rec["tail"][-1:])


which = sys.argv[1]
for i, desc in POSES.items():
    if which == "flux2":
        run(f"flux2-{i}", ["tools_src/generate.py", "flux2_edit", "--config", "local_config.json",
            "--prompt", f"Keep exactly the same character: same silver hair, yellow eyes, armor and red cape, same art style. Change only the pose: {desc}. Full body, plain gray background.",
            "--image", str(IN / "A.png"), "--seed", "7", "--output-dir", str(OUT / f"E3b/flux2-{i}")])
    elif which == "stylelock":
        run(f"stylelock-{i}", ["tools_src/generate.py", "style_lock", "--config", "local_config.json",
            "--prompt", f"same character, game art, full body, {desc}",
            "--character-ref", str(IN / "A.png"), "--width", "832", "--height", "1216", "--seed", "7",
            "--output-dir", str(OUT / f"E3b/stylelock-{i}")])
    elif which == "qwen":
        run(f"qwen-{i}", ["tools_src/gameart.py", "run", "image/qwen-image-edit/three-reference", "--allow-unverified-platform",
            "--set", f"image={IN/'A.png'}", "--set", f"identity_ref={IN/'A.png'}", "--set", f"object_ref={IN/'poses'/f'pose{i}.png'}",
            "--set", ("prompt=Picture 1 is the character to redraw. Picture 2 is the same character as the identity reference: keep her exact face, silver hair, yellow eyes, armor, red cape and sword design. "
                      f"Picture 3 is only a body-pose reference (ignore the hammer in it): redraw the character from Picture 1 in that body pose, {desc}. Full body, plain gray background."),
            "--set", "seed=7", "--timeout", "1500", "--output-dir", str(OUT / f"E3b/qwen-{i}")])
