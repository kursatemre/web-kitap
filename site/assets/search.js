// Basit Lunr.js arama istemcisi
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
