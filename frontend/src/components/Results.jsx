import React,{useEffect,useState} from 'react';
import {motion,AnimatePresence,useReducedMotion} from 'motion/react';
import {FolderOpen,Play,ArrowSquareOut,CheckCircle,Waveform,Clock,FilmStrip,Scissors,Check,WarningCircle,Trash,ArrowClockwise} from '@phosphor-icons/react';
import {ShareEditor} from './ShareEditor.jsx';
import {SubtitleEditor} from './SubtitleEditor.jsx';
import {PeakReview} from './PeakReview.jsx';
const call=(method,...args)=>window.pywebview?.api[method](...args);
const stages={transcribe:'Transcribiendo voz',caption_render:'Renderizando subtítulos',prepare:'Preparación',chat:'Descargando chat',peaks:'Revisar momentos',analyze:'Analizando reacciones',download:'Descargando fragmento',encode:'Creando vídeo vertical',thumbnail:'Preparando miniatura',saved:'Clip guardado',done:'Proceso completado',error:'Necesita atención',cancelled:'Proceso pausado'};
function elapsed(seconds){const s=Math.max(0,Math.floor(seconds));return Math.floor(s/60)+':'+String(s%60).padStart(2,'0')}
function Activity({state}){
 const [now,setNow]=useState(Date.now());const reduced=useReducedMotion();
 useEffect(()=>{if(!state.busy&&!state.awaiting_peaks)return;setNow(Date.now());const id=setInterval(()=>setNow(Date.now()),1000);return()=>clearInterval(id)},[state.busy,state.awaiting_peaks]);
 const steps=[['chat','Chat'],['peaks','Momentos'],['download','Fragmento'],['encode','Vertical'],['saved','Guardado']];
 const order=['prepare','chat','analyze','peaks','download','encode','thumbnail','saved','done'];
 const position=order.indexOf(state.stage),pct=state.stage_progress;
 return <motion.section className={'activity-panel '+(state.stage==='done'?'settled':'')} initial={{opacity:0,y:8}} animate={{opacity:1,y:0}} aria-label="Progreso de creación">
 <div className="activity-heading"><div className="activity-symbol">{state.stage==='error'?<WarningCircle size={23}/>:state.busy||state.awaiting_peaks?<Scissors size={23}/>:<CheckCircle size={23}/>}</div><div><span className="activity-label">{state.busy?'EN PROCESO':state.awaiting_peaks?'REVISAR':state.stage==='error'?'REVISAR':'ACTIVIDAD'}</span><h3>{stages[state.stage]||'Preparando clips'}</h3></div>{state.started_at&&<span className="elapsed"><Clock size={14}/>{elapsed(now/1000-state.started_at)}</span>}</div>
 <div className="stage-steps">{steps.map(([key,label])=><span key={key} className={key===state.stage?'active':position>order.indexOf(key)?'passed':''}>{position>order.indexOf(key)?<Check size={12}/>:<span className="step-point"/>}{label}</span>)}</div>
 {state.rate_limited&&<p className="rate-limit-banner" role="status">Kick está limitando peticiones. Peak Clip frena solo y reintenta; la ETA puede alargarse.</p>}
 <p className="activity-message" role="status">{state.message}</p>
 {(state.busy||state.stage==='chat')&&<><div className="stage-metrics"><span>{state.current?`Clip ${state.current} de ${state.total}`:state.stage==='chat'?'Descarga del chat':'Preparando tu selección'}</span><strong>{pct==null?'En curso':Math.round(pct)+'%'}</strong></div><div className={'progress-track '+(pct==null?'indeterminate':'')} role="progressbar" aria-label={stages[state.stage]} aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct==null?undefined:Math.round(pct)}><motion.div style={{transformOrigin:'left'}} animate={pct==null?(reduced?{x:'0%'}:{x:['-100%','350%']}):{scaleX:Math.max(0,pct)/100,x:0}} transition={pct==null?{duration:1.8,repeat:Infinity,ease:'easeInOut'}:{duration:.4}}/></div><div className="stage-footer"><span>{state.stage==='chat'?(state.eta?`Restante ${state.eta}`:'Calculando tiempo…'):`${state.completed||0} de ${state.total||'…'} clips listos`}</span><span>{state.speed&&`Velocidad ${state.speed}`}{state.stage!=='chat'&&state.eta&&` · Restante ${state.eta}`}</span></div></>}
 {!!state.events?.length&&<ol className="activity-feed" aria-label="Últimas acciones"><AnimatePresence initial={false}>{state.events.slice(-4).map(e=><motion.li key={e.id} initial={{opacity:0,y:6}} animate={{opacity:1,y:0}} exit={{opacity:0}} transition={{duration:.2}}><time>{e.time}</time><span>{e.text}</span></motion.li>)}</AnimatePresence></ol>}
 {(state.busy||state.awaiting_peaks)&&<button className="cancel" onClick={()=>call('cancel')}>Pausar proceso</button>}
 {!state.busy&&state.resumable&&<button className="resume-action" onClick={()=>call('resume')}><ArrowClockwise size={16}/>Reanudar</button>}
 </motion.section>;
}
export function Results({state,connected}){
 const [sharing,setSharing]=useState(null);
 const [editing,setEditing]=useState(null);
 const [cleaning,setCleaning]=useState(false);
 const ready=state.clips.filter(c=>c.ready).length;
 const canClean=connected&&!state.busy&&state.temps_available&&state.output_folder&&!state.output_error;
 async function cleanTemps(){
  if(cleaning||!canClean)return;
  setCleaning(true);
  try{await call('cleanup_temps')}finally{setCleaning(false)}
 }
 return <section className="results redesigned-results"><div className="result-head"><div><h2>Tus clips <span className="result-count">{state.clips.length}</span></h2><p>{ready?'Listos para ver, revisar y compartir.':'Los momentos que merecen volver a verse.'}</p></div><div className="result-head-actions"><button onClick={()=>call('open_folder')} disabled={!connected}><FolderOpen size={18}/>Abrir carpeta</button>{canClean&&<button type="button" className="cleanup-action" disabled={cleaning} onClick={cleanTemps}><Trash size={18}/>{cleaning?'Eliminando…':'Borrar chat y temporales'}</button>}</div></div>
 {state.stage&&state.stage!=='idle'?<Activity state={state}/>:<p className="results-status" role="status">{connected?state.message:'Conectando con Peak Clip…'}</p>}
 <PeakReview state={state}/>
 {state.output_error&&<p className="destination-warning">Selecciona «Usar carpeta local» y vuelve a crear los clips.</p>}
 {state.output_folder&&!state.output_error&&<div className="destination-breadcrumb" title={state.output_folder}><FolderOpen size={16}/><span>{state.channel||'Canal'}</span><span className="crumb-divider">/</span><strong>{state.folder_label||state.video_title||'Grabación'}</strong>{state.from_history&&<span className="history-badge">Historial</span>}</div>}
 {canClean&&<p className="cleanup-hint">Quedan el chat y archivos auxiliares de esta sesión. Puedes borrarlos: los clips y los textos se conservan.</p>}
 {!state.clips.length&&!state.busy?<div className="empty"><Waveform size={64} weight="thin"/><h3>Todavía no hay clips.</h3><p>Elige un directo, ajusta la sensibilidad<br/>y crea los momentos del chat.</p></div>:<div className="clip-gallery">
 {state.clips.map((c,i)=><motion.section className="clip-card" key={c.filename||c.number} initial={{opacity:0,y:16}} animate={{opacity:1,y:0}} transition={{duration:.35}}>
 <button className="clip-preview" disabled={!c.ready} onClick={()=>call('play',i)} aria-label={'Reproducir clip '+c.number}>{c.thumbnail?<img src={c.thumbnail} alt={'Fotograma del clip '+c.number}/>:<div className="preview-placeholder"><FilmStrip size={38}/><span>{c.ready?'Vista previa no disponible':'Momento detectado'}</span></div>}{c.ready&&<span className="preview-play"><Play size={22} weight="fill"/></span>}<span className="preview-duration">{c.duration||'—'} s</span><span className="preview-format">9:16</span></button>
 <div className="clip-body"><div className="clip-title-row"><h3>Clip {String(c.number).padStart(2,'0')}</h3><span className={'clip-state '+(c.ready?'ready':'')}>{c.ready?<><CheckCircle size={13} weight="fill"/>Guardado</>:'Analizado'}</span></div><p className="clip-time">{c.time}<span>→</span>{c.end}</p><div className="clip-stats"><span><Waveform size={15}/>{c.strength}× actividad</span>{c.size_bytes&&<span>{(c.size_bytes/1048576).toFixed(1)} MB</span>}</div>{c.created_at&&<p className="clip-date">Creado {new Date(c.created_at).toLocaleString('es',{day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit',second:'2-digit'})}</p>}<div className="clip-actions">{c.ready&&<button onClick={()=>call('play',i)} className="play-action"><Play size={15} weight="fill"/>Ver clip</button>}<button onClick={()=>call('twitch',i)}><ArrowSquareOut size={15}/>{c.platform==='kick'?'Kick':'Twitch'}</button>{c.ready&&<button title="Mostrar archivo en su carpeta" aria-label={'Mostrar archivo del clip '+c.number} onClick={()=>call('reveal',i)}><FolderOpen size={16}/></button>}</div>{c.ready&&<button className="caption-launch" disabled={state.busy} onClick={()=>setEditing(i)}>{c.caption_path?'Editar subtítulos':'Añadir subtítulos'}</button>}{c.ready&&<button disabled={state.busy} className="share-button" onClick={()=>setSharing(i)}>Copiar textos / compartir</button>}</div>
 </motion.section>)}
 {state.busy&&<div className="pending-clip"><div className="pending-lines"><i/><i/><i/><i/><i/></div><strong>{state.current?`Preparando clip ${state.current}`:'Escuchando al chat'}</strong><span>{stages[state.stage]}</span></div>}
 </div>}
 {!!state.logs?.length&&<details className="diagnostic-log" open={state.stage==='error'}><summary>Registro completo para diagnóstico</summary><pre>{state.logs.join('\n')}</pre></details>}
 {sharing!==null&&state.clips[sharing]&&<ShareEditor index={sharing} clip={state.clips[sharing]} status={state.social_status} onClose={()=>setSharing(null)}/>}
 {editing!==null&&state.clips[editing]&&<SubtitleEditor index={editing} clip={state.clips[editing]} state={state} onClose={()=>setEditing(null)}/>}
 </section>;
}
