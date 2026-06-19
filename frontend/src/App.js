import React, { useState, useCallback, useRef, useEffect } from 'react';
import { useAuth0 } from '@auth0/auth0-react';
import { 
  Search, Image as ImageIcon, Type, CheckCircle, FileText, Lock, 
  AlertTriangle, Download, RefreshCw, UploadCloud, ScanLine, 
  ShieldCheck, LogOut, Settings, Activity, ToggleLeft, ToggleRight, User
} from 'lucide-react';
import './App.css';

const tagClass = (type) => `report-tag tag-default`;
const formatType = (t) => t.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());

function MaskedText({ text }) {
  const parts = text.split(/(\[[A-Z_]+_MASKED\])/g);
  return (
    <>
      {parts.map((part, i) =>
        part.match(/^\[[A-Z_]+_MASKED\]$/)
          ? <span key={i} className="masked-token">{part}</span>
          : <span key={i}>{part}</span>
      )}
    </>
  );
}

function DetectionReport({ report }) {
  if (!report) return null;
  return (
    <div className="report-section">
      <div className="report-header">
        <h3><Search size={18} /> Detection Report</h3>
        <span className="report-count">{report.length} item{report.length !== 1 ? 's' : ''} found</span>
      </div>
      <div className="report-body">
        {report.length === 0 ? (
          <p className="report-empty">✓ No PII detected.</p>
        ) : (
          report.map((item, i) => (
            <div className="report-item" key={i}>
              <span className="report-item-num">{i + 1}</span>
              <div className="report-item-content">
                <p className="report-item-text">{item.text}</p>
                <div className="report-tags">
                  {item.pii_types.map(t => (
                    <span key={t} className={tagClass(t)}>{formatType(t)}</span>
                  ))}
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

export default function App() {
  const { isAuthenticated, isLoading: authLoading, loginWithRedirect, logout, getIdTokenClaims, user } = useAuth0();
  
  const [role, setRole] = useState('user');
  const [token, setToken] = useState(null);

  const [tab, setTab] = useState('file');

  const [file, setFile] = useState(null);
  const [processedUrl, setProcessedUrl] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [report, setReport] = useState(null);
  const [dragOver, setDragOver] = useState(false);

  const [inputText, setInputText] = useState('');
  const [textResult, setTextResult] = useState(null);
  const [textLoading, setTextLoading] = useState(false);
  const [textError, setTextError] = useState('');

  const [logs, setLogs] = useState([]);
  const [policies, setPolicies] = useState([]);

  const fileInputRef = useRef(null);
  const apiUrl = process.env.REACT_APP_API_URL || '';

  // Sync Auth0 user with backend and retrieve role
  useEffect(() => {
    const syncUser = async () => {
      if (isAuthenticated) {
        try {
          const claims = await getIdTokenClaims();
          const jwtToken = claims.__raw;
          setToken(jwtToken);

          // Call backend to sync user & fetch role
          const res = await fetch(`${apiUrl}/api/auth/sync`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${jwtToken}` }
          });
          if (res.ok) {
            const data = await res.json();
            setRole(data.role);
          }
        } catch (e) {
          console.error("Failed to sync user:", e);
        }
      }
    };
    syncUser();
  }, [isAuthenticated, getIdTokenClaims, apiUrl]);

  const loadAdminData = useCallback(async () => {
    if (!token || role !== 'admin') return;
    try {
      const pRes = await fetch(`${apiUrl}/api/admin/policies`, { headers: { 'Authorization': `Bearer ${token}` }});
      if(pRes.ok) setPolicies(await pRes.json());
      
      const lRes = await fetch(`${apiUrl}/api/admin/logs`, { headers: { 'Authorization': `Bearer ${token}` }});
      if(lRes.ok) setLogs(await lRes.json());
    } catch(err) {}
  }, [apiUrl, token, role]);

  useEffect(() => {
    if (tab === 'admin') loadAdminData();
  }, [tab, loadAdminData]);

  const handleApiError = (res) => {
    if (res.status === 401) {
      logout({ logoutParams: { returnTo: window.location.origin } });
      throw new Error('Session expired. Please log in again.');
    }
  };

  const handleFileSelect = useCallback((selectedFile) => {
    if (!selectedFile) return;
    setFile(selectedFile);
    setProcessedUrl(null);
    setReport(null);
    setError('');
  }, []);

  const handleProcess = async () => {
    if (!file) { setError('Please select a file first.'); return; }
    setIsLoading(true);
    setError('');
    setProcessedUrl(null);
    setReport(null);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch(`${apiUrl}/api/upload`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: formData,
      });
      handleApiError(res);
      if (!res.ok) {
        const errBody = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(errBody.detail || 'Processing failed.');
      }

      const data = await res.json();
      
      if (res.status === 202 && data.task_id) {
        pollTaskStatus(data.task_id);
      } else {
        // Fallback if backend responds synchronously
        setProcessedUrl(data.download_url);
        setReport(data.report);
        setIsLoading(false);
      }

    } catch (err) {
      setError(err.message || 'Processing failed.');
      setIsLoading(false);
    }
  };

  const pollTaskStatus = async (taskId) => {
    try {
      const res = await fetch(`${apiUrl}/api/tasks/${taskId}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      handleApiError(res);
      const data = await res.json();

      if (data.status === 'SUCCESS') {
        setProcessedUrl(data.result.download_url);
        setReport(data.result.report);
        setIsLoading(false);
      } else if (data.status === 'FAILURE') {
        setError(data.error || 'Task failed during processing.');
        setIsLoading(false);
      } else {
        // Still processing, poll again in 2 seconds
        setTimeout(() => pollTaskStatus(taskId), 2000);
      }
    } catch (err) {
      setError('Error checking task status.');
      setIsLoading(false);
    }
  };

  const handleReset = () => {
    setFile(null);
    setProcessedUrl(null);
    setReport(null);
    setError('');
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleMaskText = async () => {
    if (!inputText.trim()) { setTextError('Please enter some text.'); return; }
    setTextLoading(true);
    setTextError('');
    setTextResult(null);

    try {
      const res = await fetch(`${apiUrl}/api/mask-text`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ text: inputText }),
      });
      handleApiError(res);
      if (!res.ok) throw new Error('Text analysis failed.');
      setTextResult(await res.json());
    } catch (err) {
      setTextError(err.message || 'Text analysis failed.');
    } finally {
      setTextLoading(false);
    }
  };

  const togglePolicy = async (piiType, currentStatus) => {
    try {
      await fetch(`${apiUrl}/api/admin/policies`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ pii_type: piiType, is_active: !currentStatus })
      });
      loadAdminData();
    } catch(e) {}
  };

  if (authLoading) {
    return <div className="App auth-bg"><div className="loader-ring"></div></div>;
  }

  if (!isAuthenticated) {
    return (
      <div className="App auth-bg">
        <div className="bg-pattern" />
        <div className="auth-container">
          <div className="auth-card" style={{ textAlign: 'center' }}>
            <div className="auth-header">
              <ShieldCheck size={48} className="auth-icon" style={{ margin: '0 auto 16px' }} />
              <h2>Enterprise Privacy Suite</h2>
              <p>Corporate Single Sign-On</p>
            </div>
            <button className="btn-primary" style={{ width: '100%', justifyContent: 'center' }} onClick={() => loginWithRedirect()}>
              Log In with Auth0
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="App">
      <div className="bg-pattern" />
      <header className="App-header">
        <div className="header-top-right" style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <span style={{ color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <img src={user?.picture} alt="Avatar" style={{ width: 24, height: 24, borderRadius: '50%' }} />
            {user?.name}
          </span>
          <span style={{ color: 'var(--text-muted)' }}>Role: <b>{role}</b></span>
          <button className="btn-logout" onClick={() => logout({ logoutParams: { returnTo: window.location.origin } })}>
            <LogOut size={16} /> Sign out
          </button>
        </div>
        <div className="header-inner">
          <div className="header-badge"><span className="header-badge-dot" /> Enterprise Edition</div>
          <h1>Mask <em>Sensitive</em> Information</h1>
        </div>
      </header>

      <main className="App-main">
        <div className="tab-nav">
          <button className={`tab-btn${tab === 'file' ? ' active' : ''}`} onClick={() => setTab('file')}><FileText size={18} /> Document (Cloud OCR)</button>
          <button className={`tab-btn${tab === 'text' ? ' active' : ''}`} onClick={() => setTab('text')}><Type size={18} /> Text</button>
          {role === 'admin' && (
            <button className={`tab-btn${tab === 'admin' ? ' active' : ''}`} onClick={() => setTab('admin')}><Settings size={18} /> Admin</button>
          )}
        </div>

        {tab === 'file' && (
          <div className="upload-section">
            <div className={`drop-zone${dragOver ? ' drag-over' : ''}${file ? ' has-file' : ''}`}
                 onDrop={handleDrop} onDragOver={e => {e.preventDefault(); setDragOver(true);}} onDragLeave={() => setDragOver(false)}>
              <input ref={fileInputRef} type="file" onChange={(e) => handleFileSelect(e.target.files[0])} className="file-input-hidden" />
              {file ? (
                <>
                  <CheckCircle size={48} className="drop-icon" style={{color: 'var(--success)'}} />
                  <p className="drop-title">File ready</p>
                  <span className="file-info">{file.name} · {(file.size / 1024).toFixed(0)} KB</span>
                </>
              ) : (
                <>
                  <UploadCloud size={56} className="drop-icon" />
                  <p className="drop-title">Drop document or image</p>
                  <p className="drop-sub">Processed securely via Google Cloud Vision & AWS S3</p>
                </>
              )}
            </div>

            {error && <div className="alert alert-error"><AlertTriangle size={18} /> {error}</div>}

            <div className="btn-row">
              <button className="btn-primary" onClick={handleProcess} disabled={!file || isLoading}>
                {isLoading ? 'Processing in Cloud…' : <><Lock size={18} /> Mask Document</>}
              </button>
              {(file || processedUrl) && <button className="btn-secondary" onClick={handleReset}><RefreshCw size={16} /> Reset</button>}
              {processedUrl && <a href={processedUrl} target="_blank" rel="noreferrer" className="btn-download"><Download size={16} /> Download from S3</a>}
            </div>
            {report && !isLoading && <DetectionReport report={report} />}
          </div>
        )}

        {/* Text and Admin tabs remain same layout, just omitting implementation here for brevity to focus on changes */}
        {tab === 'text' && (
          <div className="text-section">
            <div className="text-input-wrap">
              <textarea placeholder="Paste text here..." value={inputText} onChange={e => setInputText(e.target.value)} rows={8} />
            </div>
            {textError && <div className="alert alert-error">{textError}</div>}
            <div className="btn-row">
              <button className="btn-primary" onClick={handleMaskText} disabled={!inputText.trim() || textLoading}>
                {textLoading ? 'Scanning…' : <><ScanLine size={18} /> Mask Text</>}
              </button>
              {textResult && <button className="btn-secondary" onClick={() => { setInputText(''); setTextResult(null); }}>Clear</button>}
            </div>
            {textResult && (
              <div className="text-result-card">
                <div className="text-result-header">Masked output</div>
                <div className="text-result-body">
                  {textResult.pii_found ? <MaskedText text={textResult.masked} /> : <span style={{ color: 'var(--text-muted)' }}>No PII detected.</span>}
                </div>
              </div>
            )}
          </div>
        )}

        {tab === 'admin' && role === 'admin' && (
          <div className="admin-section">
            <div className="admin-grid">
              <div className="admin-card">
                <h3><ShieldCheck size={20}/> DLP Policies</h3>
                <div className="policy-list">
                  {policies.map(p => (
                    <div className="policy-item" key={p.pii_type}>
                      <span>{p.pii_type}</span>
                      <button className="toggle-btn" onClick={() => togglePolicy(p.pii_type, p.is_active)} style={{color: p.is_active ? 'var(--accent-cyan)' : 'var(--text-muted)'}}>
                        {p.is_active ? <ToggleRight size={28}/> : <ToggleLeft size={28}/>}
                      </button>
                    </div>
                  ))}
                </div>
              </div>

              <div className="admin-card audit-card">
                <h3><Activity size={20}/> Audit Logs</h3>
                <div className="audit-table-wrap">
                  <table className="audit-table">
                    <thead><tr><th>Time</th><th>Auth0 User ID</th><th>Action</th><th>Entities Detected</th></tr></thead>
                    <tbody>
                      {logs.map(l => (
                        <tr key={l.id}>
                          <td style={{whiteSpace:'nowrap'}}>{new Date(l.timestamp).toLocaleString()}</td>
                          <td style={{maxWidth: '120px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap'}}>{l.user_id}</td>
                          <td><span className={`tag-${l.action === 'LOGIN' ? 'user' : 'primary'}`}>{l.action}</span></td>
                          <td>{(l.details?.detected || []).join(', ')}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
