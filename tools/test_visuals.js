// Layout tests for the relationship-map diagram (node tools/test_visuals.js).
// Renders fixtures through the real vzMap() in apps/web/index.html and checks the geometry that
// makes a diagram readable: no box overlaps another, nothing escapes the viewBox, edge labels do not
// collide, and a node nothing connects to is not drawn at all (that is what "dangling" looked like).
const fs = require('fs');
const src = fs.readFileSync('apps/web/index.html', 'utf8');
const js = [...src.matchAll(/<script(?![^>]*src=)[^>]*>([\s\S]*?)<\/script>/g)].pop()[1];
function fn(name){
  const m = js.match(new RegExp('\\n(?:function ' + name + '\\(|const ' + name + ' = )'));
  if(!m) throw new Error('missing ' + name);
  let i = m.index + 1;
  if(js.startsWith('const', i)){ const e = js.indexOf('\n', i); return js.slice(i, e + 1); }
  let depth = 0;
  for(let k = js.indexOf('{', i); k < js.length; k++){
    if(js[k] === '{') depth++;
    else if(js[k] === '}'){ depth--; if(!depth) return js.slice(i, k + 1); }
  }
}
const code = ['esc', 'VZ_DEFS', 'vzWrap', 'vzTextLines', 'vzLabelPos', 'vzNodeBox', 'vzFlow', 'vzMap'].map(fn).join('\n');
global.document = {createElement: () => ({set textContent(v){ this._t = String(v); },
  get innerHTML(){ return this._t.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }})};
eval(code);

let fails = 0;
const t = (name, cond) => { console.log((cond ? 'PASS ' : 'FAIL ') + name); if(!cond) fails++; };
const rects = h => [...h.matchAll(/<rect class="vznode[^"]*" x="([-\d.]+)" y="([-\d.]+)" width="([\d.]+)" height="([\d.]+)"/g)]
  .map(m => ({x: +m[1], y: +m[2], w: +m[3], h: +m[4]}));
const labels = h => [...h.matchAll(/<rect class="vzedgelblbg" x="([-\d.]+)" y="([-\d.]+)" width="([\d.]+)" height="([\d.]+)"/g)]
  .map(m => ({x: +m[1], y: +m[2], w: +m[3], h: +m[4]}));
const box = h => { const m = h.match(/viewBox="0 0 (\d+) (\d+)"/); return m ? {w: +m[1], h: +m[2]} : null; };
const overlaps = (A, gap = 0) => {
  let n = 0;
  for(let i = 0; i < A.length; i++) for(let j = i + 1; j < A.length; j++){
    const a = A[i], b = A[j];
    if(a.x < b.x + b.w + gap && b.x < a.x + a.w + gap && a.y < b.y + b.h + gap && b.y < a.y + a.h + gap) n++;
  }
  return n;
};

// the real PJP map that shipped with crossing edges and colliding labels
const pjp = {kind: 'map', title: 'Comparative Standing of Prophylaxis Agents',
  nodes: [{id: 'tmpsmx', label: 'TMP-SMX'}, {id: 'toxicity', label: 'Highest toxicity/discontinuation'},
          {id: 'pentamidine', label: 'Aerosolized pentamidine'}, {id: 'dapsone', label: 'Dapsone-based regimens'},
          {id: 'sideeffects', label: 'Side effects'}],
  edges: [{src: 'tmpsmx', dst: 'toxicity', label: 'has'},
          {src: 'tmpsmx', dst: 'pentamidine', label: 'more effective than'},
          {src: 'tmpsmx', dst: 'dapsone', label: 'more effective than'},
          {src: 'pentamidine', dst: 'sideeffects', label: 'causes'},
          {src: 'dapsone', dst: 'sideeffects', label: 'causes'}]};

const cycle = {kind: 'map', nodes: [{id: 'a', label: 'Inflammation'}, {id: 'b', label: 'Tissue injury'},
    {id: 'c', label: 'Fibrosis'}],
  edges: [{src: 'a', dst: 'b', label: 'drives'}, {src: 'b', dst: 'c', label: 'leads to'},
          {src: 'c', dst: 'a', label: 'sustains'}]};

const dirty = {kind: 'map',
  nodes: [{id: 'a', label: 'Statin therapy'}, {id: 'b', label: 'LDL-C reduction'},
          {id: 'c', label: 'Major vascular events'}, {id: 'orphan', label: 'Unconnected concept'}],
  edges: [{src: 'a', dst: 'b', label: 'lowers'}, {src: 'b', dst: 'c', label: 'reduces'},
          {src: 'a', dst: 'ghost', label: 'points nowhere'}, {src: 'c', dst: 'c', label: 'self'}]};

const wide = {kind: 'map',
  nodes: Array.from({length: 9}, (_, i) => ({id: 'n' + i, label: 'Concept number ' + i + ' with a long name'})),
  edges: Array.from({length: 8}, (_, i) => ({src: 'n0', dst: 'n' + (i + 1), label: 'relates to'}))};

for(const [name, fx] of Object.entries({pjp, cycle, dirty, wide})){
  const h = vzMap(fx);
  t(name + ': renders', !!h && h.length > 200);
  const R = rects(h), L = labels(h), B = box(h);
  t(name + ': viewBox present', !!B);
  t(name + ': no node overlaps another', overlaps(R) === 0);
  t(name + ': every node inside the viewBox',
    R.every(r => r.x >= -0.5 && r.y >= -0.5 && r.x + r.w <= B.w + 0.5 && r.y + r.h <= B.h + 0.5));
  t(name + ': edge labels do not collide', overlaps(L) === 0);
  t(name + ': edge labels do not sit on a node box',
    L.every(l => !R.some(r => l.x < r.x + r.w && r.x < l.x + l.w && l.y < r.y + r.h && r.y < l.y + l.h)));
  t(name + ': no label escapes the viewBox',
    L.every(l => l.x >= -0.5 && l.y >= -0.5 && l.x + l.w <= B.w + 0.5 && l.y + l.h <= B.h + 0.5));
}

// ---- FLOW diagrams: several edges converging on one node put their labels in the same band, which
// is exactly where labels used to stack on top of each other and become unreadable.
const flows = {
  converge: {kind: 'flow',
    nodes: [{id: 'a', label: 'Suspected PE'}, {id: 'b', label: 'Wells score'}, {id: 'c', label: 'D-dimer'},
            {id: 'd', label: 'CT pulmonary angiography'}, {id: 'e', label: 'Anticoagulate'}],
    edges: [{src: 'a', dst: 'b', label: 'assess pretest probability'}, {src: 'a', dst: 'c', label: 'if low risk'},
            {src: 'b', dst: 'd', label: 'high probability'}, {src: 'c', dst: 'd', label: 'positive'},
            {src: 'd', dst: 'e', label: 'confirmed'}, {src: 'c', dst: 'e', label: 'negative, stop'}]},
  fanout: {kind: 'flow',
    nodes: [{id: 'r', label: 'Initial assessment'}].concat(
      Array.from({length: 5}, (_, i) => ({id: 'n' + i, label: 'Pathway option ' + i}))),
    edges: Array.from({length: 5}, (_, i) => ({src: 'r', dst: 'n' + i, label: 'when criterion ' + i + ' is met'}))},
  chain: {kind: 'flow',
    nodes: Array.from({length: 5}, (_, i) => ({id: 's' + i, label: 'Step ' + i, note: 'a supporting note here'})),
    edges: Array.from({length: 4}, (_, i) => ({src: 's' + i, dst: 's' + (i+1), label: 'then proceed to the next step'}))},
};
for(const [name, fx] of Object.entries(flows)){
  const h = vzFlow(fx);
  t('flow ' + name + ': renders', !!h && h.length > 200);
  const R = rects(h), L = labels(h), B = box(h);
  t('flow ' + name + ': no two edge labels overlap', overlaps(L) === 0);
  t('flow ' + name + ': no edge label sits on a node box',
    L.every(l => !R.some(r => l.x < r.x + r.w && r.x < l.x + l.w && l.y < r.y + r.h && r.y < l.y + l.h)));
  t('flow ' + name + ': no label escapes the canvas',
    L.every(l => l.x >= -0.5 && l.x + l.w <= B.w + 0.5 && l.y >= -0.5 && l.y + l.h <= B.h + 0.5));
  t('flow ' + name + ': every label is drawn', L.length === fx.edges.length);
}

// the dangling cases: an unconnected node and an edge to a missing node are not drawn
const dh = vzMap(dirty);
t('dirty: the unconnected node is dropped', !/Unconnected/.test(dh));
t('dirty: an edge to a missing node is dropped', !/points nowhere/.test(dh));
t('dirty: a self-edge is dropped', !/>self</.test(dh));
t('dirty: the three real nodes remain', rects(dh).length === 3);
// a map with nothing left to relate renders nothing rather than a lone box
t('too small: two connected nodes render nothing',
  vzMap({kind: 'map', nodes: [{id: 'a', label: 'A'}, {id: 'b', label: 'B'}], edges: [{src: 'a', dst: 'b'}]}) === "");
t('no edges: nothing renders',
  vzMap({kind: 'map', nodes: [{id: 'a', label: 'A'}, {id: 'b', label: 'B'}, {id: 'c', label: 'C'}], edges: []}) === "");
// layering: the PJP map should read top-down, not as a ring
const pr = rects(vzMap(pjp));
t('pjp: nodes sit in distinct rows (layered, not a ring)', new Set(pr.map(r => Math.round(r.y))).size >= 3);

// a compound label breaks where it reads, not mid-word
const wrapped = vzMap({kind: 'map',
  nodes: [{id: 'a', label: 'Highest toxicity/discontinuation'}, {id: 'b', label: 'TMP-SMX'}, {id: 'c', label: 'Side effects'}],
  edges: [{src: 'b', dst: 'a', label: 'has'}, {src: 'b', dst: 'c', label: 'causes'}]});
t('compound word breaks after the slash, not mid-word', !/discontin\s*<\/tspan>/.test(wrapped) && /toxicity\//.test(wrapped));

console.log(fails ? `${fails} FAILED` : 'ALL PASS');
process.exit(fails ? 1 : 0);
