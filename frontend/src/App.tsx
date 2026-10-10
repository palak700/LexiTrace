import {useEffect,useState} from 'react';
import {Dashboard} from './pages/Dashboard';
import {Login} from './pages/Login';
import {authRequest,type User,type AuthStatus} from './services/auth';

export function App(){
 const [user,setUser]=useState<User|null>(null); const [guest,setGuest]=useState(false);
 const [status,setStatus]=useState<AuthStatus|null>(null);const [loading,setLoading]=useState(true);
 const [error,setError]=useState(''); const [logoutError,setLogoutError]=useState('');
 async function initialize(){setLoading(true);setError('');
  try{const state=await authRequest<AuthStatus>('status');setStatus(state);
   if(state.accounts_configured){try{const session=await authRequest<{user:User}>('me');setUser(session.user);}catch{setUser(null);}}
  }catch{setError('Cannot reach the backend. Start it on port 8000 and retry.');}
  finally{setLoading(false);}}
 useEffect(()=>{void initialize();},[]);
 async function logout(){setLogoutError('');
  try{if(user)await authRequest('logout',{});setUser(null);setGuest(false);}
  catch(e){setLogoutError(e instanceof Error?e.message:'Sign out failed. Please retry.');}}
 if(loading)return <main className="p-10 text-center">Loading LexiTrace…</main>;
 if(!user&&!guest)return <Login status={status} connectionError={error} onLogin={setUser} onGuest={()=>setGuest(true)} onRetry={()=>void initialize()}/>;
 return <><nav className="bg-white border-b px-6 py-3 flex justify-between items-center"><span>{user?`Signed in as ${user.name}`:'Guest demo'}</span><button className="underline" onClick={()=>void logout()}>{user?'Sign out':'Back to sign in'}</button></nav>
 {logoutError&&<p role="alert" className="text-red-700 px-6">{logoutError}</p>}<Dashboard/></>;
}
