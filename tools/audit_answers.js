// Structural audit of stored answers through the REAL renderer: node tools/audit_answers.js <answers.jsonl>
const fs=require('fs'); const src=fs.readFileSync('apps/web/index.html','utf8');
const js=[...src.matchAll(/<script(?![^>]*src=)[^>]*>([\s\S]*?)<\/script>/g)].pop()[1];
function fn(name){ const m=js.match(new RegExp('\\n(?:function '+name+'\\(|const '+name+' = )')); if(!m) throw new Error('missing '+name);
  let i=m.index+1; if(js.startsWith('const',i)){ const e=js.indexOf('\n',i); return js.slice(i,e+1); }
  let depth=0, j=js.indexOf('{',i); for(let k=j;k<js.length;k++){ if(js[k]=='{')depth++; else if(js[k]=='}'){depth--; if(!depth) return js.slice(i,k+1);} } }
global.document={createElement:()=>({set textContent(v){this._t=String(v)},get innerHTML(){return this._t.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}})};
eval(['esc','linkCitationRefs','mdInline','bulletLead','secAttr','_hlBalanced','splitEnumeration','splitSemicolons','itemHtml','blockFromLine','mdToHtml','questionHtml'].map(fn).join('\n'));
const rows=[]; for(const l of fs.readFileSync(process.argv[2],'utf8').split('\n')){ if(!l.trim()) continue; const d=JSON.parse(l); let th=d.thread; if(typeof th==='string') th=JSON.parse(th||'[]');
  const answers=(Array.isArray(th)&&th.length?th.map(t=>t&&t.answer||''):[d.answer]).filter(Boolean); answers.forEach((a,i)=>rows.push({id:d.id+(i?'#'+i:''), q:d.q, a})); }
const checks={}; const ex={}; const hit=(k,id,e)=>{ (checks[k]=checks[k]||[]).push(id); if(!ex[k]) ex[k]=e; };
const words=s=>s.trim().split(/\s+/).length;
for(const r of rows){
  const a=r.a, lines=a.split('\n'), html=mdToHtml(a);
  // ---- raw markdown ----
  const heads=lines.filter(l=>/^#{1,4}\s/.test(l));
  if(!heads.length) hit('no ## sections at all (unstructured answer)', r.id, a.slice(0,120));
  lines.forEach((l,i)=>{
    if(/^\s{2,}[-*]\s/.test(l)) hit('nested/indented bullet (renderer flattens it)', r.id, l.slice(0,120));
    if(/^\s*[-*]\s/.test(l) && words(l)>60) hit('bullet longer than 60 words', r.id, l.slice(0,120));
    if(/^\s*\d+[.)]\s/.test(l) && words(l)>60) hit('numbered item longer than 60 words', r.id, l.slice(0,120));
    if(!/^\s*([-*#|]|\d+[.)])/.test(l) && l.trim() && words(l)>130) hit('paragraph longer than 130 words', r.id, l.slice(0,120));
    if(/\[\d+\](\[\d+\]){3,}/.test(l)) hit('citation pile-up (≥4 refs in a row)', r.id, (l.match(/.{0,60}\[\d+\](\[\d+\]){3,}/)||[l])[0].slice(0,120));
    if(/\[\d+,\s*\d+/.test(l)) hit('comma-joined citations "[1, 2]"', r.id, l.slice(0,120));
    if(/\[\[[FRK]\]\][^\[]*$/.test(l) && !/\[\[\/[FRK]\]\]/.test(l)) hit('highlight marker opened but not closed on the line', r.id, l.slice(0,120));
    if(/^#{1,4}\s/.test(l) && i+1<lines.length && /^#{1,4}\s/.test((lines.slice(i+1).find(x=>x.trim())||''))) hit('empty section (heading followed by heading)', r.id, l.slice(0,120));
    if(/^\|/.test(l) && i>0 && /^\|/.test(lines[i-1]) && lines[i-1].split('|').length!==l.split('|').length && !/^\|[\s:|-]+\|$/.test(l) && !/^\|[\s:|-]+\|$/.test(lines[i-1])) hit('table row with a different column count', r.id, l.slice(0,120));
    if(/^\|/.test(l) && i+1<lines.length && !/^\|/.test(lines[i+1]) && lines[i+1].trim() && !/^\|/.test(lines[i-1]||'')) hit('single-line table (no separator row) → rendered as text', r.id, l.slice(0,120));
    if(/\b(e\.g\.|i\.e\.)\s*,?\s*$/.test(l)) hit('line ends in "e.g."', r.id, l.slice(0,120));
    if(/^\s*[-*]\s+\*\*[^*]+\*\*\s*$/.test(l)) hit('bullet that is ONLY a bold label (no substance)', r.id, l.slice(0,120));
    if(/^\s*[-*]\s+[^*]/.test(l) && !/^\s*[-*]\s+\*\*/.test(l) && !/^\s*[-*]\s+[^—:\n]{3,70}?(\s+—\s+|:\s+)/.test(l)) hit('bullet without any lead (no bold, no " — " or ":")', r.id, l.slice(0,120));
    if(/^\s*\d+[.)]\s/.test(l) && /^\s*\d+[.)]\s/.test(lines[i-1]||'') ){ const a1=parseInt(lines[i-1]), b1=parseInt(l); if(a1===b1) hit('numbered list where every item is "1."', r.id, l.slice(0,120)); }
    if(/\(\d+\)[^\n]{5,200}\(\d+\)/.test(l) && !splitEnumeration(l)) hit('inline "(1) … (2)" the splitter refused (too strict?)', r.id, l.slice(0,140));
    if(/^Basis:/i.test(l) && i>0 && lines[i-1].trim() && !/^## /.test(lines[i-1])) hit('"Basis:" line directly under text (was glued before fix)', r.id, l.slice(0,100));
    if(/^\s*[-*]\s.*\s—\s.*\s—\s.*\s—\s/.test(l)) hit('bullet with 3+ em-dash clauses', r.id, l.slice(0,120));
    if(/\bâ€|Ã©|�/.test(l)) hit('mojibake / encoding garbage', r.id, l.slice(0,120));
    if(/[:;]\s*$/.test(l) && !/^\s*[-*#|]/.test(l) && i+1<lines.length && !lines[i+1].trim()) hit('paragraph ends with ":" but nothing follows before a blank', r.id, l.slice(0,120));
  });
  const secNames=heads.map(h=>h.replace(/^#+\s*/,'').toLowerCase()); const dup=secNames.find((h,i)=>secNames.indexOf(h)!==i); if(dup) hit('duplicate section heading', r.id, dup);
  if(/^## question coverage/im.test(a) && (a.match(/^## Question coverage[\s\S]*?(?=^## |\s*$)/im)||[''])[0].split('\n').filter(l=>/^\s*[-*]/.test(l)).length<=1) hit('Question coverage with a single item (single-question ask)', r.id, '');
  const bl=(a.match(/^## (Bottom line|In brief)\s*\n+([^\n]+)/im)||[])[2]; if(bl && bl.length>420) hit('bottom line longer than 420 chars', r.id, bl.slice(0,120));
  if(bl && /\*\*/.test(bl)) hit('bold inside the bottom line', r.id, bl.slice(0,120));
  // ---- rendered ----
  if((html.match(/<ul class="mdl"><li>[^]*?<\/li><\/ul>/g)||[]).some(u=>(u.match(/<li>/g)||[]).length===1)) hit('list with a single item', r.id, '');
  if(/\*\*/.test(html.replace(/<[^>]+>/g,''))) hit('literal ** left in rendered text (unbalanced bold)', r.id, (html.replace(/<[^>]+>/g,'').match(/.{0,50}\*\*.{0,50}/)||[''])[0]);
  if(/<p class="mdp">\s*<\/p>/.test(html)) hit('empty paragraph rendered', r.id, '');
  const bigLi=(html.match(/<li>([^]*?)<\/li>/g)||[]).filter(li=>words(li.replace(/<[^>]+>/g,''))>90); if(bigLi.length) hit('rendered list item over 90 words', r.id, bigLi[0].replace(/<[^>]+>/g,'').slice(0,120));
  if(/<h5 class="mdh mdh-sub[^"]*">[^<]{120,}/.test(html)) hit('sub-heading longer than 120 chars', r.id, (html.match(/<h5 class="mdh mdh-sub[^"]*">([^<]{120,})/)||['',''])[1].slice(0,120));
  if((html.match(/<table/g)||[]).length && /<td>\s*<\/td>/.test(html)) hit('table with empty cells', r.id, '');
  if(/<td>[^<]{200,}/.test(html)) hit('table cell over 200 chars (paragraph in a cell)', r.id, (html.match(/<td>([^<]{200,})/)||['',''])[1].slice(0,120));
}
const out=Object.entries(checks).sort((a,b)=>b[1].length-a[1].length);
console.log(`answers audited: ${rows.length}\n`);
for(const [k,ids] of out){ const uniq=new Set(ids).size; console.log(`${String(uniq).padStart(4)}  ${k}`); if(ex[k]) console.log(`        e.g. ${ex[k].replace(/\s+/g,' ')}`); }
