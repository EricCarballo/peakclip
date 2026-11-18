import React,{useState,useEffect,useRef} from 'react';
import {Check,Users,ArrowClockwise} from '@phosphor-icons/react';
import {motion,AnimatePresence} from 'motion/react';
const num=n=>n==null?'No disponible':new Intl.NumberFormat('es',{notation:'compact',maximumFractionDigits:1}).format(n);
function videoStartUrl(platform,channel,video){
 if(video?.url) return video.url;
 if(platform==='kick') return `https://kick.com/${channel}/videos/${video.id}`;
 return `https://www.twitch.tv/videos/${video.id}`;
}
export function Profile({url,connected,onSelect,busy,onColor,onTitle}){
 const [data,setData]=useState(null),[error,setError]=useState(''),[loading,setLoading]=useState(false),[selected,setSelected]=useState(''),[expanded,setExpanded]=useState(true);
 const seq=useRef(0),changeButton=useRef(null),focusAfterChoice=useRef(false);
 function pick(video,platform,channel){
  setSelected(video.id);
  onSelect({
    id:video.id,
    url:videoStartUrl(platform,channel,video),
    platform:platform||'twitch',
    channel:channel||'',
  });
  onTitle?.(video.title||'');
 }
 async function load(id){
   setLoading(true);
   try{
     const r=await window.pywebview.api.inspect_link(url);
     if(seq.current!==id)return;
     if(!r.ok){setError(r.error);return}
     setData(r);if(r.channel?.color)onColor(r.channel.color);
     const platform=r.platform||r.channel?.platform||'twitch';
     if(r.kind==='video'){pick(r.videos[0],platform,r.channel?.login);setExpanded(false)}
   }catch{if(seq.current===id)setError('No pudimos consultar el canal. Reintenta en unos segundos.')}
   finally{if(seq.current===id)setLoading(false)}
 }
 useEffect(()=>{
   const id=++seq.current;setData(null);setError('');setSelected('');setExpanded(true);setLoading(false);onSelect(null);onTitle?.('');onColor('15,118,110');
   if(!url.trim()||!connected)return;
   const timer=setTimeout(()=>load(id),800);
   return()=>{clearTimeout(timer);seq.current++};
 },[url,connected]);
 function focusChoice(){if(focusAfterChoice.current&&changeButton.current){changeButton.current.focus();focusAfterChoice.current=false}}
 const ch=data?.channel, platform=data?.platform||ch?.platform||'twitch', chosen=data?.videos.find(v=>v.id===selected);
 function choose(v){pick(v,platform,ch?.login);focusAfterChoice.current=true;setExpanded(false)}
 function VideoInfo({v}){return <><img src={v.previewThumbnailURL} alt="" onError={e=>{e.target.style.visibility='hidden'}}/><div><strong>{v.title}</strong><small>{Math.floor(v.lengthSeconds/3600)} h {Math.floor(v.lengthSeconds%3600/60)} min · {num(v.viewCount)} vistas</small><small>{new Date(v.createdAt).toLocaleDateString('es')}</small></div></>}
 return <section className="profile">
 <div role="status">{loading&&<p className="loading">Consultando el canal y sus grabaciones…</p>}{error&&<div className="error">{error}<button type="button" onClick={()=>{setError('');load(++seq.current)}}>Reintentar</button></div>}</div>
 {ch&&<>
 <div className={'channel-top '+(chosen&&!expanded?'compact-channel':'')}>
 {ch.avatar?<img className="avatar" src={ch.avatar} alt={'Foto de '+ch.displayName}/>:<div className="avatar fallback">{ch.displayName[0]}</div>}
 <div className="channel-info"><h2>{ch.displayName} <span className="badge">{platform==='kick'?'Kick':'Twitch'} · {ch.stream?'En directo':'Sin emisión en vivo'}</span></h2><p>@{ch.login}</p>{expanded&&<p className="description">{ch.description||'Sin descripción.'}</p>}</div>
 <div className="followers"><Users size={20}/><strong>{num(ch.followers?.totalCount)}</strong><small>seguidores</small></div>
 </div>
 <AnimatePresence mode="wait" initial={false}>
 {!expanded&&chosen?<motion.div key="chosen" className="chosen-video" initial={{opacity:0,y:6}} animate={{opacity:1,y:0}} exit={{opacity:0}} transition={{duration:.2}} onAnimationComplete={focusChoice}>
 <div className="selection-label"><span><Check size={16} weight="bold"/> Grabación seleccionada</span><button ref={changeButton} type="button" disabled={busy} onClick={()=>setExpanded(true)}><ArrowClockwise size={16}/>Cambiar directo</button></div>
 <div className="chosen-summary"><VideoInfo v={chosen}/></div>
 </motion.div>:<motion.div key="choices" initial={{opacity:0,y:6}} animate={{opacity:1,y:0}} exit={{opacity:0}} transition={{duration:.18}}>
 {ch.stream&&<p className="live-note">{ch.stream.title} · {num(ch.stream.viewersCount)} espectadores</p>}
 <div className="recordings-head"><h3>Elige una grabación</h3><p>Al elegirla, esta lista se cerrará.</p>{chosen&&<button type="button" onClick={()=>setExpanded(false)}>Conservar selección</button>}</div>
 {!data.videos.length?<p>No hay grabaciones públicas disponibles en este canal.</p>:<div className="recordings" role="radiogroup" aria-label="Grabación">{data.videos.map(v=><button type="button" disabled={busy} role="radio" aria-checked={selected===v.id} key={v.id} className={'recording '+(selected===v.id?'selected':'')} onClick={()=>choose(v)}><VideoInfo v={v}/><span className="radio-dot">{selected===v.id&&<Check size={12}/>}</span></button>)}</div>}
 </motion.div>}
 </AnimatePresence>
 </>}
 </section>;
}
