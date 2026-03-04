# PPTX‑NLLB‑Translator (Format‑Preserving PowerPoint Translator)

Translate PowerPoint (`.pptx`) files into your target language using **Meta NLLB‑200 Distilled 600M** (open‑source) while keeping the same slide layout and formatting as much as possible.

This project focuses on translating text inside **PowerPoint shapes, tables, and speaker notes** without rebuilding slides—so **fonts, colors, and alignment** remain largely unchanged.

---

## ✨ Key Features

- ✅ **NLLB‑200 Distilled 600M only** (`facebook/nllb-200-distilled-600M`)
- ✅ **Runtime model download + caching** (downloads on first run, then reuses local cache)
- ✅ **Formatting‑friendly translation**
  - **Run mode:** best formatting preservation (updates text runs)
  - **Paragraph mode:** improved completeness for split text (joins runs per paragraph)

- ✅ Translates:
  - **Text boxes / titles / placeholders**
  - **Tables** (cell text)
  - **Speaker notes** (optional)

- ✅ **Batch translation + caching** for speed and cost‑free repeated strings
- ✅ **Do‑not‑translate protection** for acronyms/terms (configurable)
- ✅ Optional **Hindi roman‑script transliteration** *(only used when target is `hi`)*

---

## 📦 Repo Structure

```text
Document_translation/
├─ translate_pptx_nllb.py     # Main CLI entrypoint
├─ nllb_translator.py         # NLLB model loader + batch translation
├─ pptx_utils.py              # PPTX text extraction utilities
├─ postprocess_hi.py          # Optional Hindi transliteration & glossary
├─ requirements.txt
└─ .gitignore
```

---

## 🧰 Requirements

- Python **3.9+** recommended
- Works on **CPU** (GPU optional but faster)

---

## ⚙️ Installation

### 1) Create & activate a virtual environment (recommended)

**Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**macOS/Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2) Install dependencies
```bash
pip install -r requirements.txt
```

> If you want GPU acceleration, install a CUDA-enabled PyTorch build matching your CUDA version.

---

## 🚀 Usage

### Basic translation (best formatting preservation)
**English → Spanish**
```powershell
python translate_pptx_nllb.py --input Kamal_deck.pptx --output output_es.pptx --src en --tgt es --mode runs
```

### Better completeness (handles text split across multiple runs)
Use **paragraphs** mode when PowerPoint splits words like `Speech-` + `to-` + `Text`.
```powershell
python translate_pptx_nllb.py --input Kamal_deck.pptx --output output_es.pptx --src en --tgt es --mode paragraphs
```

### Translate speaker notes (default) / disable notes translation
Disable notes:
```powershell
python translate_pptx_nllb.py --input Kamal_deck.pptx --output output_es.pptx --src en --tgt es --mode runs --no-notes
```

---

## 🧾 CLI Options

```text
--input                 Input .pptx file path (required)
--output                Output .pptx file path (required)
--src                   Source language (e.g., en, hi, te) (required)
--tgt                   Target language (e.g., es, fr, de) (required)
--mode runs|paragraphs   runs = best formatting, paragraphs = better completeness
--batch-size            Batch size for translation (default: 24)
--max-new-tokens        Max tokens generated per segment (default: 128)
--beams                 Beam search width (default: 4)
--no-notes              Disable speaker notes translation
--transliterate-roman   (Hindi only) Convert leftover roman words to Hindi-script
--keep-acronyms         (Hindi only) Keep ALL-CAPS acronyms unchanged during transliteration
```

---

## 🌍 Language Codes

The CLI uses common language codes like:

- `en` (English)
- `es` (Spanish)
- `hi` (Hindi)
- `fr` (French)
- `de` (German)

Internally, NLLB uses codes like `eng_Latn`, `spa_Latn`, `hin_Deva`.

This mapping is defined in `nllb_translator.py` under `NLLB_MAP`.

### Add a missing language
If your language isn’t present, add it to `NLLB_MAP`, for example:

```python
NLLB_MAP["nl"] = "nld_Latn"  # Dutch example
```

---

## ⚡ Performance Tips

### CPU

Use smaller batches:
```powershell
--batch-size 8
```

Reduce generation length:
```powershell
--max-new-tokens 64
```

### GPU (recommended if available)

Use bigger batches:
```powershell
--batch-size 64
```

> The code automatically uses `cuda` and FP16 when available.

---

## 📥 Model Download & Cache

The model downloads automatically on first run from Hugging Face and is cached locally:

- **Windows:** `C:\Users\<YOU>\.cache\huggingface\hub`
- **Linux/macOS:** `~/.cache/huggingface/hub`

### Set a custom cache directory (optional)

**Windows (PowerShell):**
```powershell
setx HF_HOME "D:\\hf_cache"
```

> Restart the terminal after setting this.

### Optional: Hugging Face token
You may see a warning about unauthenticated requests. It’s safe to ignore, but setting a token improves rate limits:
```powershell
setx HF_TOKEN "your_huggingface_token"
```

---

## 🧠 How Formatting Is Preserved

PowerPoint text is stored as:

**TextFrame → Paragraphs → Runs**

Each run can have different font/size/bold/color.

- **Runs mode:** translate and replace only `run.text`, so styling remains.
- **Paragraphs mode:** translate combined paragraph text and write it into the first run (clearing the rest). This improves translation completeness when PowerPoint splits words across runs.

---

## 🧩 Customization

### 1) Do‑Not‑Translate Terms
Update `DEFAULT_DO_NOT_TRANSLATE` in `translate_pptx_nllb.py`:

```python
DEFAULT_DO_NOT_TRANSLATE = {
    "HSBC", "RAG", "LLM", "GenAI", "SIPREC", "API", "Power BI"
}
```

These terms are temporarily replaced with placeholders before translation and restored afterward.

### 2) Glossary (Hindi transliteration module)
If you use transliteration for Hindi, you can force specific outputs by editing `DEFAULT_GLOSSARY_HI`:

```python
DEFAULT_GLOSSARY_HI = {
    "Speech-to-Text": "स्पीच-टू-टेक्स्ट",
}
```

---

## ✅ Example Commands

### English → Spanish (recommended)
```powershell
python translate_pptx_nllb.py --input Kamal_deck.pptx --output output_es.pptx --src en --tgt es --mode runs
```

### English → French
```powershell
python translate_pptx_nllb.py --input Kamal_deck.pptx --output output_fr.pptx --src en --tgt fr --mode runs
```

### Hindi → Spanish
```powershell
python translate_pptx_nllb.py --input Kamal_deck.pptx --output output_es.pptx --src hi --tgt es --mode runs
```

---

## ⚠️ Known Limitations

Some PowerPoint elements may not be accessible via `python-pptx`, depending on how the deck was authored:

- SmartArt text (often not exposed)
- Text embedded inside images (requires OCR to translate)
- Some chart labels or embedded objects

> If you need OCR support (open‑source), it can be added using Tesseract + overlay text boxes.

---

## 🛠️ Troubleshooting

### 1) `AttributeError: TokenizersBackend has no attribute lang_code_to_id`
This project avoids that issue by:

- forcing `use_fast=False`
- using `convert_tokens_to_ids()` for language token IDs

If you still face tokenizer issues, upgrade:
```bash
pip install -U transformers tokenizers sentencepiece accelerate
```

### 2) Output contains untranslated acronyms/brand names
That can be expected—models often preserve them.

- Add them to `DEFAULT_DO_NOT_TRANSLATE` if you want them unchanged, or
- remove from the list if you want the model to attempt translation.

### 3) Slow on CPU
Try:
```powershell
--batch-size 8 --max-new-tokens 64
```

---

## 🗺️ Roadmap (Optional Enhancements)

- [ ] OCR pipeline for images (open‑source)
- [ ] Chart text extraction where possible
- [ ] Config file support (`config.yaml`) for glossary/DNT/language maps
- [ ] Streamlit UI for drag‑and‑drop translation
- [ ] Unit tests for extraction + translation steps

---

## 🤝 Contributing

Contributions are welcome!

1. Fork the repo
2. Create a feature branch
3. Open a PR with a clear description and sample PPTX (if possible)

---

## 📄 License

Choose one based on your preference:

- **MIT** (simple and permissive)
- **Apache‑2.0** (also permissive, includes patent grant)

If you tell me which one you want, I can generate the `LICENSE` file too.

---

## 🙏 Acknowledgements

- Meta NLLB‑200 model (`facebook/nllb-200-distilled-600M`)
- Hugging Face Transformers ecosystem
- `python-pptx` for PPTX manipulation
