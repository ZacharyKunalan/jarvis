import torch
import numpy as np
import json
from safetensors.torch import load_file
from transformers import WhisperProcessor, WhisperForConditionalGeneration

BASE_MODEL   = "openai/whisper-small"
ADAPTER_PATH = "whisper-jarvis-adapter/whisper-jarvis-adapter"
SAMPLE_RATE  = 16000
DEVICE       = "cuda" if torch.cuda.is_available() else "cpu"

def _apply_lora(model, adapter_path):
    """Manually merge LoRA weights into the base model."""
    weights = load_file(f"{adapter_path}/adapter_model.safetensors")
    config  = json.load(open(f"{adapter_path}/adapter_config.json"))
    alpha   = config["lora_alpha"]
    r       = config["r"]
    scale   = alpha / r

    # Group A and B matrices by layer
    layers = {}
    for key, val in weights.items():
        # key format: base_model.model.X.lora_A.weight or lora_B.weight
        if "lora_A" in key:
            base = key.replace(".lora_A.weight", "")
            layers.setdefault(base, {})["A"] = val
        elif "lora_B" in key:
            base = key.replace(".lora_B.weight", "")
            layers.setdefault(base, {})["B"] = val

    for base_key, mats in layers.items():
        if "A" not in mats or "B" not in mats:
            continue
        # Convert base_key to model parameter path
        param_key = base_key.replace("base_model.model.", "") + ".weight"
        param = model.get_parameter(param_key)
        if param is None:
            continue
        delta = (mats["B"].to(DEVICE) @ mats["A"].to(DEVICE)) * scale
        param.data += delta

    return model

print(f"Loading local Whisper STT on {DEVICE}...")
_processor = WhisperProcessor.from_pretrained(BASE_MODEL)
_model     = WhisperForConditionalGeneration.from_pretrained(BASE_MODEL)
_model     = _model.to(DEVICE)        # move to GPU first
_model     = _apply_lora(_model, ADAPTER_PATH)  # then apply LoRA
_model.eval()
print("Local Whisper STT ready.")


def transcribe(audio: np.ndarray) -> str:
    if audio.dtype == np.int16:
        audio = audio.astype(np.float32) / 32768.0
    if audio.ndim > 1:
        audio = audio.flatten()

    inputs = _processor(audio, sampling_rate=SAMPLE_RATE, return_tensors="pt")
    input_features = inputs.input_features.to(DEVICE)
    attention_mask = torch.ones(input_features.shape[:2], dtype=torch.long, device=DEVICE)

    with torch.no_grad():
        predicted_ids = _model.generate(
            input_features,
            attention_mask=attention_mask,
            language="en",
            task="transcribe",
            forced_decoder_ids=None,
        )

    return _processor.batch_decode(predicted_ids, skip_special_tokens=True)[0].strip()