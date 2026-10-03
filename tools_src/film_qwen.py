"""Qwen3-TTS worker. Run only in a separate qwen-tts environment."""
import argparse
import json
import os
from pathlib import Path
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', required=True)
    args = parser.parse_args()
    request = json.loads(Path(args.request).read_text(encoding='utf-8'))
    model_dir = Path(request['model']).resolve(strict=True)
    config = json.loads((model_dir / 'config.json').read_text(encoding='utf-8'))
    if config.get('tts_model_type') != 'custom_voice':
        raise ValueError('Only the CustomVoice model is supported by this worker')
    if not (model_dir / 'speech_tokenizer/config.json').is_file():
        raise FileNotFoundError('Local speech tokenizer is required')
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    import torch
    import soundfile as sf
    import transformers
    from qwen_tts import Qwen3TTSModel
    if not torch.cuda.is_available():
        raise RuntimeError('This validated worker requires CUDA; no silent CPU fallback')
    torch.manual_seed(request['seed'])
    torch.cuda.reset_peak_memory_stats()
    started = time.monotonic()
    model = Qwen3TTSModel.from_pretrained(str(model_dir), device_map='cuda:0',
                                        dtype=torch.bfloat16, attn_implementation='sdpa',
                                        local_files_only=True)
    with torch.inference_mode():
        wavs, rate = model.generate_custom_voice(
            text=request['text'], language='Chinese', speaker=request['speaker'],
            instruct=request['instruction'], max_new_tokens=1024,
            do_sample=False, subtalker_dosample=False)
    if len(wavs) != 1 or not 0 < len(wavs[0]) / rate <= 90:
        raise ValueError('Expected one speech clip of at most ninety seconds')
    sf.write(request['output'], wavs[0], rate, subtype='PCM_16')
    details = {'engine': 'qwen3', 'language': 'Chinese', 'speaker': request['speaker'],
               'instruction': request['instruction'], 'seed': request['seed'],
               'attention': 'sdpa', 'dtype': 'bfloat16', 'device': torch.cuda.get_device_name(),
               'torch': torch.__version__, 'transformers': transformers.__version__,
               'elapsed_seconds': time.monotonic() - started,
               'peak_allocated_bytes': torch.cuda.max_memory_allocated(),
               'native_sample_rate': rate, 'native_samples': len(wavs[0]),
               'generation': {'do_sample': False, 'subtalker_dosample': False, 'max_new_tokens': 1024}}
    Path(request['report']).write_text(json.dumps(details, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
