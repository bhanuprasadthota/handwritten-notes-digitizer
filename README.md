# Handwritten Notes Digitizer

Convert scanned handwritten notes into structured, formatted PDFs using Google Gemini AI Vision.

Built as a Capstone Project for the **Google GenAI Intensive 2025**, this tool takes photos of handwritten lecture notes and produces a clean, enriched, readable PDF — with proper headings, corrected grammar, inline diagram descriptions, and optional LaTeX-quality math rendering.

---

## How It Works

```
Scanned images → Gemini Vision (text extraction + diagram detection)
              → Gemini (reorder, enrich, structure)
              → Markdown → PDF (WeasyPrint)
              → LaTeX → PDF (pdflatex, optional)
```

1. **Text extraction** — Gemini reads each handwritten page and corrects grammar/spelling
2. **Diagram detection** — Gemini identifies and describes hand-drawn sketches on each page
3. **Enrichment** — All pages are sent to Gemini together for logical reordering and cohesion
4. **PDF generation** — Rendered via WeasyPrint (always) or pdflatex (optional, for math-heavy notes)

Progress is checkpointed after each page — if the run is interrupted by rate limits, it resumes where it left off.

---

## Features

- Multimodal OCR using Gemini Vision (handwriting → clean text)
- Diagram detection and inline description in the final document
- Natural page ordering (page2 before page10, not lexicographic)
- Per-page checkpoint system — safe to interrupt and resume
- WeasyPrint PDF with styled output (always available)
- pdflatex PDF for properly rendered math equations (optional)
- CLI interface with configurable input/output paths

---

## Installation

```bash
git clone https://github.com/bhanuprasadthota/handwritten-notes-digitizer.git
cd handwritten-notes-digitizer
pip install -r requirements.txt
```

> For LaTeX PDF support, also install TeX Live:
> - macOS: `brew install --cask mactex`
> - Ubuntu: `sudo apt install texlive-full`
> - Windows: [MiKTeX](https://miktex.org/)

---

## Setup

```bash
cp .env.example .env
# Edit .env and add your Gemini API key
# Get one free at: https://aistudio.google.com/app/apikey
```

---

## Usage

```bash
# Basic — generates notes.md and notes.pdf in ./output
python digitize.py --input ./my_notes_images --output ./output

# With LaTeX PDF (requires pdflatex installed)
python digitize.py --input ./my_notes_images --output ./output --latex

# Resume an interrupted run using saved checkpoint
python digitize.py --input ./my_notes_images --output ./output --checkpoint ./checkpoint.json
```

### Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--input` | required | Directory containing scanned note images (JPG/PNG) |
| `--output` | `./output` | Directory for generated files |
| `--checkpoint` | `checkpoint.json` | File for saving/resuming progress |
| `--latex` | off | Also generate a LaTeX-compiled PDF |

### Output files

| File | Description |
|------|-------------|
| `output/notes.md` | Structured Markdown of your notes |
| `output/notes.pdf` | Styled PDF via WeasyPrint |
| `output/notes.tex` | LaTeX source (with `--latex`) |
| `output/notes_latex.pdf` | LaTeX-compiled PDF (with `--latex` + pdflatex) |
| `checkpoint.json` | Per-page progress cache |

---

## Tech Stack

| Tool | Purpose |
|------|---------|
| Python 3.8+ | Core language |
| Google Gemini 2.0 Flash | Vision OCR, diagram detection, enrichment |
| Pillow | Image loading and preprocessing |
| WeasyPrint | Markdown → styled PDF rendering |
| markdown2 | Markdown → HTML conversion |
| pdflatex (optional) | LaTeX → high-quality math PDF |
| python-dotenv | API key management |

---

## Kaggle Notebook

The original Kaggle notebook (with all bugs fixed) is included at [`notebook.ipynb`](notebook.ipynb).

Fixes applied to the notebook vs. the original:
- Updated model from `gemini-1.5-pro` → `gemini-2.0-flash`
- Fixed natural sort (page2 now correctly comes before page10)
- Fixed truncated `Markdown(res` → `Markdown(response.text)` syntax error
- Separated `response` variable reuse into `response` and `markdown_response`
- Diagram descriptions are now injected into the final enrichment prompt
- Added per-page checkpoint system to survive rate-limit interruptions

---

## Team

- **Bhanu Prasad Thota** — bhanuprasadt27@gmail.com
- **Parvash Choudhary Talluri** — talluriparvashchoudhary2001@gmail.com

*Capstone Project — Google GenAI Intensive 2025*

---

## License

MIT License — see [LICENSE](LICENSE) for details.
