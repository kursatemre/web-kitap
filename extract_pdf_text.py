import os
import glob
import PyPDF2
from pdf2image import convert_from_path
import pytesseract
import shutil
import os
import glob
import PyPDF2
from pdf2image import convert_from_path
import pytesseract
import shutil
import fitz
from PIL import Image
from PIL import ImageFilter
import re


def extract_text_from_pdf(pdf_path, poppler_path=None, ocr_lang=None):
    """Extracts text from a PDF file. Tries text layer first, falls back to OCR."""
    text = ""
    # Try text layer extraction
    try:
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                try:
                    page_text = page.extract_text()
                except Exception:
                    page_text = None
                if page_text:
                    text += page_text + "\n"
    except Exception as e:
        print(f"An error occurred while reading {pdf_path}: {e}")

    if text.strip():
        return text

    # If no text found, try OCR
    print(f"No text layer found in {pdf_path} — attempting OCR...")
    # Ensure pytesseract knows where tesseract.exe is (try common install paths)
    if not shutil.which('tesseract'):
        possible = [r"C:\Program Files\Tesseract-OCR\tesseract.exe", r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"]
        for p in possible:
            if os.path.exists(p):
                pytesseract.pytesseract.tesseract_cmd = p
                break

    try:
        images = convert_from_path(pdf_path, dpi=300, poppler_path=poppler_path)
    except Exception as e:
        print(f"pdf2image failed to convert PDF to images: {e}")
        print("Attempting fallback: rendering pages with PyMuPDF (fitz)...")
        try:
            doc = fitz.open(pdf_path)
            images = []
            for page in doc:
                mat = fitz.Matrix(2, 2)
                pix = page.get_pixmap(matrix=mat)
                mode = "RGB" if pix.alpha == 0 else "RGBA"
                img = Image.frombytes(mode, [pix.width, pix.height], pix.samples)
                images.append(img)
        except Exception as e2:
            print(f"PyMuPDF fallback failed: {e2}")
            return text

    def compute_otsu_threshold(hist):
        total = sum(hist)
        sumB = 0
        wB = 0
        maximum = 0.0
        sum1 = sum(i * h for i, h in enumerate(hist))
        for i in range(256):
            wB += hist[i]
            if wB == 0:
                continue
            wF = total - wB
            if wF == 0:
                break
            sumB += i * hist[i]
            mB = sumB / wB
            mF = (sum1 - sumB) / wF
            between = wB * wF * (mB - mF) * (mB - mF)
            if between > maximum:
                threshold = i
                maximum = between
        return int(threshold)

    def preprocess_image(pil_img):
        # Grayscale
        gray = pil_img.convert('L')
        w, h = gray.size
        scale = 2.0 if max(w, h) < 2000 else 1.0
        if scale != 1.0:
            gray = gray.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        # Median filter to reduce noise
        gray = gray.filter(ImageFilter.MedianFilter(size=3))
        # Compute Otsu threshold
        hist = gray.histogram()
        try:
            thresh = compute_otsu_threshold(hist)
        except Exception:
            thresh = 128
        bw = gray.point(lambda p: 255 if p > thresh else 0)
        return bw

    def postprocess_text(t):
        # Normalize common ligatures and weird chars
        t = t.replace('\ufb01', 'fi').replace('\ufb02', 'fl')
        t = t.replace('\x0c', '\n')
        # Fix hyphenation at line breaks
        t = re.sub(r"-\n\s*", "", t)
        # Join lines that were broken in middle of sentences
        lines = t.splitlines()
        out_lines = []
        i = 0
        while i < len(lines):
            line = lines[i].rstrip()
            if i+1 < len(lines):
                nxt = lines[i+1].lstrip()
            else:
                nxt = ''
            if line == '':
                out_lines.append('')
                i += 1
                continue
            # if next line starts lowercase, it's likely a broken line
            if nxt and nxt[0].islower():
                merged = line + ' ' + nxt
                lines[i+1] = merged
                i += 1
                continue
            else:
                out_lines.append(line)
                i += 1
        res = '\n'.join(out_lines)
        # Collapse multiple spaces
        res = re.sub(r' {2,}', ' ', res)
        return res

    ocr_text = ""
    for i, img in enumerate(images):
        try:
            proc_img = preprocess_image(img)
            cfg = "--oem 1 --psm 3"
            if ocr_lang:
                page_text = pytesseract.image_to_string(proc_img, lang=ocr_lang, config=cfg)
            else:
                page_text = pytesseract.image_to_string(proc_img, config=cfg)
        except Exception as e:
            print(f"pytesseract failed on page {i+1}: {e}")
            print("Make sure Tesseract is installed and its path is available in PATH.")
            return text
        if page_text:
            ocr_text += page_text + "\n"

    ocr_text = postprocess_text(ocr_text)
    return ocr_text


def extract_best_variant(pdf_path, poppler_path=None, ocr_lang='tur'):
    """Try multiple OCR configs (different DPI and --psm) and return best-scoring text."""
    dpi_options = [300, 400]
    psm_options = [3, 6, 1]

    best_text = ""
    best_score = -1

    # Use PyMuPDF to render pages at different DPI if pdf2image fails
    def render_pages_with_pymupdf(path, dpi):
        doc = fitz.open(path)
        images = []
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        for page in doc:
            pix = page.get_pixmap(matrix=mat)
            mode = "RGB" if pix.alpha == 0 else "RGBA"
            img = Image.frombytes(mode, [pix.width, pix.height], pix.samples)
            images.append(img)
        return images

    for dpi in dpi_options:
        try:
            # try pdf2image first
            try:
                images = convert_from_path(pdf_path, dpi=dpi, poppler_path=poppler_path)
            except Exception:
                images = render_pages_with_pymupdf(pdf_path, dpi)

        except Exception as e:
            print(f"Rendering failed for dpi={dpi}: {e}")
            continue

        for psm in psm_options:
            cfg = f"--oem 1 --psm {psm}"
            ocr_text = ""
            for img in images:
                proc = preprocess_image(img)
                try:
                    if ocr_lang:
                        t = pytesseract.image_to_string(proc, lang=ocr_lang, config=cfg)
                    else:
                        t = pytesseract.image_to_string(proc, config=cfg)
                except Exception as e:
                    print(f"Tesseract failed (dpi={dpi},psm={psm}): {e}")
                    t = ''
                ocr_text += t + "\n"

            ocr_text = postprocess_text(ocr_text)
            # scoring heuristic: proportion of alphabetic characters
            total_chars = len(ocr_text)
            alpha_chars = sum(1 for ch in ocr_text if ch.isalpha())
            score = (alpha_chars / total_chars) if total_chars > 0 else 0

            # small bonus for more words
            words = len([w for w in ocr_text.split() if len(w) > 1])
            score += min(words / 10000.0, 0.1)

            print(f"Config dpi={dpi} psm={psm} -> words={words} alpha_ratio={score:.4f}")

            if score > best_score:
                best_score = score
                best_text = ocr_text

    return best_text


def main():
    cwd = os.path.dirname(os.path.abspath(__file__))
    pdf_pattern = os.path.join(cwd, "*.pdf")
    pdf_files = glob.glob(pdf_pattern)

    if not pdf_files:
        print("No PDF files found in the workspace directory:", cwd)
        return

    output_dir = os.path.join(cwd, "extracted_texts")
    os.makedirs(output_dir, exist_ok=True)

    # Try to get poppler path from environment if set
    poppler_path = None
    env_pp = os.environ.get('POPPLER_PATH')
    if env_pp:
        poppler_path = env_pp

    # Optional OCR language from env
    ocr_lang = os.environ.get('TESSERACT_LANG')  # e.g. 'tur' for Turkish

    for pdf in pdf_files:
        base = os.path.splitext(os.path.basename(pdf))[0]
        output_path = os.path.join(output_dir, base + ".txt")
        print(f"Processing: {pdf}")
        text = extract_text_from_pdf(pdf, poppler_path=poppler_path, ocr_lang=ocr_lang)
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(text)
            print(f"Saved: {output_path} ({len(text)} chars)")
        except Exception as e:
            print(f"Failed to write {output_path}: {e}")


if __name__ == "__main__":
    main()