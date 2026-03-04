import argparse
from pptx import Presentation
from tqdm import tqdm

from hf_translator import HFTranslator, should_translate
from pptx_utils import collect_run_targets


def translate_pptx(input_path: str, output_path: str,
                   src_lang: str, tgt_lang: str,
                   batch_size: int = 32, include_notes: bool = True):
    prs = Presentation(input_path)

    run_targets = collect_run_targets(prs, include_notes=include_notes)
    texts = [t for _, t in run_targets]

    print(f"Found {len(texts)} text-runs to translate.")

    translator = HFTranslator()  # auto picks cuda/cpu

    # Translate in batches for speed
    translated_all = texts[:]  # placeholder
    for i in tqdm(range(0, len(texts), batch_size), desc="Translating"):
        chunk = texts[i:i+batch_size]
        translated_chunk = translator.translate_batch(chunk, src_lang=src_lang, tgt_lang=tgt_lang)
        translated_all[i:i+batch_size] = translated_chunk

    # Write back (preserve format)
    for (run, _orig), tr in zip(run_targets, translated_all):
        if should_translate(_orig):
            run.text = tr

    prs.save(output_path)
    print(f"✅ Saved: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--src", required=True, help="e.g. en, hi, te")
    parser.add_argument("--tgt", required=True, help="e.g. hi, en, te")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--no-notes", action="store_true", help="Disable speaker notes translation")
    args = parser.parse_args()

    translate_pptx(
        input_path=args.input,
        output_path=args.output,
        src_lang=args.src,
        tgt_lang=args.tgt,
        batch_size=args.batch_size,
        include_notes=not args.no_notes
    )