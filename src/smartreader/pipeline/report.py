"""Generate a self-contained HTML pipeline report from a *_data.json file."""
from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_REPORT_DIR = Path(".tmp/reports")


def find_latest_data() -> Path | None:
    """Return the most recent *_data.json in .tmp/reports, or None."""
    if not _REPORT_DIR.exists():
        return None
    files = sorted(_REPORT_DIR.glob("*_data.json"))
    return files[-1] if files else None


def generate_report(data_path: Path) -> Path:
    """Read data JSON, write *_report.html next to it, return its path."""
    data = json.loads(data_path.read_text(encoding="utf-8"))
    html = _render_html(data)
    report_name = data_path.stem.replace("_data", "_report") + ".html"
    report_path = data_path.parent / report_name
    report_path.write_text(html, encoding="utf-8")
    logger.info("pipeline HTML report written to %s", report_path)
    return report_path


# ── CSS ────────────────────────────────────────────────────────────────────────

_CSS = """
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html{font-family:system-ui,-apple-system,sans-serif;font-size:14px;color:#1a202c}
body{background:#eef2f7;min-height:100vh}
a{color:#3b82f6}
:root{--c-pass:#94a3b8;--c-merge:#f59e0b;--c-drop:#f87171}

#top-bar{background:linear-gradient(135deg,#1e3a5f 0%,#2d5986 100%);color:#fff;
  padding:11px 20px;display:flex;align-items:center;gap:12px;
  position:sticky;top:0;z-index:100;box-shadow:0 2px 8px rgba(0,0,0,.2)}
.brand{font-weight:700;font-size:15px}
.sep{opacity:.35}
.run-ts{font-size:12px;color:#93c5fd}

#input-section{background:#fff;border-bottom:1px solid #e2e8f0}
.sec-toggle{width:100%;padding:12px 20px;background:none;border:none;cursor:pointer;
  display:flex;justify-content:space-between;align-items:center;font-size:14px;color:#1a202c}
.sec-toggle:hover{background:#f7fafc}
.tog-icon{font-size:11px;color:#718096;transition:transform .2s}
.sec-body{overflow:hidden;max-height:400px;transition:max-height .3s ease,padding .3s}
.sec-body.collapsed{max-height:0!important;padding:0 20px}
.sec-body-inner{padding:14px 20px}
.input-stats{display:flex;gap:32px;flex-wrap:wrap}
.sg-title{font-size:11px;font-weight:700;color:#718096;text-transform:uppercase;
  letter-spacing:.5px;margin-bottom:7px}
.stat-row{display:flex;justify-content:space-between;gap:16px;padding:3px 0;font-size:13px}
.stat-k{color:#4a5568}.stat-v{font-weight:600}

.badge{display:inline-flex;align-items:center;border-radius:10px;padding:2px 8px;
  font-size:11px;font-weight:600}
.bp{background:#dcfce7;color:#16a34a}
.bm{background:#fef3c7;color:#d97706}
.bd{background:#fee2e2;color:#dc2626}

#pipeline-section{padding:20px}
#pipeline-scroll{overflow-x:auto;padding-bottom:20px}
#pipeline-container{position:relative}

.stage-hdr{position:absolute;cursor:pointer;background:#fff;border:1.5px solid #e2e8f0;
  border-radius:8px;padding:8px 14px;box-shadow:0 1px 4px rgba(0,0,0,.08);
  display:flex;flex-direction:column;align-items:center;gap:3px;
  transition:box-shadow .15s;z-index:10}
.stage-hdr:hover{box-shadow:0 3px 10px rgba(0,0,0,.13)}
.hdr-type{font-size:11px;font-weight:700;color:#3b82f6;text-transform:uppercase;letter-spacing:.5px}
.hdr-stats{font-size:11px;color:#718096}

.item-card{position:absolute;cursor:pointer;background:#fff;border-radius:7px;
  border:1px solid #e2e8f0;border-left:4px solid transparent;
  padding:8px 10px;box-shadow:0 1px 3px rgba(0,0,0,.07);
  display:flex;flex-direction:column;justify-content:space-between;
  overflow:hidden;transition:box-shadow .15s,transform .1s,opacity .15s}
.item-card:hover{box-shadow:0 4px 14px rgba(0,0,0,.12);transform:translateY(-1px)}
.item-card.op{border-left-color:#22c55e}
.item-card.om{border-left-color:#f59e0b}
.item-card.od{border-left-color:#ef4444;opacity:.75}
.item-card.dim{opacity:.1!important;transform:none!important}
.item-card.hl{box-shadow:0 0 0 2.5px #3b82f6,0 4px 18px rgba(59,130,246,.3)!important;
  z-index:20;opacity:1!important;transform:none}
.card-title{font-size:12px;font-weight:600;line-height:1.4;overflow:hidden;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}
.card-foot{display:flex;gap:6px;align-items:center;margin-top:5px}
.card-src{font-size:10px;color:#718096;overflow:hidden;text-overflow:ellipsis;
  white-space:nowrap;flex:1}
.card-score{font-size:11px;font-weight:700;border-radius:4px;padding:1px 5px;white-space:nowrap}
.sp{color:#16a34a;background:#dcfce7}.sn{color:#dc2626;background:#fee2e2}
.sz{color:#6b7280;background:#f3f4f6}
.sum-dot{font-size:11px;color:#a0aec0;flex-shrink:0}

.flow-arrow{transition:opacity .15s}
.flow-arrow.dim{opacity:.06!important}

.detail-panel{position:fixed;top:0;right:0;height:100vh;width:390px;max-width:100vw;
  background:#fff;z-index:200;display:flex;flex-direction:column;
  box-shadow:-4px 0 24px rgba(0,0,0,.14);
  transform:translateX(100%);transition:transform .25s ease}
.detail-panel.open{transform:translateX(0)}
.det-hdr{padding:14px 16px;border-bottom:1px solid #e2e8f0;
  display:flex;align-items:center;justify-content:space-between;background:#f8fafc}
.det-title{font-weight:700;font-size:13px;flex:1;padding-right:8px;word-break:break-word}
.close-btn{background:none;border:none;cursor:pointer;font-size:16px;color:#718096;
  border-radius:4px;padding:2px 6px}
.close-btn:hover{background:#e2e8f0}
.det-body{flex:1;overflow-y:auto;padding:16px}
.det-section{margin-bottom:18px}
.ds-title{font-size:11px;font-weight:700;color:#718096;text-transform:uppercase;
  letter-spacing:.5px;margin-bottom:8px}
.dr{display:flex;flex-direction:column;gap:2px;padding:6px 0;
  border-bottom:1px solid #f0f4f8}
.dr:last-child{border-bottom:none}
.dk{font-size:11px;color:#718096}
.dv{font-size:13px;word-break:break-word}
.mono{font-family:monospace;font-size:12px;background:#f8fafc;padding:8px;
  border-radius:4px;white-space:pre-wrap;margin-top:4px}

.overlay{position:fixed;inset:0;background:rgba(0,0,0,.25);z-index:190;display:none}
.overlay.open{display:block}

@media(max-width:680px){
  #pipeline-section{padding:12px 8px}
  .detail-panel{width:100vw;height:65vh;top:auto;bottom:0;
    box-shadow:0 -4px 24px rgba(0,0,0,.14);border-radius:12px 12px 0 0;
    transform:translateY(100%)}
  .detail-panel.open{transform:translateY(0)}
}
"""

# ── JavaScript ─────────────────────────────────────────────────────────────────

_JS = r"""
// ── Globals ───────────────────────────────────────────────────────────────────
let PD, COL_ITEMS, COL_ROW_OF, IS_HL = false, ZOOM = 1, ZOOM_W = 0, ZOOM_H = 0;

// ── Utilities ─────────────────────────────────────────────────────────────────
function esc(s){return String(s??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')}
function stripMd(s){
  s=String(s??'');
  // [text](url) → text  (well-formed)
  s=s.replace(/\[([^\]\n]+)\]\(https?:\/\/[^\)\s]+\)/g,'$1');
  // truncated/unclosed [text](url... → text
  s=s.replace(/\[([^\]\n]+)\]\(https?:\/\/[^\)\s]*/g,'$1');
  // **bold** → bold  (balanced first)
  s=s.replace(/\*\*(.+?)\*\*/g,'$1');
  // strip remaining unmatched **
  s=s.replace(/\*\*/g,'');
  // *italic* → italic
  s=s.replace(/\*([^*\n]+)\*/g,'$1');
  // `code` → code
  s=s.replace(/`([^`\n]+)`/g,'$1');
  return s;
}
function fmtTs(e){return e?new Date(e*1000).toLocaleString():'—'}
function byScore(a,b){return(b.score??-Infinity)-(a.score??-Infinity)}
function scoreDelta(p,c){
  if(p?.score==null||c?.score==null)return null;
  const d=c.score-p.score;
  return Math.abs(d)<0.005?null:(d>=0?'+':'')+d.toFixed(2);
}

// ── Layout ────────────────────────────────────────────────────────────────────
const CARD_H=78, ROW_STRIDE=88, HDR_H=56, COL_W=230, CONN_W=180, PAD_B=28;
function cx(col){return col*(COL_W+CONN_W)}
function cy(row){return HDR_H+row*ROW_STRIDE}

// ── Data processing ───────────────────────────────────────────────────────────
function processData(){
  const input=DATA.input||[], stages=DATA.stages||[];
  const inputById=Object.fromEntries(input.map(i=>[i.id,i]));
  const stageById=stages.map(s=>Object.fromEntries(s.output.map(i=>[i.id,i])));

  const mergedIntoMap={}, mergeStageMap={};
  for(let si=0;si<stages.length;si++)
    for(const item of stages[si].output)
      if(item.related_ids?.length){
        if(mergeStageMap[item.id]===undefined)mergeStageMap[item.id]=si;
        for(const rid of item.related_ids)if(!mergedIntoMap[rid])mergedIntoMap[rid]=item.id;
      }

  // Assign a unique color per merge group; singles get no entry (render gray)
  const _GC=['#8b5cf6','#06b6d4','#10b981','#f97316','#ec4899','#6366f1','#14b8a6','#f59e0b'];
  const groupColorOf={};
  {let ci=0; const seen={};
    for(let si=0;si<stages.length;si++)
      for(const item of stages[si].output)
        if(item.related_ids?.length&&!seen[item.id]){
          seen[item.id]=1;
          const c=_GC[ci++%_GC.length];
          groupColorOf[item.id]=c;
          for(const rid of item.related_ids)groupColorOf[rid]=c;
        }
  }

  const inputIdSet=new Set(input.map(i=>i.id));
  const lastIds=stages.length>0?new Set(stages[stages.length-1].output.map(i=>i.id)):inputIdSet;
  const allIds=new Set(inputIdSet);
  for(const s of stages)for(const item of s.output)allIds.add(item.id);
  const outcomes={};
  for(const id of allIds)outcomes[id]=lastIds.has(id)?'passed':mergedIntoMap[id]?'merged':'discarded';

  const stageStats=stages.map((s,si)=>{
    const prevIds=si===0?inputIdSet:new Set(stages[si-1].output.map(i=>i.id));
    const outIds=new Set(s.output.map(i=>i.id));
    const created=s.output.filter(i=>!prevIds.has(i.id)).length;
    const dropped=[...prevIds].filter(id=>!outIds.has(id)).length;
    return{prevCount:prevIds.size,outCount:s.output.length,created,dropped};
  });

  // sort_score per entity: last available score recorded for that ID.
  // Captured at the point the entity exits (dropped/merged/finally passed), so it
  // represents the score just before the exit event — stable across all columns.
  const lastScore={};
  for(const it of input)if(it.score!=null)lastScore[it.id]=it.score;
  for(const s of stages)for(const it of s.output)if(it.score!=null)lastScore[it.id]=it.score;

  // Cluster primary score: merge-source items adopt their merged item's sort_score as
  // primary key so the whole group sorts together. The merged item and standalone items
  // use their own score as primary. Within a cluster, secondary = individual sort_score.
  // Two-key (primary, secondary) tuple sort avoids any magic scaling factor.
  const clusterPrimary={};
  for(const [srcId,mId] of Object.entries(mergedIntoMap))
    clusterPrimary[srcId]=lastScore[mId]??-Infinity;

  // Drop stage: for discarded items, the first stage index where they disappeared.
  // dropStage[id] = 0 means dropped before stage 0 output; = N means dropped at stage N.
  const dropStage={};
  for(const id of allIds){
    if(outcomes[id]!=='discarded')continue;
    dropStage[id]=0;
    for(let si=0;si<stages.length;si++){
      if(stageById[si][id]!==undefined)dropStage[id]=si+1;
      else break;
    }
  }

  // Global section tier:
  //   0          — merge clusters (result + sources)
  //   1          — standalone pass-through items
  //   2 … 2+N   — dropped items, one tier per drop stage;
  //               items dropped LATER get a LOWER tier number → appear first among dropped.
  function sectionTier(id){
    if(mergeStageMap[id]!==undefined||mergedIntoMap[id])return 0;
    if(outcomes[id]==='passed')return 1;
    return 2+(stages.length-(dropStage[id]??0));
  }

  function globalCmp(a,b){
    const ta=sectionTier(a), tb=sectionTier(b);
    if(ta!==tb)return ta-tb;
    const pa=clusterPrimary[a]??lastScore[a]??-Infinity;
    const pb=clusterPrimary[b]??lastScore[b]??-Infinity;
    if(Math.abs(pa-pb)>1e-9)return pb-pa;
    // Within same cluster: merged result item floats to top (its row is empty before the
    // merge stage; placing it first avoids a gap appearing in the middle of the cluster).
    const sa=mergeStageMap[a]!==undefined?Infinity:(lastScore[a]??-Infinity);
    const sb=mergeStageMap[b]!==undefined?Infinity:(lastScore[b]??-Infinity);
    return sb-sa;
  }

  // Build a global row assignment: collect all IDs in first-appearance order,
  // then sort by (clusterPrimary, lastScore) desc — stable within ties.
  // Every column uses the same globalRow[id] so items never shift between stages.
  const allIdsOrdered=[];
  {const seen=new Set();
    for(const it of input)if(!seen.has(it.id)){allIdsOrdered.push(it.id);seen.add(it.id);}
    for(const s of stages)for(const it of s.output)if(!seen.has(it.id)){allIdsOrdered.push(it.id);seen.add(it.id);}
  }
  allIdsOrdered.sort(globalCmp);
  const globalRow=Object.fromEntries(allIdsOrdered.map((id,i)=>[id,i]));

  // Compute pixel Y for each id, inserting SECTION_GAP extra pixels at every tier boundary.
  const SECTION_GAP=44; // ~half a ROW_STRIDE; visually separates merge / pass / drop tiers
  let _yExtra=0, _prevTier=-1;
  const idY={};
  for(const id of allIdsOrdered){
    const t=sectionTier(id);
    if(t!==_prevTier)_yExtra+=SECTION_GAP;
    idY[id]=HDR_H+globalRow[id]*ROW_STRIDE+_yExtra;
    _prevTier=t;
  }
  const totalPixelH=allIdsOrdered.length>0
    ?(idY[allIdsOrdered[allIdsOrdered.length-1]]+CARD_H+PAD_B)
    :(HDR_H+PAD_B);

  // cols: items in each column sorted by their fixed global row (for render iteration)
  const cols=[[...input].sort((a,b)=>globalRow[a.id]-globalRow[b.id]),
    ...stages.map(s=>[...s.output].sort((a,b)=>globalRow[a.id]-globalRow[b.id]))];
  // colRowOf maps id → globalRow[id] — used for existence checks (null = not in this col)
  const colRowOf=cols.map(items=>Object.fromEntries(items.map(item=>[item.id,globalRow[item.id]])));

  return{input,stages,inputById,stageById,inputIdSet,outcomes,mergedIntoMap,mergeStageMap,stageStats,cols,colRowOf,groupColorOf,idY,totalPixelH};
}

// ── Input header ──────────────────────────────────────────────────────────────
function renderInputHeader(pd){
  const{input,outcomes}=pd;
  const nP=Object.values(outcomes).filter(o=>o==='passed').length;
  const nM=Object.values(outcomes).filter(o=>o==='merged').length;
  const nD=Object.values(outcomes).filter(o=>o==='discarded').length;
  document.getElementById('run-ts').textContent=DATA.run_ts?new Date(DATA.run_ts).toLocaleString():'';
  document.getElementById('input-summary').innerHTML=
    `Input: <b>${input.length}</b> items \u2014 `+
    `<span class="badge bp">${nP} passed</span> `+
    `<span class="badge bm">${nM} merged</span> `+
    `<span class="badge bd">${nD} discarded</span>`;
  const catCnt={},srcCnt={};
  for(const it of input){
    const c=it.category||'(none)';
    catCnt[c]=(catCnt[c]||0)+1;
    srcCnt[it.source_id]=(srcCnt[it.source_id]||0)+1;
  }
  const mkRows=obj=>Object.entries(obj).sort((a,b)=>b[1]-a[1])
    .map(([k,v])=>`<div class="stat-row"><span class="stat-k">${esc(k)}</span><span class="stat-v">${v}</span></div>`).join('');
  document.getElementById('input-detail').innerHTML=
    `<div class="sec-body-inner"><div class="input-stats">`+
    `<div><div class="sg-title">By Category</div>${mkRows(catCnt)}</div>`+
    `<div><div class="sg-title">By Source</div>${mkRows(srcCnt)}</div>`+
    `</div></div>`;
}

function toggleInput(){
  const c=document.getElementById('input-detail').classList.toggle('collapsed');
  document.getElementById('tog-icon').textContent=c?'\u25bc':'\u25b2';
}

// ── Pipeline grid ─────────────────────────────────────────────────────────────
function renderPipeline(pd){
  COL_ITEMS=pd.cols;
  COL_ROW_OF=pd.colRowOf;
  const{input,stages,stageStats,outcomes}=pd;
  const numCols=1+stages.length;
  const totalW=numCols*COL_W+(numCols-1)*CONN_W;
  const totalH=pd.totalPixelH||HDR_H+ROW_STRIDE+PAD_B;

  const cont=document.getElementById('pipeline-container');
  cont.style.width=totalW+'px';
  cont.style.height=totalH+'px';
  cont.style.transformOrigin='top left';
  cont.style.transform=`scale(${ZOOM})`;
  ZOOM_W=totalW; ZOOM_H=totalH;
  const wrap=document.getElementById('pipeline-zoom-wrap');
  wrap.style.width=Math.round(totalW*ZOOM)+'px';
  wrap.style.height=Math.round(totalH*ZOOM)+'px';
  cont.innerHTML='';
  cont.addEventListener('click',()=>clearHighlight());

  const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');
  svg.setAttribute('width',totalW);svg.setAttribute('height',totalH);
  svg.style.cssText='position:absolute;top:0;left:0;pointer-events:none;overflow:visible';
  svg.innerHTML=`<defs>
    <marker id="ma"   markerWidth="7" markerHeight="6" refX="5" refY="3" orient="auto"><path d="M0,0 L0,6 L7,3z" fill="context-stroke"/></marker>
    <marker id="md"   markerWidth="7" markerHeight="6" refX="5" refY="3" orient="auto"><path d="M0,0 L0,6 L7,3z" fill="var(--c-drop)"/></marker>
    <marker id="mahl" markerWidth="7" markerHeight="6" refX="5" refY="3" orient="auto"><path d="M0,0 L0,6 L7,3z" fill="#3b82f6"/></marker>
  </defs>`;
  cont.appendChild(svg);

  mkHdr(cont,-1,'INPUT',`${input.length} items`,0);
  for(const item of COL_ITEMS[0])
    mkCard(cont,item.id,item,COL_ROW_OF[0][item.id],0,outcomes[item.id]);

  for(let si=0;si<stages.length;si++){
    const ss=stageStats[si];
    const info=`${ss.outCount}/${ss.prevCount}`+(ss.created?` +${ss.created}\u2197`:'');
    mkHdr(cont,si,stages[si].type.replace(/_/g,' '),info,si+1);
    for(const item of COL_ITEMS[si+1])
      mkCard(cont,item.id,item,COL_ROW_OF[si+1][item.id],si+1,outcomes[item.id]);
  }

  requestAnimationFrame(()=>drawArrows(svg,pd));
}

function mkHdr(cont,si,lbl,info,col){
  const el=document.createElement('div');
  el.className='stage-hdr';
  el.style.cssText=`left:${cx(col)}px;top:4px;width:${COL_W}px;`;
  el.innerHTML=`<div class="hdr-type">${esc(lbl)}</div><div class="hdr-stats">${esc(info)}</div>`;
  if(si>=0)el.onclick=e=>{e.stopPropagation();showStageDetail(si)};
  cont.appendChild(el);
}

function mkCard(cont,id,item,row,col,outcome){
  const el=document.createElement('div');
  el.className=`item-card ${{passed:'op',merged:'om',discarded:'od'}[outcome]||'od'}`;
  el.dataset.id=id; el.dataset.col=col;
  el.style.cssText=`left:${cx(col)}px;top:${PD.idY[id]}px;width:${COL_W}px;height:${CARD_H}px;`;
  const sc=item.score;
  const scoreHtml=sc==null?'':`<span class="card-score ${sc>0.005?'sp':sc<-0.005?'sn':'sz'}">${(sc>=0?'+':'')+sc.toFixed(2)}</span>`;
  const sumDot=item.summary?`<span class="sum-dot" title="Has summary">\u03a3</span>`:'';
  el.innerHTML=`<div class="card-title">${esc(stripMd(item.title))}</div>`+
    `<div class="card-foot"><span class="card-src">${esc(item.source_id)}</span>${sumDot}${scoreHtml}</div>`;
  el.onclick=e=>{e.stopPropagation();highlightFlow(id);showItemDetail(id,col)};
  const _gc=PD.groupColorOf[id];
  if(_gc)el.style.borderLeftColor=_gc;
  cont.appendChild(el);
}

// ── Arrows ────────────────────────────────────────────────────────────────────
function drawArrows(svg,pd){
  const{stages,stageById,inputById,mergedIntoMap,mergeStageMap}=pd;
  let extra='';

  for(let si=0;si<stages.length;si++){
    const prevById=si===0?inputById:stageById[si-1];
    const currById=stageById[si];
    const prevIds=new Set(Object.keys(prevById));
    const currIds=new Set(Object.keys(currById));
    const stype=stages[si].type;
    const sc=si, dc=si+1;
    const x1=cx(sc)+COL_W, x2=cx(dc);

    // Pass-through arrows (items that will merge later still get arrows until the merge stage)
    for(const id of prevIds){
      if(!currIds.has(id))continue;
      if(COL_ROW_OF[sc][id]==null||COL_ROW_OF[dc][id]==null)continue;
      const y=PD.idY[id]+CARD_H/2;
      extra+=mkArrow(x1,y,x2,y,'pass',
        getLabel(prevById[id],currById[id],stype),id,id,sc,pd.groupColorOf[id]||null);
    }

    // Drop arrows (gone, not merged at this stage)
    for(const id of prevIds){
      if(currIds.has(id))continue;
      const mId=mergedIntoMap[id];
      if(mId&&mergeStageMap[mId]===si)continue;
      if(mId)continue;
      if(COL_ROW_OF[sc][id]==null)continue;
      const y=PD.idY[id]+CARD_H/2, midX=(x1+x2)/2;
      extra+=mkArrow(x1,y,midX,y,'drop',null,id,'__drop__',sc);
    }

    // Merge arrows: sources converge to merged item
    for(const item of stages[si].output){
      if(!item.related_ids?.length)continue;
      if(COL_ROW_OF[dc][item.id]==null)continue;
      const y2=PD.idY[item.id]+CARD_H/2;
      for(const srcId of item.related_ids){
        if(COL_ROW_OF[sc][srcId]==null)continue;
        extra+=mkArrow(x1,PD.idY[srcId]+CARD_H/2,x2,y2,'merge',null,srcId,item.id,sc,pd.groupColorOf[srcId]||null);
      }
    }
  }

  svg.innerHTML+=extra;

  // Attach click handlers to SVG groups (pointer-events enabled)
  svg.querySelectorAll('g.flow-arrow').forEach(g=>{
    g.style.pointerEvents='all';
    g.style.cursor='pointer';
    g.addEventListener('click',e=>{
      e.stopPropagation();
      const id=g.dataset.dstId==='__drop__'?g.dataset.srcId:g.dataset.srcId;
      highlightFlow(id);
    });
  });
}

function mkArrow(x1,y1,x2,y2,type,lbl,srcId,dstId,srcCol,groupColor){
  const isDrop=type==='drop';
  const color=isDrop?'var(--c-drop)':(groupColor||'#94a3b8');
  const marker=isDrop?'url(#md)':'url(#ma)';
  const dash=isDrop?'stroke-dasharray="5 4"':'';
  const op=isDrop?0.5:1;
  const dx=(x2-x1)*0.45;
  const d=`M${x1},${y1} C${x1+dx},${y1} ${x2-dx},${y2} ${x2},${y2}`;
  let g=`<g class="flow-arrow" data-src-id="${esc(srcId)}" data-dst-id="${esc(dstId)}" data-src-col="${srcCol}" data-type="${type}">`;
  // Wide transparent hit area
  g+=`<path d="${d}" fill="none" stroke="transparent" stroke-width="12"/>`;
  // Visual path — stores original attrs as data-* for restore
  g+=`<path class="ap" d="${d}" fill="none" stroke="${color}" stroke-width="1.5" ${dash} marker-end="${marker}" opacity="${op}" data-color="${color}" data-marker="${marker}" data-op="${op}"/>`;
  if(lbl){
    const lx=(x1+x2)/2, ly=(y1+y2)/2-5, tw=lbl.length*6.5+8;
    g+=`<rect class="alb" x="${lx-tw/2}" y="${ly-10}" width="${tw}" height="15" rx="3" fill="rgba(255,255,255,.92)"/>`;
    g+=`<text class="alt" x="${lx}" y="${ly+2}" text-anchor="middle" font-size="11" font-weight="600" fill="#374151">${esc(lbl)}</text>`;
  }
  if(isDrop)
    g+=`<text x="${x2+4}" y="${y1+5}" font-size="13" text-anchor="middle" fill="var(--c-drop)" opacity=".8">\u2717</text>`;
  g+=`</g>`;
  return g;
}

function getLabel(prev,curr,stype){
  if(!prev||!curr)return null;
  if(stype==='keyword_score'||stype==='openai_score')return scoreDelta(prev,curr);
  if((stype==='summarize'||stype==='openai_summarize')&&!prev.summary&&curr.summary)return '\u03a3';
  if(stype==='trim'&&prev.summary&&curr.summary&&curr.summary.length<prev.summary.length-10)return 'cut';
  return null;
}

// ── Highlight ─────────────────────────────────────────────────────────────────
function computeChain(startId){
  const nc=1+PD.stages.length, chain=[];
  // All columns where startId itself appears
  for(let c=0;c<nc;c++)if(COL_ROW_OF[c][startId]!=null)chain.push({id:startId,col:c});
  // Follow merged-into chain forward
  let curr=startId;
  while(PD.mergedIntoMap[curr]){
    const mId=PD.mergedIntoMap[curr];
    for(let c=0;c<nc;c++)if(COL_ROW_OF[c][mId]!=null)chain.push({id:mId,col:c});
    curr=mId;
  }
  // If startId is itself a merged result, include its source items too
  if(PD.mergeStageMap[startId]!=null){
    const si=PD.mergeStageMap[startId];
    const item=PD.stages[si].output.find(i=>i.id===startId);
    if(item)for(const srcId of(item.related_ids||[]))
      for(let c=0;c<=si;c++)if(COL_ROW_OF[c][srcId]!=null)chain.push({id:srcId,col:c});
  }
  return chain;
}

function highlightFlow(startId){
  IS_HL=true;
  const chain=computeChain(startId);
  const hlSet=new Set(chain.map(({id,col})=>`${id}::${col}`));

  // Cards
  document.querySelectorAll('.item-card').forEach(el=>{
    const isHl=hlSet.has(`${el.dataset.id}::${el.dataset.col}`);
    el.classList.toggle('dim',!isHl);
    el.classList.toggle('hl',isHl);
  });

  // Arrows
  document.querySelectorAll('g.flow-arrow').forEach(el=>{
    const srcId=el.dataset.srcId, dstId=el.dataset.dstId;
    const sc=+el.dataset.srcCol, dc=sc+1;
    const srcHl=hlSet.has(`${srcId}::${sc}`);
    const dstHl=dstId==='__drop__'?false:hlSet.has(`${dstId}::${dc}`);
    const isHl=srcHl&&(dstId==='__drop__'?true:dstHl);
    el.classList.toggle('dim',!isHl);
    const ap=el.querySelector('.ap');
    if(ap){
      ap.setAttribute('stroke',isHl?'#3b82f6':ap.dataset.color);
      ap.setAttribute('stroke-width',isHl?'2.5':'1.5');
      ap.setAttribute('marker-end',isHl?'url(#mahl)':ap.dataset.marker);
      ap.setAttribute('opacity',isHl?'1':ap.dataset.op);
    }
    const alb=el.querySelector('.alb'), alt=el.querySelector('.alt');
    if(alb)alb.setAttribute('fill',isHl?'rgba(219,234,254,.95)':'rgba(255,255,255,.92)');
    if(alt)alt.setAttribute('fill',isHl?'#1d4ed8':'#374151');
  });
}

function clearHighlight(){
  if(!IS_HL)return;
  IS_HL=false;
  document.querySelectorAll('.item-card').forEach(el=>el.classList.remove('dim','hl'));
  document.querySelectorAll('g.flow-arrow').forEach(el=>{
    el.classList.remove('dim');
    const ap=el.querySelector('.ap');
    if(ap){
      ap.setAttribute('stroke',ap.dataset.color);
      ap.setAttribute('stroke-width','1.5');
      ap.setAttribute('marker-end',ap.dataset.marker);
      ap.setAttribute('opacity',ap.dataset.op);
    }
    const alb=el.querySelector('.alb'), alt=el.querySelector('.alt');
    if(alb)alb.setAttribute('fill','rgba(255,255,255,.92)');
    if(alt)alt.setAttribute('fill','#374151');
  });
}

// ── Detail panels ─────────────────────────────────────────────────────────────
function showItemDetail(id,col){
  const item=col===0?PD.inputById[id]:(PD.stageById[col-1]||{})[id];
  if(!item)return;
  const outcome=PD.outcomes[id];
  const ctx=col===0?'Input state':`After: ${esc(PD.stages[col-1].type)}`;
  let html=`<div class="det-section"><div class="ds-title">${ctx}</div>`+
    dr('Outcome',`<span class="badge ${{passed:'bp',merged:'bm',discarded:'bd'}[outcome]||'bd'}">${outcome}</span>`)+
    dr('Title',esc(stripMd(item.title)))+
    dr('Source',`${esc(item.source_id)} (${esc(item.source_type)})`);
  if(item.category)html+=dr('Category',esc(item.category));
  if(item.score!=null)html+=dr('Score',item.score.toFixed(4));
  html+=dr('Published',fmtTs(item.published_ts));
  html+=dr('ID',`<code>${esc(item.id)}</code>`);
  if(item.url)html+=dr('URL',`<a href="${esc(item.url)}" target="_blank">${esc(item.url)}</a>`);
  html+=`</div>`;
  if(item.summary)
    html+=`<div class="det-section"><div class="ds-title">Summary</div><div class="dv mono">${esc(stripMd(item.summary))}</div></div>`;
  if(item.body)
    html+=`<div class="det-section"><div class="ds-title">Body</div><div class="dv mono">${esc(stripMd(item.body.slice(0,2000)))}${item.body.length>2000?'\n\u2026':''}</div></div>`;
  if(item.related_ids?.length){
    const refs=item.related_ids.map(rid=>{
      const ref=PD.inputById[rid];
      return`<div class="dr"><div class="dv">${esc(ref?stripMd(ref.title):rid)}</div></div>`;
    }).join('');
    html+=`<div class="det-section"><div class="ds-title">Merged from</div>${refs}</div>`;
  }
  openDetail(stripMd(item.title),html);
}

function showStageDetail(si){
  const stage=PD.stages[si], ss=PD.stageStats[si];
  const pct=ss.prevCount>0?Math.round(ss.outCount/ss.prevCount*100):0;
  let html=`<div class="det-section"><div class="ds-title">Stage ${si+1} \u2014 ${esc(stage.type)}</div>`+
    dr('Input items',ss.prevCount)+dr('Output items',ss.outCount)+
    dr('Dropped',ss.dropped)+dr('Pass rate',pct+'%');
  if(ss.created)html+=dr('Created (merged)',ss.created);
  html+=`</div>`;
  if(stage.config&&Object.keys(stage.config).length){
    html+=`<div class="det-section"><div class="ds-title">Config</div>`;
    for(const[k,v]of Object.entries(stage.config)){
      const vs=typeof v==='string'&&v.length>60?v:JSON.stringify(v);
      html+=`<div class="dr"><div class="dk">${esc(k)}</div><div class="dv${typeof v==='string'&&v.length>60?' mono':''}">${esc(vs)}</div></div>`;
    }
    html+=`</div>`;
  }
  openDetail(stage.type,html);
}

function dr(k,v){return`<div class="dr"><div class="dk">${k}</div><div class="dv">${v}</div></div>`}

function openDetail(title,body){
  document.getElementById('det-title').textContent=title;
  document.getElementById('det-body').innerHTML=body;
  document.getElementById('det-panel').classList.add('open');
  document.getElementById('overlay').classList.add('open');
}

function closeDetail(){
  document.getElementById('det-panel').classList.remove('open');
  document.getElementById('overlay').classList.remove('open');
  clearHighlight();
}

// ── Pinch zoom ────────────────────────────────────────────────────────────────
function initPinch(){
  const scroll=document.getElementById('pipeline-scroll');
  let d0=0,z0=1;
  function dist(t){return Math.hypot(t[1].clientX-t[0].clientX,t[1].clientY-t[0].clientY)}
  scroll.addEventListener('touchstart',e=>{
    if(e.touches.length===2){d0=dist(e.touches);z0=ZOOM;e.preventDefault()}
  },{passive:false});
  scroll.addEventListener('touchmove',e=>{
    if(e.touches.length!==2)return;
    e.preventDefault();
    ZOOM=Math.min(2.5,Math.max(0.25,z0*dist(e.touches)/d0));
    const wrap=document.getElementById('pipeline-zoom-wrap');
    const cont=document.getElementById('pipeline-container');
    wrap.style.width=Math.round(ZOOM_W*ZOOM)+'px';
    wrap.style.height=Math.round(ZOOM_H*ZOOM)+'px';
    cont.style.transform=`scale(${ZOOM})`;
  },{passive:false});
}

// ── Boot ──────────────────────────────────────────────────────────────────────
PD=processData();
renderInputHeader(PD);
renderPipeline(PD);
initPinch();
"""

# ── HTML template ──────────────────────────────────────────────────────────────

def _render_html(data: dict) -> str:
    data_json = json.dumps(data, ensure_ascii=False)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SmartReader Pipeline Report</title>
<style>{_CSS}</style>
</head>
<body>
<div id="app">
  <header id="top-bar">
    <span class="brand">SmartReader</span>
    <span class="sep">|</span>
    <span id="run-ts" class="run-ts"></span>
  </header>

  <div id="input-section">
    <button class="sec-toggle" onclick="toggleInput()">
      <span id="input-summary">Loading\u2026</span>
      <span id="tog-icon" class="tog-icon">\u25bc</span>
    </button>
    <div id="input-detail" class="sec-body collapsed"></div>
  </div>

  <div id="pipeline-section">
    <div id="pipeline-scroll">
      <div id="pipeline-zoom-wrap" style="position:relative;display:inline-block"><div id="pipeline-container"></div></div>
    </div>
  </div>
</div>

<div id="det-panel" class="detail-panel">
  <div class="det-hdr">
    <span id="det-title" class="det-title"></span>
    <button class="close-btn" onclick="closeDetail()">\u2715</button>
  </div>
  <div id="det-body" class="det-body"></div>
</div>
<div id="overlay" class="overlay" onclick="closeDetail()"></div>

<script>
const DATA = {data_json};
{_JS}
</script>
</body>
</html>"""
