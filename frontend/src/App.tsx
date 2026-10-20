import {useEffect,useState} from 'react';
import {Dashboard} from './pages/Dashboard';
import {UserDashboard} from './pages/UserDashboard';
import {AuthPage} from './pages/AuthPage';
import {ApiError,request,type User,type Capabilities} from './services/api';
export function App(){
  const [user,setUser]=useState<User|null>(null);
  const [loading,setLoading]=useState(true);
  const [anonymous,setAnonymous]=useState(false);
  const [showAuth,setShowAuth]=useState(false);
  const [error,setError]=useState('');
  async function restore(){
    setLoading(true);setError('');
    try{
      const config=await request<Capabilities>('/capabilities');setAnonymous(config.allow_anonymous);
      try{setUser(await request<User>('/auth/me'));}catch(e){if(!(e instanceof ApiError&&e.status===401)&&!config.allow_anonymous)throw e;}
    }catch{setError('Unable to connect to the server. Check that the backend is running.');}
    finally{setLoading(false);}
  }
  useEffect(()=>{void restore();},[]);
  if(loading)return <main className="loading-screen">Loading your workspace...</main>;
  if(error)return <main className="loading-screen"><p role="alert">{error}</p><button className="primary" onClick={restore}>Try again</button></main>;
  if(!user&&(showAuth||!anonymous))return <>{anonymous&&<button className="text-button auth-back" onClick={()=>setShowAuth(false)}>Back to analysis</button>}<AuthPage onAuthenticated={value=>{setUser(value);setShowAuth(false);}}/></>;
  const signOut=()=>{setUser(null);setShowAuth(false);};
  return user?.role==='admin'?<Dashboard user={user} onSignedOut={signOut}/>:<UserDashboard user={user} onSignedOut={signOut} onSignIn={()=>setShowAuth(true)}/>;
}
