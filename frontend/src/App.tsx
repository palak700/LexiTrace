import {useEffect, useState} from 'react';
import {Dashboard} from './pages/Dashboard';
import {UserDashboard} from './pages/UserDashboard';
import {AuthPage} from './pages/AuthPage';
import {ApiError, request, type User} from './services/api';

export function App() {
  const [user,setUser] = useState<User|null>(null);
  const [loading,setLoading] = useState(true);
  const [error,setError] = useState('');
  async function restore() {
    setLoading(true); setError('');
    try { setUser(await request<User>('/auth/me')); }
    catch(e) { if (!(e instanceof ApiError && e.status===401)) setError('Unable to connect to the server. Check that the backend is running.'); }
    finally { setLoading(false); }
  }
  useEffect(()=>{void restore();},[]);
  if (loading) return <main className="loading-screen">Loading your workspace...</main>;
  if (error) return <main className="loading-screen"><p role="alert">{error}</p><button className="primary" onClick={restore}>Try again</button></main>;
  if (!user) return <AuthPage onAuthenticated={setUser}/>;
  return user.role==='admin' ? <Dashboard user={user} onSignedOut={()=>setUser(null)}/> : <UserDashboard user={user} onSignedOut={()=>setUser(null)}/>;
}
