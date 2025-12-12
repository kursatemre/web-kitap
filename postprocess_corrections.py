import re
import os
from difflib import get_close_matches


def build_vocabulary(folder):
    freqs = {}
    for fn in os.listdir(folder):
        if not fn.lower().endswith('.txt'):
            continue
        path = os.path.join(folder, fn)
        text = open(path, 'r', encoding='utf-8', errors='ignore').read()
        words = re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü]+", text)
        for w in words:
            wlow = w.lower()
            freqs[wlow] = freqs.get(wlow, 0) + 1
    # keep words with at least 2 occurrences to reduce noise
    vocab = {w for w, c in freqs.items() if c >= 2}
    return vocab, freqs


def correct_text(text, vocab, freqs, cutoff=0.75):
    # Split into tokens preserving non-word separators
    tokens = re.split(r'([A-Za-zÇĞİÖŞÜçğıöşü]+)', text)
    for i, tok in enumerate(tokens):
        if re.fullmatch(r'[A-Za-zÇĞİÖŞÜçğıöşü]+', tok):
            low = tok.lower()
            if low in vocab:
                continue
            # try close matches from vocab
            matches = get_close_matches(low, vocab, n=1, cutoff=cutoff)
            if matches:
                replacement = matches[0]
                # preserve capitalization
                if tok.istitle():
                    replacement = replacement.capitalize()
                elif tok.isupper():
                    replacement = replacement.upper()
                tokens[i] = replacement
    return ''.join(tokens)


def main():
    src = os.path.join(os.path.dirname(__file__), 'extracted_texts')
    dst = os.path.join(os.path.dirname(__file__), 'corrected_texts')
    os.makedirs(dst, exist_ok=True)

    vocab, freqs = build_vocabulary(src)
    print(f'Vocabulary size: {len(vocab)}')

    for fn in os.listdir(src):
        if not fn.lower().endswith('.txt'):
            continue
        in_path = os.path.join(src, fn)
        out_path = os.path.join(dst, fn)
        text = open(in_path, 'r', encoding='utf-8', errors='ignore').read()
        corrected = correct_text(text, vocab, freqs, cutoff=0.72)
        open(out_path, 'w', encoding='utf-8').write(corrected)
        print(f'Wrote: {out_path}')


if __name__ == '__main__':
    main()
