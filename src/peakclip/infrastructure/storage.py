"""Output validation before downloads, with actionable Windows errors."""
import os
import tempfile
import re
import json
import uuid
from pathlib import Path
from datetime import datetime

DEFAULT_OUTPUT = Path(os.environ.get('LOCALAPPDATA', Path.home()/'AppData'/'Local'))/'PeakClip'/'Clips'
HISTORY_INDEX = DEFAULT_OUTPUT.parent/'history-index.json'

class OutputError(RuntimeError):
    pass

def safe_name(value, fallback, limit=80):
    name=re.sub(r'[<>:"/\\|?*\x00-\x1f]', ' ', str(value or ''))
    name=re.sub(r'\s+', ' ', name).strip(' .')[:limit].rstrip(' .')
    if not name: name=fallback
    if re.fullmatch(r'(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?',name,re.I): name='_'+name
    return name

def file_stamp():
    return datetime.now().strftime('%Y-%m-%d_%H-%M-%S_%f')

def prepare_output(folder, vod, channel_name='', title='', folder_label='', platform='twitch'):
    base = Path(folder) if folder else DEFAULT_OUTPUT
    try:
        base.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryFile(dir=base) as probe:
            probe.write(b'Peak Clip output check')
            probe.flush()
        parent=base/safe_name(channel_name,'canal',40)
        parent.mkdir(parents=True,exist_ok=True)
        # Custom label wins; otherwise the stream title names the folder.
        name=safe_name(folder_label or title,'Directo '+vod)
        output=parent/name
        # Never merge different broadcasts that happen to share a title.
        marker=output/'.peakclip-video.json'
        if output.exists():
            try: same=json.loads(marker.read_text(encoding='utf-8')).get('vod')==vod
            except (OSError,ValueError): same=False
            if not same: output=parent/(name+' ['+vod+']')
        output.mkdir(parents=True,exist_ok=True)
        marker=output/'.peakclip-video.json'
        if not marker.exists():
            with marker.open('x',encoding='utf-8') as f:
                json.dump({'vod':vod,'channel':channel_name,'title':title,'folder_label':folder_label or title,'platform':platform or 'twitch'},f,ensure_ascii=False)
        return output
    except OSError as exc:
        raise OutputError('No podemos escribir en la carpeta elegida. Windows puede estar protegiéndola. Pulsa «Usar carpeta local» o elige otra carpeta y vuelve a intentarlo.') from exc

def session_directory(output):
    target=output/'.peakclip'/(file_stamp()+'_'+uuid.uuid4().hex[:8])
    target.mkdir(parents=True)
    return target

def workspace_scratch(output):
    return Path(output)/'.peakclip'

def session_file(output):
    return Path(output)/'.peakclip-session.json'

def resume_file(output):
    return Path(output)/'.peakclip-resume.json'

def chat_progress_file(output):
    return Path(output)/'.peakclip-chat-progress.json'

def save_resume(output,payload):
    target=resume_file(output)
    temp=target.with_suffix('.json.tmp')
    temp.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    temp.replace(target)
    return str(target)

def load_resume(output):
    target=resume_file(output)
    if not target.is_file(): return None
    try:
        data=json.loads(target.read_text(encoding='utf-8'))
    except (OSError,ValueError):
        return None
    return data if isinstance(data,dict) else None

def clear_resume(output):
    for path in (resume_file(output),chat_progress_file(output)):
        try: path.unlink(missing_ok=True)
        except OSError: pass

def temps_present(output):
    root=workspace_scratch(output)
    if not root.is_dir(): return False
    try: return any(root.rglob('*'))
    except OSError: return False

def cleanup_workspace(output):
    """Delete chat, previews and session scratch. Keep clips and share sidecars."""
    root=workspace_scratch(output)
    if not root.exists():
        return {'ok':True,'removed':0,'bytes':0,'already_clean':True}
    removed=0
    freed=0
    for path in sorted(root.rglob('*'),reverse=True):
        try:
            if path.is_file():
                freed+=path.stat().st_size
                path.unlink()
                removed+=1
            elif path.is_dir():
                path.rmdir()
        except OSError:
            continue
    try:
        if root.exists() and not any(root.iterdir()):
            root.rmdir()
    except OSError:
        pass
    return {'ok':True,'removed':removed,'bytes':freed,'already_clean':removed==0}

def _clip_public(item):
    keep=('number','time','end','duration','strength','url','ready','path','filename','created_at','size_bytes','video_title','channel','platform','thumbnail_file','caption_path')
    return {key:item[key] for key in keep if key in item and item[key] is not None}

def save_session(output,clips,meta=None):
    """Persist clip list (without huge base64 thumbs) so history can reopen texts later."""
    output=Path(output)
    meta=meta or {}
    payload={
        'channel':meta.get('channel') or '',
        'title':meta.get('title') or meta.get('video_title') or '',
        'folder_label':meta.get('folder_label') or output.name,
        'platform':meta.get('platform') or 'twitch',
        'vod':meta.get('vod') or '',
        'updated_at':datetime.now().isoformat(timespec='seconds'),
        'clips':[_clip_public(c) for c in clips if c.get('ready') and c.get('path')],
    }
    target=session_file(output)
    temp=target.with_suffix('.json.tmp')
    temp.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    temp.replace(target)
    marker=output/'.peakclip-video.json'
    try:
        data=json.loads(marker.read_text(encoding='utf-8')) if marker.exists() else {}
    except (OSError,ValueError):
        data={}
    data.update({k:payload[k] for k in ('channel','title','folder_label','platform','vod') if payload.get(k)})
    data['updated_at']=payload['updated_at']
    marker.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    remember_history(output)
    return str(target)

def remember_history(output):
    """Track session folders outside the default tree (custom destinations)."""
    try:
        path=str(Path(output).resolve())
        entries=[]
        if HISTORY_INDEX.exists():
            try: entries=json.loads(HISTORY_INDEX.read_text(encoding='utf-8'))
            except (OSError,ValueError): entries=[]
        if not isinstance(entries,list): entries=[]
        entries=[e for e in entries if isinstance(e,str) and e.lower()!=path.lower()]
        entries.insert(0,path)
        HISTORY_INDEX.parent.mkdir(parents=True,exist_ok=True)
        HISTORY_INDEX.write_text(json.dumps(entries[:200],ensure_ascii=False,indent=2),encoding='utf-8')
    except OSError:
        pass

def _thumb_data(path):
    try:
        import base64
        data=Path(path).read_bytes()
        return 'data:image/jpeg;base64,'+base64.b64encode(data).decode()
    except OSError:
        return None

def _discover_clips(folder):
    clips=[]
    for path in sorted(folder.glob('clip*.mp4')):
        if '_subtitulos_' in path.stem: continue
        if not path.is_file(): continue
        social_path=path.with_suffix('.social.json')
        social_data=None
        if social_path.exists():
            try: social_data=json.loads(social_path.read_text(encoding='utf-8'))
            except (OSError,ValueError): social_data=None
        thumb=path.with_suffix('.jpg')
        number=len(clips)+1
        match=re.match(r'clip(\d+)_',path.name,re.I)
        if match: number=int(match.group(1))
        item={
            'number':number,
            'filename':path.name,
            'path':str(path),
            'ready':True,
            'size_bytes':path.stat().st_size,
            'created_at':datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec='seconds'),
            'thumbnail_file':str(thumb) if thumb.exists() else '',
        }
        if social_data: item['social']=social_data
        if thumb.exists():
            data=_thumb_data(thumb)
            if data: item['thumbnail']=data
        clips.append(item)
    clips.sort(key=lambda c:c.get('number') or 0)
    return clips

def _history_row(folder):
    folder=Path(folder)
    marker=folder/'.peakclip-video.json'
    if not marker.exists() and not any(folder.glob('clip*.mp4')):
        return None
    try: meta=json.loads(marker.read_text(encoding='utf-8')) if marker.exists() else {}
    except (OSError,ValueError): meta={}
    session=session_file(folder)
    clips=[]
    updated=meta.get('updated_at') or ''
    if session.exists():
        try:
            payload=json.loads(session.read_text(encoding='utf-8'))
            clips=payload.get('clips') or []
            updated=payload.get('updated_at') or updated
            meta={**meta,**{k:payload.get(k) for k in ('channel','title','folder_label','platform','vod') if payload.get(k)}}
        except (OSError,ValueError):
            clips=[]
    if not clips:
        clips=_discover_clips(folder)
    ready=[c for c in clips if c.get('ready') and Path(c.get('path') or '').is_file()]
    mp4s=list(folder.glob('clip*.mp4'))
    if not ready and not mp4s:
        return None
    try: mtime=session.stat().st_mtime if session.exists() else (marker.stat().st_mtime if marker.exists() else folder.stat().st_mtime)
    except OSError: mtime=0
    return {
        'path':str(folder),
        'channel':meta.get('channel') or folder.parent.name,
        'title':meta.get('title') or folder.name,
        'folder_label':meta.get('folder_label') or folder.name,
        'platform':meta.get('platform') or 'twitch',
        'vod':meta.get('vod') or '',
        'clips':len(ready) or len(mp4s),
        'updated_at':updated or datetime.fromtimestamp(mtime).isoformat(timespec='seconds'),
        'mtime':mtime,
    }

def list_history(roots=None,limit=40):
    roots=[Path(r) for r in (roots or [DEFAULT_OUTPUT]) if r]
    seen=set()
    rows=[]
    indexed=[]
    if HISTORY_INDEX.exists():
        try: indexed=json.loads(HISTORY_INDEX.read_text(encoding='utf-8'))
        except (OSError,ValueError): indexed=[]
    candidates=[]
    for root in roots:
        if not root.is_dir(): continue
        for marker in root.rglob('.peakclip-video.json'):
            candidates.append(marker.parent)
    for entry in indexed if isinstance(indexed,list) else []:
        if isinstance(entry,str): candidates.append(Path(entry))
    for folder in candidates:
        try: key=str(folder.resolve()).lower()
        except OSError: continue
        if key in seen or not folder.is_dir(): continue
        seen.add(key)
        row=_history_row(folder)
        if row: rows.append(row)
    rows.sort(key=lambda r:r.get('mtime') or 0,reverse=True)
    for row in rows: row.pop('mtime',None)
    return rows[:limit]

def load_history(path):
    folder=Path(path)
    if not folder.is_dir(): raise FileNotFoundError('No encontramos esa carpeta del historial.')
    marker=folder/'.peakclip-video.json'
    meta={}
    if marker.exists():
        try: meta=json.loads(marker.read_text(encoding='utf-8'))
        except (OSError,ValueError): meta={}
    session=session_file(folder)
    clips=[]
    if session.exists():
        try:
            payload=json.loads(session.read_text(encoding='utf-8'))
            meta={**meta,**{k:payload.get(k) for k in ('channel','title','folder_label','platform','vod','updated_at') if payload.get(k)}}
            for item in payload.get('clips') or []:
                clip_path=Path(item.get('path') or '')
                if not clip_path.is_file(): continue
                entry=dict(item)
                entry['ready']=True
                social_path=clip_path.with_suffix('.social.json')
                if social_path.exists():
                    try: entry['social']=json.loads(social_path.read_text(encoding='utf-8'))
                    except (OSError,ValueError): pass
                thumb_name=entry.get('thumbnail_file') or str(clip_path.with_suffix('.jpg'))
                thumb=Path(thumb_name)
                if thumb.is_file():
                    data=_thumb_data(thumb)
                    if data: entry['thumbnail']=data
                    entry['thumbnail_file']=str(thumb)
                clips.append(entry)
        except (OSError,ValueError):
            clips=[]
    if not clips:
        clips=_discover_clips(folder)
        for entry in clips:
            entry.setdefault('channel',meta.get('channel') or folder.parent.name)
            entry.setdefault('video_title',meta.get('title') or folder.name)
            entry.setdefault('platform',meta.get('platform') or 'twitch')
    clips.sort(key=lambda c:c.get('number') or 0)
    return {
        'path':str(folder),
        'channel':meta.get('channel') or folder.parent.name,
        'title':meta.get('title') or folder.name,
        'folder_label':meta.get('folder_label') or folder.name,
        'platform':meta.get('platform') or 'twitch',
        'vod':meta.get('vod') or '',
        'clips':clips,
    }
