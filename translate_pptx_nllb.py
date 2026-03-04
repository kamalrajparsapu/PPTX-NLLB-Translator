import argparse
from typing import Dict, List, Tuple, Optional

from pptx import Presentation
from tqdm import tqdm

from nllb_translator import NLLBTranslator, should_translate
from pptx_utils import collect_run_targets, collect_paragraph_targets
from postprocess_hi import transliterate_roman_to_hindi


# ----------------------------
# Customization
# ----------------------------
DEFAULT_DO_NOT_TRANSLATE = {
    "HSBC", "RAG", "LLM", "GenAI", "SIPREC", "PJSUA", "DTCC", "API", "Power BI", "LangChain"
}

# Glossary can force specific translations/transliterations
DEFAULT_GLOSSARY_HI: Dict[str, str] = {
    "Speech-to-Text": "स्पीच-टू-टेक्स्ट",
    "Real-time": "रीयल-टाइम",
}


def protect_terms(text: str, terms: set) -> Tuple[str, Dict[str, str]]:
    """
    Replace do-not-translate terms with placeholders before translation.
    Then restore them after translation.
    """
    mapping = {}
    protected = text
    idx = 0
    # Sort by length desc so "Power BI" is protected before "BI"
    for term in sorted(terms, key=len, reverse=True):
        if term and term in protected:
            token = f"__DNT_{idx}__"
            protected = protected.replace(term, token)
            mapping[token] = term
            idx += 1
    return protected, mapping


def restore_terms(text: str, mapping: Dict[str, str]) -> str:
    for token, term in mapping.items():
        text = text.replace(token, term)
    return text


def chunk_list(items: List[str], size: int):
    for i in range(0, len(items), size):
        yield i, items[i:i + size]


def translate_texts_with_cache(
    translator: NLLBTranslator,
    texts: List[str],
    src: str,
    tgt: str,
    batch_size: int,
    max_new_tokens: int,
    num_beams: int,
    do_not_translate_terms: set
) -> List[str]:
    """
    Batch translation with caching + do-not-translate protection.
    """
    cache: Dict[str, str] = {}
    results = [""] * len(texts)

    for start, chunk in tqdm(list(chunk_list(texts, batch_size)), desc="Translating (NLLB)"):
        # Prepare chunk with protection + cache lookup
        to_send = []
        send_indices = []
        restore_maps: Dict[int, Dict[str, str]] = {}

        for j, t in enumerate(chunk):
            global_index = start + j

            if not should_translate(t):
                results[global_index] = t
                continue

            # Cache check (raw input)
            if t in cache:
                results[global_index] = cache[t]
                continue

            protected, mapping = protect_terms(t, do_not_translate_terms)
            to_send.append(protected)
            send_indices.append(global_index)
            restore_maps[global_index] = mapping

        if not to_send:
            continue

        translated = translator.translate_batch(
            to_send, src_lang=src, tgt_lang=tgt,
            max_new_tokens=max_new_tokens, num_beams=num_beams
        )

        for idx, tr in zip(send_indices, translated):
            tr = restore_terms(tr, restore_maps.get(idx, {}))
            results[idx] = tr
            cache[texts[idx]] = tr

    return results


def main():
    parser = argparse.ArgumentParser(description="Translate PPTX using ONLY NLLB-200 Distilled 600M (format-preserving).")
    parser.add_argument("--input", required=True, help="Input .pptx path")
    parser.add_argument("--output", required=True, help="Output .pptx path")
    parser.add_argument("--src", required=True, help="Source language (e.g. en)")
    parser.add_argument("--tgt", required=True, help="Target language (e.g. hi)")
    parser.add_argument("--batch-size", type=int, default=24)
    parser.add_argument("--max-new-tokens", type=int, default=128)
    parser.add_argument("--beams", type=int, default=4)
    parser.add_argument("--no-notes", action="store_true", help="Do not translate speaker notes")
    parser.add_argument("--mode", choices=["runs", "paragraphs"], default="runs",
                        help="runs=best formatting, paragraphs=better completeness for split words")
    parser.add_argument("--transliterate-roman", action="store_true",
                        help="For Hindi target: convert remaining roman words to Hindi-script sound-like text")
    parser.add_argument("--keep-acronyms", action="store_true",
                        help="When transliterating, keep ALL-CAPS acronyms unchanged")
    args = parser.parse_args()

    prs = Presentation(args.input)

    translator = NLLBTranslator()  # auto cpu/cuda

    include_notes = not args.no_notes
    dnt = set(DEFAULT_DO_NOT_TRANSLATE)

    # --------------- MODE A: RUNS (best formatting) ---------------
    if args.mode == "runs":
        run_targets = collect_run_targets(prs, include_notes=include_notes)
        texts = [t for _, t in run_targets]
        print(f"Found {len(texts)} text-runs to translate (mode=runs).")

        translated_all = translate_texts_with_cache(
            translator=translator,
            texts=texts,
            src=args.src,
            tgt=args.tgt,
            batch_size=args.batch_size,
            max_new_tokens=args.max_new_tokens,
            num_beams=args.beams,
            do_not_translate_terms=dnt
        )

        # Optional: transliteration postprocess for Hindi
        if args.transliterate_roman and args.tgt == "hi":
            translated_all = [
                transliterate_roman_to_hindi(
                    t,
                    keep_all_caps_acronyms=args.keep_acronyms,
                    glossary=DEFAULT_GLOSSARY_HI
                )
                for t in translated_all
            ]

        # Write back preserving formatting
        for (run, _orig), tr in zip(run_targets, translated_all):
            run.text = tr

    # --------------- MODE B: PARAGRAPHS (better completeness) ---------------
    else:
        para_targets = collect_paragraph_targets(prs, include_notes=include_notes)
        combined_texts = [combined for _, combined in para_targets]
        print(f"Found {len(combined_texts)} paragraphs to translate (mode=paragraphs).")

        translated_all = translate_texts_with_cache(
            translator=translator,
            texts=combined_texts,
            src=args.src,
            tgt=args.tgt,
            batch_size=args.batch_size,
            max_new_tokens=args.max_new_tokens,
            num_beams=args.beams,
            do_not_translate_terms=dnt
        )

        if args.transliterate_roman and args.tgt == "hi":
            translated_all = [
                transliterate_roman_to_hindi(
                    t,
                    keep_all_caps_acronyms=args.keep_acronyms,
                    glossary=DEFAULT_GLOSSARY_HI
                )
                for t in translated_all
            ]

        # Write back: keep formatting of first run, clear others
        for (runs, _orig), tr in zip(para_targets, translated_all):
            if not runs:
                continue
            runs[0].text = tr
            for r in runs[1:]:
                r.text = ""

    prs.save(args.output)
    print(f"✅ Saved translated PPTX: {args.output}")


if __name__ == "__main__":
    main()