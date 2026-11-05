"""2026-10-20 角色類實驗改用 Skye 重跑（E2、E3、E3b、E6、E7 影片）。
輸入：output/experiments/skye-20261020/inputs/S.png（扛錘 3/4 錨點，裁切放大到 832×1248、灰底）、
M_weapon.png（只框冰錘）、M_scarf.png（只框橘色領巾）、pose1-5.png（沿用 10-19 的骨架圖）。
Skye 是遊戲專案素材：輸入與輸出都只留在本機 output/（不進 repo）。
用法（repo 根目錄、ComfyUI 已啟動）：python run_skye_experiments.py <e2|e6|e3|flux2|stylelock|qwen|e7>
"""
import json, os, pathlib, subprocess, sys, time

PY = r"C:\Users\XU\ComfyUI\.venv\Scripts\python.exe"
OUT = pathlib.Path("output/experiments/skye-20261020")
IN = OUT / "inputs"
env = dict(os.environ, PYTHONUTF8="1")
LOOK = ("same chibi horse-eared girl: mint hair, horse ears, teal eyes, cream shirt with orange neckerchief, "
        "navy shorts, black boots, and the same blue-and-gold ice hammer design")
POSES = {
    1: "wide stance, both arms raised above the head holding the hammer up high",
    2: "standing, both arms raised straight overhead holding the hammer up",
    3: "jumping in the air with knees bent, both arms raised overhead holding the hammer",
    4: "leaping sideways, one arm raised high holding the hammer above the head",
    5: "lunging forward, one arm raised high holding the hammer",
}


def run(tag, args):
    t = time.time()
    p = subprocess.run([PY, *args], capture_output=True, text=True, encoding="utf-8", env=env)
    rec = {"tag": tag, "seconds": round(time.time() - t, 1), "rc": p.returncode,
           "tail": (p.stdout + p.stderr).strip().splitlines()[-2:]}
    with open(OUT / "timings.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(tag, rec["seconds"], rec["rc"], rec["tail"][-1:], flush=True)
    return rec


def newest_png(d):
    return max(pathlib.Path(d).rglob("*.png"), key=lambda p: p.stat().st_mtime)


def edit_check(name, task, prompt, mask):
    raw = OUT / name / "ours-raw"
    run(f"{name}-raw", ["tools_src/generate.py", task, "--config", "local_config.json", "--prompt", prompt,
                        "--image", str(IN / "S.png"), "--mask", str(IN / mask), "--seed", "7", "--output-dir", str(raw)])
    edited = newest_png(raw)
    run(f"{name}-cmp-raw", ["tools_src/gameart.py", "edit", "compare", "--source", str(IN / "S.png"), "--edited", str(edited),
                            "--mask", str(IN / mask), "--output-dir", str(OUT / name / "cmp-ours-raw")])
    run(f"{name}-composite", ["tools_src/gameart.py", "edit", "composite", "--source", str(IN / "S.png"), "--edited", str(edited),
                              "--mask", str(IN / mask), "--output-dir", str(OUT / name / "ours-composite")])
    comp = newest_png(OUT / name / "ours-composite")
    run(f"{name}-cmp-composite", ["tools_src/gameart.py", "edit", "compare", "--source", str(IN / "S.png"), "--edited", str(comp),
                                  "--mask", str(IN / mask), "--output-dir", str(OUT / name / "cmp-ours-composite")])


which = sys.argv[1]
if which == "e2":
    edit_check("E2", "guided_inpaint", "a long spear", "M_weapon.png")
elif which == "e6":
    edit_check("E6", "inpaint", "red neckerchief", "M_scarf.png")
elif which == "e7":
    run("e7-video", ["tools_src/gameart.py", "run", "video/wan/img2video", "--allow-unverified-platform",
                     "--set", f"start_image={IN / 'S.png'}",
                     "--set", "prompt=a chibi horse-eared girl standing with a big ice hammer on her shoulder, hair and tail swaying gently, subtle breathing, static camera",
                     "--set", "width=480", "--set", "height=704", "--set", "length=49", "--set", "seed=7",
                     "--output-dir", str(OUT / "E7" / "video")])
else:
    for i, desc in POSES.items():
        if which == "e3":
            run(f"e3-{i}", ["tools_src/generate.py", "character_action", "--config", "local_config.json",
                            "--prompt", "same character, game art", "--character-ref", str(IN / "S.png"),
                            "--pose-ref", str(IN / f"pose{i}.png"), "--seed", "7", "--output-dir", str(OUT / f"E3/ours-{i}")])
        elif which == "flux2":
            run(f"flux2-{i}", ["tools_src/generate.py", "flux2_edit", "--config", "local_config.json",
                               "--prompt", f"Keep exactly the {LOOK}, same art style. Change only the pose: {desc}. Full body, plain gray background.",
                               "--image", str(IN / "S.png"), "--seed", "7", "--output-dir", str(OUT / f"E3b/flux2-{i}")])
        elif which == "stylelock":
            run(f"stylelock-{i}", ["tools_src/generate.py", "style_lock", "--config", "local_config.json",
                                   "--prompt", f"same character, game art, full body, {desc}",
                                   "--character-ref", str(IN / "S.png"), "--width", "832", "--height", "1216", "--seed", "7",
                                   "--output-dir", str(OUT / f"E3b/stylelock-{i}")])
        elif which == "qwen":
            run(f"qwen-{i}", ["tools_src/gameart.py", "run", "image/qwen-image-edit/three-reference", "--allow-unverified-platform",
                              "--set", f"image={IN / 'S.png'}", "--set", f"identity_ref={IN / 'S.png'}",
                              "--set", f"object_ref={IN / f'pose{i}.png'}",
                              "--set", ("prompt=Picture 1 is the character to redraw. Picture 2 is the same character as the identity reference: "
                                        f"keep the {LOOK}. Picture 3 is only a body-pose reference (ignore the hammer drawn in it): "
                                        f"redraw the character from Picture 1 in that body pose, {desc}. Full body, plain gray background."),
                              "--set", "seed=7", "--timeout", "1500", "--output-dir", str(OUT / f"E3b/qwen-{i}")])
