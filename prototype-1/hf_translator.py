import re
from dataclasses import dataclass
from typing import Optional, List, Tuple

import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM


# ----------------------------
# Helpers
# ----------------------------
def normalize_text(s: str) -> str:
    if s is None:
        return ""
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip()

def should_translate(s: str) -> bool:
    s2 = normalize_text(s)
    if not s2:
        return False
    # skip symbols/numbers only
    if re.fullmatch(r"[\W\d_]+", s2, flags=re.UNICODE):
        return False
    return True


# ----------------------------
# NLLB language code mapping
# NLLB uses codes like: eng_Latn, hin_Deva, tel_Telu, tam_Taml ...
# Extend this dict for your needs.
# ----------------------------
NLLB_MAP = {
    "en": "eng_Latn",
    "hi": "hin_Deva",
    "te": "tel_Telu",
    "ta": "tam_Taml",
    "kn": "kan_Knda",
    "ml": "mal_Mlym",
    "mr": "mar_Deva",
    "bn": "ben_Beng",
    "gu": "guj_Gujr",
    "pa": "pan_Guru",
    "ur": "urd_Arab",
    "ar": "arb_Arab",
    "fr": "fra_Latn",
    "de": "deu_Latn",
    "es": "spa_Latn",
    "it": "ita_Latn",
    "pt": "por_Latn",
    "ru": "rus_Cyrl",
    "ja": "jpn_Jpan",
    "ko": "kor_Hang",
    "zh": "zho_Hans",
}

@dataclass
class LoadedModel:
    name: str
    tokenizer: any
    model: any
    kind: str  # "marian" or "nllb"


class HFTranslator:
    """
    Best-effort open-source translator:
    1) Tries MarianMT for speed (Helsinki-NLP/opus-mt-<src>-<tgt>)
    2) Falls back to NLLB-200 distilled for coverage & quality
    """
    def __init__(self, device: Optional[str] = None):
        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = device
        self._loaded: Optional[LoadedModel] = None

    def _load_marian(self, src: str, tgt: str) -> LoadedModel:
        model_name = f"Helsinki-NLP/opus-mt-{src}-{tgt}"
        tok = AutoTokenizer.from_pretrained(model_name)
        mdl = AutoModelForSeq2SeqLM.from_pretrained(model_name).to(self.device)
        mdl.eval()
        return LoadedModel(name=model_name, tokenizer=tok, model=mdl, kind="marian")

    def _load_nllb(self) -> LoadedModel:
        model_name = "facebook/nllb-200-distilled-600M"
        tok = AutoTokenizer.from_pretrained(model_name)
        mdl = AutoModelForSeq2SeqLM.from_pretrained(model_name).to(self.device)
        mdl.eval()
        return LoadedModel(name=model_name, tokenizer=tok, model=mdl, kind="nllb")

    def load(self, src_lang: str, tgt_lang: str):
        """
        Auto-download & load the best model for the language pair.
        """
        # Try Marian first for speed
        try:
            self._loaded = self._load_marian(src_lang, tgt_lang)
            print(f"✅ Loaded MarianMT model: {self._loaded.name}")
            return
        except Exception as e:
            print(f"⚠️ Marian model not available for {src_lang}->{tgt_lang}. Falling back to NLLB.")
            self._loaded = self._load_nllb()
            print(f"✅ Loaded NLLB model: {self._loaded.name}")

    @torch.inference_mode()
    def translate_batch(self, texts: List[str], src_lang: str, tgt_lang: str,
                        max_new_tokens: int = 256) -> List[str]:
        if self._loaded is None:
            self.load(src_lang, tgt_lang)

        # keep alignment
        out = []
        for t in texts:
            if not should_translate(t):
                out.append(t)
            else:
                out.append(None)

        # indices that need translation
        idxs = [i for i, v in enumerate(out) if v is None]
        if not idxs:
            return out

        batch = [normalize_text(texts[i]) for i in idxs]

        tok = self._loaded.tokenizer
        mdl = self._loaded.model

        if self._loaded.kind == "nllb":
            # NLLB requires special lang codes
            if src_lang not in NLLB_MAP or tgt_lang not in NLLB_MAP:
                raise ValueError(
                    f"NLLB mapping missing for src={src_lang} or tgt={tgt_lang}. "
                    f"Add it to NLLB_MAP."
                )
            src_code = NLLB_MAP[src_lang]
            tgt_code = NLLB_MAP[tgt_lang]
            tok.src_lang = src_code
            forced_bos = tok.lang_code_to_id[tgt_code]

            inputs = tok(batch, return_tensors="pt", padding=True, truncation=True).to(self.device)
            gen = mdl.generate(
                **inputs,
                forced_bos_token_id=forced_bos,
                max_new_tokens=max_new_tokens,
                num_beams=4
            )
            decoded = tok.batch_decode(gen, skip_special_tokens=True)

        else:
            # MarianMT
            inputs = tok(batch, return_tensors="pt", padding=True, truncation=True).to(self.device)
            gen = mdl.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                num_beams=4
            )
            decoded = tok.batch_decode(gen, skip_special_tokens=True)

        for i, tr in zip(idxs, decoded):
            out[i] = tr

        return out
