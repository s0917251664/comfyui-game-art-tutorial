# 已驗證版本清單（tested-version manifest）

這份文件記錄「曾在同一台已安裝機器上實際跑通」的工具、custom node（自訂節點）、Python 套件與模型版本。它不是目前最新版推薦，也不應把可變的 main/master 分支當成版本。安裝流程先依這份清單的已驗證版本重現；要升級時，另做一次完整 smoke test（冒煙測試）並更新紀錄。

目前狀態：**已驗證（verified）**，capture machine 為 XU-Nano-PC，完成日期為 2026-08-31。這筆資料直接取自 C:\Users\XU\ComfyUI 的實際安裝、模型檔與本機 ComfyUI API；repo 本身仍不提交 local_config.json、device_config.json 或 video_capabilities.json。

偵測器在 2026-08-31T02:34:30.150519+00:00 重新產生本機 capability config，加入 node schema fingerprint；之後在 2026-08-31 完成圖片 smoke、H3 全部影片 task、video_concat 與 Wan 的 i2v/control smoke，並完成 contract/sidecar/resume 與 concat policy smoke。偵測器只掃描既有檔案與 runtime，不下載模型；本文件的 SHA-256 是另外對實際檔案計算的結果。

## 跨設備重建的定義

「精準移植」是重建同一套**偵測規則、版本基線與 task 契約**，不是把來源機的硬體快照硬套到目標機，也不承諾不同 GPU/backend 的輸出逐位元相同：

- 會隨 repository 一起移動並鎖定的是 `tools_src/` 原始碼、ComfyUI/custom node commit、模型家族與對應 SHA-256，以及圖片／影片 task 的 CLI 契約。
- 每台目標機都必須重新執行 `detect_device.py`；圖片 checkpoint family、tier 與預設解析度由該機的 backend、VRAM／統一記憶體動態決定。不得複製來源機的 `device_config.json`。
- 要使用影片時，每台目標機都必須重新執行 `detect_video_capabilities.py`；可用 backend 與 task capability 由該機現有模型、Python runtime 與 ComfyUI node schema 動態決定。不得複製來源機的 `video_capabilities.json`。
- `local_config.json` 只記錄目標機的絕對路徑與 URL，也必須在目標機重建。`workflows/` 是不進版控的維護用視覺化參考；正式 task 由 `generate.py` 依上述 machine-specific config 組 graph，不靠人工逐台修改 workflow JSON。
- 本頁的 XU-Nano-PC hash 是已驗證的 SDXL／影片基線。若目標硬體偵測到另一個 tier，只能使用該 tier 已明確支援並完成 smoke 的模型組；例如目前 `sd15` 的 SDXL add-on 路徑尚未實機驗證，不能為了追求「相同」而強制載入 SDXL 模型造成 OOM 或架構不相容。

## 擷取規則

在另一台已安裝機器上，先以 tools_src/detect_device.py 產生圖片的 device_config.json，再以 tools_src/detect_video_capabilities.py 掃描既有影片模型、runtime 與 /object_info。兩者都不負責下載模型。完成至少一次最小圖片與影片 smoke、並驗收輸出容器後，才可把該台機器的 capture_status 改為 verified。

每個 hash 都要對應實際檔案、模型家族與來源；影片模型必須涵蓋 diffusion_models、text_encoders、vae 三類路徑。若模型由 extra_model_paths.yaml 指向共享模型庫，應記錄共享模型庫的真實檔案路徑。拿不到的欄位保留 null/pending，不能用猜測的 commit、版本或 hash 填補。

Windows PowerShell 的基本擷取指令如下（把路徑換成該機器的實際值）：

    $ComfyUiPath = '<ComfyUI 安裝路徑>'
    $PythonExe = "$ComfyUiPath\.venv\Scripts\python.exe"
    git -C $ComfyUiPath rev-parse HEAD
    git -C "$ComfyUiPath\custom_nodes\ComfyUI-Manager" rev-parse HEAD
    git -C "$ComfyUiPath\custom_nodes\ComfyUI_IPAdapter_plus" rev-parse HEAD
    git -C "$ComfyUiPath\custom_nodes\comfyui_controlnet_aux" rev-parse HEAD
    & $PythonExe --version
    & $PythonExe -c "import torch, PIL, av; print('torch', torch.__version__); print('Pillow', PIL.__version__); print('PyAV', av.__version__)"
    Get-FileHash "$ComfyUiPath\models\diffusion_models\<影片模型檔名>" -Algorithm SHA256

## XU-Nano-PC manifest

    manifest_version: 1
    capture_status: verified
    captured_at: '2026-08-31'
    machine: XU-Nano-PC
    capability_config_captured_at: '2026-08-31T02:34:30.150519+00:00'
    device_config:
      os: Windows
      backend: cuda
      tier: sdxl
      gpu_name: NVIDIA GeForce RTX 4080
      driver_version: '581.08'
      vram_mb: 16376
      unified_memory_mb: null
      default_width: 1024
      default_height: 1024
      torch_index_url: https://download.pytorch.org/whl/cu130
    comfyui:
      version: v0.34.0
      commit: 12d5279438bfefc058a269eae805ceab6047777f
      source: https://github.com/comfyanonymous/ComfyUI.git
    custom_nodes:
      ComfyUI-Manager:
        commit: 14de630433a5f0665881de4ae973c12ea94b02f2
        source: https://github.com/Comfy-Org/ComfyUI-Manager.git
      ComfyUI_IPAdapter_plus:
        commit: a0f451a5113cf9becb0847b92884cb10cbdec0ef
        source: https://github.com/cubiq/ComfyUI_IPAdapter_plus.git
      comfyui_controlnet_aux:
        commit: e8b689a513c3e6b63edc44066560ca5919c0576e
        source: https://github.com/Fannovel16/comfyui_controlnet_aux.git
    runtime:
      python: 3.13.9
      python_build: '3.13.9 | packaged by Anaconda, Inc. | (main, Oct 21 2025, 19:09:58) [MSC v.1929 64 bit (AMD64)]'
      platform: Windows-11-10.0.26200-SP0
      torch: 2.13.0+cu130
      torch_cuda_available: true
      torch_cuda_version: '13.0'
      pillow: 12.2.0
      pyav: 18.1.0
    models:
      - kind: image
        directory: checkpoints
        file: sd_xl_base_1.0.safetensors
        family: SDXL base
        bytes: 6938078334
        sha256: 31E35C80FC4829D14F90153F4C74CD59C90B779F6AFE05A74CD6120B893F7E5B
        source: https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors
        captured_from: 'C:\Users\XU\ComfyUI\models\checkpoints\sd_xl_base_1.0.safetensors'
      - kind: image
        directory: checkpoints
        file: juggernautXL_ragnarok.safetensors
        family: Juggernaut XL Ragnarok
        bytes: 7105350162
        sha256: DD08FA32F98D05A2443CA1419E46DF1575A0811F6E3B246D9DD47FF20F5EB66A
        source: https://civitai.com/models/133005/juggernaut-xl
        captured_from: 'C:\Users\XU\ComfyUI\models\checkpoints\juggernautXL_ragnarok.safetensors'
      - kind: image
        directory: checkpoints
        file: Illustrious-XL-v1.1.safetensors
        family: Illustrious XL v1.1
        bytes: 6938040728
        sha256: 536863E9F0C13B0CE834E2F8A19ADA425EE4F722C0AD3D0051EC7E6ADAA8156C
        source: https://huggingface.co/OnomaAIResearch/Illustrious-XL-v1.1/tree/main
        captured_from: 'C:\Users\XU\ComfyUI\models\checkpoints\Illustrious-XL-v1.1.safetensors'
      - kind: image
        directory: checkpoints
        file: ponyDiffusionV6XL_v6StartWithThisOne.safetensors
        family: Pony Diffusion V6 XL
        bytes: 6938041050
        sha256: 67AB2FD8EC439A89B3FEDB15CC65F54336AF163C7EB5E4F2ACC98F090A29B0B3
        source: https://civitai.com/models/257749/pony-diffusion-v6-xl
        captured_from: 'C:\Users\XU\ComfyUI\models\checkpoints\ponyDiffusionV6XL_v6StartWithThisOne.safetensors'
      - kind: image
        directory: controlnet
        file: controlnet-canny-sdxl-1.0.safetensors
        family: SDXL ControlNet Canny
        bytes: 2502139104
        sha256: 80664D80E3F233371CB6921110D0A6B7A40C01571905463F9DDE5637E7894ED3
        source: https://huggingface.co/lllyasviel/sd_control_collection/resolve/main/diffusers_xl_canny_full.safetensors
        captured_from: 'C:\Users\XU\ComfyUI\models\controlnet\controlnet-canny-sdxl-1.0.safetensors'
      - kind: image
        directory: controlnet
        file: controlnet-depth-sdxl-1.0.safetensors
        family: SDXL ControlNet Depth
        bytes: 2502139104
        sha256: 8BA4DFAA1958F1F68E5DC7F9839F9EF4E153AEF0D330291E5CF966C925F97477
        source: https://huggingface.co/lllyasviel/sd_control_collection/resolve/main/diffusers_xl_depth_full.safetensors
        captured_from: 'C:\Users\XU\ComfyUI\models\controlnet\controlnet-depth-sdxl-1.0.safetensors'
      - kind: image
        directory: controlnet
        file: controlnet-openpose-sdxl-1.0.safetensors
        family: SDXL ControlNet OpenPose
        bytes: 5004167829
        sha256: 5A4B928CB1E93748217900CB66D4135BF70D932D2924232F925910FAD9E43A92
        source: https://huggingface.co/thibaud/controlnet-openpose-sdxl-1.0/resolve/main/OpenPoseXL2.safetensors
        captured_from: 'C:\Users\XU\ComfyUI\models\controlnet\controlnet-openpose-sdxl-1.0.safetensors'
      - kind: image
        directory: ipadapter
        file: ip-adapter-plus_sdxl_vit-h.safetensors
        family: IPAdapter Plus SDXL ViT-H
        bytes: 847517512
        sha256: 3F5062B8400C94B7159665B21BA5C62ACDCD7682262743D7F2AEFEDEF00E6581
        source: https://huggingface.co/h94/IP-Adapter/resolve/main/sdxl_models/ip-adapter-plus_sdxl_vit-h.safetensors
        captured_from: 'C:\Users\XU\ComfyUI\models\ipadapter\ip-adapter-plus_sdxl_vit-h.safetensors'
      - kind: image
        directory: clip_vision
        file: CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors
        family: CLIP Vision ViT-H for IPAdapter
        bytes: 2528373448
        sha256: 6CA9667DA1CA9E0B0F75E46BB030F7E011F44F86CBFB8D5A36590FCD7507B030
        source: https://huggingface.co/h94/IP-Adapter/resolve/main/models/image_encoder/model.safetensors
        captured_from: 'C:\Users\XU\ComfyUI\models\clip_vision\CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors'
      - kind: image
        directory: background_removal
        file: birefnet.safetensors
        family: BiRefNet background removal
        bytes: 444473596
        sha256: 9AB37426BF4DE0567AF6B5D21B16151357149139362E6E8992021B8CE356A154
        source: https://huggingface.co/Comfy-Org/BiRefNet/resolve/main/background_removal/birefnet.safetensors
        captured_from: 'C:\Users\XU\ComfyUI\models\background_removal\birefnet.safetensors'
      - kind: image
        directory: upscale_models
        file: 4x-UltraSharp.pth
        family: 4x-UltraSharp upscaler
        bytes: 66961958
        sha256: A5812231FC936B42AF08A5EDBA784195495D303D5B3248C24489EF0C4021FE01
        source: https://huggingface.co/lokCX/4x-Ultrasharp/resolve/main/4x-UltraSharp.pth
        captured_from: 'C:\Users\XU\ComfyUI\models\upscale_models\4x-UltraSharp.pth'
      - kind: video
        directory: diffusion_models
        file: wan2.2_ti2v_5B_fp16.safetensors
        family: Wan 2.2 TI2V 5B
        bytes: 9999658848
        sha256: 456F901338BD9EADBDED3828B819109A9B68E8A525CA5CF8D0049A69FCFECA1E
        source: https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/tree/main/split_files/diffusion_models
        captured_from: 'C:\Users\XU\ComfyUI\models\diffusion_models\wan2.2_ti2v_5B_fp16.safetensors'
      - kind: video
        directory: diffusion_models
        file: wan2.2_fun_control_5B_bf16.safetensors
        family: Wan 2.2 Fun Control 5B
        bytes: 10003303280
        sha256: ACE4718A7C87EE3E5606A68AB79142C4395E81AECE76B8120BC886F0FBBE1D16
        source: https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/tree/main/split_files/diffusion_models
        captured_from: 'C:\Users\XU\ComfyUI\models\diffusion_models\wan2.2_fun_control_5B_bf16.safetensors'
      - kind: video
        directory: text_encoders
        file: umt5_xxl_fp8_e4m3fn_scaled.safetensors
        family: Wan shared text encoder
        bytes: 6735906897
        sha256: C3355D30191F1F066B26D93FBA017AE9809DCE6C627DDA5F6A66EAA651204F68
        source: https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/tree/main/split_files/text_encoders
        captured_from: 'C:\Users\XU\ComfyUI\models\text_encoders\umt5_xxl_fp8_e4m3fn_scaled.safetensors'
      - kind: video
        directory: vae
        file: wan2.2_vae.safetensors
        family: Wan 2.2 VAE
        bytes: 1409400960
        sha256: E40321BD36B9709991DAE2530EB4AC303DD168276980D3E9BC4B6E2B75FED156
        source: https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/tree/main/split_files/vae
        captured_from: 'C:\Users\XU\ComfyUI\models\vae\wan2.2_vae.safetensors'
      - kind: video
        directory: diffusion_models
        file: minimax_h3_fl2va_pruned_int8_convrot.safetensors
        family: MiniMax H3 FL2VA int8
        bytes: 20970379616
        sha256: E889202C41DAFB67B10D67B97F0D8541508036A6090AF23425A5C2615D03C47A
        source: https://huggingface.co/Comfy-Org/MiniMax-H3/tree/main/diffusion_models
        captured_from: 'C:\Users\XU\ComfyUI\models\diffusion_models\minimax_h3_fl2va_pruned_int8_convrot.safetensors'
      - kind: video
        directory: diffusion_models
        file: minimax_h3_ref2va_pruned_int8_convrot.safetensors
        family: MiniMax H3 Ref2VA int8
        bytes: 20970379616
        sha256: 9255F52B6677845AD238F20DFAAFA94727053694127AB7F255C048F0F9365779
        source: https://huggingface.co/Comfy-Org/MiniMax-H3/tree/main/diffusion_models
        captured_from: 'C:\Users\XU\ComfyUI\models\diffusion_models\minimax_h3_ref2va_pruned_int8_convrot.safetensors'
      - kind: video
        directory: text_encoders
        file: qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors
        family: MiniMax H3 Qwen3VL text encoder
        bytes: 15687142551
        sha256: 35A88D51044231FE332301D7A62AA81E3F2CBA62FEBEB446E2C1E3E0EF76F2C6
        source: https://huggingface.co/Comfy-Org/MiniMax-H3/tree/main/text_encoders
        captured_from: 'C:\Users\XU\ComfyUI\models\text_encoders\qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors'
      - kind: video
        directory: vae
        file: minimax_h3_video_vae_fp16.safetensors
        family: MiniMax H3 video VAE
        bytes: 5207808496
        sha256: 7C1F131492E7EDDACAAC9069A61B81BDD39DE5CC96561E677C5EAB1CDCE5E522
        source: https://huggingface.co/Comfy-Org/MiniMax-H3/tree/main/vae
        captured_from: 'C:\Users\XU\ComfyUI\models\vae\minimax_h3_video_vae_fp16.safetensors'
      - kind: video
        directory: vae
        file: minimax_h3_audio_vae_fp32.safetensors
        family: MiniMax H3 audio VAE
        bytes: 605254808
        sha256: 8E505D95DD1561D47ABD43D4238FD40D9BB1AE9E147ED0A4CBA778D76AE4DB48
        source: https://huggingface.co/Comfy-Org/MiniMax-H3/tree/main/vae
        captured_from: 'C:\Users\XU\ComfyUI\models\vae\minimax_h3_audio_vae_fp32.safetensors'
    smoke_test:
      status: passed
      date: '2026-08-31'
      command: generate.py concept --config C:\Users\XU\tools\comfyui-game-art-tutorial\local_config.json --style realistic --prompt "a stylized game character portrait, painterly lighting, neutral background" --negative "blurry, low quality, distorted anatomy" --width 512 --height 512 --seed 20260840 --output-dir <repo>\output\smoke_20260831
      output: 'C:\Users\XU\.codex\worktrees\d2fb\comfyui-game-art-tutorial\output\smoke_20260831\concept_00052_.png'
      width: 512
      height: 512
      bytes: 383732
    video_smoke_test:
      status: passed
      date: '2026-08-31'
      capability_config: 'C:\Users\XU\ComfyUI\tools\video_capabilities.json'
      node_check: available
      output_policy: no automatic playback; all outputs inspected with PyAV
      contract_sidecar_smoke:
        status: passed
        date: '2026-08-31'
        command: >-
          generate.py img2video --config C:\Users\XU\tools\comfyui-game-art-tutorial\local_config.json
          --video-config C:\Users\XU\ComfyUI\tools\video_capabilities.json
          --comfy-url http://127.0.0.1:8188 --backend h3 --timeout 1800
          --image C:\Users\XU\.codex\worktrees\5bdf\comfyui-game-art-tutorial\第一張測試圖.png
          --prompt "subtle idle motion, cloth and hair move gently, camera locked"
          --negative "blurry, low quality, text, watermark" --duration 2 --seed 20260831
          --shot-id smoke01 --output-dir C:\Users\XU\tools\comfyui-game-art-tutorial\output\smoke_contract_20260831
        output: 'C:\Users\XU\tools\comfyui-game-art-tutorial\output\smoke_contract_20260831\shot_smoke01_img2video_00001_.mp4'
        sidecar: 'C:\Users\XU\tools\comfyui-game-art-tutorial\output\smoke_contract_20260831\shot_smoke01_img2video_00001_.mp4.json'
        prompt_id: '96d7667c-e64b-4933-b2e7-08e9476c211a'
        capability_schema_fingerprint: '35de8f3b2312c3086bfc94939994dc8fb2f32951233dcd3c23019a01a10c9c82'
        seed: 20260831
        contract: {width: 768, height: 768, fps: 24, frames: 56, audio: true}
        actual: {width: 768, height: 768, fps: 24.0, frames: 56, duration_seconds: 2.333333, codec: h264, pixel_format: yuv420p, audio_codec: aac, audio_sample_rate: 32000, audio_channels: 2}
        sidecar_bytes: 2744
        elapsed_seconds: 93.497
      contract_resume_smoke:
        status: passed
        date: '2026-08-31'
        command: same contract_sidecar_smoke command with --resume
        evidence: sidecar and PyAV contract revalidated; no new ComfyUI queue/GPU job submitted
      concat_policy_smoke:
        status: passed
        date: '2026-08-31'
        command: >-
          generate.py video_concat --video C:\Users\XU\tools\comfyui-game-art-tutorial\output\bakeoff_h3_playable.mp4
          --video C:\Users\XU\tools\comfyui-game-art-tutorial\output\bakeoff_wan22.mp4
          --name concat_drop --audio-policy drop --resize-mode strict
          --output-dir C:\Users\XU\tools\comfyui-game-art-tutorial\output\smoke_contract_20260831
        output: 'C:\Users\XU\tools\comfyui-game-art-tutorial\output\smoke_contract_20260831\concat_drop.mp4'
        sidecar: 'C:\Users\XU\tools\comfyui-game-art-tutorial\output\smoke_contract_20260831\concat_drop.mp4.json'
        actual: {width: 832, height: 480, fps: 24.0, frames: 105, duration_seconds: 4.375, audio: false}
        negative_cases: mixed_audio_default_rejected; mismatched_dimensions_default_rejected; transactional_frame_failure_preserved_previous_set
      tasks:
        - task: img2video
          backend: h3
          output: 'C:\Users\XU\.codex\worktrees\d2fb\comfyui-game-art-tutorial\output\smoke_20260831\img2video_00009_.mp4'
          width: 512
          height: 512
          fps: 24.0
          frames: 56
          duration_seconds: 2.333333
          audio: true
          elapsed_seconds: 47.559
          bytes: 138470
        - task: fx_loop
          backend: h3
          output: 'C:\Users\XU\.codex\worktrees\d2fb\comfyui-game-art-tutorial\output\smoke_20260831\fx_loop_00001_.mp4'
          width: 512
          height: 512
          fps: 24.0
          frames: 56
          duration_seconds: 2.333333
          audio: true
          elapsed_seconds: 43.488
          bytes: 220529
        - task: transition
          backend: h3
          output: 'C:\Users\XU\.codex\worktrees\d2fb\comfyui-game-art-tutorial\output\smoke_20260831\transition_00001_.mp4'
          width: 512
          height: 768
          fps: 24.0
          frames: 56
          duration_seconds: 2.333333
          audio: true
          elapsed_seconds: 63.733
          bytes: 370387
        - task: clip_extend
          backend: h3
          output: 'C:\Users\XU\.codex\worktrees\d2fb\comfyui-game-art-tutorial\output\smoke_20260831\clip_extend_00015_.mp4'
          width: 512
          height: 768
          fps: 24.0
          frames: 56
          duration_seconds: 2.333333
          audio: true
          elapsed_seconds: 55.830
          bytes: 297035
        - task: character_video
          backend: h3
          output: 'C:\Users\XU\.codex\worktrees\d2fb\comfyui-game-art-tutorial\output\smoke_20260831\character_video_00005_.mp4'
          width: 512
          height: 768
          fps: 24.0
          frames: 56
          duration_seconds: 2.333333
          audio: true
          elapsed_seconds: 58.588
          bytes: 483837
        - task: camera_move
          backend: h3
          output: 'C:\Users\XU\.codex\worktrees\d2fb\comfyui-game-art-tutorial\output\smoke_20260831\camera_move_00002_.mp4'
          width: 512
          height: 512
          fps: 24.0
          frames: 56
          duration_seconds: 2.333333
          audio: true
          elapsed_seconds: 45.589
          bytes: 259178
        - task: pose_drive
          backend: h3
          output: 'C:\Users\XU\.codex\worktrees\d2fb\comfyui-game-art-tutorial\output\smoke_20260831\pose_drive_00007_.mp4'
          width: 512
          height: 768
          fps: 24.0
          frames: 56
          duration_seconds: 2.333333
          audio: true
          elapsed_seconds: 194.415
          bytes: 316487
        - task: video_concat
          backend: local
          output: 'C:\Users\XU\.codex\worktrees\d2fb\comfyui-game-art-tutorial\output\smoke_20260831\video_concat_smoke.mp4'
          width: 512
          height: 512
          fps: 24.0
          frames: 112
          duration_seconds: 4.666667
          audio: true
          elapsed_seconds: 0.680
          bytes: 333521
        - task: img2video
          backend: wan
          output: 'C:\Users\XU\.codex\worktrees\d2fb\comfyui-game-art-tutorial\output\smoke_20260831\img2video_00010_.mp4'
          width: 512
          height: 512
          fps: 24.0
          frames: 49
          duration_seconds: 2.041667
          audio: false
          elapsed_seconds: 28.769
          bytes: 158203
        - task: pose_drive
          backend: wan
          output: 'C:\Users\XU\.codex\worktrees\d2fb\comfyui-game-art-tutorial\output\smoke_20260831\pose_drive_00008_.mp4'
          width: 512
          height: 768
          fps: 24.0
          frames: 49
          duration_seconds: 2.041667
          audio: false
          elapsed_seconds: 84.960
          bytes: 261119

workflows/ 依 AGENTS.md 規範不進版控；本輪沒有實際手動開發 workflow，因此記錄為 N/A。影片輸出沒有自動播放。

### 版本更新門檻

只有在同一個 manifest 內的 ComfyUI commit、custom node commits、Python/PyTorch/Pillow/PyAV 版本與使用到的模型 SHA-256（包含影片 diffusion_models、text_encoders、vae）都已擷取，並且至少完成一次最小產圖與影片 smoke test、輸出檔驗收後，才把 capture_status 改成 verified。只更新其中一項時，保留 pending_on_installed_machine，避免把未驗證的混合環境誤當成可重現版本。

本筆 XU-Nano-PC capture 已滿足上述門檻；其他機器仍應各自重新偵測、計算 hash 與 smoke test，不可直接套用本機絕對路徑或假設 backend。
