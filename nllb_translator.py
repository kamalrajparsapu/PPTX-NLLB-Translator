import re
from dataclasses import dataclass
from typing import Optional, List, Dict

import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM


# Translate anything that contains at least one letter (Latin or Devanagari)
LETTER_RE = re.compile(r"[A-Za-z\u0900-\u097F]")


def normalize_text(s: str) -> str:
    if s is None:
        return ""
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    # keep spaces stable
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip()


def should_translate(s: str) -> bool:
    if s is None:
        return False
    s = s.strip()
    if not s:
        return False
    return bool(LETTER_RE.search(s))


# Extend this mapping as needed
NLLB_MAP: Dict[str, str] = {
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
class NLLBLoaded:
    tokenizer: any
    model: any
    device: str
    dtype: torch.dtype


class NLLBTranslator:
    """
    NLLB-200 Distilled 600M ONLY.
    Downloads model at runtime (first time) via Hugging Face and caches locally.
    """
    MODEL_NAME = "facebook/nllb-200-distilled-600M"

    def __init__(self, device: Optional[str] = None, use_fp16_if_cuda: bool = True):
        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = device
        self.dtype = torch.float16 if (device == "cuda" and use_fp16_if_cuda) else torch.float32
        self._loaded: Optional[NLLBLoaded] = None

    def _ensure_loaded(self):
        if self._loaded is not None:
            return

        # Critical: use_fast=False to avoid tokenizer backend attribute issues
        tok = AutoTokenizer.from_pretrained(self.MODEL_NAME, use_fast=False)

        # Use dtype (not torch_dtype) to avoid deprecation warnings
        mdl = AutoModelForSeq2SeqLM.from_pretrained(self.MODEL_NAME, dtype=self.dtype)
        mdl.to(self.device)
        mdl.eval()

        self._loaded = NLLBLoaded(tokenizer=tok, model=mdl, device=self.device, dtype=self.dtype)
        print(f"✅ Loaded NLLB model: {self.MODEL_NAME} on {self.device} ({self.dtype})")

    def _lang_token_id(self, tok, lang_code: str) -> int:
        """
        Robust language token -> id conversion (works across tokenizer versions).
        """
        lang_id = tok.convert_tokens_to_ids(lang_code)
        if lang_id is None or lang_id == tok.unk_token_id:
            raise ValueError(
                f"Cannot map language code '{lang_code}' to a token id. "
                f"Add correct code to NLLB_MAP or verify tokenizer vocab."
            )
        return lang_id

    @torch.inference_mode()
    def translate_batch(
        self,
        texts: List[str],
        src_lang: str,
        tgt_lang: str,
        max_new_tokens: int = 128,
        num_beams: int = 4,
    ) -> List[str]:
        self._ensure_loaded()

        if src_lang not in NLLB_MAP or tgt_lang not in NLLB_MAP:
            raise ValueError(
                f"NLLB mapping missing for src='{src_lang}' or tgt='{tgt_lang}'. "
                f"Add to NLLB_MAP in nllb_translator.py"
            )

        tok = self._loaded.tokenizer
        mdl = self._loaded.model

        # Maintain alignment with input
        out: List[Optional[str]] = [None] * len(texts)
        translate_idxs: List[int] = []
        batch_texts: List[str] = []

        for i, t in enumerate(texts):
            if should_translate(t):
                translate_idxs.append(i)
                batch_texts.append(normalize_text(t))
            else:
                out[i] = t

        if not batch_texts:
            return [x if x is not None else "" for x in out]

        src_code = NLLB_MAP[src_lang]
        tgt_code = NLLB_MAP[tgt_lang]

        tok.src_lang = src_code
        forced_bos = self._lang_token_id(tok, tgt_code)

        inputs = tok(batch_texts, return_tensors="pt", padding=True, truncation=True).to(self.device)

        generated = mdl.generate(
            **inputs,
            forced_bos_token_id=forced_bos,
            max_new_tokens=max_new_tokens,
            num_beams=num_beams,
        )

        decoded = tok.batch_decode(generated, skip_special_tokens=True)

        for idx, tr in zip(translate_idxs, decoded):
            out[idx] = tr

        return [x if x is not None else "" for x in out]