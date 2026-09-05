// Structural tests for the answer markdown renderer in apps/web/index.html (node tools/test_md_render.js)
const fs=require('fs'); const src=fs.readFileSync('apps/web/index.html','utf8');
const js=[...src.matchAll(/<script(?![^>]*src=)[^>]*>([\s\S]*?)<\/script>/g)].pop()[1];
function fn(name){ const m=js.match(new RegExp('\\n(?:function '+name+'\\(|const '+name+' = )')); if(!m) throw new Error('missing '+name);
  let i=m.index+1; if(js.startsWith('const',i)){ const e=js.indexOf('\n',i); return js.slice(i,e+1); }
  let depth=0, j=js.indexOf('{',i); for(let k=j;k<js.length;k++){ if(js[k]=='{')depth++; else if(js[k]=='}'){depth--; if(!depth) return js.slice(i,k+1);} } }
const code=['esc','linkCitationRefs','mdInline','bulletLead','secAttr','_hlBalanced','splitEnumeration','splitSemicolons','itemHtml','blockFromLine','mdToHtml','questionHtml'].map(fn).join('\n');
global.document={createElement:()=>({set textContent(v){this._t=String(v)},get innerHTML(){return this._t.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}})};
eval(code);
let fails=0; const t=(name,cond)=>{ console.log((cond?'PASS ':'FAIL ')+name); if(!cond) fails++; };
const enumTxt="The retrieved evidence does not: (1) provide any data on the likelihood of progression; (2) identify risk factors for progression beyond worsening symptoms; (3) distinguish between acute and chronic bronchitis; (4) quantify the risk of progression in the elderly.";
let h=mdToHtml(enumTxt);
t('inline (1)..(4) becomes stem + 4-item list', /mdstem/.test(h) && (h.match(/<li>/g)||[]).length===4 && /provide any data/.test(h));
h=mdToHtml('A phase (2) trial reported benefit [3]. The quote "(1) first (2) second" appears verbatim.');
t('year-like / quoted markers do not split', !/<ol/.test(h));
h=mdToHtml('Overall: [[F]](1) reduce dose[[/F]]; (2) monitor renal function every three months; (3) stop below thirty.');
t('highlight pair spanning items → no split', !/<ol/.test(h));
h=mdToHtml('The findings pertain to specific clinical scenarios: a single case of asymptomatic cryptogenic brain abscess [1]; a case of painless appendicitis in a patient without abdominal pain [4]; a patient with mycetoma who remained asymptomatic on follow-up with no pain or swelling [2]; a cohort with silent infections reported elsewhere in the same review [3].');
t('semicolon chain → stem + list', /mdstem/.test(h) && (h.match(/<li>/g)||[]).length===4);
h=mdToHtml('## Bottom line\nStop it [1].\nBasis: FDA label [1]; KDIGO guideline [2].');
t('Basis line is its own muted paragraph with · separators', /class="mdp basis"/.test(h) && /·/.test(h) && !/;\s*KDIGO/.test(h));
t('lede stays serif-first (Bottom line heading tagged)', /data-sec="lead"/.test(h));
h=mdToHtml('## Watch for\n- **Recheck eGFR** — every 3 months while 30–44 [5] — because a fall below thirty means the drug must be stopped outright.');
t('Watch for tagged + second em-dash clause demoted to a note', /data-sec="watch"/.test(h) && /li-note/.test(h));
h=mdToHtml('Line one about a point.\nLine two about another point.');
t('single newline = new paragraph', (h.match(/<p /g)||[]).length===2);
h=mdToHtml('- Item one: (1) alpha beta gamma; (2) delta epsilon zeta; (3) eta theta iota.');
t('enumeration inside a bullet → nested numbered list', /<li>.*<ol class="mdl mdol">/.test(h) && (h.match(/<li>/g)||[]).length===4);
h=questionHtml("A 68-year-old man with **HFrEF** presents with:\n- 3 weeks of exertional dyspnea\n- orthopnea\n\nLabs: creatinine 1.8, potassium 5.4.\nWhat is the differential and initial workup?");
t('question: paragraphs + list kept, no bold, long class', /qlong/.test(h) && (h.match(/<li>/g)||[]).length===2 && !/\*\*|<strong>/.test(h) && (h.match(/<p>/g)||[]).length===3);
t('question: short one-liner stays plain', !/qlong/.test(questionHtml("Metformin dose at eGFR 30-45?")));
console.log(fails? `${fails} FAILED` : 'all passed'); process.exit(fails?1:0);
