import React from 'react';
import {Plus,X} from '@phosphor-icons/react';
import {call} from '../lib/bridge';

export function SessionTabs({tabs=[],active,onChange}){
  async function create(){
    const result=await call('tab_new');
    if(!result?.ok){alert(result?.error||'No se pudo crear la pestaña.');return}
    onChange?.(result);
  }
  async function focus(id){
    if(id===active)return;
    const result=await call('tab_focus',id);
    if(result?.ok) onChange?.(result);
  }
  async function close(e,id){
    e.stopPropagation();
    const result=await call('tab_close',id);
    if(!result?.ok){alert(result?.error||'No se pudo cerrar.');return}
    onChange?.(result);
  }
  return <div className="session-tabs" role="tablist" aria-label="Sesiones de clips">
    {tabs.map(tab=>(
      <button
        key={tab.id}
        type="button"
        role="tab"
        aria-selected={tab.id===active}
        className={'session-tab '+(tab.id===active?'active':'')+(tab.busy?' busy':'')}
        onClick={()=>focus(tab.id)}
        title={tab.message||tab.title}
      >
        <span className="session-tab-label">{tab.title}</span>
        {tab.busy&&<span className="session-dot" aria-hidden="true"/>}
        {tabs.length>1&&<button type="button" className="session-close" onClick={e=>close(e,tab.id)} aria-label={'Cerrar '+tab.title}><X size={12}/></button>}
      </button>
    ))}
    <button type="button" className="session-add" disabled={tabs.length>=3} onClick={create} title="Nueva sesión (máx. 3)">
      <Plus size={14}/>
    </button>
  </div>;
}
