import os, sys, re, threading, subprocess, shutil, json
from pathlib import Path
import webview
from datetime import datetime
import base64, time
import traceback

from peakclip.domain import chat_analysis as engine
from peakclip.domain.progress import telemetry
from peakclip.platforms import channel, kick
from peakclip.infrastructure.storage import (
    DEFAULT_OUTPUT, OutputError, prepare_output, session_directory, file_stamp,
    cleanup_workspace, temps_present, save_session, list_history, load_history,
    save_resume, load_resume, clear_resume, chat_progress_file,
)
from peakclip.infrastructure.tools import ensure_tools_on_path
from peakclip.social import drafts as social
from peakclip.social import youtube as youtube_share

DATA = DEFAULT_OUTPUT
window = None

class API:
    def __init__(self):
        self.lock=threading.Lock(); self.cancelled=threading.Event(); self.process=None
        self.state={'busy':False,'message':'Pega un enlace para comenzar.','clips':[],'logs':[],'output_error':False,'default_folder':str(DATA),'output_folder':None,'temps_available':False}
        self.metadata={}
        self.publish_lock=threading.Lock()
        self.state['social_status']={'busy':False,'message':''}
        self.state.update(stage='idle',stage_progress=None,current=0,total=0,completed=0,events=[],speed='',eta='',started_at=None,resumable=False)
        self.job=None
    def default_folder(self):
        return str(DATA)
    def status(self):
        with self.lock: return json.loads(json.dumps(self.state))
    def update(self,**values):
        with self.lock: self.state.update(values)
    def folder(self):
        result=window.create_file_dialog(webview.FileDialog.FOLDER)
        return result[0] if result else ''
    def inspect_link(self,value):
        try:
            result=channel.inspect(value)
            platform=result.get('platform') or result['channel'].get('platform') or 'twitch'
            with self.lock:
                for video in result['videos']:
                    self.metadata[video['id']]={
                        'channel':result['channel']['login'],
                        'title':video['title'],
                        'platform':platform,
                        'source':video.get('source') or '',
                        'channel_id':video.get('channel_id') or result['channel'].get('channel_id'),
                        'start_time':video.get('start_time') or video.get('createdAt') or '',
                        'duration':video.get('lengthSeconds') or 0,
                        'url':video.get('url') or '',
                        'is_live':bool(video.get('is_live')),
                    }
            return {'ok':True,**result}
        except ValueError as e: return {'ok':False,'error':str(e)}
        except kick.KickError as e: return {'ok':False,'error':str(e)}
        except Exception: return {'ok':False,'error':'No pudimos consultar el canal. Comprueba tu conexión y vuelve a intentarlo.'}
    def open_folder(self):
        try:
            target=getattr(self,'output',DATA)
            target.mkdir(parents=True,exist_ok=True)
            os.startfile(str(target))
        except OSError:
            self.update(message='No se puede abrir la carpeta. Elige una carpeta local disponible.',output_error=True)
    def cancel(self):
        self.cancelled.set()
        self.update(message='Pausando. Guardamos el progreso para poder reanudar.')
        if self.process and self.process.poll() is None:
            subprocess.run(['taskkill','/PID',str(self.process.pid),'/T','/F'],creationflags=subprocess.CREATE_NO_WINDOW,capture_output=True)
    def phase(self,stage,message,**values):
        with self.lock:
            event={'id':str(time.time_ns()),'time':datetime.now().strftime('%H:%M:%S'),'text':message}
            self.state['events']=(self.state['events']+[event])[-12:]
            self.state.update(stage=stage,message=message,stage_progress=None,speed='',eta='',**values)
    def public_error(self,exc):
        """Keep technical HTTP/network codes out of the main status line."""
        if isinstance(exc,kick.KickError): return str(exc)
        msg=str(exc or '').strip()
        low=msg.lower()
        if '429' in msg or 'too many requests' in low:
            return 'Kick está limitando las peticiones ahora mismo. Espera un minuto y vuelve a intentarlo.'
        if re.search(r'http\s*error\s*\d+',low) or re.search(r'\b[45]\d{2}\b',msg):
            return 'Kick no respondió bien. Espera un momento y vuelve a intentarlo.'
        if 'timed out' in low or 'urlopen' in low or 'getaddrinfo' in low or 'connection' in low:
            return 'No hay respuesta de la red. Comprueba tu conexión e inténtalo de nuevo.'
        if msg and 'traceback' not in low and len(msg)<180:
            return msg
        return 'Algo falló al procesar el directo. Inténtalo de nuevo.'
    def run(self,args,stage=None,duration=0):
        if self.cancelled.is_set(): raise RuntimeError('Proceso cancelado.')
        self.process=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',creationflags=subprocess.CREATE_NO_WINDOW)
        for line in self.process.stdout:
            with self.lock: self.state['logs']=(self.state['logs']+[line.strip()])[-100:]
            if stage:
                values=telemetry(line.strip(),stage,duration)
                if values: self.update(**values)
        code=self.process.wait()
        if self.cancelled.is_set(): raise RuntimeError('Proceso cancelado.')
        if code: raise RuntimeError('La herramienta no pudo completar la operación. Consulta los detalles; el vídeo puede no estar disponible.')
    def start(self,options):
        if self.state['busy']: return False
        try:
            platform,kind,vod=channel.parse_link(options['url'])
            if kind!='video': raise ValueError('Elige una grabación del canal antes de generar clips.')
            for key,lo,hi in [('count',1,30),('before',0,120),('after',1,120)]:
                if not lo<=int(options[key])<=hi: raise ValueError(f'El valor de {key} debe estar entre {lo} y {hi}.')
            if float(options['minimum']) not in (1.5,2,3): raise ValueError('Selecciona una sensibilidad válida.')
            if options['folder'] and (not Path(options['folder']).is_absolute() or '://' in options['folder']): raise ValueError('Elige una carpeta local válida para guardar los clips.')
            mode=str(options.get('folder_mode') or 'stream')
            if mode not in ('stream','custom'): raise ValueError('Elige cómo nombrar la carpeta del directo.')
            if mode=='custom' and not str(options.get('folder_name') or '').strip():
                raise ValueError('Escribe un nombre para la carpeta dentro del canal, o usa el título del directo.')
            if platform=='kick' and vod in self.metadata:
                meta=self.metadata.get(vod) or {}
                if meta.get('is_live'):
                    raise ValueError('Ese directo de Kick sigue en vivo. Espera a que termine para crear clips.')
                if int(meta.get('duration') or 0)<60:
                    raise ValueError('Elige un directo de Kick ya terminado. Los que siguen en vivo no sirven para clips.')
        except (ValueError,KeyError,TypeError) as e:
            self.update(message=str(e)); return False
        with self.lock:
            if self.state['busy']: return False
            self.state['busy']=True
        self.cancelled.clear()
        self.job={'platform':platform,'vod':vod,'options':options.copy(),'resume':False}
        self.update(clips=[],logs=[],events=[],output_error=False,output_folder=None,temps_available=False,resumable=False,stage='prepare',stage_progress=None,current=0,total=0,completed=0,speed='',eta='',started_at=time.time(),message='Comprobando la carpeta de destino…')
        threading.Thread(target=self.work,args=(platform,vod,options.copy(),False),daemon=True).start(); return True
    def resume(self):
        if self.state.get('busy'): return False
        folder=getattr(self,'output',None)
        job=load_resume(folder) if folder else None
        if not job and self.job and self.job.get('options'):
            job=self.job
        if not job or not job.get('options') or not job.get('vod'):
            self.update(message='No hay un proceso para reanudar. Vuelve a crear los clips.')
            return False
        platform=job.get('platform') or 'twitch'
        vod=job.get('vod')
        options=dict(job.get('options') or {})
        with self.lock:
            if self.state['busy']: return False
            self.state['busy']=True
        self.cancelled.clear()
        self.job={**job,'resume':True,'platform':platform,'vod':vod,'options':options}
        ready=[c for c in (self.state.get('clips') or []) if c.get('ready')]
        self.update(logs=[],events=[],output_error=False,resumable=False,stage='prepare',stage_progress=None,current=0,speed='',eta='',started_at=time.time(),message='Reanudando desde el último punto guardado…',clips=ready,completed=len(ready))
        threading.Thread(target=self.work,args=(platform,vod,options,True),daemon=True).start(); return True
    def _write_job(self,output,platform,vod,o,metadata,stage,peaks=None,clips=None,chat_complete=False):
        serial_peaks=[]
        for peak in peaks or []:
            serial_peaks.append(list(peak) if isinstance(peak,(tuple,list)) else peak)
        # Drop huge base64 thumbs from resume snapshots.
        serial_clips=[]
        for clip in clips or []:
            if not clip.get('ready'): continue
            entry={k:v for k,v in clip.items() if k!='thumbnail'}
            serial_clips.append(entry)
        payload={
            'version':1,
            'platform':platform,
            'vod':vod,
            'options':o,
            'metadata':metadata,
            'stage':stage,
            'chat_complete':bool(chat_complete),
            'peaks':serial_peaks,
            'clips':serial_clips,
            'updated_at':datetime.now().isoformat(timespec='seconds'),
        }
        self.job=payload
        try: save_resume(output,payload)
        except OSError: pass
    def work(self,platform,vod,o,resume=False):
        metadata={}
        peaks=[]
        clips=[]
        chat_complete=False
        try:
            self.phase('prepare','Reanudando el proceso.' if resume else 'Preparando el directo y su carpeta.')
            with self.lock: metadata=self.metadata.get(vod)
            saved=None
            if resume:
                saved=load_resume(getattr(self,'output',None)) if getattr(self,'output',None) else None
                if not saved and self.job: saved=self.job
                if saved and saved.get('metadata'): metadata=saved.get('metadata') or metadata
            if metadata is None:
                info=kick.inspect(vod) if platform=='kick' else channel.inspect(f'https://www.twitch.tv/videos/{vod}')
                video=info['videos'][0]
                metadata={
                    'channel':info['channel']['login'],
                    'title':video['title'],
                    'platform':platform,
                    'source':video.get('source') or '',
                    'channel_id':video.get('channel_id') or info['channel'].get('channel_id'),
                    'start_time':video.get('start_time') or video.get('createdAt') or '',
                    'duration':video.get('lengthSeconds') or 0,
                    'url':video.get('url') or '',
                    'is_live':bool(video.get('is_live')),
                }
            platform=metadata.get('platform') or platform
            if platform=='kick':
                if metadata.get('is_live'):
                    raise RuntimeError('Ese directo de Kick sigue en vivo. Espera a que termine para crear clips.')
                if int(metadata.get('duration') or 0)<60:
                    raise RuntimeError('Elige un directo de Kick ya terminado. Los que siguen en vivo no sirven para clips.')
            label=(o.get('folder_name') or '').strip() if o.get('folder_mode')=='custom' else ''
            output=prepare_output(o['folder'],vod,metadata['channel'],metadata['title'],folder_label=label,platform=platform)
            self.output=output
            if resume:
                saved=load_resume(output) or saved or {}
            else:
                clear_resume(output)
                saved={}
            session=session_directory(output)
            self.update(output_folder=str(output),channel=metadata['channel'],video_title=metadata['title'],folder_label=output.name,temps_available=True,platform=platform,from_history=False,resumable=False)
            ensure_tools_on_path()
            needed=(['yt-dlp','ffmpeg'] if o['cut'] else []) + ([] if platform=='kick' else ['TwitchDownloaderCLI'])
            for tool in needed:
                if not shutil.which(tool):
                    raise RuntimeError(f'Falta {tool}. En la versión portable debe estar en la carpeta tools junto a Peak Clip.exe.')
            chat=session/'chat.json'
            chat_checkpoint=chat_progress_file(output)
            chat_complete=bool(saved.get('chat_complete'))
            if chat_complete and not chat.exists():
                prior=kick.load_chat_progress(chat_checkpoint)
                if prior and prior.get('complete') and prior.get('comments') is not None:
                    kick.write_chat_file(chat,metadata.get('channel_id') or prior.get('channel_id'),prior.get('comments') or [])
            if not chat_complete or not chat.exists():
                self.phase('chat','Reanudando la descarga del chat.' if resume and chat_checkpoint.exists() else 'Descargando el chat del directo.')
                self._write_job(output,platform,vod,o,metadata,'chat',peaks=saved.get('peaks') or [],clips=saved.get('clips') or [],chat_complete=False)
                if platform=='kick':
                    def chat_progress(count,pages,note=None):
                        if note: self.update(message=note)
                        else: self.update(message=f'Descargando chat de Kick… {count:,} mensajes ({pages} páginas)')
                    kick.download_chat(
                        metadata.get('channel_id'),
                        metadata.get('start_time'),
                        metadata.get('duration') or 0,
                        chat,
                        progress=chat_progress,
                        cancelled=self.cancelled.is_set,
                        checkpoint=chat_checkpoint,
                    )
                else:
                    self.run(['TwitchDownloaderCLI','chatdownload','--id',vod,'-o',str(chat)],stage='chat')
                chat_complete=True
            else:
                self.phase('chat','Chat ya descargado. Continuamos.')
            self._write_job(output,platform,vod,o,metadata,'analyze',peaks=saved.get('peaks') or [],clips=saved.get('clips') or [],chat_complete=True)
            self.phase('analyze','Buscando las reacciones más fuertes del chat.')
            messages,_=engine.leer_chat(chat)
            if not messages: raise RuntimeError('El chat está vacío. Prueba otro directo.')
            peaks=saved.get('peaks') if resume and saved.get('peaks') else None
            if not peaks:
                peaks=engine.buscar_picos(engine.contar(messages,10),10,int(o['count']),90,float(o['minimum']))
            self.update(total=len(peaks))
            if peaks: self.phase('analyze',f'{len(peaks)} momentos encontrados en {len(messages):,} mensajes.')
            self._write_job(output,platform,vod,o,metadata,'clips',peaks=peaks,clips=saved.get('clips') or [],chat_complete=True)
            media=metadata.get('source') if platform=='kick' else f'https://www.twitch.tv/videos/{vod}'
            if platform=='kick' and not media:
                raise RuntimeError('Kick no devolvió la fuente de vídeo de esta grabación.')
            clips=list(saved.get('clips') or []) if resume else []
            if resume and not clips:
                with self.lock: clips=[c for c in (self.state.get('clips') or []) if c.get('ready')]
            done_numbers={int(c.get('number')) for c in clips if c.get('ready') and c.get('number') is not None}
            self.update(clips=list(clips),completed=len(done_numbers),total=len(peaks))
            for n,(strength,i,_,__) in enumerate(peaks,1):
                if self.cancelled.is_set(): raise RuntimeError('Proceso cancelado.')
                if n in done_numbers:
                    continue
                start=max(0,i*10-int(o['before'])); end=i*10+10+int(o['after'])
                moment=metadata.get('url') or (f'https://kick.com/{metadata["channel"]}/videos/{vod}' if platform=='kick' else f'https://www.twitch.tv/videos/{vod}?t={i*10}s')
                if platform=='twitch': moment=f'https://www.twitch.tv/videos/{vod}?t={i*10}s'
                item={'number':n,'time':engine.hms(start),'end':engine.hms(end),'duration':end-start,'strength':round(strength,1),'url':moment,'ready':False,'video_title':metadata['title'],'channel':metadata['channel'],'platform':platform}
                item['social']=social.suggest(metadata['title'],metadata['channel'],messages,start,end,platform_source=platform)
                if o['cut']:
                    self.phase('download',f'Descargando el fragmento {n} de {len(peaks)}.',current=n)
                    raw=session/f'fragmento_{n}.mp4'
                    dest=self.output/f'clip{n}_{file_stamp()}.mp4'
                    self.run(['yt-dlp','--newline','--no-playlist','-f','best[height<=1080]/best','--download-sections',f'*{start}-{end}','--force-keyframes-at-cuts','-o',str(raw),media],stage='download')
                    self.phase('encode',f'Convirtiendo clip {n} a formato vertical 1080 × 1920.')
                    filters='[0:v]split=2[b][f];[b]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:2[bg];[f]scale=1080:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2'
                    try:
                        self.run(['ffmpeg','-n','-nostats','-progress','pipe:1','-i',str(raw),'-filter_complex',filters,'-c:v','libx264','-crf','20','-preset','veryfast','-c:a','aac',str(dest)],stage='encode',duration=end-start)
                    except Exception:
                        if dest.exists(): dest.rename(session/(dest.name+'.incompleto'))
                        raise
                    self.phase('thumbnail',f'Preparando la vista previa del clip {n}.')
                    thumb=session/f'preview_{n}.jpg'
                    try:
                        self.run(['ffmpeg','-v','error','-n','-ss','1','-i',str(raw),'-frames:v','1','-vf','scale=480:270:force_original_aspect_ratio=decrease,pad=480:270:(ow-iw)/2:(oh-ih)/2','-q:v','4',str(thumb)])
                        lasting=dest.with_suffix('.jpg')
                        shutil.copy2(thumb,lasting)
                        item['thumbnail_file']=str(lasting)
                        item['thumbnail']='data:image/jpeg;base64,'+base64.b64encode(lasting.read_bytes()).decode()
                    except Exception:
                        pass
                    raw.unlink(missing_ok=True)
                    item.update(ready=True,path=str(dest),filename=dest.name,created_at=datetime.now().isoformat(timespec='seconds'),size_bytes=dest.stat().st_size)
                    try: social.save(dest,item['social'])
                    except OSError: self.phase('saved','Clip guardado; no se pudieron guardar sus textos. Puedes reintentarlo desde Compartir.')
                    self.phase('saved',f'Clip {n} guardado. {engine.hms(start)} a {engine.hms(end)}.')
                clips.append(item); self.update(clips=list(clips))
                self.update(completed=len([c for c in clips if c.get('ready') or not o['cut']]))
                self._write_job(output,platform,vod,o,metadata,'clips',peaks=peaks,clips=clips,chat_complete=True)
                if o['cut']:
                    self._persist_session(clips,metadata,output,vod)
            if self.cancelled.is_set(): raise RuntimeError('Proceso cancelado. Los clips terminados se conservaron.')
            result_word=('clip guardado.' if len(clips)==1 else 'clips guardados.') if o['cut'] else ('momento encontrado.' if len(clips)==1 else 'momentos encontrados.')
            message=f'Listo. {len(clips)} {result_word}' if clips else 'No encontramos picos claros. Prueba una sensibilidad más amplia.'
            if o.get('cleanup_temps') and temps_present(output):
                cleaned=cleanup_workspace(output)
                if cleaned['removed']:
                    freed=cleaned['bytes']/1048576
                    message+=f' Chat y temporales eliminados ({cleaned["removed"]} archivos'
                    message+=f', {freed:.1f} MB).' if freed>=0.1 else ').'
            if o['cut']:
                self._persist_session(clips,metadata,output,vod)
            clear_resume(output)
            self.job=None
            self.phase('done',message,resumable=False)
        except OutputError as e:
            self._mark_resumable(platform,vod,o,metadata,peaks,clips,chat_complete)
            self.phase('error',self.public_error(e),output_error=True,logs=[traceback.format_exc()],resumable=True)
        except Exception as e:
            try:
                folder=getattr(self,'output',None)
                with self.lock: current=list(self.state.get('clips') or [])
                if folder and current:
                    self._persist_session(current,metadata or {},folder,vod)
            except Exception:
                pass
            self._mark_resumable(platform,vod,o,metadata,peaks,clips,chat_complete)
            if self.cancelled.is_set():
                message='Proceso pausado. Pulsa Reanudar para continuar donde lo dejaste.'
                if clips: message='Proceso pausado. Los clips listos se conservaron. Pulsa Reanudar para seguir.'
                self.phase('cancelled',message,logs=self.status()['logs']+[traceback.format_exc()],resumable=True)
            else:
                self.phase('error',self.public_error(e)+' Puedes pulsar Reanudar para no empezar de cero.',logs=self.status()['logs']+[traceback.format_exc()],resumable=True)
        finally:
            folder=getattr(self,'output',None)
            self.update(busy=False,temps_available=bool(folder and temps_present(folder)))
    def _mark_resumable(self,platform,vod,o,metadata,peaks,clips,chat_complete):
        folder=getattr(self,'output',None)
        if not folder or not o: return
        try:
            self._write_job(folder,platform,vod,o,metadata or {},'paused',peaks=peaks or [],clips=clips or [],chat_complete=chat_complete)
            self.update(resumable=True)
        except Exception:
            pass
    def _persist_session(self,clips,metadata,output,vod=''):
        ready=[c for c in clips if c.get('ready') and c.get('path')]
        if not ready or not output: return
        try:
            save_session(output,ready,{
                'channel':(metadata or {}).get('channel') or '',
                'title':(metadata or {}).get('title') or '',
                'folder_label':Path(output).name,
                'platform':(metadata or {}).get('platform') or 'twitch',
                'vod':vod or (metadata or {}).get('vod') or '',
            })
        except OSError:
            pass
    def cleanup_temps(self):
        if self.state.get('busy'): return {'ok':False,'error':'Espera a que termine el proceso.'}
        folder=getattr(self,'output',None)
        if not folder or not Path(folder).is_dir():
            return {'ok':False,'error':'No hay una carpeta de clips para limpiar.'}
        try:
            result=cleanup_workspace(folder)
        except Exception:
            return {'ok':False,'error':'No se pudieron eliminar los archivos temporales.'}
        still=temps_present(folder)
        self.update(temps_available=still)
        if result['already_clean']:
            self.update(message='No quedaban chat ni archivos temporales.')
            return {'ok':True,**result}
        freed=result['bytes']/1048576
        note=f'Eliminados {result["removed"]} archivos temporales'
        note+=f' ({freed:.1f} MB).' if freed>=0.1 else '.'
        self.update(message=note+' Se conservaron los clips y sus textos.')
        return {'ok':True,**result}
    def play(self,index):
        clip=self.state['clips'][int(index)]
        if clip.get('ready'): os.startfile(clip['path'])
    def social_draft(self,index):
        clip=self.status()['clips'][int(index)]
        source=clip.get('platform') or 'twitch'
        data=clip.get('social') or social.suggest(clip.get('video_title',''),clip.get('channel',''),[],0,0,platform_source=source)
        data=social.ensure_platforms(data,clip.get('video_title',''),clip.get('channel',''),platform_source=source)
        with self.lock: self.state['clips'][int(index)]['social']=data
        return data
    def save_social(self,index,drafts):
        try:
            clip=self.status()['clips'][int(index)]
            source=clip.get('platform') or 'twitch'
            data=social.ensure_platforms(clip.get('social') or {'basis':{}},clip.get('video_title',''),clip.get('channel',''),platform_source=source)
            data['platforms']=social.validate(drafts)
            if clip.get('ready'): social.save(clip['path'],data)
            with self.lock: self.state['clips'][int(index)]['social']=data
            return {'ok':True}
        except Exception: return {'ok':False,'error':'No se pudieron guardar los textos. Comprueba la carpeta e inténtalo de nuevo.'}
    def social_accounts(self):
        return {'youtube':youtube_share.account(),'tiktok':{'connected':False},'instagram':{'connected':False},'facebook':{'connected':False}}
    def connect_youtube(self):
        if not self.publish_lock.acquire(blocking=False): return False
        try: path=window.create_file_dialog(webview.FileDialog.OPEN,file_types=('Credenciales Google (*.json)',))
        except Exception: self.publish_lock.release();return False
        if not path: self.publish_lock.release();return False
        self.update(social_status={'busy':True,'message':'Autoriza tu canal en la ventana de Google. El enlace caduca en 3 minutos.'})
        def connect():
            try:
                result=youtube_share.connect(path[0]);self.update(social_status={'busy':False,'message':'Conectado: '+result['name']})
            except Exception: self.update(social_status={'busy':False,'message':'No se pudo conectar. Usa un JSON OAuth de escritorio, habilita YouTube Data API y autoriza tu cuenta.'})
            finally: self.publish_lock.release()
        threading.Thread(target=connect,daemon=True).start();return True
    def disconnect_youtube(self):
        if self.publish_lock.locked(): return False
        youtube_share.disconnect();return True
    def share_portal(self,platform):
        import webbrowser
        if platform in social.PORTALS: webbrowser.open(social.PORTALS[platform])
    def publish_youtube(self,index,draft,privacy,kids):
        if not self.publish_lock.acquire(blocking=False): return False
        try:
            clip=self.status()['clips'][int(index)]
            if not clip.get('ready'): raise ValueError()
            receipt=Path(clip['path']).with_suffix('.youtube.json')
            if receipt.exists():
                self.update(social_status={'busy':False,'message':'Este clip ya se envió a YouTube. Revisa la publicación existente.','url':json.loads(receipt.read_text(encoding='utf-8'))['url']})
                self.publish_lock.release();return False
            data=social.validate({'youtube':draft})['youtube']
        except Exception: self.publish_lock.release();return False
        self.update(social_status={'busy':True,'message':'Subiendo a YouTube…'})
        def publish():
            try:
                url=youtube_share.upload(clip['path'],data,privacy,kids,lambda pct:self.update(social_status={'busy':True,'message':f'Subiendo a YouTube: {pct}%'}))
                self.update(social_status={'busy':False,'message':'Vídeo enviado a YouTube.','url':url})
                Path(clip['path']).with_suffix('.youtube.json').write_text(json.dumps({'url':url,'privacy':privacy,'uploaded_at':datetime.now().isoformat()}),encoding='utf-8')
            except Exception: self.update(social_status={'busy':False,'message':'La subida no se confirmó. Revisa YouTube Studio antes de reintentar para evitar duplicados.'})
            finally: self.publish_lock.release()
        threading.Thread(target=publish,daemon=True).start();return True
    def twitch(self,index):
        import webbrowser
        webbrowser.open(self.state['clips'][int(index)]['url'])
    def reveal(self,index):
        clip=self.status()['clips'][int(index)]
        if clip.get('ready') and Path(clip['path']).is_file():
            subprocess.Popen(['explorer.exe','/select,',clip['path']])
    def history_list(self):
        try:
            roots=[DEFAULT_OUTPUT]
            folder=getattr(self,'output',None)
            if folder:
                try:
                    parents=Path(folder).parents
                    roots.append(parents[1] if len(parents)>1 else Path(folder).parent)
                except Exception:
                    pass
            return {'ok':True,'items':list_history(roots)}
        except Exception:
            return {'ok':False,'error':'No se pudo leer el historial.','items':[]}
    def history_open(self,path):
        if self.state.get('busy'):
            return {'ok':False,'error':'Espera a que termine el proceso actual.'}
        try:
            data=load_history(path)
        except FileNotFoundError as e:
            return {'ok':False,'error':str(e)}
        except Exception:
            return {'ok':False,'error':'No se pudo abrir esa sesión del historial.'}
        if not data.get('clips'):
            return {'ok':False,'error':'Esa carpeta ya no tiene clips.'}
        folder=Path(data['path'])
        self.output=folder
        self.update(
            clips=data['clips'],
            output_folder=str(folder),
            channel=data.get('channel') or '',
            video_title=data.get('title') or '',
            folder_label=data.get('folder_label') or folder.name,
            platform=data.get('platform') or 'twitch',
            from_history=True,
            stage='done',
            message=f'Historial · {data.get("channel") or "canal"} · {len(data["clips"])} clips. Puedes copiar los textos otra vez.',
            output_error=False,
            temps_available=temps_present(folder),
            logs=[],
            events=[],
            current=0,
            total=len(data['clips']),
            completed=len(data['clips']),
            stage_progress=None,
            speed='',
            eta='',
        )
        return {'ok':True,'clips':len(data['clips']),'channel':data.get('channel') or '','title':data.get('title') or ''}

