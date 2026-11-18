"""Public channel/VOD metadata for Twitch and Kick."""
import json, re, base64
import io, colorsys
from PIL import Image
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from . import kick

def avatar_color(data):
    with Image.open(io.BytesIO(data)) as source:
        pixels=source.convert('RGB').resize((48,48))
        buckets={}
        for rgb in pixels.getdata():
            h,s,v=colorsys.rgb_to_hsv(*(c/255 for c in rgb))
            if s<.18 or v<.16: continue
            key=int(h*18)%18
            score,total=buckets.get(key,(0,[]))
            buckets[key]=(score+s*v,total+[rgb])
        if not buckets: return None
        _,colors=max(buckets.values(),key=lambda item:item[0])
        average=[sum(c[i] for c in colors)/len(colors)/255 for i in range(3)]
        h,s,v=colorsys.rgb_to_hsv(*average)
        rgb=colorsys.hsv_to_rgb(h,max(.45,min(s,.75)),.8)
        return ','.join(str(round(c*255)) for c in rgb)

def detect_platform(value):
    text=(value or '').strip()
    if not text: raise ValueError('Pega un enlace de Twitch o de Kick.')
    if re.fullmatch(r'\d+',text): return 'twitch'
    if kick.UUID.fullmatch(text): return 'kick'
    host=urlparse(text if '://' in text else 'https://'+text).hostname or ''
    if host in kick.HOSTS: return 'kick'
    if host in ('twitch.tv','www.twitch.tv','m.twitch.tv'): return 'twitch'
    raise ValueError('Pega un enlace de Twitch (twitch.tv/…) o de Kick (kick.com/…).')

def parse_twitch(value):
    value=value.strip()
    if re.fullmatch(r'\d+',value): return 'video',value
    url=urlparse(value if '://' in value else 'https://'+value)
    if url.scheme not in ('http','https') or url.hostname not in ('twitch.tv','www.twitch.tv','m.twitch.tv'):
        raise ValueError('Pega un enlace de Twitch o de Kick. La carpeta de destino se elige por separado.')
    path=url.path.strip('/')
    match=re.fullmatch(r'videos/(\d+)',path)
    if match: return 'video',match[1]
    if re.fullmatch(r'[A-Za-z0-9_]{2,25}(?:/videos)?',path) and path.split('/')[0] not in ('directory','settings','downloads','search','videos'):
        return 'channel',path.split('/')[0].lower()
    raise ValueError('Usa twitch.tv/canal, twitch.tv/videos/NUMERO, kick.com/canal o kick.com/canal/videos/UUID.')

def parse_link(value):
    platform=detect_platform(value)
    if platform=='kick':
        kind,identifier=kick.parse_link(value)
    else:
        kind,identifier=parse_twitch(value)
    return platform,kind,identifier

def query(text):
    req=Request('https://gql.twitch.tv/gql',data=json.dumps({'query':text}).encode(),headers={'Client-ID':'kimne78kx3ncx6brgo4mv6wki5h1ko','Content-Type':'application/json'})
    with urlopen(req,timeout=20) as response: result=json.load(response)
    if result.get('errors'): raise ValueError('Twitch no pudo devolver los datos del canal. Inténtalo de nuevo.')
    return result['data']

def inspect_twitch(value):
    kind,identifier=parse_twitch(value)
    fields='id title lengthSeconds viewCount createdAt previewThumbnailURL(width:640,height:360)'
    profile='id login displayName description profileImageURL(width:150) followers{totalCount} stream{title viewersCount game{name}}'
    if kind=='video':
        video=query('{video(id:'+json.dumps(identifier)+'){'+fields+' owner{'+profile+'}}}')['video']
        if not video: raise ValueError('Esta grabación no existe o ya no está disponible.')
        user=video.pop('owner'); videos=[video]
    else:
        user=query('{user(login:'+json.dumps(identifier)+'){'+profile+' videos(first:8,type:ARCHIVE,sort:TIME){edges{node{'+fields+'}}}}}')['user']
        if not user: raise ValueError('No encontramos ese canal. Revisa el enlace.')
        videos=[edge['node'] for edge in user.pop('videos')['edges']]
    if not user: raise ValueError('El canal de esta grabación ya no está disponible.')
    user['avatar']=None
    user['color']=None
    user['platform']='twitch'
    try:
        url=user['profileImageURL']
        if urlparse(url).hostname=='static-cdn.jtvnw.net':
            with urlopen(url,timeout=10) as response:
                mime=response.headers.get_content_type(); data=response.read(2_000_000)
            if mime in ('image/png','image/jpeg','image/webp'):
                user['avatar']='data:'+mime+';base64,'+base64.b64encode(data).decode()
                user['color']=avatar_color(data)
    except Exception: pass
    for video in videos:
        video['url']=f"https://www.twitch.tv/videos/{video['id']}"
    return {'channel':user,'videos':videos,'kind':kind,'platform':'twitch'}

def inspect(value):
    platform=detect_platform(value)
    if platform=='kick': return kick.inspect(value)
    return inspect_twitch(value)
