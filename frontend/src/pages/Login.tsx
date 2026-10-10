import {useState, type FormEvent} from 'react';
import {authRequest, type AuthStatus, type User} from '../services/auth';

type Props={status:AuthStatus|null; connectionError:string; onLogin:(user:User)=>void; onGuest:()=>void; onRetry:()=>void};
export function Login({status,connectionError,onLogin,onGuest,onRetry}:Props){
 const [register,setRegister]=useState(false);const [name,setName]=useState('');
 const [email,setEmail]=useState('');const [password,setPassword]=useState('');
 const [busy,setBusy]=useState(false);const [error,setError]=useState('');
 async function submit(e:FormEvent){e.preventDefault();setBusy(true);setError('');
  try{const result=await authRequest<{user:User}>(register?'register':'login',register?{name,email,password}:{email,password});
   setPassword('');onLogin(result.user);
  }catch(e){setError(e instanceof Error?e.message:'Sign in failed');}finally{setBusy(false);}}
 return <main className="min-h-screen flex items-center justify-center px-5 py-10 bg-paper">
 <div className="w-full max-w-md bg-white border border-ink/10 rounded-2xl p-8 shadow-sm">
 <div className="mb-8"><div className="text-xs font-semibold uppercase tracking-widest text-moss">Detect · Localize · Explain</div>
 <h1 className="text-3xl font-bold mt-2">LexiTrace</h1><p className="text-ink/65 mt-2">Explore the evidence behind AI text analysis.</p></div>
 <h2 className="text-xl font-semibold">{register?'Create your account':'Welcome back'}</h2>
 <p className="text-sm text-ink/65 mt-1 mb-5">{register?'Register to start analyzing text.':'Sign in to your account to continue.'}</p>
 <form onSubmit={submit} className="space-y-4">
 {register&&<label className="block text-sm font-medium">Name<input className="block w-full border rounded-lg p-3 mt-1" autoComplete="name" required maxLength={80} value={name} onChange={e=>setName(e.target.value)}/></label>}
 <label className="block text-sm font-medium">Email<input className="block w-full border rounded-lg p-3 mt-1" type="email" autoComplete="email" required maxLength={254} value={email} onChange={e=>setEmail(e.target.value)}/></label>
 <label className="block text-sm font-medium">Password<input className="block w-full border rounded-lg p-3 mt-1" type="password" autoComplete={register?'new-password':'current-password'} required minLength={register?10:1} maxLength={128} value={password} onChange={e=>setPassword(e.target.value)}/></label>
 {register&&<p className="text-xs text-ink/60">Use at least 10 characters.</p>}
 {(error||connectionError)&&<p className="text-sm text-red-700" role="alert">{error||connectionError}</p>}
 <button disabled={busy||!status?.accounts_configured} className="w-full bg-ink text-white p-3 rounded-lg font-semibold disabled:opacity-50">{busy?'Please wait…':register?'Create account':'Sign in'}</button>
 </form>
 <p className="text-sm mt-5 text-center">{register?'Already have an account?':'New to LexiTrace?'} <button className="text-bluegray font-semibold underline" disabled={busy} onClick={()=>{setRegister(!register);setPassword('');setError('');}}>{register?'Sign in':'Create account'}</button></p>
 {status?.guest_allowed&&<div className="border-t mt-6 pt-5"><button className="w-full border border-ink/20 p-3 rounded-lg" onClick={onGuest}>Try guest demo</button><p className="text-xs text-ink/60 mt-2">Guest mode uses untrained demo analysis. Accounts become available when PostgreSQL is configured.</p></div>}
 {connectionError&&<button className="underline text-sm mt-4" onClick={onRetry}>Retry connection</button>}
 </div></main>;
}
