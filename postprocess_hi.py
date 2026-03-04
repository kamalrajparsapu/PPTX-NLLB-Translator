import re
from typing import Dict, Optional
from indic_transliteration import sanscript
from indic_transliteration.sanscript import transliterate

# Roman tokens (words) including hyphens, e.g., Speech-to-Text, Coforge, GenAI
ROMAN_RE = re.compile(r"[A-Za-z][A-Za-z0-9\-]*")


def apply_glossary(text: str, glossary: Optional[Dict[str, str]] = None) -> str:
    """
    Replace fixed terms first (case-sensitive).
    Example glossary: {"Speech-to-Text": "स्पीच-टू-टेक्स्ट"}
    """
    if not glossary:
        return text
    for k, v in glossary.items():
        text = text.replace(k, v)
    return text


def transliterate_roman_to_hindi(
    text: str,
    keep_all_caps_acronyms: bool = False,
    glossary: Optional[Dict[str, str]] = None
) -> str:
    """
    Convert remaining Roman words into Devanagari script (approx sound-like).
    Set keep_all_caps_acronyms=False to also convert AI/RAG/LLM style tokens.
    """
    text = apply_glossary(text, glossary)

    def _conv(m: re.Match) -> str:
        w = m.group(0)

        # Optionally keep acronyms unchanged
        if keep_all_caps_acronyms and w.isupper() and len(w) <= 8:
            return w

        # Transliterate using ITRANS->DEVANAGARI (approx for English tokens)
        try:
            return transliterate(w, sanscript.ITRANS, sanscript.DEVANAGARI)
        except Exception:
            return w

    return ROMAN_RE.sub(_conv, text)