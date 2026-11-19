import React,{useState,useEffect} from 'react';
import {createRoot} from 'react-dom/client';
import {MotionConfig} from 'motion/react';
import {ArrowRight,FolderOpen,ClockCounterClockwise} from '@phosphor-icons/react';
import './styles/style.css';
import brandIcon from './assets/peak-clip.png';
import './styles/refinement.css';
import './styles/channel-theme.css';
import './styles/studio.css';
import './styles/social.css';
import {Results} from './components/Results.jsx';
import {Profile} from './components/Profile.jsx';
import {History} from './components/History.jsx';
import {SubtitleSettings,defaultCaptions} from './components/SubtitleSettings.jsx';
import './styles/captions.css';

const call=(method,...args)=>window.pywebview?.api[method](...args);

function App(){
  const [form,setForm]=useState({
    url:'',folder:'',count:10,minimum:3,before:20,after:15,cut:true,
    folder_mode:'stream',folder_name:'',cleanup_temps:true,captions:false,caption_settings:{...defaultCaptions}
  });
  const [state,setState]=useState({busy:false,message:'Pega un enlace para comenzar.',clips:[],logs:[]});
  const [connected,setConnected]=useState(false);
  const [selected,setSelected]=useState(null);
  const [tint,setTint]=useState('15,118,110');
  const [streamTitle,setStreamTitle]=useState('');
  const [historyOpen,setHistoryOpen]=useState(false);

  useEffect(()=>{
    const timer=setInterval(async()=>{
      if(window.pywebview){
        setConnected(true);
        const s=await call('status');
        if(s) setState(s);
      }
    },500);
    return()=>clearInterval(timer);
  },[]);

  const field=(key,value)=>setForm(f=>({...f,[key]:value}));
  const folderPreview=form.folder_mode==='custom'&&form.folder_name.trim()
    ? form.folder_name.trim()
    :(streamTitle||'título del directo');

  return (
    <MotionConfig reducedMotion="user">
      <main style={{"--channel-rgb":tint}}>
        <div className="ambient" aria-hidden="true"/>
        <header>
          <span className="brand">
            <img src={brandIcon} alt="" width={32} height={32}/>
            Peak Clip
          </span>
          <div className="header-actions">
            <span className="muted">Clips desde el chat del directo</span>
            <button type="button" className="history-launch" disabled={!connected||state.busy} onClick={()=>setHistoryOpen(true)}>
              <ClockCounterClockwise size={16}/>
              Historial
            </button>
          </div>
        </header>

        <section className={selected?'intro compact-intro':'intro'}>
          <h1>Encuentra el momento<br/><span>y llévatelo listo para redes.</span></h1>
          <p className="muted">Pega un canal o una grabación de Twitch o Kick. Peak Clip marca los picos del chat y te deja los textos listos para copiar.</p>
        </section>

        <section className="source-panel">
          <div hidden={!!selected}>
            <label htmlFor="source">Enlace del canal o de la grabación</label>
            <div className="source-row">
              <input
                id="source"
                type="text"
                disabled={state.busy}
                placeholder="twitch.tv/canal · kick.com/canal · /videos/…"
                value={form.url}
                onChange={e=>{setSelected(null);setStreamTitle('');field('url',e.target.value)}}
              />
              <span>Twitch / Kick</span>
            </div>
            <p className="input-help">Acepta Twitch y Kick. La carpeta de destino se elige más abajo.</p>
          </div>
          {selected&&(
            <div className="source-selected-header">
              <span>Origen · {selected.platform==='kick'?'Kick':'Twitch'}</span>
              <button type="button" disabled={state.busy} onClick={()=>{setSelected(null);setStreamTitle('');field('url','')}}>Cambiar enlace</button>
            </div>
          )}
          <Profile
            url={form.url}
            connected={connected}
            busy={state.busy}
            onSelect={setSelected}
            onColor={setTint}
            onTitle={setStreamTitle}
          />
        </section>

        <div className="workspace">
          <form onSubmit={async e=>{
            e.preventDefault();
            if(!selected?.url) return;
            await call('start',{...form,url:selected.url});
          }}>
            <fieldset disabled={state.busy||!connected}>
              <h2 className="form-heading">Prepara tus clips</h2>

              <div className="sensitivity-field">
                <span className="field-label">Sensibilidad del chat</span>
                <div className="sensitivity" role="radiogroup" aria-label="Sensibilidad">
                  {[[3,'Estricta','3×'],[2,'Equilibrada','2×'],[1.5,'Amplia','1.5×']].map(([value,label,hint])=>(
                    <button
                      type="button"
                      role="radio"
                      aria-checked={form.minimum===value}
                      className={form.minimum===value?'chosen':''}
                      key={value}
                      onClick={()=>field('minimum',value)}
                    >
                      <strong>{label}</strong>
                      <span>{hint}</span>
                    </button>
                  ))}
                </div>
                <small>Un umbral menor encuentra más momentos, aunque pueden ser menos relevantes.</small>
              </div>

              <div className="numbers">
                {[['count','Máximo de clips',1,30],['before','Segundos antes',0,120],['after','Segundos después',1,120]].map(([key,title,min,max])=>(
                  <label key={key}>
                    {title}
                    <input type="number" min={min} max={max} required value={form[key]} onChange={e=>field(key,Number(e.target.value))}/>
                  </label>
                ))}
              </div>

              <div className="folder-naming">
                <span className="field-label">Carpeta dentro del canal</span>
                <div className="folder-mode" role="radiogroup" aria-label="Nombre de la carpeta">
                  <button type="button" role="radio" aria-checked={form.folder_mode==='stream'} className={form.folder_mode==='stream'?'chosen':''} onClick={()=>field('folder_mode','stream')}>
                    Usar título del directo
                  </button>
                  <button type="button" role="radio" aria-checked={form.folder_mode==='custom'} className={form.folder_mode==='custom'?'chosen':''} onClick={()=>field('folder_mode','custom')}>
                    Elegir otro nombre
                  </button>
                </div>
                {form.folder_mode==='custom'&&(
                  <label className="custom-folder-label">
                    Nombre de la carpeta
                    <input
                      type="text"
                      maxLength={80}
                      placeholder="Ej. highlights gta, clips abril…"
                      value={form.folder_name}
                      onChange={e=>field('folder_name',e.target.value)}
                      required
                    />
                  </label>
                )}
                <p className="folder-path-preview" title={'Canal / '+folderPreview}>
                  <FolderOpen size={14}/>
                  <span>canal</span>
                  <span className="crumb-divider">/</span>
                  <strong>{folderPreview}</strong>
                  <span className="crumb-divider">/</span>
                  <span>clips…</span>
                </p>
              </div>

              <label>
                Carpeta de destino
                <button type="button" className="folder" onClick={async()=>{
                  const folder=await call('folder');
                  if(folder) field('folder',folder);
                }}>
                  <FolderOpen size={20}/>
                  <span>{form.folder||state.default_folder||'Carpeta local de Peak Clip'}</span>
                </button>
              </label>
              <button className="local-folder" type="button" onClick={async()=>{field('folder',await call('default_folder'))}}>Usar carpeta local</button>

              <label className="check">
                <input type="checkbox" checked={form.cut} onChange={e=>field('cut',e.target.checked)}/>
                Generar vídeos verticales
                <small>Desactívalo para analizar solamente.</small>
              </label>

              <label className="check">
                <input type="checkbox" checked={form.cleanup_temps} onChange={e=>field('cleanup_temps',e.target.checked)}/>
                Borrar chat y temporales al terminar
                <small>Quita el chat descargado y la carpeta auxiliar. Los clips y sus textos se quedan.</small>
              </label>

              {form.cut&&<div className="caption-form-option">
                <label className="check"><input type="checkbox" checked={form.captions} onChange={e=>field('captions',e.target.checked)}/>Añadir subtítulos<small>Transcripción local. La primera vez se descarga el modelo de voz.</small></label>
                {form.captions&&<><SubtitleSettings compact value={form.caption_settings} onChange={v=>field('caption_settings',v)}/><p className="footnote">Se exporta una versión subtitulada. Después puedes corregir el texto y cambiar el estilo en cada clip.</p></>}
              </div>}
              <button className="primary" disabled={!selected?.url} type="submit">
                {state.busy?'Procesando…':form.cut?'Crear clips':'Analizar chat'}
                <ArrowRight size={20}/>
              </button>
            </fieldset>
            <p className="footnote">
              {selected?.url
                ?`Se guarda en canal / carpeta elegida (${selected.platform==='kick'?'Kick':'Twitch'}). Cada clip lleva fecha y hora; puedes copiar título, descripción y hashtags al compartir.`
                :'Selecciona una grabación para habilitar el análisis.'}
            </p>
          </form>
          <Results state={state} connected={connected}/>
        </div>
        <footer>Procesamiento local · Vertical 1080 × 1920 · Textos listos para copiar</footer>
        <History open={historyOpen} onClose={()=>setHistoryOpen(false)} busy={state.busy}/>
      </main>
    </MotionConfig>
  );
}

createRoot(document.getElementById('root')).render(<App/>);
