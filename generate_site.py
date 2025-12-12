#!/usr/bin/env python3
"""Basit site jeneratörü: `corrected_texts/*.txt` -> `site/` (HTML + Lunr.js arama dizini).

Kullanım:
  python generate_site.py

Çıktı:
  site/index.html
  site/search_index.json
  site/pages/<slug>.html
  site/assets/{search.js,styles.css}
"""
import os
import glob
import json
import pathlib
import html
from datetime import datetime

ROOT = pathlib.Path(__file__).resolve().parent
CORRECTED_DIR = ROOT / "corrected_texts"
OUT_DIR = ROOT / "site"
PAGES_DIR = OUT_DIR / "pages"
ASSETS_DIR = OUT_DIR / "assets"


def slugify(name: str) -> str:
    s = name.lower()
    keep = []
    for ch in s:
        if ch.isalnum():
            keep.append(ch)
        elif ch.isspace() or ch in ('-', '_'):
            keep.append('-')
    slug = ''.join(keep)
    # collapse dashes
    while '--' in slug:
        slug = slug.replace('--', '-')
    return slug.strip('-') or 'page'


def ensure_dirs():
    PAGES_DIR.mkdir(parents=True, exist_ok=True)
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)


def read_text_files():
    files = sorted(glob.glob(str(CORRECTED_DIR / '*.txt')))
    docs = []
    for path in files:
        p = pathlib.Path(path)
        title = p.stem
        with p.open('r', encoding='utf-8', errors='replace') as f:
            text = f.read().strip()
        slug = slugify(title)
        url = f'pages/{slug}.html'
        docs.append({'id': slug, 'title': title, 'text': text, 'url': url})
    return docs


def render_page(doc):
    title = html.escape(doc['title'])
    paragraphs = []
    for part in doc['text'].split('\n\n'):
        p = part.strip().replace('\n', ' ')
        if not p:
            continue
        paragraphs.append(f'<p>{html.escape(p)}</p>')

    body = '\n'.join(paragraphs)
    html_page = f'''<!doctype html>
<html lang="tr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{title}</title>
  <link rel="stylesheet" href="../assets/styles.css">
</head>
<body>
  <header>
    <a href="../index.html">← Geri</a>
    <h1>{title}</h1>
  </header>
  <main>
{body}
  </main>
  <footer>
    <small>Oluşturuldu: {datetime.utcnow().isoformat()} UTC</small>
  </footer>
</body>
</html>'''
    return html_page


def write_assets():
    styles = """body{font-family:Segoe UI,Helvetica,Arial,sans-serif;margin:0;padding:0}
header{background:#0b64a0;color:#fff;padding:12px 18px}
header a{color:#fff;text-decoration:none;margin-right:12px}
main{padding:18px;max-width:900px;margin:auto}
input[type=text]{width:100%;padding:10px;font-size:16px;margin-bottom:12px}
.result{padding:10px;border-bottom:1px solid #eee}
.result a{font-weight:600;color:#0b64a0}
"""
    (ASSETS_DIR / 'styles.css').write_text(styles, encoding='utf-8')

    search_js = """// Basit Lunr.js arama istemcisi
let lunrIndex = null;
let docs = [];
async function initSearch(){
  const res = await fetch('search_index.json');
  docs = await res.json();
  // build lunr index
  lunrIndex = lunr(function(){
    this.ref('id');
    this.field('title');
    this.field('text');
    for(const d of docs){ this.add(d); }
  });
  document.getElementById('search-box').addEventListener('input', onSearch);
}

function snippet(text, q){
  if(!text) return '';
  const i = text.toLowerCase().indexOf(q.toLowerCase());
  if(i === -1) return text.slice(0,200) + '...';
  const start = Math.max(0, i-60);
  return (start>0? '...':'' ) + text.slice(start, start+260) + '...';
}

function onSearch(e){
  const q = e.target.value.trim();
  const out = document.getElementById('results');
  out.innerHTML = '';
  if(!q) return;
  const results = lunrIndex.search(q);
  for(const r of results.slice(0,50)){
    const doc = docs.find(d=>d.id === r.ref);
    const div = document.createElement('div'); div.className='result';
    const a = document.createElement('a'); a.href = doc.url; a.textContent = doc.title;
    const s = document.createElement('div'); s.innerHTML = snippet(doc.text, q);
    div.appendChild(a); div.appendChild(s); out.appendChild(div);
  }
}

document.addEventListener('DOMContentLoaded', initSearch);
"""
    (ASSETS_DIR / 'search.js').write_text(search_js, encoding='utf-8')


def write_index_page():
    index_html = '''<!doctype html>
<html lang="tr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Web-Kitap</title>
  <link rel="stylesheet" href="assets/styles.css">
  <script src="https://unpkg.com/lunr/lunr.js"></script>
  <script src="assets/search.js" defer></script>
</head>
<body>
  <header>
    <h1>Web-Kitap</h1>
  </header>
  <main>
    <label for="search-box">Ara:</label>
    <input id="search-box" type="text" placeholder="Kelime veya cümle girin...">
    <div id="results"></div>
    <hr>
    <h2>İçindekiler</h2>
    <ul>
{{TOC}}
    </ul>
  </main>
</body>
</html>'''
    return index_html


def build():
    ensure_dirs()
    docs = read_text_files()
    # write pages
    for d in docs:
        page_html = render_page(d)
        (PAGES_DIR / f"{d['id']}.html").write_text(page_html, encoding='utf-8')

    # write search index json (docs with id,title,text,url)
    si = [{'id': d['id'], 'title': d['title'], 'text': d['text'], 'url': d['url']} for d in docs]
    (OUT_DIR / 'search_index.json').write_text(json.dumps(si, ensure_ascii=False), encoding='utf-8')

    # assets
    write_assets()

    # index page with TOC
    toc_items = '\n'.join([f'      <li><a href="{d["url"]}">{html.escape(d["title"])}</a></li>' for d in docs])
    index_html = write_index_page().replace('{{TOC}}', toc_items)
    (OUT_DIR / 'index.html').write_text(index_html, encoding='utf-8')

    print(f"Wrote site to: {OUT_DIR}")


if __name__ == '__main__':
    if not CORRECTED_DIR.exists():
        print('Düzeltmiş metinleri içeren `corrected_texts/` dizini bulunamadı. Önce OCR ve düzeltme çalıştırın.')
    else:
        build()
