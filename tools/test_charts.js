// Chart-renderer tests (node tools/test_charts.js). Renders long-label fixtures for every chart kind
// through the real chartSvg() in apps/web/index.html and asserts: no label is ever truncated, every
// label survives verbatim, and the SVG viewBox is sized from its text. Also writes a fixture page
// (scratch dir or CHART_FIXTURE_OUT; CHART_ONLY=kind,kind filters it) whose script measures real text bounding boxes: run it through
// tools/mobile_shot.py with NOESIS_SHOT_JS='JSON.stringify(window.__chartQA)' to prove nothing
// overlaps or leaves the viewBox at a phone width.
const fs=require('fs'), path=require('path');
const src=fs.readFileSync('apps/web/index.html','utf8');
const js=[...src.matchAll(/<script(?![^>]*src=)[^>]*>([\s\S]*?)<\/script>/g)].pop()[1];
function fn(name){ const m=js.match(new RegExp('\\n(?:function '+name+'\\(|const '+name+' = )')); if(!m) throw new Error('missing '+name);
  let i=m.index+1; if(js.startsWith('const',i)){ const e=js.indexOf('\n',i); return js.slice(i,e+1); }
  let depth=0, j=js.indexOf('{',i); for(let k=j;k<js.length;k++){ if(js[k]=='{')depth++; else if(js[k]=='}'){depth--; if(!depth) return js.slice(i,k+1);} } }
const code=['esc','_CHART_COLS','_chartTicks','_fmtTick','_CW','_LH','_wrapText','_maxLen','_strW','_textLines','chartSvg'].map(fn).join('\n');
global.document={createElement:()=>({set textContent(v){this._t=String(v)},get innerHTML(){return this._t.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}})};
global._CHART_UID=0;
eval(code);
let fails=0; const t=(name,cond)=>{ console.log((cond?'PASS ':'FAIL ')+name); if(!cond) fails++; };

const LONG1="Semaglutide 2.4 mg weekly plus lifestyle counselling (STEP 1 trial, 68 weeks)";
const LONG2="Placebo plus lifestyle counselling";
const LONG3="Tirzepatide 15 mg weekly (SURMOUNT-1, 72 weeks)";
const fixtures = {
  bar: {kind:"bar", title:"Mean weight change from baseline at 68–72 weeks", unit:"% body weight",
    bars:[{label:LONG1,value:14.9,value_str:"−14.9%",finding:1},{label:LONG3,value:20.9,value_str:"−20.9% (95% CI −21.8 to −19.9)",finding:2},{label:LONG2,value:2.4,value_str:"−2.4%",finding:1}]},
  grouped_bar: {kind:"grouped_bar", title:"Efficacy vs discontinuation for adverse events", unit:"%",
    bars:[{label:LONG1,series:"≥5% weight loss",value:86.4,value_str:"86.4%",finding:1},{label:LONG1,series:"Stopped for adverse events",value:7,value_str:"7.0%",finding:1},
          {label:LONG2,series:"≥5% weight loss",value:31.5,value_str:"31.5%",finding:1},{label:LONG2,series:"Stopped for adverse events",value:3.1,value_str:"3.1%",finding:1}]},
  interval: {kind:"interval", title:"Hazard ratio for major adverse cardiovascular events, by trial", unit:"HR",
    bars:[{label:"SELECT (semaglutide 2.4 mg, established CVD, no diabetes)",value:0.80,value_str:"0.80",low:0.72,high:0.90,low_str:"0.72",high_str:"0.90",finding:3},
          {label:"LEADER (liraglutide, type 2 diabetes)",value:0.87,value_str:"0.87",low:0.78,high:0.97,low_str:"0.78",high_str:"0.97",finding:4},
          {label:"Placebo reference",value:1,value_str:"1.00",low:1,high:1,finding:4}]},
  line: {kind:"line", title:"HbA1c over follow-up, by treatment arm", unit:"% HbA1c",
    bars:["Baseline visit","Week 12 (first titration)","Week 24","Week 36","Week 52 (primary endpoint)","Week 68 extension","Week 104 open-label extension"]
      .flatMap((l,i)=>[{label:l,series:"Semaglutide 1 mg weekly",value:8.1-0.25*i,value_str:(8.1-0.25*i).toFixed(2)+"%",finding:5},
                       {label:l,series:"Sitagliptin 100 mg daily",value:8.1-0.12*i,value_str:(8.1-0.12*i).toFixed(2)+"%",finding:5}])},
  pie: {kind:"pie", title:"Causes of community-acquired pneumonia requiring admission", unit:"share of isolates",
    bars:[{label:"Streptococcus pneumoniae (all serotypes)",value:38,value_str:"38%",finding:6},{label:"Respiratory viruses (influenza, RSV, rhinovirus)",value:27,finding:6},
          {label:"Haemophilus influenzae",value:9,finding:6},{label:"Atypical organisms (Mycoplasma, Legionella, Chlamydophila)",value:11,finding:6},{label:"Staphylococcus aureus",value:4,finding:6},{label:"Other / not identified",value:11,finding:6}]},
  pie_small: {kind:"pie", title:"Small pie", bars:[{label:"Guideline-backed",value:60,finding:1},{label:"Extrapolated",value:25,finding:1},{label:"Not established",value:15,finding:1}]},
  icon_array: {kind:"icon_array", title:"Absolute risk of a serious gastrointestinal adverse event at 68 weeks", scale:100,
    bars:[{label:"On semaglutide 2.4 mg weekly (treated arm)",value:10,value_str:"10",finding:1},{label:"On placebo (untreated comparison arm)",value:6,value_str:"6",finding:1}]},
  range_band: {kind:"range_band", title:"Patient values against reference ranges", unit:"",
    bars:[{label:"Serum potassium (this admission, venous sample)",value:5.9,value_str:"5.9 mmol/L",low:3.5,high:5.0,low_str:"3.5",high_str:"5.0",finding:7},
          {label:"eGFR (CKD-EPI 2021, creatinine only)",value:28,value_str:"28 mL/min/1.73 m²",low:60,high:120,low_str:"60",high_str:"120",finding:7},
          {label:"Far-out value (narrow band on this scale)",value:900,value_str:"900",low:60,high:120,low_str:"60",high_str:"120",finding:7}]},
};
const out = {};
for(const [name, ch] of Object.entries(fixtures)){
  const h = chartSvg(ch); out[name] = h;
  const plain = h.replace(/<[^>]+>/g, " ");
  t(name+': renders', h.length > 200);
  t(name+': no truncation ellipsis', !/…/.test(h));
  const labels = [...new Set(ch.bars.map(b => b.label))];
  const allWords = labels.every(l => l.split(/\s+/).every(w => plain.includes(w.replace(/&/g,'&amp;'))));
  t(name+': every label word survives', allWords);
  const vb = h.match(/viewBox="0 0 (\d+(?:\.\d+)?) (\d+(?:\.\d+)?)"/);
  t(name+': viewBox present', !!vb);
}
t('bar: label column is sized from the longest wrapped line (> 150px)', +(out.bar.match(/<tspan x="(\d+)"/)||[])[1] > 150);
t('line: widened plot keeps every x label (7 categories, 7 x-label groups)', (out.line.match(/class="c-tick"><tspan/g)||[]).length === 7);
t('pie: long labels go to the side legend (no leader lines)', !/c-lead/.test(out.pie) && /<rect x="236"/.test(out.pie));
t('pie_small: short well-separated slices keep external labels', /c-lead/.test(out.pie_small));
t('range_band: narrow band pushes edge labels apart', /text-anchor="end" class="c-tick">60</.test(out.range_band) && /text-anchor="start" class="c-tick">120</.test(out.range_band));

// fixture page for the browser measurement pass
const styles=[...src.matchAll(/<style[^>]*>([\s\S]*?)<\/style>/g)].map(m=>m[1]).join('\n');
const fonts=(src.match(/<link[^>]*fonts\.googleapis[^>]*>/g)||[]).join('\n');
const qa = `
window.__chartQA = (()=>{
  const res=[];
  document.querySelectorAll('svg.chart').forEach((svg,si)=>{
    const vb=svg.viewBox.baseVal; const texts=[...svg.querySelectorAll('text')];
    const boxes=texts.map(tx=>{const b=tx.getBBox();return {t:tx.textContent.trim().slice(0,40),x:b.x,y:b.y,w:b.width,h:b.height};});
    const outside=boxes.filter(b=>b.x< -0.5||b.y< -0.5||b.x+b.w>vb.width+0.5||b.y+b.h>vb.height+0.5);
    const overlaps=[];
    for(let i=0;i<boxes.length;i++)for(let j=i+1;j<boxes.length;j++){const a=boxes[i],b=boxes[j];
      const ox=Math.min(a.x+a.w,b.x+b.w)-Math.max(a.x,b.x), oy=Math.min(a.y+a.h,b.y+b.h)-Math.max(a.y,b.y);
      if(ox>1&&oy>1) overlaps.push([a.t,b.t,Math.round(ox),Math.round(oy)]);}
    res.push({svg:si,texts:texts.length,outside,overlaps,width:svg.getBoundingClientRect().width});
  });
  return {docScrollW:document.documentElement.scrollWidth,innerWidth,charts:res};
})();`;
const page = `<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>chart fixtures</title>${fonts}<style>${styles}</style></head>
<body class="theme-clinical"><div id="idmodal" hidden></div><main style="max-width:42rem;margin:1rem auto;padding:0 12px"><div class="answer md">${Object.entries(out).filter(([k])=>!process.env.CHART_ONLY||process.env.CHART_ONLY.split(',').includes(k)).map(([,v])=>v).join('\n')}</div></main><script>${qa}</script></body></html>`;
const outPath = process.env.CHART_FIXTURE_OUT || path.join(process.env.SCRATCH || '.', 'chart_fixtures.html');
fs.writeFileSync(outPath, page);
console.log('fixture page:', outPath);
console.log(fails ? `${fails} FAILED` : 'ALL PASS'); process.exit(fails ? 1 : 0);
