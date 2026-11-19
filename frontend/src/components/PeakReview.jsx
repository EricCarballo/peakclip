import React,{useEffect,useState} from 'react';
import {Play} from '@phosphor-icons/react';
import {call} from '../lib/bridge';

export function PeakReview({state}){
  const peaks=state.peaks_preview||[];
  const heat=state.chat_heatmap||[];
  const [selected,setSelected]=useState(()=>new Set(peaks.filter(p=>p.selected!==false).map(p=>p.id)));
  useEffect(()=>{
    setSelected(new Set((state.peaks_preview||[]).filter(p=>p.selected!==false).map(p=>p.id)));
  },[state.peaks_preview,state.awaiting_peaks]);
  if(!state.awaiting_peaks||!peaks.length) return null;
  function toggle(id){
    setSelected(prev=>{
      const next=new Set(prev);
      if(next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }
  async function confirm(){
    const result=await call('confirm_peaks',[...selected]);
    if(!result?.ok) alert(result?.error||'No se pudo continuar.');
  }
  return <section className="peak-review" aria-label="Momentos detectados">
    <div className="peak-review-head">
      <div>
        <h3>Mapa del chat</h3>
        <p>Elige qué picos convertir en clips. Puedes quitar los que no aporten.</p>
      </div>
      <button type="button" className="peak-continue" disabled={!selected.size} onClick={confirm}>
        Continuar · {selected.size}
      </button>
    </div>
    {!!heat.length&&<div className="chat-heatmap" aria-hidden="true">
      {heat.map((value,i)=><span key={i} style={{opacity:Math.max(0.08,value),height:`${18+value*28}px`}}/>)}
      {peaks.map(peak=><i key={peak.id} className={selected.has(peak.id)?'on':''} style={{left:`${(peak.bucket/Math.max(heat.length-1,1))*100}%`}}/>)}
    </div>}
    <div className="peak-list">
      {peaks.map(peak=>(
        <label key={peak.id} className={'peak-item '+(selected.has(peak.id)?'chosen':'')}>
          <input type="checkbox" checked={selected.has(peak.id)} onChange={()=>toggle(peak.id)}/>
          <span className="peak-index">{String(peak.id).padStart(2,'0')}</span>
          <span className="peak-times"><Play size={12}/>{peak.time} → {peak.end}</span>
          <strong>{peak.strength}×</strong>
        </label>
      ))}
    </div>
  </section>;
}
