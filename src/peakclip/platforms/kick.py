"""Public Kick metadata + VOD chat replay. Kick's web API may change or block some networks."""
import json, re, base64, time, http.client, ssl
from pathlib import Path
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse, quote
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

HEADERS={
    'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept':'application/json, text/plain, */*',
    'Accept-Language':'es-ES,es;q=0.9,en;q=0.8',
    'Referer':'https://kick.com/',
    'Origin':'https://kick.com',
}
HOSTS=('kick.com','www.kick.com')
UUID=re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',re.I)
RESERVED={'about','browse','categories','category','clips','community','dashboard','directory','downloads','following','home','messages','search','settings','subscriptions','transactions','videos'}

class KickError(RuntimeError):
    """User-facing Kick failure without raw HTTP codes."""

def friendly_http(code):
    if code==429:
        return 'Kick está limitando las peticiones ahora mismo. Espera un minuto y vuelve a intentarlo.'
    if code in (401,403):
        return 'Kick rechazó la consulta. Prueba de nuevo en unos minutos.'
    if code==404:
        return 'Kick no encontró ese canal o grabación.'
    if code>=500:
        return 'Kick no responde bien ahora mismo. Inténtalo de nuevo en un momento.'
    return 'Kick no pudo completar la consulta. Comprueba tu conexión e inténtalo de nuevo.'

def _retry_wait(headers,delay):
    wait=delay
    try:
        retry_after=headers.get('Retry-After') if headers else None
        if retry_after and str(retry_after).strip().isdigit():
            wait=max(wait,min(40,int(str(retry_after).strip())))
    except Exception:
        pass
    return wait

def get_json(url,timeout=25,retries=8,on_retry=None):
    delay=0.9
    last=None
    for attempt in range(retries):
        try:
            req=Request(url,headers=HEADERS)
            with urlopen(req,timeout=timeout) as response:
                return json.loads(response.read().decode())
        except HTTPError as exc:
            last=exc
            code=getattr(exc,'code',None) or 0
            if code in (429,500,502,503,504) and attempt+1<retries:
                wait=_retry_wait(exc.headers,delay)
                if on_retry: on_retry(code,wait,attempt+1)
                time.sleep(wait)
                delay=min(delay*1.6,24)
                continue
            raise KickError(friendly_http(code)) from None
        except URLError as exc:
            last=exc
            if attempt+1<retries:
                if on_retry: on_retry(0,delay,attempt+1)
                time.sleep(delay)
                delay=min(delay*1.6,18)
                continue
            raise KickError('No hay respuesta de Kick. Revisa tu conexión e inténtalo de nuevo.') from None
        except TimeoutError:
            last=TimeoutError('timeout')
            if attempt+1<retries:
                if on_retry: on_retry(0,delay,attempt+1)
                time.sleep(delay)
                delay=min(delay*1.6,18)
                continue
            raise KickError('Kick tardó demasiado en responder. Inténtalo de nuevo.') from None
        except json.JSONDecodeError:
            raise KickError('Kick devolvió una respuesta inválida. Inténtalo de nuevo.') from None
    if isinstance(last,HTTPError):
        raise KickError(friendly_http(getattr(last,'code',429))) from None
    raise KickError('No hay respuesta de Kick. Revisa tu conexión e inténtalo de nuevo.') from None

class KickSession:
    """Keep-alive HTTPS client for chat paging (avoids TLS handshake per page)."""
    def __init__(self,timeout=20):
        self.timeout=timeout
        self.conn=None
    def open(self):
        context=ssl.create_default_context()
        self.conn=http.client.HTTPSConnection('kick.com',timeout=self.timeout,context=context)
        return self
    def close(self):
        if self.conn:
            try: self.conn.close()
            except Exception: pass
            self.conn=None
    def __enter__(self): return self.open()
    def __exit__(self,*_): self.close()
    def get_json(self,path,retries=8,on_retry=None):
        delay=0.6
        last=None
        for attempt in range(retries):
            try:
                if self.conn is None: self.open()
                self.conn.request('GET',path,headers=HEADERS)
                response=self.conn.getresponse()
                body=response.read()
                code=response.status
                if code==200:
                    return json.loads(body.decode())
                if code in (429,500,502,503,504) and attempt+1<retries:
                    wait=_retry_wait(dict(response.getheaders()),delay)
                    if on_retry: on_retry(code,wait,attempt+1)
                    time.sleep(wait)
                    delay=min(delay*1.6,24)
                    self.close(); self.open()
                    continue
                raise KickError(friendly_http(code)) from None
            except (http.client.HTTPException,OSError,TimeoutError) as exc:
                last=exc
                if attempt+1<retries:
                    if on_retry: on_retry(0,delay,attempt+1)
                    time.sleep(delay)
                    delay=min(delay*1.6,18)
                    self.close(); self.open()
                    continue
                raise KickError('No hay respuesta de Kick. Revisa tu conexión e inténtalo de nuevo.') from None
            except json.JSONDecodeError:
                raise KickError('Kick devolvió una respuesta inválida. Inténtalo de nuevo.') from None
        raise KickError('No hay respuesta de Kick. Revisa tu conexión e inténtalo de nuevo.') from None

def parse_link(value):
    value=value.strip()
    if UUID.fullmatch(value): return 'video',value.lower()
    url=urlparse(value if '://' in value else 'https://'+value)
    if url.scheme not in ('http','https') or url.hostname not in HOSTS:
        raise ValueError('Pega un enlace de Kick o de Twitch. La carpeta de destino se elige por separado.')
    parts=[p for p in url.path.strip('/').split('/') if p]
    if len(parts)>=3 and parts[1]=='videos':
        return 'video',parts[2].lower()
    if len(parts)==1 and parts[0].lower() not in RESERVED and re.fullmatch(r'[A-Za-z0-9_-]{2,30}',parts[0]):
        return 'channel',parts[0].lower()
    raise ValueError('Usa kick.com/canal o kick.com/canal/videos/UUID.')

def parse_start(value):
    if not value: return None
    text=str(value).strip().replace(' ','T')
    for fmt in ('%Y-%m-%dT%H:%M:%S%z','%Y-%m-%dT%H:%M:%S.%f%z','%Y-%m-%dT%H:%M:%S','%Y-%m-%dT%H:%M:%S.%f'):
        try:
            dt=datetime.strptime(text.replace('Z','+00:00') if text.endswith('Z') else text,fmt)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    try: return datetime.fromisoformat(text.replace('Z','+00:00'))
    except ValueError: return None

def duration_seconds(value):
    if value is None: return 0
    n=float(value)
    # Kick VOD/livestream duration fields are milliseconds.
    return n/1000

def estimate_duration(item,start):
    """Fallback when Kick reports 0 (common for live or unfinished VODs)."""
    length=int(duration_seconds(item.get('duration') or (item.get('video') or {}).get('duration') or 0))
    if length>0: return length
    if not start: return 0
    end=parse_start(item.get('updated_at') or item.get('ended_at') or '')
    if end and end>start:
        return max(0,int((end-start).total_seconds()))
    # Live/unfinished: use elapsed time so chat replay still has a window.
    if item.get('is_live'):
        now=datetime.now(timezone.utc)
        if start.tzinfo is None: start=start.replace(tzinfo=timezone.utc)
        return max(0,int((now-start).total_seconds()))
    return 0

def normalize_video(item,channel_slug):
    video=item.get('video') or {}
    uuid=(video.get('uuid') or item.get('uuid') or '').lower()
    if not uuid: return None
    start=parse_start(item.get('start_time') or item.get('created_at'))
    length=estimate_duration(item,start)
    thumb=(item.get('thumbnail') or {})
    preview=thumb.get('src') if isinstance(thumb,dict) else thumb
    is_live=bool(item.get('is_live'))
    return {
        'id':uuid,
        'title':item.get('session_title') or item.get('title') or 'Directo de Kick',
        'lengthSeconds':length,
        'viewCount':video.get('views') if video.get('views') is not None else item.get('views') or item.get('viewer_count'),
        'createdAt':(start or datetime.now(timezone.utc)).isoformat(),
        'previewThumbnailURL':preview or '',
        'source':item.get('source') or '',
        'channel_id':item.get('channel_id'),
        'start_time':start.isoformat() if start else '',
        'slug':item.get('slug') or '',
        'channel_slug':channel_slug,
        'is_live':is_live,
        'url':f'https://kick.com/{channel_slug}/videos/{uuid}',
    }

def profile_image_url(user):
    """Kick currently exposes profile_pic; older payloads used profilepic."""
    if not isinstance(user,dict): return ''
    return (user.get('profile_pic') or user.get('profilepic') or '').strip()

def load_avatar(url):
    try:
        from peakclip.platforms.channel import avatar_color
        host=(urlparse(url).hostname or '').lower()
        # Kick CDN lives on files.kick.com (and similar *.kick.com hosts).
        if not (host=='kick.com' or host.endswith('.kick.com')): return None,None
        req=Request(url,headers=HEADERS)
        with urlopen(req,timeout=10) as response:
            mime=response.headers.get_content_type(); data=response.read(2_000_000)
        if mime not in ('image/png','image/jpeg','image/webp'): return None,None
        return 'data:'+mime+';base64,'+base64.b64encode(data).decode(), avatar_color(data)
    except Exception:
        return None,None

def channel_payload(raw):
    user=raw.get('user') or {}
    login=(raw.get('slug') or user.get('username') or '').lower()
    stream=None
    live=raw.get('livestream')
    if isinstance(live,dict) and live.get('session_title'):
        stream={'title':live.get('session_title'),'viewersCount':live.get('viewer_count')}
    picture=profile_image_url(user)
    avatar,color=load_avatar(picture)
    return {
        'id':str(raw.get('id') or ''),
        'login':login,
        'displayName':user.get('username') or login,
        'description':user.get('bio') or '',
        'profileImageURL':picture,
        'followers':{'totalCount':raw.get('followers_count') or raw.get('followersCount')},
        'stream':stream,
        'avatar':avatar,
        'color':color,
        'platform':'kick',
        'channel_id':raw.get('id'),
    }

def inspect(value):
    kind,identifier=parse_link(value)
    if kind=='video':
        meta=get_json('https://kick.com/api/v1/video/'+identifier)
        live=meta.get('livestream') or {}
        channel_raw=live.get('channel') or {}
        if not channel_raw.get('slug'):
            raise ValueError('Esta grabación de Kick no existe o ya no está disponible.')
        if live.get('is_live'):
            raise ValueError('Ese directo de Kick sigue en vivo. Espera a que termine para crear clips.')
        # Merge livestream fields for normalize_video.
        item={
            **live,
            'video':meta,
            'source':meta.get('source') or live.get('source') or '',
            'session_title':live.get('session_title') or 'Directo de Kick',
            'duration':live.get('duration') or meta.get('duration'),
            'start_time':live.get('start_time') or live.get('created_at') or meta.get('created_at'),
            'updated_at':meta.get('updated_at') or live.get('updated_at'),
            'channel_id':live.get('channel_id') or channel_raw.get('id'),
            'thumbnail':live.get('thumbnail') or {},
            'views':meta.get('views'),
            'is_live':bool(live.get('is_live')),
        }
        channel=channel_payload(channel_raw if channel_raw.get('user') else get_json('https://kick.com/api/v2/channels/'+channel_raw.get('slug')))
        video=normalize_video(item,channel['login'])
        if not video: raise ValueError('Esta grabación de Kick no existe o ya no está disponible.')
        if int(video.get('lengthSeconds') or 0)<60:
            raise ValueError('Esta grabación de Kick aún no tiene duración usable. Elige un directo ya terminado.')
        return {'channel':channel,'videos':[video],'kind':'video','platform':'kick'}
    raw=get_json('https://kick.com/api/v2/channels/'+identifier)
    if not raw or not raw.get('slug'): raise ValueError('No encontramos ese canal de Kick. Revisa el enlace.')
    channel=channel_payload(raw)
    listing=get_json('https://kick.com/api/v2/channels/'+identifier+'/videos')
    videos=[]
    for item in (listing if isinstance(listing,list) else []):
        # Live entries appear in /videos with duration 0 and break chat clipping.
        if item.get('is_live'): continue
        video=normalize_video(item,channel['login'])
        if not video: continue
        if int(video.get('lengthSeconds') or 0)<60: continue
        videos.append(video)
        if len(videos)>=8: break
    return {'channel':channel,'videos':videos,'kind':'channel','platform':'kick'}

def load_chat_progress(path):
    path=Path(path) if path else None
    if not path or not path.is_file(): return None
    try:
        data=json.loads(path.read_text(encoding='utf-8'))
    except (OSError,ValueError):
        return None
    if not isinstance(data,dict): return None
    return data

def save_chat_progress(path,payload):
    if not path: return
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(payload,ensure_ascii=False),encoding='utf-8')
    temp.replace(path)

def write_chat_file(dest,channel_id,comments):
    dest=Path(dest)
    dest.parent.mkdir(parents=True,exist_ok=True)
    ordered=sorted(comments,key=lambda c:c['content_offset_seconds'])
    dest.write_text(json.dumps({'comments':ordered,'video':{'id':str(channel_id)},'source':'kick'},ensure_ascii=False),encoding='utf-8')
    return len(ordered)

def format_eta(seconds):
    seconds=max(0,int(seconds))
    if seconds<60: return f'{seconds}s'
    minutes,sec=divmod(seconds,60)
    if minutes<60: return f'{minutes}:{sec:02d}'
    hours,minutes=divmod(minutes,60)
    return f'{hours}:{minutes:02d}:{sec:02d}'

def chat_coverage(oldest,start,end):
    """Fraction of the VOD window already walked (Kick pages go from end → start)."""
    if not oldest or not start or not end or end<=start: return 0.0
    if oldest.tzinfo is None: oldest=oldest.replace(tzinfo=timezone.utc)
    if start.tzinfo is None: start=start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None: end=end.replace(tzinfo=timezone.utc)
    oldest=min(max(oldest,start),end)
    return max(0.0,min(1.0,(end-oldest).total_seconds()/max(1.0,(end-start).total_seconds())))

def download_chat(channel_id,start_iso,duration_seconds,dest,progress=None,cancelled=None,checkpoint=None):
    """Fetch Kick chat replay into a TwitchDownloader-compatible JSON.

    Goes as fast as Kick allows (keep-alive, no delay until a 429), then backs
    off briefly and recovers. Optional checkpoint path supports resume.
    """
    start=parse_start(start_iso)
    if not start or not channel_id: raise KickError('No se pudo localizar el chat de este directo de Kick.')
    end=start+timedelta(seconds=max(1,int(duration_seconds or 0)))
    # Kick chat cursors are epoch microseconds.
    cursor=str(int(end.timestamp()*1_000_000))
    comments=[]
    seen=set()
    pages=0
    # No artificial delay until Kick rate-limits; then throttle and recover.
    pace=0.0
    min_pace=0.0
    max_pace=0.75
    hit_limit=False
    last_persist=time.monotonic()
    begun=time.monotonic()
    last_report=0.0
    frontier=end
    prior=load_chat_progress(checkpoint)
    if prior and str(prior.get('channel_id'))==str(channel_id) and prior.get('start_iso')==start_iso and int(prior.get('duration') or 0)==int(duration_seconds or 0):
        if prior.get('complete') and prior.get('comments') is not None:
            comments=list(prior.get('comments') or [])
            write_chat_file(dest,channel_id,comments)
            if progress: progress(len(comments),int(prior.get('pages') or 0),'Chat reanudado desde copia guardada.',percent=100,eta='0s',speed='')
            return len(comments)
        cursor=str(prior.get('cursor') or cursor)
        comments=list(prior.get('comments') or [])
        pages=int(prior.get('pages') or 0)
        for item in comments:
            # Rebuild dedupe keys from offsets+body when ids were not stored.
            key=str(item.get('id') or f"{item.get('content_offset_seconds')}|{(item.get('message') or {}).get('body')}")
            seen.add(key)
        if progress and comments:
            progress(len(comments),pages,f'Reanudando chat… {len(comments):,} mensajes guardados')
    def report(note=None,force=False,percent=None,eta=None,speed=None):
        nonlocal last_report
        if not progress: return
        now=time.monotonic()
        if not force and (now-last_report)<0.25: return
        last_report=now
        progress(len(comments),pages,note,percent=percent,eta=eta,speed=speed)
    def emit_stats(force=False,note=None,done=False):
        covered=1.0 if done else chat_coverage(frontier,start,end)
        elapsed=max(0.001,time.monotonic()-begun)
        percent=round(covered*100,1)
        speed=f'{len(comments)/elapsed:.0f} msg/s' if comments else f'{pages/elapsed:.1f} pág/s'
        eta=''
        if done:
            eta='0s'
        elif covered>=0.03 and elapsed>=0.8:
            remaining=(1.0-covered)/(covered/elapsed)
            eta=format_eta(remaining)
        report(note=note,force=force,percent=percent,eta=eta,speed=speed)
    def persist(complete=False):
        nonlocal last_persist
        if not checkpoint: return
        save_chat_progress(checkpoint,{
            'channel_id':str(channel_id),
            'start_iso':start_iso,
            'duration':int(duration_seconds or 0),
            'cursor':str(cursor),
            'pages':pages,
            'complete':bool(complete),
            'comments':comments,
            'updated_at':datetime.now(timezone.utc).isoformat(),
        })
        last_persist=time.monotonic()
    def on_retry(code,wait,attempt):
        nonlocal pace,hit_limit
        if code==429:
            hit_limit=True
            pace=min(max_pace,max(pace*2.0,0.12))
        report(note=f'Kick pide un respiro… reintento {attempt} en {int(wait)}s',force=True)
        persist(False)
    try:
        with KickSession() as session:
            while True:
                if cancelled and cancelled():
                    persist(False)
                    raise RuntimeError('Proceso cancelado.')
                path=f'/api/v2/channels/{int(channel_id)}/messages?cursor={quote(str(cursor))}'
                payload=session.get_json(path,on_retry=on_retry)
                data=payload.get('data') or {}
                batch=data.get('messages') or []
                nxt=data.get('cursor')
                pages+=1
                if not batch: break
                reached_start=False
                for msg in batch:
                    created=parse_start(msg.get('created_at'))
                    if not created: continue
                    if created>end: continue
                    if created<start:
                        reached_start=True
                        continue
                    mid=str(msg.get('id') or '')
                    key=mid or f"{(created-start).total_seconds()}|{msg.get('content') or ''}"
                    if key in seen: continue
                    seen.add(key)
                    comments.append({
                        'id':mid,
                        'content_offset_seconds':(created-start).total_seconds(),
                        'message':{'body':msg.get('content') or ''},
                    })
                times=[t for m in batch if (t:=parse_start(m.get('created_at')))]
                oldest=min(times) if times else None
                if oldest:
                    if oldest.tzinfo is None: oldest=oldest.replace(tzinfo=timezone.utc)
                    frontier=min(frontier,oldest)
                emit_stats(force=reached_start)
                # Disk checkpoints are expensive on long VODs; keep them sparse.
                if pages%30==0 or (time.monotonic()-last_persist)>=8:
                    persist(False)
                if reached_start or not nxt or str(nxt)==str(cursor) or (oldest and oldest<start):
                    break
                cursor=nxt
                if hit_limit:
                    pace=max(min_pace,pace*0.9)
                    if pace<=0.02: hit_limit=False; pace=0.0
                if pace>0:
                    time.sleep(pace)
        count=write_chat_file(dest,channel_id,comments)
        emit_stats(force=True,done=True)
        persist(True)
        return count
    except Exception:
        persist(False)
        raise
