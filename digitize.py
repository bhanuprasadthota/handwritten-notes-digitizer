#!/usr/bin/env python3
"""
Handwritten Notes Digitizer
Converts scanned handwritten note images to a structured, formatted PDF.

Usage:
    python digitize.py --input ./notes_images --output ./output
    python digitize.py --input ./notes_images --output ./output --latex
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import google.generativeai as genai
import markdown2
from dotenv import load_dotenv
from PIL import Image
from weasyprint import HTML

load_dotenv()

MODEL_NAME = "gemini-2.0-flash"
MAX_RETRIES = 5
RETRY_WAIT = 45


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def natural_sort_key(filename: str) -> list:
    """Sort filenames with embedded numbers naturally so page2 < page10."""
    return [int(c) if c.isdigit() else c.lower() for c in re.split(r"(\d+)", filename)]


def load_images(image_dir: str) -> list:
    """Return (filename, PIL.Image) pairs sorted in natural order."""
    exts = {".png", ".jpg", ".jpeg"}
    files = [f for f in os.listdir(image_dir) if Path(f).suffix.lower() in exts]
    files.sort(key=natural_sort_key)
    return [(f, Image.open(os.path.join(image_dir, f))) for f in files]


def safe_generate(model, prompt, max_retries: int = MAX_RETRIES, wait_time: int = RETRY_WAIT) -> str:
    """Call Gemini with automatic retry on 429 rate-limit errors."""
    for attempt in range(max_retries):
        try:
            return model.generate_content(prompt).text
        except Exception as exc:
            if "429" in str(exc):
                print(f"  Rate limit hit. Waiting {wait_time}s... ({attempt + 1}/{max_retries})")
                time.sleep(wait_time)
            else:
                print(f"  Gemini error: {exc}")
                return ""
    print("  Max retries exceeded.")
    return ""


# ---------------------------------------------------------------------------
# Checkpoint
# ---------------------------------------------------------------------------

def load_checkpoint(path: str) -> dict:
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}


def save_checkpoint(path: str, data: dict) -> None:
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


# ---------------------------------------------------------------------------
# Pipeline steps
# ---------------------------------------------------------------------------

def extract_pages(model, images: list, checkpoint_path: str) -> list:
    """
    For each image: extract text and detect diagrams.
    Results are checkpointed after each page so progress survives interruptions.
    """
    checkpoint = load_checkpoint(checkpoint_path)
    results = []

    for filename, img in images:
        if filename in checkpoint:
            print(f"  [cached] {filename}")
            results.append(checkpoint[filename])
            continue

        print(f"  Extracting text: {filename} ...")
        text = safe_generate(model, [
            "This is a scanned handwritten page of notes. "
            "Extract all text and rewrite it with grammar and spelling corrections. "
            "Preserve all technical content, formulas, and structure exactly.",
            img,
        ])

        print(f"  Detecting diagrams: {filename} ...")
        diagram_response = safe_generate(model, [
            f"Scanned page: {filename}. Ignore all written text.",
            "Identify any hand-drawn diagrams, sketches, flowcharts, or visual elements. "
            "Describe each clearly: what is shown, labels, and relationships. "
            "If there are none, reply exactly: No diagrams.",
            img,
        ])
        diagrams = None if "No diagrams" in diagram_response else diagram_response

        entry = {"filename": filename, "text": text, "diagrams": diagrams}
        checkpoint[filename] = entry
        save_checkpoint(checkpoint_path, checkpoint)
        print(f"  -> {len(text)} chars extracted" + (" | diagram detected" if diagrams else ""))
        results.append(entry)

    return results


def enrich_and_format(model, results: list) -> str:
    """
    Send all extracted pages to Gemini for reordering, enrichment,
    and Markdown formatting. Diagram descriptions are injected inline.
    """
    pages = []
    for i, entry in enumerate(results, 1):
        block = f"### Page {i} ({entry['filename']})\n\n{entry['text']}"
        if entry.get("diagrams"):
            block += f"\n\n> **Diagram:** {entry['diagrams']}"
        pages.append(block)

    joined = "\n\n---\n\n".join(pages)

    prompt = f"""You are an expert in academic writing and document formatting.

Below are scanned handwritten notes extracted page by page. Please:

1. Reorder content logically if pages appear out of sequence.
2. Fix transitions so the document reads cohesively.
3. Add minimal context where necessary for clarity.
4. Incorporate any diagram descriptions as clearly labelled callout blocks.
5. Format the final output as clean **Markdown** optimised for PDF export:
   - Use # and ## for section headings
   - Use bullet points and numbered lists where appropriate
   - Wrap mathematical expressions in \\[ ... \\] LaTeX blocks
   - Render diagram notes as > Diagram: ... blockquotes
6. Output only Markdown — no meta-commentary, no preamble.

Notes:
{joined}
"""
    print("  Sending all pages to Gemini for enrichment...")
    return safe_generate(model, prompt)


def to_latex(model, markdown_text: str) -> str:
    """Ask Gemini to convert the structured Markdown to a compilable LaTeX document."""
    prompt = f"""Convert the following Markdown document into a complete, compilable LaTeX document.

Requirements:
- \\documentclass{{article}} with packages: geometry, amsmath, amssymb, fontenc, inputenc, hyperref
- Proper \\begin{{document}} ... \\end{{document}} wrapper
- Convert all Markdown headings, bullets, and math blocks correctly
- Inline math: \\( ... \\), display math: \\[ ... \\]
- Include \\title, \\author, \\date and \\maketitle
- Output only valid LaTeX — no Markdown, no code fences

Markdown input:
{markdown_text}
"""
    print("  Asking Gemini to generate LaTeX...")
    return safe_generate(model, prompt)


# ---------------------------------------------------------------------------
# Output renderers
# ---------------------------------------------------------------------------

def markdown_to_pdf(markdown_text: str, output_path: str) -> None:
    """Render Markdown → styled HTML → PDF via WeasyPrint."""
    html_body = markdown2.markdown(
        markdown_text,
        extras=["fenced-code-blocks", "tables", "header-ids", "strike"],
    )
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
  body {{
    font-family: Georgia, 'Times New Roman', serif;
    max-width: 820px; margin: 50px auto;
    line-height: 1.7; color: #1a1a1a; font-size: 15px;
  }}
  h1 {{ font-size: 2em; border-bottom: 2px solid #333; padding-bottom: 6px; margin-top: 1.5em; }}
  h2 {{ font-size: 1.5em; color: #222; margin-top: 1.4em; }}
  h3 {{ font-size: 1.2em; }}
  blockquote {{
    background: #f0f4ff; border-left: 4px solid #4a7fd4;
    margin: 1em 0; padding: 10px 16px; border-radius: 0 6px 6px 0;
  }}
  code {{ background: #f4f4f4; padding: 2px 6px; border-radius: 4px; font-size: 0.9em; }}
  pre  {{ background: #f4f4f4; padding: 14px; border-radius: 6px; overflow-x: auto; }}
  table {{ border-collapse: collapse; width: 100%; margin: 1em 0; }}
  th, td {{ border: 1px solid #ccc; padding: 8px 12px; text-align: left; }}
  th {{ background: #eef; }}
</style></head><body>{html_body}</body></html>"""
    HTML(string=html).write_pdf(output_path)


def compile_pdflatex(latex_text: str, output_path: str) -> bool:
    """
    Compile LaTeX to PDF using pdflatex (run twice for cross-references).
    Returns True on success, False if pdflatex is not installed.
    """
    try:
        subprocess.run(["pdflatex", "--version"], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False

    with tempfile.TemporaryDirectory() as tmpdir:
        tex_path = os.path.join(tmpdir, "notes.tex")
        with open(tex_path, "w") as f:
            f.write(latex_text)

        for _ in range(2):  # run twice for correct cross-references
            result = subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", "notes.tex"],
                cwd=tmpdir,
                capture_output=True,
                text=True,
            )

        pdf_path = os.path.join(tmpdir, "notes.pdf")
        if os.path.exists(pdf_path):
            shutil.copy(pdf_path, output_path)
            return True

    return False


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert scanned handwritten notes to PDF using Google Gemini AI"
    )
    parser.add_argument("--input",      required=True,              help="Directory of scanned note images")
    parser.add_argument("--output",     default="output",           help="Output directory (default: ./output)")
    parser.add_argument("--checkpoint", default="checkpoint.json",  help="Checkpoint file for resuming")
    parser.add_argument("--latex",      action="store_true",        help="Also generate a LaTeX PDF (requires pdflatex)")
    args = parser.parse_args()

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit("Error: GEMINI_API_KEY not set. Copy .env.example to .env and add your key.")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(MODEL_NAME)
    os.makedirs(args.output, exist_ok=True)

    # --- Step 1: Load images ---
    print(f"\n[1/4] Loading images from: {args.input}")
    images = load_images(args.input)
    if not images:
        raise SystemExit(f"No images found in {args.input}")
    print(f"      Found {len(images)} image(s): {[f for f, _ in images]}")

    # --- Step 2: Extract text + detect diagrams ---
    print(f"\n[2/4] Extracting text and detecting diagrams (checkpoint: {args.checkpoint})")
    results = extract_pages(model, images, args.checkpoint)

    # --- Step 3: Enrich and structure ---
    print("\n[3/4] Enriching and structuring notes...")
    markdown_text = enrich_and_format(model, results)

    md_path = os.path.join(args.output, "notes.md")
    with open(md_path, "w") as f:
        f.write(markdown_text)
    print(f"      Saved: {md_path}")

    # --- Step 4: Generate PDF(s) ---
    print("\n[4/4] Generating output files...")

    pdf_path = os.path.join(args.output, "notes.pdf")
    markdown_to_pdf(markdown_text, pdf_path)
    print(f"      Saved PDF (WeasyPrint): {pdf_path}")

    if args.latex:
        latex_text = to_latex(model, markdown_text)

        tex_path = os.path.join(args.output, "notes.tex")
        with open(tex_path, "w") as f:
            f.write(latex_text)
        print(f"      Saved LaTeX source: {tex_path}")

        latex_pdf_path = os.path.join(args.output, "notes_latex.pdf")
        if compile_pdflatex(latex_text, latex_pdf_path):
            print(f"      Saved LaTeX PDF: {latex_pdf_path}")
        else:
            print("      pdflatex not found — LaTeX source saved. Compile manually or install TeX Live:")
            print("      https://tug.org/texlive/")

    print(f"\nDone. Outputs in: {args.output}/")


if __name__ == "__main__":
    main()
