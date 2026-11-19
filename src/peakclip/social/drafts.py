"""Local, editable suggestions. No model service or automatic public posting."""
import json,re,unicodedata
from collections import Counter
from pathlib import Path

PLATFORMS=('youtube','tiktok','instagram','facebook')
PORTALS={
    'youtube':'https://studio.youtube.com',
    'tiktok':'https://www.tiktok.com/tiktokstudio/upload',
    'instagram':'https://www.instagram.com',
    'facebook':'https://business.facebook.com/latest/home',
}
STOP=set('para como cuando donde esto esta este ese esa que los las del con por una uno unos unas el la un de en y a o es se lo me te si no ya mi tu más muy pero porque ahora jajaja jajajaja xd jajaj lol kekw lul clip pog twitch kick live stream streaming https www com'.split())

# Reach tags that creators expect on each network.
BOOST={
    'tiktok':['#fyp','#fy','#foryou','#foryoupage','#viral','#parati','#gaming','#clip','#streamer','#xyzbca'],
    'youtube':['#Shorts','#Viral','#Gaming','#Clip','#YouTubeShorts','#streamer'],
    'instagram':['#Reels','#reelsinstagram','#viral','#fyp','#explore','#parati','#gaming','#clip','#streamer','#instareels'],
    'facebook':['#Reels','#facebookreels','#viral','#gaming','#clip','#streamer','#video'],
}

def hashtag(value):
    clean=''.join(c for c in unicodedata.normalize('NFKD',value) if not unicodedata.combining(c))
    tag='#'+re.sub(r'[^a-zA-Z0-9_]','',clean)[:40]
    return tag if len(tag)>1 else ''

def title_topics(title):
    words=re.findall(r'[\wáéíóúñ]{3,}',re.sub(r'https?://\S+','',title.lower()))
    return [w for w in words if w not in STOP and not w.isdigit()][:5]

def join_tags(*groups,limit=500):
    seen=[]
    for tag in groups:
        if not tag or tag in seen: continue
        candidate=' '.join(seen+[tag])
        if len(candidate)>limit: break
        seen.append(tag)
    return ' '.join(seen)

def transcript_lines(cues,start,end):
    """Flatten caption cues overlapping the clip window into (offset, text) pairs."""
    lines=[]
    for cue in cues or []:
        try:
            cue_start=float(cue.get('start') or 0)
            cue_end=float(cue.get('end') or cue_start)
            text=str(cue.get('text') or '').strip()
        except (TypeError,ValueError):
            continue
        if not text: continue
        if cue_end<start or cue_start>end: continue
        lines.append((max(start,cue_start),text))
    return lines

def suggest(title,channel,messages,start,end,platform_source='twitch',transcript=None):
    nearby=[text for t,text in messages if start<=t<=end]
    spoken=[text for _,text in transcript_lines(transcript,0,max(end-start,0)+1)] if transcript is not None else []
    # Prefer spoken words for titles when transcription exists; chat still adds reaction topics.
    spoken_words=Counter(
        w for text in spoken
        for w in re.findall(r'[\wáéíóúñ]{3,}',re.sub(r'https?://\S+','',text.lower()))
        if w not in STOP and not w.isdigit()
    )
    chat_words=Counter(
        w for text in set(nearby)
        for w in re.findall(r'[\wáéíóúñ]{4,}',re.sub(r'https?://\S+','',text.lower()))
        if w not in STOP and not w.isdigit()
    )
    voice_topics=[w for w,_ in spoken_words.most_common(8)][:5]
    chat_topics=[w for w,count in chat_words.most_common(10) if count>=2][:5]
    title=re.sub(r'https?://\S+','',title).strip() or 'Un momento del directo'
    topics=list(dict.fromkeys(voice_topics+chat_topics+title_topics(title)))[:6]
    quote=''
    if spoken:
        quote=max(spoken,key=len)
        quote=re.sub(r'\s+',' ',quote).strip()
        if len(quote)>90: quote=quote[:87].rstrip()+'…'
    base=f'{channel}: {quote}' if quote else f'{channel}: {title}'
    if quote:
        description=f'«{quote}» — momento del directo de {channel}.'
        if title and title.lower() not in quote.lower():
            description+=f' Directo: {title}.'
    else:
        description=f'Un momento del directo «{title}» de {channel}.'
    if chat_topics: description+=' El chat reaccionó hablando de '+', '.join(chat_topics[:3])+'.'
    if voice_topics and not quote: description+=' Se habla de '+', '.join(voice_topics[:3])+'.'
    source_tags=['#Kick','#KickClips','#ClipsDeKick'] if platform_source=='kick' else ['#Twitch','#TwitchClips','#ClipsDeTwitch']
    core=[t for t in [hashtag(channel)]+source_tags+[hashtag(w) for w in topics] if t]
    result={}
    for platform in PLATFORMS:
        if quote:
            heading=base if platform=='youtube' else (
                quote if platform=='tiktok' else f'{channel}: {quote}'
            )
        else:
            heading=base if platform=='youtube' else (
                f'El chat reacciona: {title}' if platform=='tiktok'
                else f'Un momento con {channel}: {title}'
            )
        prompt=' ¿Qué opinas de este momento?' if platform in ('instagram','facebook') else ''
        extra=list(BOOST[platform])
        if platform_source=='kick' and platform=='tiktok': extra=['#kick','#kickclips']+extra
        if platform_source=='twitch' and platform=='tiktok': extra=['#twitch','#twitchclips']+extra
        result[platform]={
            'title':heading[:100] if platform=='youtube' else heading[:180],
            'description':(description+prompt)[:4500],
            'hashtags':join_tags(*(core+extra)),
        }
    note='Sugerencias locales'
    if spoken: note+=' a partir de la voz del clip'
    note+=' con hashtags de alcance. Revísalas: no garantizan viralidad.'
    return {
        'platforms':result,
        'basis':{
            'messages':len(nearby),
            'transcript_lines':len(spoken),
            'topics':topics,
            'quote':quote,
            'note':note,
        },
    }

def ensure_platforms(data,title='',channel='',platform_source='twitch'):
    data=data or {}
    platforms=dict(data.get('platforms') or {})
    fresh=suggest(title or 'Un momento del directo',channel or 'canal',[],0,0,platform_source=platform_source)
    for platform in PLATFORMS:
        if platform not in platforms:
            platforms[platform]=fresh['platforms'][platform]
    # Drop experimental Twitch share tab if present in older drafts.
    platforms.pop('twitch',None)
    data['platforms']=platforms
    data.setdefault('basis',fresh['basis'])
    return data

def validate(drafts):
    result={}
    for platform in PLATFORMS:
        d=drafts.get(platform,{})
        result[platform]={key:str(d.get(key,''))[:limit] for key,limit in [('title',180),('description',4500),('hashtags',500)]}
    return result

def save(path,data):
    target=Path(path).with_suffix('.social.json')
    temp=target.with_suffix('.json.tmp')
    temp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    temp.replace(target)
    return str(target)
