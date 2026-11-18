"""Optional YouTube connection; refresh tokens stay in Windows Credential Manager."""
import json, threading
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from keyring.backends.Windows import WinVaultKeyring

SCOPES=['https://www.googleapis.com/auth/youtube.upload','https://www.googleapis.com/auth/youtube.readonly']
vault=WinVaultKeyring()
lock=threading.Lock()

def read():
    raw=vault.get_password('PeakClip','youtube')
    return json.loads(raw) if raw else None

def account():
    try:
        data=read()
        return {'connected':bool(data),'name':data.get('name','') if data else ''}
    except Exception: return {'connected':False,'name':''}

def connect(path):
    config=json.loads(Path(path).read_text(encoding='utf-8'))
    if 'installed' not in config: raise ValueError('El archivo debe ser un cliente OAuth de tipo Aplicación de escritorio.')
    c=config['installed']
    if c.get('auth_uri')!='https://accounts.google.com/o/oauth2/auth' or c.get('token_uri')!='https://oauth2.googleapis.com/token':
        raise ValueError('El JSON no contiene las direcciones oficiales de Google.')
    flow=InstalledAppFlow.from_client_config(config,SCOPES)
    creds=flow.run_local_server(port=0,timeout_seconds=180,authorization_prompt_message='',success_message='Peak Clip: cuenta autorizada. Puedes cerrar esta ventana.')
    service=build('youtube','v3',credentials=creds,cache_discovery=False)
    rows=service.channels().list(part='snippet',mine=True).execute().get('items',[])
    if not rows: raise ValueError('La cuenta autorizada no tiene un canal de YouTube disponible.')
    record={'name':rows[0]['snippet']['title'],'id':rows[0]['id'],'credentials':json.loads(creds.to_json())}
    vault.set_password('PeakClip','youtube',json.dumps(record))
    return account()

def disconnect():
    if read(): vault.delete_password('PeakClip','youtube')

def upload(path,draft,privacy,kids,notify):
    if not lock.acquire(blocking=False): raise ValueError('Ya hay una subida en curso.')
    try:
        data=read()
        if not data: raise ValueError('Conecta tu canal de YouTube primero.')
        if privacy not in ('private','unlisted','public') or not isinstance(kids,bool): raise ValueError('Selecciona privacidad y audiencia.')
        title=draft['title'].strip()
        description=draft['description'].strip()+'\n\n'+draft['hashtags'].strip()
        if not title or len(title)>100 or len(description)>5000: raise ValueError('YouTube requiere un título de 1 a 100 caracteres y una descripción de hasta 5000.')
        creds=Credentials.from_authorized_user_info(data['credentials'],SCOPES)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request());data['credentials']=json.loads(creds.to_json());vault.set_password('PeakClip','youtube',json.dumps(data))
        service=build('youtube','v3',credentials=creds,cache_discovery=False)
        req=service.videos().insert(part='snippet,status',body={'snippet':{'title':title,'description':description,'categoryId':'24'},'status':{'privacyStatus':privacy,'selfDeclaredMadeForKids':kids}},media_body=MediaFileUpload(path,mimetype='video/mp4',chunksize=8*1024*1024,resumable=True))
        result=None
        while result is None:
            status,result=req.next_chunk(num_retries=2)
            if status: notify(round(status.progress()*100))
        return 'https://www.youtube.com/watch?v='+result['id']
    finally: lock.release()
