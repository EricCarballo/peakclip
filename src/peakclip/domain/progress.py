"""Parse actual downloader/encoder output; unknown progress stays indeterminate."""
import re

def telemetry(line,stage,duration=0):
    result={}
    if stage=='transcribe' and line.startswith('CAPTION_PROGRESS='):
        try: result['stage_progress']=max(0,min(100,float(line.split('=',1)[1])))
        except ValueError: pass
    if stage=='download':
        match=re.search(r'(?:PEAK_DOWNLOAD:|\[download\]\s*)(\d+(?:\.\d+)?)%',line)
        if match: result['stage_progress']=min(100,float(match[1]))
        speed=re.search(r'\bat\s+([\d.]+\s*\w+/s)',line)
        eta=re.search(r'ETA\s+([\d:]+)',line)
        if speed: result['speed']=speed[1]
        if eta: result['eta']=eta[1]
    if stage=='chat':
        match=re.search(r'Downloading\s+(\d+)%',line)
        if match: result['stage_progress']=min(100,int(match[1]))
    if stage=='encode':
        if line.startswith('out_time_us=') and duration:
            try: result['stage_progress']=min(100,max(0,int(line.split('=',1)[1])/1_000_000/duration*100))
            except ValueError: pass
        if line.startswith('speed='): result['speed']=line.split('=',1)[1].strip()
    return result
