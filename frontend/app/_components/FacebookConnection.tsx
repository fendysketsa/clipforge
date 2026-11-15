"use client";
import { useEffect, useState } from 'react';
import { Facebook, Loader2, RefreshCw, LogIn, ExternalLink } from 'lucide-react';
import { facebookRequest, type FacebookConfig, type FacebookSession } from '../../lib/facebook';

export function FacebookConnection({onChange}: {onChange?: (session: FacebookSession) => void}) {
  const [config, setConfig] = useState<FacebookConfig | null>(null);
  const [session, setSession] = useState<FacebookSession>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    let alive = true;
    facebookRequest<FacebookConfig>('facebook/config').then(value => {
      if (alive) {setConfig(value); setSession(value.session); onChange?.(value.session);}
    }).catch(reason => {if (alive) setError(reason.message);});
    return () => {alive = false;};
  }, [onChange]);
  const check = async (login = false) => {
    setBusy(true); setError('');
    try {
      const value = await facebookRequest<FacebookSession>(login ? 'social/login' : 'facebook/session/check', {});
      setSession(value); onChange?.(value);
    } catch (reason) {setError(reason instanceof Error ? reason.message : 'Pemeriksaan gagal.');}
    finally {setBusy(false);}
  };
  const labels: Record<string, string> = {ready:'Akun target terverifikasi', login_required:'Perlu login Facebook',
    account_unverified:'Identitas perlu diperiksa', browser_unavailable:'Browser belum terhubung'};
  return <section className="connectionCard fbConnection" aria-label="Koneksi Facebook">
    <header><span className="connectionLogo fbLogo"><Facebook size={25}/></span><div><h2>Facebook Reels</h2><p>{config?.target_email || 'fendysketsa@gmail.com'}</p></div></header>
    <span className={`connectionState ${session.account_verified ? 'isReady' : ''}`}>
      {busy ? <Loader2 size={14} className="spin"/> : <Facebook size={14}/>}
      {busy ? 'Memeriksa browser…' : labels[session.status || ''] || 'Sesi belum diperiksa'}
    </span>
    <p>{error || session.message || 'Gunakan browser bersama YouTube dan TikTok untuk menyimpan login Facebook.'}</p>
    {error ? <p role="alert" className="fbError">Koneksi belum siap digunakan.</p> : null}
    <div className="connectionActions">
      <button className="uiButton uiButton--primary" type="button" disabled={busy || !config} onClick={() => check(true)}><LogIn size={15}/> Buka login bersama</button>
      <button className="uiButton" type="button" disabled={busy || !config} onClick={() => check()}><RefreshCw size={15}/> Periksa sesi</button>
      <a className="uiButton" href="https://www.facebook.com/" target="_blank" rel="noreferrer"><ExternalLink size={14}/> Buka Facebook</a>
    </div>
    <small>{config?.login_note || 'Login tiap platform tersimpan di satu profil browser. Verifikasi ulang dapat diminta oleh platform.'}</small>
    {session.account_verified ? <small>{session.professional_mode === true ? 'Mode profesional terdeteksi pada profil.' : 'Mode profesional belum terverifikasi; periksa profil Facebook.'}</small> : null}
    {session.checked_at ? <small>Terakhir diperiksa: {new Date(session.checked_at).toLocaleString('id-ID', {timeZone:'Asia/Jakarta'})} WIB</small> : null}
  </section>;
}
