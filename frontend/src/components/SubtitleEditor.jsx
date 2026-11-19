import React,{useEffect,useRef,useState} from 'react';
import {X,Play,FloppyDisk,DownloadSimple,Plus,Trash,ClosedCaptioning} from '@phosphor-icons/react';
import {call} from '../lib/bridge';
import {SubtitleSettings,defaultCaptions} from './SubtitleSettings';
import '../styles/captions.css';

export function SubtitleEditor({index,clip,state,onClose}) {
  const dialog=useRef(null),video=useRef(null),revision=useRef(state.caption_status?.revision);
  const [document,setDocument]=useState(null),[url,setUrl]=useState(''),[original,setOriginal]=useState('');
  const [rendered,setRendered]=useState(false),[time,setTime]=useState(0),[notice,setNotice]=useState(''),[loading,setLoading]=useState(true),[saving,setSaving]=useState(false);
  const busy=state.busy||saving;
  const status=state.caption_status;
  const [duration,setDuration]=useState(clip.duration||0);
  useEffect(()=>{
    let alive=true;dialog.current.showModal();
    call('caption_open',index).then(r=>{
      if(!alive)return;
      if(!r.ok)throw new Error(r.error);
      setDocument(r.document||{version:1,language:'es',settings:{...defaultCaptions},cues:[]});
      setUrl(r.url);setOriginal(r.url);
      setDuration(r.duration||clip.duration);
    }).catch(e=>{if(alive)setNotice(e.message)}).finally(()=>{if(alive)setLoading(false)});
    return()=>{alive=false};
  },[index]);
  useEffect(()=>{
    if(status?.index!==index||status?.busy||status?.revision===revision.current)return;
    revision.current=status?.revision;
    if(status?.document)setDocument(status.document);
    if(status?.url){setUrl(status.url);setRendered(true);setTime(0)}
    if(status?.message)setNotice(status.message);
  },[status,index]);
  useEffect(()=>{
    let frame;
    const tick=()=>{if(video.current&&!video.current.paused)setTime(video.current.currentTime);frame=requestAnimationFrame(tick)};
    frame=requestAnimationFrame(tick);return()=>cancelAnimationFrame(frame);
  },[]);

  async function action(method,...args){
    setNotice('');setSaving(true);
    try{const result=await call(method,index,...args);if(!result?.ok)throw new Error(result?.error||'No se pudo completar la operación.');return result}
    catch(e){setNotice(e.message);return null}
    finally{setSaving(false)}
  }
  function editDocument(next){setDocument(next);if(rendered){setUrl(original);setRendered(false)}}
  function editCue(i,key,value){
    editDocument({...document,cues:document.cues.map((c,n)=>n===i?{...c,[key]:value,words:[]}:c)});
  }
  async function save(close=false){
    if(busy||!document)return;
    const result=await action('caption_save',document);
    if(result){setDocument(result.document);setNotice('Correcciones guardadas. Exporta para aplicarlas al vídeo.');if(close)onClose()}
  }
  function addCue(){
    const cues=[...document.cues];let start=0;
    for(const cue of cues){if(cue.start-start>=1)break;start=cue.end}
    const next=cues.find(c=>c.start>=start+1);
    const end=Math.min(start+2,next?.start??duration,duration);
    if(end-start<.1){setNotice('No queda espacio libre. Ajusta los tiempos de una frase existente.');return}
    cues.push({start,end,text:'Nueva frase',words:[]});cues.sort((a,b)=>a.start-b.start);editDocument({...document,cues});
  }
  const active=document?.cues.find(c=>time>=c.start&&time<c.end);
  const activeWords=active?.words?.length?active.words:active?.text.split(/\s+/).map((text,i,all)=>({text,start:active.start+i*(active.end-active.start)/all.length,end:active.start+(i+1)*(active.end-active.start)/all.length}));
  const config=document?.settings||defaultCaptions;
  return <dialog ref={dialog} className="caption-dialog" onCancel={e=>{e.preventDefault();if(!busy)save(true)}} aria-labelledby="caption-editor-title">
    <div className="caption-editor-head"><div><span className="caption-eyebrow">CLIP {String(clip.number).padStart(2,'0')} · ESTUDIO</span><h2 id="caption-editor-title">Dale voz al momento.</h2></div><button type="button" aria-label="Guardar y cerrar subtítulos" disabled={busy} onClick={()=>document?save(true):onClose()}><X size={20}/></button></div>
    {loading?<p className="caption-loading">Abriendo el clip…</p>:document&&<div className="caption-editor-layout">
      <aside className="caption-monitor">
        <div className="caption-screen">
          <video ref={video} key={url} src={url} controls playsInline preload="metadata" onTimeUpdate={e=>setTime(e.target.currentTime)} onError={()=>setNotice('No se pudo reproducir la vista previa. Comprueba que el archivo sigue en su carpeta.')}/>
          {!rendered&&active&&<div key={active.start} className={'live-caption live-'+config.template+(config.motion?' animated':'')} style={{top:{upper:'21.875%',middle:'50%',lower:'72.917%'}[config.position],fontSize:`${config.size/10.8}cqw`,'--caption-color':config.color}}>
            {activeWords?.map((w,i)=><React.Fragment key={i}><span className={config.motion&&config.template==='focus'&&time>=w.start&&time<w.end?'spoken':''}>{w.text}</span>{' '}</React.Fragment>)}
          </div>}
        </div>
        <p className="caption-monitor-label">{rendered?'Vídeo renderizado':'Guía en vivo · renderiza para comprobar el acabado'}</p>
        <div className="caption-monitor-actions"><button disabled={busy||!document.cues.length} onClick={()=>action('caption_export',document,true)}><Play size={15}/>Renderizar muestra</button>{rendered&&<button onClick={()=>{setUrl(original);setRendered(false)}}>Volver a editar</button>}</div>
        <p className="caption-help">La muestra usa los primeros 8 segundos. El original se conserva siempre.</p>
      </aside>
      <div className="caption-workbench">
        <fieldset disabled={busy}>
          <SubtitleSettings value={config} onChange={settings=>editDocument({...document,settings})}/>
          <div className="caption-transcript-head"><div><h3>Lo que se dice</h3><p>Corrige el texto y los tiempos en segundos.</p></div><button type="button" onClick={addCue}><Plus size={15}/>Frase</button></div>
          {!document.cues.length?<div className="caption-no-text"><ClosedCaptioning size={30}/><h3>Vamos a escuchar el clip.</h3><p>Transcripción en tu equipo, sin coste por minuto. La primera vez se descarga el modelo de voz.</p><button className="caption-transcribe" onClick={()=>action('caption_transcribe',config)}>Transcribir audio</button><small>También puedes añadir frases manualmente.</small></div>:<>
            <p className="caption-alignment-note">Al cambiar una frase, sus palabras se reparten dentro del intervalo. Revisa la sincronización al reproducir.</p>
            <div className="caption-cues">{document.cues.map((cue,i)=><div key={i} className={'caption-cue '+(active===cue?'current':'')}>
              <button className="cue-seek" aria-label={'Escuchar frase '+(i+1)} onClick={()=>{setRendered(false);setUrl(original);if(video.current){video.current.currentTime=cue.start;video.current.play().catch(()=>{})}}}>{String(i+1).padStart(2,'0')}<Play size={12}/></button>
              <div className="cue-content"><textarea aria-label={'Texto de frase '+(i+1)} maxLength={160} rows={2} value={cue.text} onChange={e=>editCue(i,'text',e.target.value)}/><div className="cue-times"><label>Inicio<input aria-label={'Inicio de frase '+(i+1)} type="number" min="0" max={duration} step="0.01" value={cue.start} onChange={e=>editCue(i,'start',Number(e.target.value))}/></label><span>→</span><label>Fin<input aria-label={'Fin de frase '+(i+1)} type="number" min="0" max={duration} step="0.01" value={cue.end} onChange={e=>editCue(i,'end',Number(e.target.value))}/></label></div></div>
              <button className="cue-remove" aria-label={'Eliminar frase '+(i+1)} onClick={()=>editDocument({...document,cues:document.cues.filter((_,n)=>n!==i)})}><Trash size={15}/></button>
            </div>)}</div>
          </>}
        </fieldset>
      </div>
    </div>}
    <div className="caption-editor-foot">
      <div className="caption-operation" role="status">{busy?<><span className="caption-spinner"/>{state.message}{state.stage_progress!=null&&<b>{Math.round(state.stage_progress)}%</b>}</>:notice||'Elige un estilo, revisa el texto y exporta.'}</div>
      <div className="caption-footer-actions">{state.caption_job&&state.busy?<button onClick={()=>call('cancel')}>Cancelar operación</button>:<><button disabled={busy||!document} onClick={()=>save()}><FloppyDisk size={17}/>Guardar texto</button><button className="caption-export" disabled={busy||!document?.cues.length} onClick={()=>action('caption_export',document,false)}><DownloadSimple size={18}/>Exportar subtitulado</button></>}</div>
    </div>
  </dialog>;
}
