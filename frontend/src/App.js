import React, { useState, useCallback, useRef, useEffect } from 'react';
import { useAuth0 } from '@auth0/auth0-react';
import { 
  Search, Image as ImageIcon, Type, CheckCircle, FileText, Lock, 
  AlertTriangle, Download, RefreshCw, UploadCloud, ScanLine, 
  ShieldCheck, LogOut, Settings, Activity, ToggleLeft, ToggleRight, User,
  ShieldAlert, Layers, Cpu, Zap
} from 'lucide-react';
import confetti from 'canvas-confetti';
import './App.css';

const tagClass = (type) => `report-tag tag-default`;
const formatType = (t) => t.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());

// Component 4: Masked Token "Redaction Bar" Style
function MaskedText({ text }) {
  const parts = text.split(/(\[[A-Z_]+_MASKED\])/g);
  return (
    <>
      {parts.map((part, i) => {
        const match = part.match(/^\[([A-Z_]+)_MASKED\]$/);
        if (match) {
          return <span key={i} className="redaction-bar" title={`Redacted: ${formatType(match[1])}`}>█████</span>;
        }
        return <span key={i}>{part}</span>;
      })}
    </>
  );
}

// Component 5: Slide-In Detection Report with Number Odometer
function OdometerCount({ endCount }) {
  const [count, setCount] = useState(0);
  useEffect(() => {
    let start = 0;
    const duration = 1000;
    const stepTime = Math.abs(Math.floor(duration / (endCount || 1)));
    const timer = setInterval(() => {
      start += 1;
      if (start > endCount) {
        clearInterval(timer);
      } else {
        setCount(start);
      }
    }, stepTime);
    return () => clearInterval(timer);
  }, [endCount]);
  return <span className="report-count">{count} item{count !== 1 ? 's' : ''} found</span>;
}

function DetectionReport({ report }) {
  if (!report) return null;
  return (
    <div className="report-section">
      <div className="report-header">
        <h3><Search size={18} /> Detection Report</h3>
        <OdometerCount endCount={report.length} />
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

// Component 8: Before/After Image Reveal Slider
function ImageReveal({ original, masked }) {
  const [sliderPos, setSliderPos] = useState(50);
  
  if (!original) {
    return <img src={masked} alt="Masked Document" />;
  }

  return (
    <div className="image-compare-wrapper">
      <img className="img-original" src={original} alt="Original" />
      <img className="img-masked" src={masked} alt="Masked" style={{ clipPath: `inset(0 0 0 ${sliderPos}%)` }} />
      <div className="slider-handle" style={{ left: `${sliderPos}%` }}></div>
      <input 
        type="range" 
        min="0" max="100" 
        value={sliderPos} 
        onChange={(e) => setSliderPos(e.target.value)}
        className="compare-range" 
      />
    </div>
  );
}

export default function App() {
  const { isAuthenticated, isLoading: authLoading, loginWithRedirect, logout, getIdTokenClaims, user } = useAuth0();
  
  const [role, setRole] = useState('user');
  const [token, setToken] = useState(null);

  const [tab, setTab] = useState('file');

  const [file, setFile] = useState(null);
  const [originalPreview, setOriginalPreview] = useState(null);
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
  const [users, setUsers] = useState([]);
  // Session Stats (Component 7)
  const [stats, setStats] = useState({ docs: 0, pii: 0 });

  const fileInputRef = useRef(null);
  const apiUrl = process.env.REACT_APP_API_URL || '';

  // Component 2: Risk Score & Character Count
  const charCount = inputText.length;
  const riskMatches = inputText.match(/\b\d{4}\s?\d{4}\s?\d{4}\b|\b[\w.-]+@[\w.-]+\.\w{2,}\b|\b\d{10}\b/g) || [];
  const riskScore = riskMatches.length;
  const riskClass = riskScore === 0 ? 'risk-low' : riskScore < 3 ? 'risk-medium' : 'risk-high';
  const riskLabel = riskScore === 0 ? 'Low Risk' : riskScore < 3 ? 'Medium Risk' : 'High Risk';

  useEffect(() => {
    const syncUser = async () => {
      if (isAuthenticated) {
        try {
          const claims = await getIdTokenClaims();
          const jwtToken = claims.__raw;
          setToken(jwtToken);

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

      const uRes = await fetch(`${apiUrl}/api/admin/users`, { headers: { 'Authorization': `Bearer ${token}` }});
      if(uRes.ok) setUsers(await uRes.json());
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
    
    // For Before/After image slider
    if (selectedFile.type.startsWith('image/')) {
      const url = URL.createObjectURL(selectedFile);
      setOriginalPreview(url);
    } else {
      setOriginalPreview(null);
    }
  }, []);

  const triggerConfetti = () => {
    confetti({ particleCount: 100, spread: 70, origin: { y: 0.6 }, colors: ['#06B6D4', '#3B82F6', '#FFFFFF'] });
  };

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
        setProcessedUrl(data.download_url);
        setReport(data.report);
        setIsLoading(false);
        triggerConfetti();
        setStats(s => ({ docs: s.docs + 1, pii: s.pii + (data.report?.length || 0) }));
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
        triggerConfetti(); // Component 9: Confetti Burst
        setStats(s => ({ docs: s.docs + 1, pii: s.pii + (data.result.report?.length || 0) }));
      } else if (data.status === 'FAILURE') {
        setError(data.error || 'Task failed during processing.');
        setIsLoading(false);
      } else {
        setTimeout(() => pollTaskStatus(taskId), 2000);
      }
    } catch (err) {
      setError('Error checking task status.');
      setIsLoading(false);
    }
  };

  const handleReset = () => {
    setFile(null);
    setOriginalPreview(null);
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
      const data = await res.json();
      setTextResult(data);
      setStats(s => ({ ...s, pii: s.pii + (data.report?.length || 0) }));
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

  const changeUserRole = async (userId, newRole) => {
    try {
      const res = await fetch(`${apiUrl}/api/admin/users/${userId}/role`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ role: newRole })
      });
      if (!res.ok) {
        const err = await res.json();
        alert(`Error: ${err.detail}`);
      } else {
        loadAdminData();
      }
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
      
      {/* Component 7: Sidebar Stats Panel */}
      <aside className="stats-sidebar">
        <div className="sidebar-title"><Activity size={14} style={{display:'inline', marginBottom:'-2px', marginRight:'4px'}}/> Session Activity</div>
        <div className="stat-item">
          <span className="stat-label">Documents Processed</span>
          <span className="stat-value">{stats.docs}</span>
        </div>
        <div className="stat-item">
          <span className="stat-label">PII Items Redacted</span>
          <span className="stat-value highlight">{stats.pii}</span>
        </div>
      </aside>

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

      {/* Component 6: Micro Status Bar */}
      <div className="micro-status-bar">
        <div className="status-indicator"><div className="status-dot online"></div> Auth0 Connected</div>
        <div className="status-indicator"><div className="status-dot online"></div> Redis Queue Ready</div>
        <div className="status-indicator"><div className="status-dot online"></div> GCP Vision Active</div>
      </div>

      <main className="App-main">
        {/* Component 10: Glassmorphism Stat Cards */}
        <div className="stat-cards-container">
          <div className="glass-stat-card">
            <div className="stat-icon-wrap"><Layers size={20} /></div>
            <div className="stat-card-content">
              <h4>Supported Formats</h4>
              <p>PDF · DOCX · IMG</p>
            </div>
          </div>
          <div className="glass-stat-card">
            <div className="stat-icon-wrap"><Search size={20} /></div>
            <div className="stat-card-content">
              <h4>Detection Engine</h4>
              <p>Presidio + GCP Vision</p>
            </div>
          </div>
          <div className="glass-stat-card">
            <div className="stat-icon-wrap"><Zap size={20} /></div>
            <div className="stat-card-content">
              <h4>Processing</h4>
              <p>Async via Celery</p>
            </div>
          </div>
        </div>

        <div className="tab-nav">
          <button className={`tab-btn${tab === 'file' ? ' active' : ''}`} onClick={() => setTab('file')}><FileText size={18} /> Document (Cloud OCR)</button>
          <button className={`tab-btn${tab === 'text' ? ' active' : ''}`} onClick={() => setTab('text')}><Type size={18} /> Text</button>
          {role === 'admin' && (
            <button className={`tab-btn${tab === 'admin' ? ' active' : ''}`} onClick={() => setTab('admin')}><Settings size={18} /> Admin</button>
          )}
        </div>

        {tab === 'file' && (
          <div className="upload-section">
            {!processedUrl && !isLoading && (
              <div 
                className={`drop-zone ${dragOver ? 'drag-over' : ''} ${file ? 'has-file' : ''}`}
                onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setDragOver(false);
                  if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
                    handleFileSelect(e.dataTransfer.files[0]);
                  }
                }}
                onClick={() => fileInputRef.current?.click()}
              >
                {/* Component 1: Animated Scanning Line */}
                <div className="scan-line"></div>
                
                {file ? (
                  <>
                    <CheckCircle className="drop-icon" size={48} style={{ color: 'var(--success)' }} />
                    <h3 className="drop-title">Ready to process</h3>
                    <p className="drop-sub">Click process to detect and mask PII.</p>
                    <div className="file-info"><FileText size={16}/> {file.name}</div>
                  </>
                ) : (
                  <>
                    <UploadCloud className="drop-icon" size={48} />
                    <h3 className="drop-title">Drag & drop document</h3>
                    <p className="drop-sub">Support for PDF, DOCX, JPG, PNG, WEBP</p>
                    <span className="drop-browse">or browse files</span>
                  </>
                )}
                <input 
                  type="file" 
                  ref={fileInputRef} 
                  className="file-input-hidden"
                  onChange={(e) => handleFileSelect(e.target.files[0])}
                  accept=".pdf,.docx,.jpg,.jpeg,.png,.webp"
                />
              </div>
            )}

            {error && <div className="alert alert-error"><AlertTriangle size={18} /> {error}</div>}

            {isLoading && (
              <div className="loading-state">
                {/* Component 3: Shield Helix Loader */}
                <div className="shield-loader-container">
                  <div className="shield-ring"></div>
                  <div className="shield-ring"></div>
                  <ShieldAlert size={36} className="shield-icon" />
                </div>
                <p>AI Masking in Progress...</p>
              </div>
            )}

            {!isLoading && file && !processedUrl && (
              <div className="btn-row">
                <button className="btn-secondary" onClick={handleReset}><RefreshCw size={16}/> Clear</button>
                <button className="btn-primary" onClick={handleProcess}><Lock size={16}/> Mask Document</button>
              </div>
            )}

            {processedUrl && !isLoading && (
              <div className="result-section">
                {file.type.startsWith('image/') ? (
                  <div className="image-card">
                    <div className="image-card-header">
                      <span className="image-card-title"><span className="image-card-title-dot dot-processed"/> Before & After</span>
                      <a href={processedUrl} download className="btn-download"><Download size={16} /> Download Masked</a>
                    </div>
                    <div className="image-card-body" style={{ padding: 0 }}>
                      <ImageReveal original={originalPreview} masked={processedUrl} />
                    </div>
                  </div>
                ) : (
                  <div className="image-card">
                    <div className="image-card-header">
                      <span className="image-card-title"><span className="image-card-title-dot dot-processed"/> Secure Document Generated</span>
                      <a href={processedUrl} download className="btn-download"><Download size={16} /> Download PDF/DOCX</a>
                    </div>
                  </div>
                )}
                
                <DetectionReport report={report} />
                
                <div className="btn-row" style={{ marginTop: '32px' }}>
                  <button className="btn-secondary" onClick={handleReset}><RefreshCw size={16}/> Process Another</button>
                </div>
              </div>
            )}
          </div>
        )}

        {tab === 'text' && (
          <div className="text-section">
            <div className="text-input-wrap">
              <div className="text-input-header">
                <label>Input Text</label>
                <span className={`risk-badge ${riskClass}`}>{riskLabel} ({charCount} chars)</span>
              </div>
              <textarea 
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                placeholder="Paste raw text here... (e.g. My SSN is 123-45-678 and email is test@corp.com)"
                disabled={textLoading}
              />
            </div>
            
            {textError && <div className="alert alert-error"><AlertTriangle size={18} /> {textError}</div>}
            
            <div className="btn-row">
              <button 
                className="btn-primary" 
                onClick={handleMaskText} 
                disabled={textLoading || !inputText.trim()}
              >
                {textLoading ? 'Analyzing...' : <><ScanLine size={16}/> Mask Text</>}
              </button>
            </div>

            {textResult && !textLoading && (
              <div className="text-result-card">
                <div className="text-result-header">
                  <span>Sanitized Output</span>
                </div>
                <div className="text-result-body">
                  <MaskedText text={textResult.masked} />
                </div>
                <DetectionReport report={textResult.pii_found ? [{ text: "Raw Text Input", pii_types: textResult.pii_types }] : []} />
              </div>
            )}
          </div>
        )}

        {tab === 'admin' && role === 'admin' && (
          <div className="admin-section">
            <div className="admin-grid" style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '24px' }}>
              <div className="admin-card">
                <h3><ShieldCheck size={20}/> DLP Policies</h3>
                <p style={{fontSize: 13, color: 'var(--text-muted)', marginBottom: 16}}>Toggle which PII entities the engine should actively mask.</p>
                <div className="policy-list">
                  {policies.map(p => (
                    <div className="policy-item" key={p.pii_type}>
                      <span style={{fontWeight: 500, fontSize: 14}}>{formatType(p.pii_type)}</span>
                      <button className="toggle-btn" onClick={() => togglePolicy(p.pii_type, p.is_active)} style={{ color: p.is_active ? 'var(--success)' : 'var(--text-muted)' }}>
                        {p.is_active ? <ToggleRight size={24}/> : <ToggleLeft size={24}/>}
                      </button>
                    </div>
                  ))}
                </div>
              </div>
              <div className="admin-card">
                <h3><Activity size={20}/> Audit Logs</h3>
                <p style={{fontSize: 13, color: 'var(--text-muted)', marginBottom: 16}}>Immutable record of all PII processing activity.</p>
                <div className="audit-table-wrap">
                  <table className="audit-table">
                    <thead><tr><th>Time</th><th>User (Auth0)</th><th>Action</th><th>IP Address</th></tr></thead>
                    <tbody>
                      {logs.map(l => (
                        <tr key={l.id}>
                          <td>{new Date(l.timestamp).toLocaleString()}</td>
                          <td><span className="tag-user"><User size={10} style={{display:'inline'}}/> {l.user_id}</span></td>
                          <td><span className="tag-primary">{l.action}</span></td>
                          <td style={{fontFamily: 'monospace'}}>{l.ip_address}</td>
                        </tr>
                      ))}
                      {logs.length === 0 && <tr><td colSpan="4" style={{textAlign:'center', color:'var(--text-muted)'}}>No logs found</td></tr>}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
            
            {/* Component: User Management Row */}
            <div className="admin-card" style={{ marginTop: '24px' }}>
              <h3><User size={20}/> User Management & RBAC</h3>
              <p style={{fontSize: 13, color: 'var(--text-muted)', marginBottom: 16}}>Control access privileges and promote members to administrative roles.</p>
              <div className="audit-table-wrap">
                <table className="audit-table">
                  <thead><tr><th>ID</th><th>Username / Auth0 Sub</th><th>Current Role</th><th>Change Role</th></tr></thead>
                  <tbody>
                    {users.map(u => (
                      <tr key={u.id}>
                        <td>{u.id}</td>
                        <td style={{fontFamily: 'monospace'}}>{u.username}</td>
                        <td><span className={`role-badge role-${u.role}`}>{u.role}</span></td>
                        <td>
                          <select 
                            className="role-select" 
                            value={u.role}
                            onChange={(e) => changeUserRole(u.id, e.target.value)}
                          >
                            <option value="user">User</option>
                            <option value="admin">Admin</option>
                          </select>
                        </td>
                      </tr>
                    ))}
                    {users.length === 0 && <tr><td colSpan="4" style={{textAlign:'center', color:'var(--text-muted)'}}>No users found</td></tr>}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
