import React, {useEffect, useState} from 'react';
import {call} from '../lib/bridge';

export const defaultCaptions = {template:'focus', size:76, color:'#F8D34F', position:'lower', motion:true};

export function SubtitleSettings({value, onChange, compact=false}) {
  const [templates,setTemplates]=useState([]);
  const [error,setError]=useState('');
  useEffect(()=>{let alive=true;call('caption_catalog').then(t=>{if(alive)setTemplates(t)}).catch(()=>{if(alive)setError('No se pudieron cargar las plantillas.')});return()=>{alive=false}},[]);
  const change=(key,v)=>onChange({...value,[key]:v});
  return <div className={'subtitle-settings '+(compact?'compact-settings':'')}>
    <div className="caption-section-title"><strong>Estilo del subtítulo</strong><span>Muestras de estilo</span></div>
    {error&&<p role="alert">{error}</p>}
    <div className="caption-templates" role="radiogroup" aria-label="Plantilla de subtítulos">
      {templates.map(t=><button type="button" role="radio" aria-checked={value.template===t.id} key={t.id} className={'caption-template '+(value.template===t.id?'chosen':'')} onClick={()=>onChange({...value,template:t.id,size:t.size})}>
        <span className={'caption-sample sample-'+t.id+(value.motion?'':' still')} aria-hidden="true" style={{'--caption-color':value.color}}><span>ESTE ES</span> <b>EL MOMENTO</b></span>
        <span className="template-name">{t.name}</span>{!compact&&<small>{t.description}</small>}
      </button>)}
    </div>
    {!compact&&<>
      <div className="caption-controls">
        <label>Tamaño <span>{value.size}</span><input aria-label="Tamaño del subtítulo" type="range" min="44" max="110" value={value.size} onChange={e=>change('size',Number(e.target.value))}/></label>
        <label className="caption-color">Color de énfasis<input type="color" value={value.color} onChange={e=>change('color',e.target.value)}/></label>
      </div>
      <div className="caption-position" role="radiogroup" aria-label="Posición de subtítulos">{[['upper','Arriba'],['middle','Centro'],['lower','Abajo']].map(([v,n])=><button type="button" key={v} role="radio" aria-checked={value.position===v} onClick={()=>change('position',v)}>{n}</button>)}</div>
      <label className="caption-motion"><input type="checkbox" checked={value.motion} onChange={e=>change('motion',e.target.checked)}/> Animación y palabra activa</label>
    </>}
  </div>;
}
