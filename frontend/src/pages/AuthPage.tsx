import {useState, type FormEvent} from 'react';
import {ArrowRight, FileText, ShieldCheck, UserRound} from 'lucide-react';
import {request, type User} from '../services/api';

export function AuthPage({onAuthenticated}:{onAuthenticated:(user:User)=>void}) {
  const [mode,setMode] = useState<'login'|'signup'>('login');
  const [role,setRole] = useState<'user'|'admin'>('user');
  const [busy,setBusy] = useState(false);
  const [error,setError] = useState('');
  async function submit(event:FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(''); setBusy(true);
    const values = Object.fromEntries(new FormData(event.currentTarget));
    try { onAuthenticated(await request<User>(`/auth/${mode}`, {method:'POST',body:JSON.stringify({...values,role})})); }
    catch(e) { setError(e instanceof Error ? e.message : 'Unable to sign in.'); }
    finally { setBusy(false); }
  }
  return <main className="auth-layout">
    <section className="auth-story">
      <a className="brand" href="/" aria-label="LexiTrace home"><span className="brand-mark"><FileText size={23}/></span>LexiTrace</a>
      <div><p className="eyebrow">A clearer view of your writing</p><h1>Every document<br/>has a story.</h1><p className="story-copy">Explore AI authorship signals with a document-level assessment and a clear breakdown of the results.</p>
      <div className="story-note"><ShieldCheck size={24}/><span>Document authorship analysis<br/><small>Human, AI-Generated, AI-Edited Human</small></span></div></div>
      <p className="story-footer">Thoughtful analysis. Informed decisions.</p>
    </section>
    <section className="auth-form-side"><div className="auth-card">
      <p className="eyebrow">Your workspace awaits</p><h2>{mode==='login'?'Welcome back':'Create your account'}</h2><p className="muted">{mode==='login'?'Sign in to continue to your dashboard.':'Get started with document-level analysis.'}</p>
      <div className="segmented" aria-label="Authentication mode">{(['login','signup'] as const).map(item=><button key={item} type="button" aria-pressed={mode===item} className={mode===item?'active':''} disabled={busy} onClick={()=>{setMode(item);setError('');}}>{item==='login'?'Log in':'Sign up'}</button>)}</div>
      <fieldset className="role-picker" disabled={busy}><legend>Account type</legend>{(['user','admin'] as const).map(item=><label key={item} className={role===item?'selected':''}><input type="radio" name="account-type" value={item} checked={role===item} onChange={()=>{setRole(item);setError('');}}/>{item==='user'?<UserRound size={18}/>:<ShieldCheck size={18}/>}<span>{item==='user'?'User':'Administrator'}</span></label>)}</fieldset>
      <form onSubmit={submit} key={`${mode}-${role}`}>
        <fieldset className="form-fields" disabled={busy}>
          {mode==='signup'&&<label>Full name<input name="name" autoComplete="name" required maxLength={100} placeholder="Your full name"/></label>}
          <label>Email address<input name="email" type="email" autoComplete="email" required maxLength={254} placeholder="you@example.com"/></label>
          <label>Password<input name="password" type="password" autoComplete={mode==='signup'?'new-password':'current-password'} required minLength={8} maxLength={128} placeholder={mode==='signup'?'At least 8 characters':'Enter your password'}/></label>
          {mode==='signup'&&role==='admin'&&<label>Administrator setup code<input name="admin_code" type="password" required maxLength={256} autoComplete="off" placeholder="Enter your setup code"/><small className="muted">Provided by the person who runs this server.</small></label>}
        </fieldset>
        {error&&<p className="error" role="alert">{error}</p>}
        <button className="primary auth-submit" disabled={busy}>{busy?'Please wait...':mode==='login'?'Log in':'Create account'}<ArrowRight size={18}/></button>
      </form>
      <p className="auth-footnote">AI detection is probabilistic. Results are signals, not proof of authorship.</p>
    </div></section>
  </main>;
}
