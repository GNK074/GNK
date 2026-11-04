import {useEffect,useRef,useState} from 'react';
import {api} from '../services/api';

// Only a short-lived GNK ticket reaches this socket; broker tokens stay on server.
export function DhanPrivateFeed({account,instrument}:{account:string;instrument?:any}) {
 const [query,setQuery]=useState(''),[items,setItems]=useState<any[]>([]),[selected,setSelected]=useState<any>(instrument),[active,setActive]=useState(false),[data,setData]=useState<any>(null),[note,setNote]=useState('');
 const socket=useRef<WebSocket|null>(null);
 useEffect(()=>{setSelected(instrument);setActive(false)},[instrument,account]);
 useEffect(()=>{if(!query.trim()){setItems([]);return}let valid=true;const t=setTimeout(()=>api('/dhan/instruments?'+new URLSearchParams({q:query})).then(d=>{if(valid)setItems(d.items)}).catch(e=>{if(valid)setNote(e.message)}),300);return()=>{valid=false;clearTimeout(t)}},[query]);
 useEffect(()=>{
  if(!active||!account||!selected)return;
  let disposed=false;let timer:number|undefined;const subscriptionId=crypto.randomUUID();
  async function subscribe(){await api('/auth/session');await api('/dhan/stream/subscribe','POST',{account_id:account,instrument_ids:[selected.id],subscription_id:subscriptionId})}
  async function open(){try{await subscribe();if(disposed)return;const t=await api('/dhan/stream-ticket','POST',{account_id:account});if(disposed)return;const ws=new WebSocket(`${location.protocol==='https:'?'wss:':'ws:'}//${location.host}/ws/v1/dhan`,['gnk.dhan',t.ticket]);socket.current=ws;ws.onmessage=e=>{if(!disposed){try{setData(JSON.parse(e.data));setNote('')}catch{setNote('Invalid stream message')}}};ws.onclose=()=>{if(!disposed){setNote('Private stream closed. Reconnect to refresh your session.');setActive(false);setData(null)}};ws.onerror=()=>{if(!disposed)setNote('Private stream unavailable')};timer=window.setInterval(()=>subscribe().catch(e=>{setNote(e.message);setActive(false)}),120000)}catch(e){if(!disposed){setNote((e as Error).message);setActive(false)}}}
  open();return()=>{disposed=true;clearInterval(timer);socket.current?.close();socket.current=null;setData(null);api('/dhan/stream/subscribe','POST',{account_id:account,instrument_ids:[],subscription_id:subscriptionId}).catch(()=>{})};
 },[active,account,selected?.id]);
 const tick=data?.ticks?.find((r:any)=>r.instrument_key===selected?.instrument_key);
 return <section className="market-card"><h2>Private live feed</h2><p>Visible only to your GNK account. Broker data permissions apply. Order notifications are confirmed against the broker ledger before fills are recorded.</p>
 <div className="market-controls"><label>Find NSE equity<input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search synchronized Dhan symbols" disabled={active}/></label>{items.map(i=><button disabled={active} key={i.id} onClick={()=>{setSelected(i);setItems([]);setQuery('')}}>{i.symbol}</button>)}<span>{selected?.symbol||'Select an instrument'}</span><button disabled={!account||!selected||active} onClick={()=>{setNote('Connecting…');setActive(true)}}>Connect private feed</button><button disabled={!active} onClick={()=>{setActive(false);setNote('Disconnected')}}>Disconnect feed</button></div>
 <p role="status">{note||`${data?.connection?.market_connected==='1'?'Broker connected':'Awaiting broker connection'} · ${tick?.data_status||'UNAVAILABLE'}`}</p>
 {tick&&<p>{selected?.symbol} · {tick.ltp??'—'} · {tick.data_status} · {tick.exchange_timestamp?new Date(tick.exchange_timestamp*1000).toLocaleString('en-IN',{timeZone:'Asia/Kolkata'}):'No exchange timestamp'}</p>}
 {data?.order_update&&<p>Order {data.order_update.order_id}: {data.order_update.status} · REST reconciliation required</p>}
 </section>
}
