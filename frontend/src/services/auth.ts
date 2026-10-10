export type User = {id:number; name:string; email:string};
export type AuthStatus = {accounts_configured:boolean; guest_allowed:boolean};
const base = import.meta.env.VITE_API_BASE_URL ?? '';
export async function authRequest<T>(path:string, body?:unknown):Promise<T>{
 const response=await fetch(`${base}/api/auth/${path}`,{method:body===undefined?'GET':'POST',credentials:'include',
  headers:body===undefined?undefined:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});
 if(!response.ok){const payload=await response.json().catch(()=>({}));
  throw new Error(typeof payload.detail==='string'?payload.detail:'Check your details and try again.');}
 return response.json();
}
