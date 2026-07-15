# Disable cuDNN: cuDNN 9.19 + driver 535 crashes on conv3d (Qwen2.5-VL vision tower).
# cuDNN is only used for conv layers; LLM attention (FlashAttention) is unaffected.
try:
    import torch
    torch.backends.cudnn.enabled = False
except Exception:
    pass
