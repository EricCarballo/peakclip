import React,{useEffect,useState} from 'react';
import {ClockCounterClockwise,X,FolderOpen,FilmStrip} from '@phosphor-icons/react';

const call=(method,...args)=>window.pywebview?.api[method](...args);

function when(value){
  if(!value) return '';
  try{
    return new Date(value).toLocaleString('es',{day:'2-digit',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit'});
  }catch{
    return value;
  }
}

export function History({open,onClose,busy}){
  const [items,setItems]=useState([]);
  const [loading,setLoading]=useState(false);
  const [error,setError]=useState('');
  const [opening,setOpening]=useState('');

  useEffect(()=>{
    if(!open) return;
    let alive=true;
    (async()=>{
      setLoading(true); setError('');
      try{
        const result=await call('history_list');
        if(!alive) return;
        if(!result?.ok){ setError(result?.error||'No se pudo cargar el historial.'); setItems([]); }
        else setItems(result.items||[]);
      }catch{
        if(alive){ setError('No se pudo cargar el historial.'); setItems([]); }
      }finally{
        if(alive) setLoading(false);
      }
    })();
    return()=>{alive=false};
  },[open]);

  if(!open) return null;

  async function openSession(path){
    if(busy||opening) return;
    setOpening(path); setError('');
    try{
      const result=await call('history_open',path);
      if(!result?.ok){ setError(result?.error||'No se pudo abrir la sesión.'); return; }
      onClose();
    }catch{
      setError('No se pudo abrir la sesión.');
    }finally{
      setOpening('');
    }
  }

  return (
    <div className="history-overlay" role="dialog" aria-modal="true" aria-label="Historial de clips" onClick={onClose}>
      <div className="history-panel" onClick={e=>e.stopPropagation()}>
        <div className="history-head">
          <div>
            <span className="history-kicker"><ClockCounterClockwise size={16}/>Historial</span>
            <h2>Sesiones anteriores</h2>
            <p>Vuelve a una carpeta de clips para copiar títulos, descripciones y hashtags.</p>
          </div>
          <button type="button" className="history-close" onClick={onClose} aria-label="Cerrar historial"><X size={18}/></button>
        </div>
        {error&&<p className="history-error" role="alert">{error}</p>}
        {loading?<p className="history-empty">Cargando sesiones…</p>:!items.length?<div className="history-empty"><FilmStrip size={42} weight="thin"/><p>Todavía no hay sesiones guardadas. Cuando generes clips, aparecerán aquí.</p></div>:(
          <ul className="history-list">
            {items.map(item=>(
              <li key={item.path}>
                <div>
                  <strong>{item.channel||'Canal'}</strong>
                  <span className="history-meta">{item.platform==='kick'?'Kick':'Twitch'} · {item.clips} clip{item.clips===1?'':'s'}</span>
                  <p title={item.title}>{item.folder_label||item.title}</p>
                  <time dateTime={item.updated_at}>{when(item.updated_at)}</time>
                </div>
                <button type="button" disabled={busy||!!opening} onClick={()=>openSession(item.path)}>
                  <FolderOpen size={16}/>
                  {opening===item.path?'Abriendo…':'Abrir'}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
