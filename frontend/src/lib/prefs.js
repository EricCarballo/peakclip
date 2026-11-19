const THEME_KEY='peakclip.theme';
const CAPTION_KEY='peakclip.caption_settings';

export function loadTheme(){
  const value=localStorage.getItem(THEME_KEY);
  return value==='light'||value==='dark'||value==='system'?value:'system';
}

export function applyTheme(mode){
  const resolved=mode==='system'
    ?(window.matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light')
    :mode;
  document.documentElement.dataset.theme=resolved;
  document.documentElement.dataset.themeMode=mode;
  localStorage.setItem(THEME_KEY,mode);
  return resolved;
}

export function cycleTheme(mode){
  const order=['system','light','dark'];
  const next=order[(order.indexOf(mode)+1)%order.length];
  applyTheme(next);
  return next;
}

export function loadCaptionSettings(fallback){
  try{
    const raw=localStorage.getItem(CAPTION_KEY);
    if(!raw) return {...fallback};
    return {...fallback,...JSON.parse(raw)};
  }catch{
    return {...fallback};
  }
}

export function saveCaptionSettings(value){
  localStorage.setItem(CAPTION_KEY,JSON.stringify(value));
}
