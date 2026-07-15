"""UIClip design-quality scorer (Wu et al., UIST 2024) — human-aligned UI aesthetics.

Model: biglab/uiclip_jitteredwebsites-2-224-paraphrased_webpairs_humanpairs (CLIP ViT-B/32,
fine-tuned on 2.3M UIs + pro-designer human ratings). Score = P(well-designed) via
softmax of image vs {"well-designed", "poor design"} text prompts. Range (0,1), higher=better,
MONOTONE (a valid maximization objective, unlike hand-crafted inverted-U metrics).

Tall full-page screenshots are handled with a vertical sliding window (mean-pooled),
as recommended by the paper.
"""
from __future__ import annotations
import os, threading
import torch
from PIL import Image

_MODEL = "biglab/uiclip_jitteredwebsites-2-224-paraphrased_webpairs_humanpairs"
_PROC = "openai/clip-vit-base-patch32"
_LOGIT_SCALE = 100.0
_lock = threading.Lock()
_state = {}


def _init(device="cpu"):
    if _state:
        return
    torch.backends.cudnn.enabled = False   # cuDNN 9.19+driver535 crashes conv (see pyfix)
    from transformers import CLIPModel, CLIPProcessor
    os.environ.setdefault("XDG_CACHE_HOME", "/data_seoul/sunghyun/.cache")
    m = CLIPModel.from_pretrained(_MODEL).to(device).eval()
    p = CLIPProcessor.from_pretrained(_PROC)
    _state["m"], _state["p"], _state["dev"] = m, p, device


def _windows(img: Image.Image, size=224):
    """Resize to width=size, tile vertically into size x size windows (overlap for short pages)."""
    img = img.convert("RGB")
    w, h = img.size
    nw = img.resize((size, max(size, int(h * size / w))))
    H = nw.size[1]
    ys = list(range(0, max(1, H - size + 1), size))
    if not ys or ys[-1] != H - size:
        ys.append(max(0, H - size))
    return [nw.crop((0, y, size, y + size)) for y in ys[:6]]   # cap 6 windows


@torch.no_grad()
def score(image_path: str, description: str = "", device="cpu") -> float:
    """Return UIClip design-quality P(well-designed) in [0,1]."""
    _init(device)
    m, p, dev = _state["m"], _state["p"], _state["dev"]
    try:
        wins = _windows(Image.open(image_path))
    except Exception:
        return 0.0
    desc = (" " + description.strip()) if description else ""
    texts = [f"ui screenshot. well-designed.{desc}", f"ui screenshot. poor design.{desc}"]
    with _lock:
        pix = p(images=wins, return_tensors="pt").to(dev)
        img_emb = m.get_image_features(**pix)
        img_emb = torch.nn.functional.normalize(img_emb, dim=-1).mean(0, keepdim=True)
        img_emb = torch.nn.functional.normalize(img_emb, dim=-1)
        tok = p(text=texts, return_tensors="pt", padding=True).to(dev)
        txt_emb = torch.nn.functional.normalize(m.get_text_features(**tok), dim=-1)
        s = (_LOGIT_SCALE * img_emb @ txt_emb.T).softmax(dim=-1)
    return float(s[0, 0].item())


if __name__ == "__main__":
    import sys
    print(round(score(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else ""), 4))
