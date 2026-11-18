import React,{useEffect,useRef,useState} from 'react';
import {X,Copy,FloppyDisk,ArrowSquareOut,Check,FilmStrip} from '@phosphor-icons/react';

const names={youtube:'YouTube',tiktok:'TikTok',instagram:'Instagram',facebook:'Facebook'};
const api=(method,...args)=>window.pywebview.api[method](...args);

function pack(d){
  return [d.title,d.description,d.hashtags].filter(Boolean).join('\n\n');
}

export function ShareEditor({index,clip,onClose,status}){
  const dialog=useRef(null);
  const [tab,setTab]=useState('tiktok');
  const [drafts,setDrafts]=useState(null);
  const [basis,setBasis]=useState('');
  const [notice,setNotice]=useState('');
  const [accounts,setAccounts]=useState({});
  const [privacy,setPrivacy]=useState('private');
  const [kids,setKids]=useState(null);
  const [confirm,setConfirm]=useState(false);
  const [working,setWorking]=useState(false);
  const [copied,setCopied]=useState('');
  const [step,setStep]=useState(1);

  useEffect(()=>{
    const node=dialog.current;
    if(!node) return;
    if(typeof node.showModal==='function') node.showModal();
    else node.setAttribute('open','');
    api('social_draft',index).then(r=>{
      setDrafts(r.platforms);
      setBasis(r.basis?.note||'Revisa los textos antes de compartir.');
    }).catch(()=>setNotice('No se pudieron cargar los textos.'));
    api('social_accounts').then(setAccounts);
  },[index]);

  useEffect(()=>{
    if(!status?.busy) api('social_accounts').then(setAccounts);
  },[status?.busy]);

  const d=drafts?.[tab];
  const canPublish=tab==='youtube'&&accounts.youtube?.connected;
  const tagCount=d?.hashtags?d.hashtags.trim().split(/\s+/).filter(Boolean).length:0;
  const titleMax=tab==='youtube'?100:180;

  function edit(key,value){
    setConfirm(false);
    setCopied('');
    setDrafts(old=>({...old,[tab]:{...old[tab],[key]:value}}));
  }

  async function save(){
    if(!drafts) return false;
    const result=await api('save_social',index,drafts);
    setNotice(result.ok?'Textos guardados junto al clip.':result.error);
    return result.ok;
  }

  async function close(){
    if(working) return;
    if(drafts&&!await save()) return;
    onClose();
  }

  async function writeClipboard(text,okMessage,key=''){
    try{
      await navigator.clipboard.writeText(text);
    }catch{
      const el=document.createElement('textarea');
      el.value=text;
      dialog.current.appendChild(el);
      el.select();
      const ok=document.execCommand('copy');
      el.remove();
      if(!ok){
        setNotice('No se pudo copiar. Selecciona el texto y pulsa Ctrl+C.');
        return false;
      }
    }
    await save();
    setCopied(key||'all');
    setNotice(okMessage);
    if(key==='all'||!key) setStep(2);
    return true;
  }

  async function copyAll(){
    if(!d) return;
    await writeClipboard(
      pack(d),
      'Listo: publicación copiada. Ahora abre '+names[tab]+' y pega el texto al subir el vídeo.',
      'all'
    );
  }

  async function copyField(key,label){
    if(!d?.[key]){ setNotice('No hay '+label.toLowerCase()+' para copiar.'); return; }
    await writeClipboard(d[key],label+' copiado.',key);
  }

  async function openPlatform(){
    await api('share_portal',tab);
    setStep(3);
    setNotice('Abre el archivo del clip, súbelo y pega los textos copiados.');
  }

  return (
    <dialog ref={dialog} className="share-dialog" onCancel={e=>{e.preventDefault();close()}} aria-labelledby="share-title">
      <div className="share-shell">
        <div className="share-header">
          <div>
            <p className="share-kicker">Clip {String(clip.number).padStart(2,'0')} · {clip.time} → {clip.end}</p>
            <h2 id="share-title">Compartir en redes</h2>
          </div>
          <button type="button" className="share-close" aria-label="Guardar y cerrar" onClick={close}><X size={20}/></button>
        </div>

        <ol className="share-steps" aria-label="Pasos para publicar">
          <li className={step===1?'active':step>1?'done':''}><span>1</span>Edita y copia</li>
          <li className={step===2?'active':step>2?'done':''}><span>2</span>Abre la app</li>
          <li className={step===3?'active':''}><span>3</span>Pega y sube</li>
        </ol>

        <p className="share-lead">{basis}</p>

        <div className="platform-tabs" role="tablist" aria-label="Plataforma">
          {Object.entries(names).map(([key,name])=>(
            <button
              type="button"
              role="tab"
              aria-selected={tab===key}
              key={key}
              onClick={()=>{setTab(key);setConfirm(false);setNotice('');setCopied('');setStep(1)}}
            >{name}</button>
          ))}
        </div>

        {d&&<>
          <fieldset className="share-fields" disabled={working}>
            <label>
              <span className="field-head">Título o primera línea <span className="share-count">{d.title.length}/{titleMax}</span></span>
              <div className="field-with-copy">
                <input value={d.title} maxLength={titleMax} onChange={e=>edit('title',e.target.value)}/>
                <button type="button" className={'copy-chip'+(copied==='title'?' copied':'')} onClick={()=>copyField('title','Título')}>
                  {copied==='title'?<Check size={14}/>:<Copy size={14}/>}{copied==='title'?'Copiado':'Copiar'}
                </button>
              </div>
            </label>
            <label>
              <span className="field-head">Descripción</span>
              <div className="field-with-copy">
                <textarea value={d.description} maxLength={4500} rows={3} onChange={e=>edit('description',e.target.value)}/>
                <button type="button" className={'copy-chip'+(copied==='description'?' copied':'')} onClick={()=>copyField('description','Descripción')}>
                  {copied==='description'?<Check size={14}/>:<Copy size={14}/>}{copied==='description'?'Copiado':'Copiar'}
                </button>
              </div>
            </label>
            <label>
              <span className="field-head">Hashtags <span className="share-count">{tagCount}</span></span>
              <div className="field-with-copy">
                <textarea className="hashtag-box" value={d.hashtags} maxLength={500} rows={3} onChange={e=>edit('hashtags',e.target.value)}/>
                <button type="button" className={'copy-chip'+(copied==='hashtags'?' copied':'')} onClick={()=>copyField('hashtags','Hashtags')}>
                  {copied==='hashtags'?<Check size={14}/>:<Copy size={14}/>}{copied==='hashtags'?'Copiado':'Copiar'}
                </button>
              </div>
            </label>
          </fieldset>

          <div className="share-bar">
            <button type="button" className={'share-primary'+(copied==='all'?' done':'')} onClick={copyAll}>
              {copied==='all'?<Check size={18}/>:<Copy size={18}/>}
              {copied==='all'?'Publicación copiada':'Copiar título + descripción + #'}
            </button>
            <div className="share-bar-row">
              <button type="button" className={step>=2?'share-next':''} onClick={openPlatform}>
                <ArrowSquareOut size={16}/>Abrir {names[tab]}
              </button>
              <button type="button" onClick={()=>api('reveal',index)}><FilmStrip size={16}/>Mostrar vídeo</button>
              <button type="button" onClick={save}><FloppyDisk size={16}/>Guardar</button>
            </div>
            <p className="share-tip">
              {tab==='tiktok'
                ?'En TikTok pega el texto en la descripción. Incluye #fyp y #fy para el For You.'
                :tab==='youtube'
                  ?'En YouTube Shorts el título va aparte; los hashtags puedes pegarlos en la descripción.'
                  :'Copia, abre la app, adjunta el clip y pega. Abrir la web no vincula tu cuenta.'}
            </p>
          </div>

          <details className="account-panel" open={canPublish||undefined}>
            {tab==='youtube'?<>
              <summary>{accounts.youtube?.connected?'Canal de YouTube: '+accounts.youtube.name:'Publicar en YouTube (opcional)'}</summary>
              <p>Si no conectas YouTube, usa copiar y pegar en Studio. Para publicar desde Peak Clip necesitas un JSON OAuth de escritorio con YouTube Data API.</p>
              <div className="account-controls">
                <button type="button" disabled={status?.busy} onClick={async()=>{setNotice('Selecciona tu JSON OAuth de Google.');await api('connect_youtube')}}>
                  {accounts.youtube?.connected?'Cambiar canal':'Importar JSON y conectar'}
                </button>
                {accounts.youtube?.connected&&(
                  <button type="button" disabled={status?.busy} onClick={async()=>{await api('disconnect_youtube');setAccounts(await api('social_accounts'))}}>Desconectar</button>
                )}
              </div>
              {canPublish&&<>
                <p>Visibilidad</p>
                <div className="choice-row">
                  {[['private','Privado'],['unlisted','No listado'],['public','Público']].map(([key,name])=>(
                    <button type="button" aria-pressed={privacy===key} key={key} onClick={()=>{setPrivacy(key);setConfirm(false)}}>{name}</button>
                  ))}
                </div>
                <p>¿Este vídeo está creado específicamente para niños?</p>
                <div className="choice-row">
                  {[[false,'No'],[true,'Sí']].map(([key,name])=>(
                    <button type="button" key={name} aria-pressed={kids===key} onClick={()=>{setKids(key);setConfirm(false)}}>{name}</button>
                  ))}
                </div>
                <button type="button" disabled={kids===null||status?.busy||!d.title.trim()} onClick={()=>setConfirm(true)}>Preparar subida a YouTube</button>
                {confirm&&(
                  <div className="publish-confirm">
                    <p>Se enviará este clip al canal <strong>{accounts.youtube.name}</strong> con visibilidad <strong>{privacy==='public'?'pública':privacy==='private'?'privada':'no listada'}</strong>.</p>
                    <button type="button" disabled={status?.busy||working} onClick={async()=>{
                      setWorking(true);
                      try{ if(await save()) await api('publish_youtube',index,d,privacy,kids); setConfirm(false); }
                      finally{ setWorking(false); }
                    }}>Confirmar y enviar vídeo</button>
                  </div>
                )}
              </>}
            </>:<>
              <summary>Publicación manual en {names[tab]}</summary>
              <p>
                {tab==='tiktok'
                  ?'La publicación directa no está disponible sin una app aprobada por TikTok.'
                  :'La publicación directa requiere una app de Meta autorizada.'}
                {' '}Usa copiar → abrir → pegar. «Mostrar vídeo» selecciona el archivo en el Explorador.
              </p>
            </>}
          </details>
        </>}

        {(notice||status?.message)&&(
          <div className={'share-notice'+(copied?' copied-notice':'')} role="status">
            {notice&&<p>{notice}</p>}
            {status?.message&&<p>{status.message}</p>}
            {status?.url&&<a href={status.url} target="_blank" rel="noreferrer">Abrir vídeo en YouTube</a>}
          </div>
        )}
      </div>
    </dialog>
  );
}
