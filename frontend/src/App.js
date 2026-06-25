import React, { useState, useCallback, useRef, useEffect, useLayoutEffect } from 'react';
import { useAuth0 } from '@auth0/auth0-react';
import { 
  Search, Image as ImageIcon, Type, CheckCircle, FileText, Lock, 
  AlertTriangle, Download, RefreshCw, UploadCloud, ScanLine, 
  ShieldCheck, LogOut, Settings, Activity, ToggleLeft, ToggleRight, User,
  ShieldAlert, Layers, Cpu, Zap, Database, X, ChevronRight
} from 'lucide-react';
import confetti from 'canvas-confetti';
import './App.css';

/* ============================================================
   UTILITY HELPERS
   ============================================================ */
const formatType = (t) => t.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());

/* ============================================================
   TOAST NOTIFICATION SYSTEM
   ============================================================ */
let toastIdCounter = 0;
const ToastContext = React.createContext(null);

function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);

  const addToast = useCallback((message, type = 'info', duration = 5000) => {
    const id = ++toastIdCounter;
    setToasts(prev => [...prev.slice(-2), { id, message, type, duration }]);
    return id;
  }, []);

  const removeToast = useCallback((id) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  return (
    <ToastContext.Provider value={{ addToast, removeToast }}>
      {children}
      <ToastContainer toasts={toasts} removeToast={removeToast} />
    </ToastContext.Provider>
  );
}

function useToast() {
  return React.useContext(ToastContext);
}

function ToastContainer({ toasts, removeToast }) {
  return (
    <div className="toast-container">
      {toasts.map(t => (
        <Toast key={t.id} toast={t} onRemove={removeToast} />
      ))}
    </div>
  );
}

function Toast({ toast, onRemove }) {
  const [visible, setVisible] = useState(false);
  const [width, setWidth] = useState(100);

  useEffect(() => {
    requestAnimationFrame(() => setVisible(true));
    const step = 100 / (toast.duration / 50);
    const interval = setInterval(() => {
      setWidth(w => {
        if (w <= 0) { clearInterval(interval); onRemove(toast.id); return 0; }
        return w - step;
      });
    }, 50);
    return () => clearInterval(interval);
  }, [toast.id, toast.duration, onRemove]);

  const icons = { success: <CheckCircle size={16} />, error: <AlertTriangle size={16} />, info: <ShieldCheck size={16} /> };

  return (
    <div className={`toast toast-${toast.type} ${visible ? 'toast-visible' : ''}`}>
      <div className="toast-icon">{icons[toast.type] || icons.info}</div>
      <span className="toast-message">{toast.message}</span>
      <button className="toast-close" onClick={() => onRemove(toast.id)}><X size={14} /></button>
      <div className="toast-progress" style={{ width: `${width}%` }} />
    </div>
  );
}

/* ============================================================
   COMMAND PALETTE (Ctrl+K)
   ============================================================ */
function CommandPalette({ isOpen, onClose, onNavigate }) {
  const [query, setQuery] = useState('');
  const inputRef = useRef(null);

  const commands = [
    { id: 'file',  label: 'Upload Document',       icon: <FileText size={16} />,    shortcut: 'Ctrl+U', tab: 'file'  },
    { id: 'text',  label: 'Scan Text',              icon: <Type size={16} />,        shortcut: 'Ctrl+T', tab: 'text'  },
    { id: 'cloud', label: 'Cloud Bucket Scan',      icon: <Database size={16} />,    shortcut: 'Ctrl+S', tab: 'cloud' },
    { id: 'admin', label: 'Admin Dashboard',        icon: <Settings size={16} />,    shortcut: 'Ctrl+A', tab: 'admin' },
    { id: 'audit', label: 'View Audit Logs',        icon: <Activity size={16} />,    tab: 'admin' },
  ];

  const filtered = commands.filter(c =>
    c.label.toLowerCase().includes(query.toLowerCase())
  );

  useEffect(() => {
    if (isOpen) { setQuery(''); setTimeout(() => inputRef.current?.focus(), 50); }
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div className="palette-backdrop" onClick={onClose}>
      <div className="palette-modal" onClick={e => e.stopPropagation()}>
        <div className="palette-search-row">
          <Search size={18} className="palette-search-icon" />
          <input
            ref={inputRef}
            className="palette-input"
            placeholder="Type a command..."
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Escape') onClose();
              if (e.key === 'Enter' && filtered.length > 0) { onNavigate(filtered[0].tab); onClose(); }
            }}
          />
          <kbd className="palette-esc">Esc</kbd>
        </div>
        <div className="palette-list">
          {filtered.map(cmd => (
            <button key={cmd.id} className="palette-item" onClick={() => { onNavigate(cmd.tab); onClose(); }}>
              <span className="palette-item-icon">{cmd.icon}</span>
              <span className="palette-item-label">{cmd.label}</span>
              {cmd.shortcut && <kbd className="palette-item-shortcut">{cmd.shortcut}</kbd>}
              <ChevronRight size={14} className="palette-item-arrow" />
            </button>
          ))}
          {filtered.length === 0 && (
            <div className="palette-empty">No commands found</div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ============================================================
   HERO CANVAS ANIMATION — streaming redaction visualization
   ============================================================ */
function HeroCanvas() {
  const canvasRef = useRef(null);

  useLayoutEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let animId;
    let W = canvas.offsetWidth;
    let H = canvas.offsetHeight;
    canvas.width = W;
    canvas.height = H;

    const COLS = Math.floor(W / 14);
    const FONT_SIZE = 13;
    const SHIELD_Y = H * 0.62;
    const PARTICLES = [];

    const WORDS = [
      'john.doe@corp.com', '9876543210', 'Aadhaar-2345', '4532 1234 5678 9012',
      'ABCDE1234F', 'SSN:123-45', 'Dr. Sarah Kim', 'MRN-90421',
      '192.168.0.1', 'passport-A1234', 'BankAcc-99812', 'MH12AB1234',
    ];

    const streams = Array.from({ length: COLS }, (_, i) => ({
      x: i * 14 + 7,
      y: Math.random() * -H,
      speed: 0.4 + Math.random() * 0.6,
      word: WORDS[Math.floor(Math.random() * WORDS.length)],
      charIdx: 0,
      redacted: false,
      opacity: 0.6 + Math.random() * 0.4,
    }));

    function spawnParticle(x, y) {
      for (let i = 0; i < 6; i++) {
        PARTICLES.push({
          x, y,
          vx: (Math.random() - 0.5) * 2,
          vy: (Math.random() - 1) * 1.5,
          life: 1,
          r: Math.random() * 3 + 1,
        });
      }
    }

    function draw() {
      ctx.clearRect(0, 0, W, H);

      // Subtle grid
      ctx.strokeStyle = 'rgba(6,182,212,0.04)';
      ctx.lineWidth = 1;
      for (let gx = 0; gx < W; gx += 40) {
        ctx.beginPath(); ctx.moveTo(gx, 0); ctx.lineTo(gx, H); ctx.stroke();
      }
      for (let gy = 0; gy < H; gy += 40) {
        ctx.beginPath(); ctx.moveTo(0, gy); ctx.lineTo(W, gy); ctx.stroke();
      }

      // Shield line glow
      const grad = ctx.createLinearGradient(0, SHIELD_Y, W, SHIELD_Y);
      grad.addColorStop(0, 'transparent');
      grad.addColorStop(0.3, 'rgba(6,182,212,0.5)');
      grad.addColorStop(0.5, 'rgba(6,182,212,0.9)');
      grad.addColorStop(0.7, 'rgba(6,182,212,0.5)');
      grad.addColorStop(1, 'transparent');
      ctx.strokeStyle = grad;
      ctx.lineWidth = 2;
      ctx.shadowColor = '#06B6D4';
      ctx.shadowBlur = 12;
      ctx.beginPath(); ctx.moveTo(0, SHIELD_Y); ctx.lineTo(W, SHIELD_Y); ctx.stroke();
      ctx.shadowBlur = 0;

      // Streams
      ctx.font = `${FONT_SIZE}px "SFMono-Regular", Consolas, monospace`;
      for (const s of streams) {
        s.y += s.speed;
        s.charIdx = Math.floor(s.y / FONT_SIZE);

        const chars = s.word.split('');
        chars.forEach((ch, idx) => {
          const cy = s.y - (chars.length - idx) * FONT_SIZE;
          if (cy < 0 || cy > H) return;

          const isBelow = cy >= SHIELD_Y;
          if (isBelow && !s.redacted && cy - SHIELD_Y < FONT_SIZE) {
            s.redacted = true;
            spawnParticle(s.x, SHIELD_Y);
          }

          const alpha = Math.max(0, s.opacity - (chars.length - idx) * 0.06);
          if (isBelow) {
            ctx.fillStyle = `rgba(0,0,0,${alpha * 0.9})`;
            ctx.fillRect(s.x - 6, cy - FONT_SIZE + 2, 12, FONT_SIZE);
            ctx.fillStyle = `rgba(6,182,212,0.1)`;
            ctx.fillRect(s.x - 6, cy - FONT_SIZE + 2, 12, FONT_SIZE);
          } else {
            const distToShield = SHIELD_Y - cy;
            const fade = Math.min(1, distToShield / 80);
            ctx.fillStyle = `rgba(6,182,212,${alpha * fade})`;
            ctx.fillText(ch, s.x - 4, cy);
          }
        });

        if (s.y - chars.length * FONT_SIZE > H) {
          s.y = -chars.length * FONT_SIZE;
          s.word = WORDS[Math.floor(Math.random() * WORDS.length)];
          s.redacted = false;
          s.speed = 0.4 + Math.random() * 0.6;
        }
      }

      // Particles
      for (let i = PARTICLES.length - 1; i >= 0; i--) {
        const p = PARTICLES[i];
        p.x += p.vx; p.y += p.vy; p.life -= 0.03;
        if (p.life <= 0) { PARTICLES.splice(i, 1); continue; }
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r * p.life, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(6,182,212,${p.life * 0.8})`;
        ctx.fill();
      }

      animId = requestAnimationFrame(draw);
    }

    draw();

    const onResize = () => {
      W = canvas.offsetWidth; H = canvas.offsetHeight;
      canvas.width = W; canvas.height = H;
    };
    window.addEventListener('resize', onResize);
    return () => { cancelAnimationFrame(animId); window.removeEventListener('resize', onResize); };
  }, []);

  return <canvas ref={canvasRef} className="hero-canvas" aria-hidden="true" />;
}

/* ============================================================
   LIVE PII HEATMAP — inline highlight overlay in textarea
   ============================================================ */
const PII_PATTERNS = [
  { name: 'EMAIL',       pattern: /\b[\w.+-]+@[\w-]+\.[a-z]{2,}\b/gi,                              level: 'high'     },
  { name: 'PHONE',       pattern: /\b(\+91[\-\s]?)?[6-9]\d{9}\b|\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b/g, level: 'high'  },
  { name: 'AADHAAR',     pattern: /\b\d{4}\s?\d{4}\s?\d{4}\b/g,                                    level: 'critical' },
  { name: 'PAN',         pattern: /\b[A-Z]{5}[0-9]{4}[A-Z]\b/g,                                    level: 'critical' },
  { name: 'CREDIT CARD', pattern: /\b(?:\d{4}[-\s]?){3}\d{4}\b/g,                                  level: 'critical' },
  { name: 'SSN',         pattern: /\b\d{3}-\d{2}-\d{4}\b/g,                                        level: 'critical' },
  { name: 'IP ADDRESS',  pattern: /\b(?:\d{1,3}\.){3}\d{1,3}\b/g,                                  level: 'medium'   },
  { name: 'DATE',        pattern: /\b\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}\b/g,                        level: 'low'      },
];

function LiveHeatmap({ text }) {
  const highlights = [];
  const seen = new Set();

  for (const def of PII_PATTERNS) {
    const re = new RegExp(def.pattern.source, def.pattern.flags.includes('g') ? def.pattern.flags : def.pattern.flags + 'g');
    let m;
    while ((m = re.exec(text)) !== null) {
      const key = `${m.index}-${m.index + m[0].length}`;
      if (!seen.has(key)) {
        seen.add(key);
        highlights.push({ start: m.index, end: m.index + m[0].length, name: def.name, level: def.level });
      }
    }
  }
  highlights.sort((a, b) => a.start - b.start);

  if (highlights.length === 0) return null;

  const parts = [];
  let cursor = 0;
  for (const h of highlights) {
    if (h.start > cursor) parts.push(<span key={`t${cursor}`}>{text.slice(cursor, h.start)}</span>);
    parts.push(
      <mark key={`h${h.start}`} className={`pii-mark pii-mark-${h.level}`} data-label={h.name}>
        {text.slice(h.start, h.end)}
      </mark>
    );
    cursor = h.end;
  }
  if (cursor < text.length) parts.push(<span key="tail">{text.slice(cursor)}</span>);

  return (
    <div className="heatmap-overlay" aria-hidden="true">
      {parts}
    </div>
  );
}

/* ============================================================
   MASKED TOKEN RENDERER
   ============================================================ */
function MaskedText({ text }) {
  const parts = text.split(/(\[[A-Z_]+_MASKED\])/g);
  return (
    <>
      {parts.map((part, i) => {
        const match = part.match(/^\[([A-Z_]+)_MASKED\]$/);
        if (match) {
          return (
            <span key={i} className="redaction-bar" title={`Redacted: ${formatType(match[1])}`}>
              {Array.from({ length: Math.max(4, match[1].length) }, () => '\u2588').join('')}
            </span>
          );
        }
        return <span key={i}>{part}</span>;
      })}
    </>
  );
}

/* ============================================================
   ODOMETER COUNT
   ============================================================ */
function OdometerCount({ endCount }) {
  const [count, setCount] = useState(0);
  useEffect(() => {
    let start = 0;
    const duration = 1000;
    const stepTime = Math.abs(Math.floor(duration / (endCount || 1)));
    const timer = setInterval(() => {
      start += 1;
      if (start > endCount) { clearInterval(timer); } else { setCount(start); }
    }, stepTime);
    return () => clearInterval(timer);
  }, [endCount]);
  return <span className="report-count">{count} item{count !== 1 ? 's' : ''} found</span>;
}

/* ============================================================
   DETECTION REPORT
   ============================================================ */
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
          <p className="report-empty">No PII detected in this document.</p>
        ) : (
          report.map((item, i) => (
            <div className="report-item" key={i} style={{ animationDelay: `${i * 60}ms` }}>
              <span className="report-item-num">{i + 1}</span>
              <div className="report-item-content">
                <p className="report-item-text">{item.text}</p>
                <div className="report-tags">
                  {item.pii_types.map(t => (
                    <span key={t} className="report-tag tag-default">{formatType(t)}</span>
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

/* ============================================================
   IMAGE REVEAL SLIDER
   ============================================================ */
function ImageReveal({ original, masked }) {
  const [sliderPos, setSliderPos] = useState(50);
  if (!original) return <img src={masked} alt="Masked Document" />;
  return (
    <div className="image-compare-wrapper">
      <img className="img-original" src={original} alt="Original" />
      <img className="img-masked" src={masked} alt="Masked" style={{ clipPath: `inset(0 0 0 ${sliderPos}%)` }} />
      <div className="slider-handle" style={{ left: `${sliderPos}%` }} />
      <input type="range" min="0" max="100" value={sliderPos}
        onChange={(e) => setSliderPos(e.target.value)} className="compare-range" />
    </div>
  );
}

/* ============================================================
   ANIMATED SUCCESS CHECKMARK
   ============================================================ */
function SuccessCheck() {
  return (
    <svg className="success-check" viewBox="0 0 52 52" aria-hidden="true">
      <circle className="success-check-circle" cx="26" cy="26" r="25" fill="none" />
      <path className="success-check-mark" fill="none" d="M14.1 27.2l7.1 7.2 16.7-16.8" />
    </svg>
  );
}

/* ============================================================
   MAIN APP
   ============================================================ */
export default function App() {
  const { isAuthenticated, isLoading: authLoading, loginWithRedirect, logout, getIdTokenClaims, user } = useAuth0();
  const { addToast } = useToast();

  const [role, setRole] = useState('user');
  const [token, setToken] = useState(null);
  const [paletteOpen, setPaletteOpen] = useState(false);

  const getInitialTab = () => {
    const hash = window.location.hash.replace('#', '');
    return ['file', 'text', 'cloud', 'admin'].includes(hash) ? hash : 'file';
  };
  const [tab, setTabState] = useState(getInitialTab);
  const [tabKey, setTabKey] = useState(0);

  const setTab = useCallback((newTab) => {
    setTabState(newTab);
    setTabKey(k => k + 1);
    window.location.hash = newTab;
  }, []);

  useEffect(() => {
    const handleHashChange = () => {
      const hash = window.location.hash.replace('#', '');
      if (['file', 'text', 'cloud', 'admin'].includes(hash)) { setTabState(hash); setTabKey(k => k + 1); }
    };
    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  // Command palette keyboard shortcut
  useEffect(() => {
    const onKey = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') { e.preventDefault(); setPaletteOpen(p => !p); }
      if (e.key === 'Escape') setPaletteOpen(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const [file, setFile] = useState(null);
  const [originalPreview, setOriginalPreview] = useState(null);
  const [processedUrl, setProcessedUrl] = useState(null);
  const [certificateUrl, setCertificateUrl] = useState(null);
  const [generateCertificate, setGenerateCertificate] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [taskMessage, setTaskMessage] = useState('');
  const [error, setError] = useState('');
  const [report, setReport] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const [showSuccess, setShowSuccess] = useState(false);

  const [inputText, setInputText] = useState('');
  const [textResult, setTextResult] = useState(null);
  const [textLoading, setTextLoading] = useState(false);
  const [textError, setTextError] = useState('');

  const [cloudForm, setCloudForm] = useState({ provider: 'aws', bucket_name: '', prefix: '', access_key: '', secret_key: '', mode: 'discovery' });
  const [cloudLoading, setCloudLoading] = useState(false);
  const [cloudResult, setCloudResult] = useState(null);
  const [cloudError, setCloudError] = useState('');

  const [logs, setLogs] = useState([]);
  const [policies, setPolicies] = useState([]);
  const [users, setUsers] = useState([]);
  const [customRegex, setCustomRegex] = useState([]);
  const [settings, setSettings] = useState({ masking_style: 'LABEL' });
  const [analytics, setAnalytics] = useState([]);
  const [newRegexName, setNewRegexName] = useState('');
  const [newRegexPattern, setNewRegexPattern] = useState('');
  const [adminError, setAdminError] = useState('');
  const [stats, setStats] = useState({ docs: 0, pii: 0 });

  const fileInputRef = useRef(null);
  const apiUrl = process.env.REACT_APP_API_URL || '';

  // Risk assessment for text tab
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
          console.log('[AUTH DEBUG] Auth0 ID Token Claims:', claims);

          const res = await fetch(`${apiUrl}/api/auth/sync`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${jwtToken}` }
          });
          console.log('[AUTH DEBUG] /api/auth/sync status:', res.status);
          if (res.ok) {
            const data = await res.json();
            setRole(data.role);
            addToast(`Signed in successfully. Role: ${data.role}`, 'success');
          } else {
            const errData = await res.json().catch(() => ({}));
            console.error('[AUTH DEBUG] sync FAILED:', res.status, errData);
          }

          const dbgRes = await fetch(`${apiUrl}/api/auth/debug`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${jwtToken}` }
          });
          if (dbgRes.ok) { const dbg = await dbgRes.json(); console.log('[AUTH DEBUG] backend token debug:', dbg); }
        } catch (e) {
          console.error('Failed to sync user:', e);
        }
      }
    };
    syncUser();
  }, [isAuthenticated, getIdTokenClaims, apiUrl, addToast]);

  const loadAdminData = useCallback(async () => {
    if (!token || role !== 'admin') return;
    try {
      const headers = { 'Authorization': `Bearer ${token}` };
      const urls = [
        `${apiUrl}/api/admin/policies`,
        `${apiUrl}/api/admin/logs`,
        `${apiUrl}/api/admin/users`,
        `${apiUrl}/api/admin/custom-regex`,
        `${apiUrl}/api/admin/settings`,
        `${apiUrl}/api/admin/analytics`
      ];
      const responses = await Promise.allSettled(urls.map(url => fetch(url, { headers })));
      const jsonPromises = responses.map(res =>
        (res.status === 'fulfilled' && res.value.ok) ? res.value.json() : Promise.resolve(null)
      );
      const data = await Promise.all(jsonPromises);
      if (data[0]) setPolicies(data[0]);
      if (data[1]) setLogs(data[1]);
      if (data[2]) setUsers(data[2]);
      if (data[3]) setCustomRegex(data[3]);
      if (data[4]) setSettings(data[4]);
      if (data[5]) setAnalytics(data[5]);
    } catch(err) { console.error('Failed to load admin data', err); }
  }, [apiUrl, token, role]);

  const handleAddRegex = async () => {
    setAdminError('');
    try {
      const res = await fetch(`${apiUrl}/api/admin/custom-regex`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ name: newRegexName, pattern: newRegexPattern })
      });
      handleApiError(res);
      if (!res.ok) { const data = await res.json().catch(()=>({})); throw new Error(data.detail || 'Failed to add regex.'); }
      setNewRegexName(''); setNewRegexPattern('');
      loadAdminData();
      addToast('Custom regex rule added successfully', 'success');
    } catch(e) { setAdminError(e.message); addToast(e.message, 'error'); }
  };

  const handleDeleteRegex = async (id) => {
    setAdminError('');
    try {
      const res = await fetch(`${apiUrl}/api/admin/custom-regex/${id}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      handleApiError(res);
      if (!res.ok) throw new Error('Failed to delete regex.');
      loadAdminData();
      addToast('Regex rule removed', 'info');
    } catch(e) { setAdminError(e.message); addToast(e.message, 'error'); }
  };

  const handleSettingsChange = async (e) => {
    const val = e.target.value;
    setSettings({ masking_style: val });
    setAdminError('');
    try {
      const res = await fetch(`${apiUrl}/api/admin/settings`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ masking_style: val })
      });
      handleApiError(res);
      if (!res.ok) throw new Error('Failed to update settings.');
      addToast(`Masking style updated to ${val}`, 'success');
    } catch(e) { setAdminError(e.message); }
  };

  useEffect(() => { if (tab === 'admin') loadAdminData(); }, [tab, loadAdminData]);

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
    setShowSuccess(false);
    if (selectedFile.type.startsWith('image/')) {
      const url = URL.createObjectURL(selectedFile);
      setOriginalPreview(url);
    } else {
      setOriginalPreview(null);
    }
  }, []);

  const triggerConfetti = () => {
    confetti({ particleCount: 120, spread: 80, origin: { y: 0.6 }, colors: ['#06B6D4', '#3B82F6', '#10B981', '#FFFFFF'] });
  };

  const handleProcess = async () => {
    if (!file) { setError('Please select a file first.'); return; }
    setIsLoading(true);
    setError('');
    setProcessedUrl(null);
    setReport(null);
    setShowSuccess(false);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('generate_certificate', generateCertificate);

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
        setCertificateUrl(data.certificate_url || null);
        setReport(data.report);
        setIsLoading(false);
        setShowSuccess(true);
        triggerConfetti();
        addToast(`Document processed — ${data.report?.length || 0} PII items redacted`, 'success');
        setStats(s => ({ docs: s.docs + 1, pii: s.pii + (data.report?.length || 0) }));
      }
    } catch (err) {
      setError(err.message || 'Processing failed.');
      addToast(err.message || 'Processing failed', 'error');
      setIsLoading(false);
    }
  };

  const pollTaskStatus = async (taskId, isCloud = false) => {
    try {
      const res = await fetch(`${apiUrl}/api/tasks/${taskId}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      handleApiError(res);
      const data = await res.json();

      if (data.status === 'SUCCESS') {
        if (isCloud) {
          setCloudResult(data.result);
          setCloudLoading(false);
          addToast(`Cloud scan complete — ${data.result.files_scanned} files scanned`, 'success');
        } else {
          setProcessedUrl(data.result.download_url);
          setCertificateUrl(data.result.certificate_url || null);
          setReport(data.result.report);
          setShowSuccess(true);
          triggerConfetti();
          addToast(`Document processed — ${data.result.report?.length || 0} PII items redacted`, 'success');
          setStats(s => ({ docs: s.docs + 1, pii: s.pii + (data.result.report?.length || 0) }));
          setIsLoading(false);
        }
        setTaskMessage('');
      } else if (data.status === 'FAILURE') {
        const errMsg = data.error || 'Task failed during processing.';
        if (isCloud) { setCloudError(errMsg); setCloudLoading(false); } else { setError(errMsg); setIsLoading(false); }
        addToast(errMsg, 'error');
        setTaskMessage('');
      } else {
        if (data.message) setTaskMessage(data.message);
        setTimeout(() => pollTaskStatus(taskId, isCloud), 2000);
      }
    } catch (err) {
      setError('Error checking task status.');
      addToast('Error checking task status', 'error');
      setIsLoading(false);
      setTaskMessage('');
    }
  };

  const handleReset = () => {
    setFile(null);
    setOriginalPreview(null);
    setProcessedUrl(null);
    setCertificateUrl(null);
    setReport(null);
    setError('');
    setTaskMessage('');
    setShowSuccess(false);
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
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ text: inputText }),
      });
      handleApiError(res);
      if (!res.ok) throw new Error('Text analysis failed.');
      const data = await res.json();
      setTextResult(data);
      addToast(data.pii_found ? `${data.pii_types.length} PII type(s) detected and masked` : 'No PII detected in text', data.pii_found ? 'success' : 'info');
      setStats(s => ({ ...s, pii: s.pii + (data.pii_types?.length || 0) }));
    } catch (err) {
      setTextError(err.message || 'Failed to analyze text.');
      addToast(err.message || 'Analysis failed', 'error');
    } finally {
      setTextLoading(false);
    }
  };

  const handleCloudScan = async () => {
    setCloudError('');
    setCloudResult(null);
    setCloudLoading(true);
    try {
      const res = await fetch(`${apiUrl}/api/cloud-scan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify(cloudForm)
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Scan failed');
      if (res.status === 202 && data.task_id) {
        addToast('Cloud scan started — this may take several minutes', 'info');
        pollTaskStatus(data.task_id, true);
      } else {
        setCloudResult(data);
        setCloudLoading(false);
      }
    } catch (err) {
      setCloudError(err.message || 'Failed to start cloud scan.');
      addToast(err.message || 'Cloud scan failed', 'error');
      setCloudLoading(false);
    }
  };

  const togglePolicy = async (piiType, currentStatus) => {
    setAdminError('');
    try {
      const res = await fetch(`${apiUrl}/api/admin/policies`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ pii_type: piiType, is_active: !currentStatus })
      });
      handleApiError(res);
      if (!res.ok) throw new Error('Failed to toggle policy.');
      loadAdminData();
      addToast(`${formatType(piiType)} detection ${!currentStatus ? 'enabled' : 'disabled'}`, 'info');
    } catch(e) { setAdminError(e.message); }
  };

  if (authLoading) {
    return (
      <div className="App auth-bg">
        <div className="bg-pattern" />
        <div className="auth-loading">
          <div className="shield-loader-container">
            <div className="shield-ring" />
            <div className="shield-ring" />
            <ShieldAlert size={36} className="shield-icon" />
          </div>
          <p className="auth-loading-text">Establishing secure session...</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div className="App auth-bg">
        <div className="bg-pattern" />
        <HeroCanvas />
        <div className="auth-container">
          <div className="auth-card">
            <div className="auth-header">
              <div className="auth-shield-wrap">
                <ShieldCheck size={40} className="auth-icon" />
              </div>
              <h2>Enterprise Privacy Suite</h2>
              <p>Secure access via corporate SSO. All sessions are encrypted and audited.</p>
            </div>
            <button className="btn-primary auth-submit" onClick={() => loginWithRedirect()}>
              <Lock size={16} />
              Sign in with Auth0
            </button>
            <p className="auth-footnote">
              Protected by HIPAA-compliant identity infrastructure
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="App">
      <div className="bg-pattern" />

      <CommandPalette isOpen={paletteOpen} onClose={() => setPaletteOpen(false)} onNavigate={setTab} />

      {/* Session Activity Sidebar */}
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
        <div className="sidebar-divider" />
        <button className="sidebar-palette-btn" onClick={() => setPaletteOpen(true)}>
          <Search size={13} />
          <span>Quick commands</span>
          <kbd>Ctrl K</kbd>
        </button>
      </aside>

      <header className="App-header">
        <div className="header-top-right">
          <button className="palette-trigger" onClick={() => setPaletteOpen(true)} title="Open command palette (Ctrl+K)">
            <Search size={14} />
            <span>Ctrl K</span>
          </button>
          <span className="header-user">
            {user?.picture && <img src={user.picture} alt="Avatar" className="header-avatar" />}
            <span className="header-username">{user?.name}</span>
          </span>
          <span className="role-pill role-pill-header">{role}</span>
          <button className="btn-logout" onClick={() => logout({ logoutParams: { returnTo: window.location.origin } })}>
            <LogOut size={14} /> Sign out
          </button>
        </div>

        <div className="header-inner">
          <div className="header-badge"><span className="header-badge-dot" /> Enterprise Edition</div>
          <h1>Mask <em>Sensitive</em> Information</h1>
          <p>AI-powered PII detection and redaction across documents, text, and cloud storage — with full compliance audit trails.</p>
        </div>
      </header>

      <div className="micro-status-bar">
        <div className="status-indicator"><div className="status-dot online" />Auth0 Connected</div>
        <div className="status-indicator"><div className="status-dot online" />Redis Queue Ready</div>
        <div className="status-indicator"><div className="status-dot online" />GCP Vision Active</div>
      </div>

      <main className="App-main">
        {/* Feature Cards */}
        <div className="stat-cards-container">
          {[
            { icon: <Layers size={20} />, title: 'Supported Formats', sub: 'PDF · DOCX · IMG · CSV · JSONL', delay: '0ms' },
            { icon: <Search size={20} />, title: 'Detection Engine', sub: 'Presidio + GCP Vision OCR', delay: '80ms' },
            { icon: <Zap size={20} />, title: 'Async Processing', sub: 'Celery + Redis Worker Queue', delay: '160ms' },
          ].map((c, i) => (
            <div key={i} className="glass-stat-card" style={{ animationDelay: c.delay }}>
              <div className="stat-icon-wrap">{c.icon}</div>
              <div className="stat-card-content">
                <h4>{c.title}</h4>
                <p>{c.sub}</p>
              </div>
            </div>
          ))}
        </div>

        {/* Tab Navigation */}
        <div className="tab-nav">
          <button className={`tab-btn${tab === 'file'  ? ' active' : ''}`} onClick={() => setTab('file')}><FileText size={16} /> Document</button>
          <button className={`tab-btn${tab === 'text'  ? ' active' : ''}`} onClick={() => setTab('text')}><Type size={16} /> Text Scanner</button>
          <button className={`tab-btn${tab === 'cloud' ? ' active' : ''}`} onClick={() => setTab('cloud')}><Database size={16} /> Cloud Scan</button>
          {role === 'admin' && (
            <button className={`tab-btn${tab === 'admin' ? ' active' : ''}`} onClick={() => setTab('admin')}><Settings size={16} /> Admin</button>
          )}
        </div>

        {/* TAB: File Upload */}
        {tab === 'file' && (
          <div key={`file-${tabKey}`} className="tab-content upload-section">
            {!processedUrl && !isLoading && (
              <div
                className={`drop-zone ${dragOver ? 'drag-over' : ''} ${file ? 'has-file' : ''}`}
                onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={(e) => {
                  e.preventDefault(); setDragOver(false);
                  if (e.dataTransfer.files && e.dataTransfer.files.length > 0) handleFileSelect(e.dataTransfer.files[0]);
                }}
                onClick={() => { if (!file) fileInputRef.current?.click(); }}
              >
                <div className="scan-line" />
                {file ? (
                  <>
                    <CheckCircle className="drop-icon" size={48} style={{ color: 'var(--success)' }} />
                    <h3 className="drop-title">Ready to process</h3>
                    <p className="drop-sub">Click Mask Document to detect and redact all PII.</p>
                    <div className="file-info"><FileText size={16}/> {file.name}</div>
                  </>
                ) : (
                  <>
                    <UploadCloud className="drop-icon" size={48} />
                    <h3 className="drop-title">Drag and drop document or ZIP archive</h3>
                    <p className="drop-sub">Supports PDF, DOCX, JPG, PNG, WEBP, CSV, JSONL and batch ZIP</p>
                    <span className="drop-browse">or click to browse files</span>
                  </>
                )}
                <input type="file" ref={fileInputRef} className="file-input-hidden"
                  onChange={(e) => handleFileSelect(e.target.files[0])}
                  accept=".pdf,.docx,.jpg,.jpeg,.png,.webp,.zip,.csv,.jsonl" />
              </div>
            )}

            {error && <div className="alert alert-error"><AlertTriangle size={18} /> {error}</div>}

            {isLoading && (
              <div className="loading-state">
                <div className="shield-loader-container">
                  <div className="shield-ring" />
                  <div className="shield-ring" />
                  <ShieldAlert size={36} className="shield-icon" />
                </div>
                <p className="loading-label">{taskMessage || 'Initializing AI Engine...'}</p>
                <div className="loading-progress-track">
                  <div className="loading-progress-bar" />
                </div>
              </div>
            )}

            {!isLoading && file && !processedUrl && (
              <div className="btn-row" style={{ flexDirection: 'column', alignItems: 'center', gap: '16px' }}>
                <label className="cert-checkbox-label">
                  <input type="checkbox" checked={generateCertificate} onChange={e => setGenerateCertificate(e.target.checked)} />
                  <span>Generate HIPAA Compliance Certificate (PDF/DOCX only)</span>
                </label>
                <div className="btn-row">
                  <button className="btn-secondary" onClick={handleReset}><RefreshCw size={16}/> Clear</button>
                  <button className="btn-primary" onClick={handleProcess}><Lock size={16}/> Mask Document</button>
                </div>
              </div>
            )}

            {processedUrl && !isLoading && (
              <div className="result-section">
                {showSuccess && (
                  <div className="success-banner">
                    <SuccessCheck />
                    <div>
                      <strong>Document sanitized successfully</strong>
                      <p>{report?.length || 0} PII items identified and redacted.</p>
                    </div>
                  </div>
                )}
                {file && file.type.startsWith('image/') ? (
                  <div className="image-card">
                    <div className="image-card-header">
                      <span className="image-card-title"><span className="image-card-title-dot dot-processed"/> Before and After</span>
                      <a href={processedUrl} download className="btn-download"><Download size={16} /> Download Masked</a>
                    </div>
                    <div className="image-card-body" style={{ padding: 0 }}>
                      <ImageReveal original={originalPreview} masked={processedUrl} />
                    </div>
                  </div>
                ) : (
                  <div className="image-card">
                    <div className="image-card-header">
                      <span className="image-card-title"><span className="image-card-title-dot dot-processed"/> Secure Document Ready</span>
                      <div style={{ display: 'flex', gap: '12px' }}>
                        {certificateUrl && (
                          <a href={certificateUrl} download className="btn-secondary"><ShieldCheck size={16} /> Certificate</a>
                        )}
                        <a href={processedUrl} download className="btn-download"><Download size={16} /> Download File</a>
                      </div>
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

        {/* TAB: Text Scanner */}
        {tab === 'text' && (
          <div key={`text-${tabKey}`} className="tab-content text-section">
            <div className="text-input-wrap">
              <div className="text-input-header">
                <label>Input Text</label>
                <span className={`risk-badge ${riskClass}`}>{riskLabel} ({charCount} chars)</span>
              </div>
              <div className="heatmap-container">
                <textarea
                  value={inputText}
                  onChange={(e) => setInputText(e.target.value)}
                  placeholder="Paste raw text here... e.g. My Aadhaar is 2345 6789 0123 and email is test@corp.com"
                  disabled={textLoading}
                  spellCheck={false}
                />
                {inputText && <LiveHeatmap text={inputText} />}
              </div>
              {inputText && (
                <div className="heatmap-legend">
                  <span className="legend-label">Live preview:</span>
                  <span className="legend-item legend-critical">Critical</span>
                  <span className="legend-item legend-high">High</span>
                  <span className="legend-item legend-medium">Medium</span>
                  <span className="legend-item legend-low">Low</span>
                </div>
              )}
            </div>

            {textError && <div className="alert alert-error"><AlertTriangle size={18} /> {textError}</div>}

            <div className="btn-row">
              <button className="btn-primary" onClick={handleMaskText} disabled={textLoading || !inputText.trim()}>
                {textLoading ? <><RefreshCw size={16} className="spin" /> Analyzing...</> : <><ScanLine size={16}/> Mask Text</>}
              </button>
            </div>

            {textResult && !textLoading && (
              <div className="text-result-card">
                <div className="text-result-header">
                  <span>Sanitized Output</span>
                  {textResult.pii_found && (
                    <span className="result-pii-count">{textResult.pii_types.length} type(s) removed</span>
                  )}
                </div>
                <div className="text-result-body">
                  <MaskedText text={textResult.masked} />
                </div>
                <DetectionReport report={textResult.pii_found ? [{ text: 'Raw Text Input', pii_types: textResult.pii_types }] : []} />
              </div>
            )}
          </div>
        )}

        {/* TAB: Cloud Scan */}
        {tab === 'cloud' && (
          <div key={`cloud-${tabKey}`} className="tab-content text-section">
            <div className="section-heading">
              <Database size={20} />
              <div>
                <h3>Cloud Data Discovery</h3>
                <p>Scan entire AWS S3 or Azure Blob buckets for sensitive PII. Connect your data source securely.</p>
              </div>
            </div>

            <div className="admin-card" style={{marginBottom: '24px'}}>
              <div className="cloud-form-grid">
                <div className="text-input-wrap">
                  <label>Cloud Provider</label>
                  <select className="config-input" value={cloudForm.provider} onChange={e => setCloudForm({...cloudForm, provider: e.target.value})} disabled={cloudLoading}>
                    <option value="aws">AWS S3</option>
                    <option value="azure">Azure Blob Storage</option>
                  </select>
                </div>
                <div className="text-input-wrap">
                  <label>Bucket / Container Name</label>
                  <input type="text" className="config-input" value={cloudForm.bucket_name} onChange={e => setCloudForm({...cloudForm, bucket_name: e.target.value})} placeholder="e.g. my-production-data" disabled={cloudLoading} />
                </div>
                <div className="text-input-wrap">
                  <label>Prefix / Folder (Optional)</label>
                  <input type="text" className="config-input" value={cloudForm.prefix} onChange={e => setCloudForm({...cloudForm, prefix: e.target.value})} placeholder="e.g. 2024/uploads/" disabled={cloudLoading} />
                </div>
                <div className="text-input-wrap">
                  <label>{cloudForm.provider === 'aws' ? 'AWS Access Key ID' : 'Account Name'}</label>
                  <input type="text" className="config-input" value={cloudForm.access_key} onChange={e => setCloudForm({...cloudForm, access_key: e.target.value})} placeholder={cloudForm.provider === 'aws' ? 'AKIA...' : 'Not required for Azure'} disabled={cloudLoading || cloudForm.provider === 'azure'} />
                </div>
                <div className="text-input-wrap">
                  <label>{cloudForm.provider === 'aws' ? 'AWS Secret Access Key' : 'Azure Connection String'}</label>
                  <input type="password" className="config-input" value={cloudForm.secret_key} onChange={e => setCloudForm({...cloudForm, secret_key: e.target.value})} placeholder="..." disabled={cloudLoading} />
                </div>
                <div className="text-input-wrap">
                  <label>Operation Mode</label>
                  <select className="config-input" value={cloudForm.mode} onChange={e => setCloudForm({...cloudForm, mode: e.target.value})} disabled={cloudLoading}>
                    <option value="discovery">Discovery Only (Generate JSON Report)</option>
                    <option value="sanitize">Sanitize (Redact files and write to sanitized/ prefix)</option>
                  </select>
                </div>
              </div>

              <div className="btn-row">
                <button className="btn-primary" onClick={handleCloudScan} disabled={cloudLoading || !cloudForm.bucket_name || !cloudForm.secret_key}>
                  {cloudLoading
                    ? <><RefreshCw size={16} className="spin" /> {taskMessage || 'Scanning Bucket...'}</>
                    : <><Search size={16}/> Start Bucket Scan</>}
                </button>
              </div>
            </div>

            {cloudError && <div className="alert alert-error"><AlertTriangle size={18} /> {cloudError}</div>}

            {cloudResult && !cloudLoading && (
              <div className="result-section">
                <div className="image-card">
                  <div className="image-card-header">
                    <span className="image-card-title"><span className="image-card-title-dot dot-processed"/> Scan Complete</span>
                    <a href={cloudResult.download_url} download className="btn-download"><Download size={16} /> Download JSON Report</a>
                  </div>
                  <div className="image-card-body cloud-result-body">
                    <div className="cloud-stat"><span className="cloud-stat-num">{cloudResult.files_scanned}</span><span className="cloud-stat-label">Files Scanned</span></div>
                    <div className="cloud-stat cloud-stat-alert"><span className="cloud-stat-num">{cloudResult.files_with_pii}</span><span className="cloud-stat-label">Files with PII</span></div>
                    <p className="cloud-result-note">
                      {cloudForm.mode === 'sanitize'
                        ? 'Sanitized files have been uploaded to your bucket under the sanitized/ prefix.'
                        : 'Review the downloaded JSON report for detailed file-level PII analytics.'}
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* TAB: Admin */}
        {tab === 'admin' && role === 'admin' && (
          <div key={`admin-${tabKey}`} className="tab-content admin-section">
            {adminError && <div className="alert alert-error" style={{marginBottom: '16px'}}><AlertTriangle size={18} /> {adminError}</div>}

            <div className="admin-grid-2col">
              <div className="admin-card">
                <h3><ShieldCheck size={20}/> Detection Policies</h3>
                <p className="admin-card-desc">Configure active Data Loss Prevention (DLP) entities to detect and redact.</p>
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
                <div className="admin-card-header-flex">
                  <h3><Activity size={20}/> Audit Logs</h3>
                  <a href={`${apiUrl}/api/admin/logs/export`} className="btn-export" download>Export CSV</a>
                </div>
                <p className="admin-card-desc">Immutable audit log of all system processing and authentication events.</p>
                <div className="audit-table-wrap">
                  <table className="audit-table">
                    <thead><tr><th>Time</th><th>User</th><th>Action</th><th>IP</th></tr></thead>
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

            <div className="admin-card" style={{ marginTop: '24px' }}>
              <h3><User size={20}/> User Management and RBAC</h3>
              <p className="admin-card-desc">Users and roles are strictly synchronized with the server environment variable whitelist.</p>
              <div className="audit-table-wrap">
                <table className="audit-table">
                  <thead><tr><th>ID</th><th>Username / Auth0 Sub</th><th>Role</th></tr></thead>
                  <tbody>
                    {users.map(u => (
                      <tr key={u.id}>
                        <td>{u.id}</td>
                        <td style={{fontFamily: 'monospace'}}>{u.username}</td>
                        <td><span className={`role-badge role-${u.role}`}>{u.role}</span></td>
                      </tr>
                    ))}
                    {users.length === 0 && <tr><td colSpan="3" style={{textAlign:'center', color:'var(--text-muted)'}}>No users found</td></tr>}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="admin-grid-2col">
              <div className="admin-card">
                <h3><Activity size={20}/> Advanced Analytics</h3>
                <p className="admin-card-desc">Historical aggregation of redacted entities across the organization.</p>
                <div className="analytics-list">
                  {analytics.map(a => {
                    const maxCount = analytics[0]?.count || 1;
                    const pct = Math.round((a.count / maxCount) * 100);
                    return (
                      <div key={a.name} className="analytics-item">
                        <div className="analytics-item-header">
                          <span className="analytics-name">{a.name}</span>
                          <span className="analytics-count">{a.count} detections</span>
                        </div>
                        <div className="analytics-bar-track">
                          <div className="analytics-bar-fill" style={{ width: `${pct}%` }} />
                        </div>
                      </div>
                    );
                  })}
                  {analytics.length === 0 && <span style={{color:'var(--text-muted)'}}>No analytics data yet.</span>}
                </div>
              </div>

              <div className="admin-card">
                <h3><Settings size={20}/> Global Masking Style</h3>
                <p className="admin-card-desc">Establish global standards for data redaction across all processed documents.</p>
                <div className="masking-options">
                  {[
                    { value: 'LABEL',    label: '[ENTITY_MASKED]', desc: 'Labeled token' },
                    { value: 'BLACKOUT', label: '████████',        desc: 'Full blackout'  },
                    { value: 'ASTERISK', label: '***',             desc: 'Asterisk'       },
                  ].map(opt => (
                    <label key={opt.value} className={`masking-option ${settings.masking_style === opt.value ? 'masking-option-active' : ''}`}>
                      <input type="radio" name="masking" value={opt.value} checked={settings.masking_style === opt.value} onChange={handleSettingsChange} />
                      <span className="masking-option-label">{opt.label}</span>
                      <span className="masking-option-desc">{opt.desc}</span>
                    </label>
                  ))}
                </div>
              </div>
            </div>

            <div className="admin-card" style={{ marginTop: '24px' }}>
              <h3><Type size={20}/> Custom Regex Policy Builder</h3>
              <p className="admin-card-desc">Construct custom regular expressions to detect and redact proprietary data formats.</p>
              <div className="regex-builder-form">
                <input type="text" className="regex-input" placeholder="Entity Name (e.g. EMP_ID)" value={newRegexName} onChange={e=>setNewRegexName(e.target.value)} />
                <input type="text" className="regex-input font-mono" placeholder="Regex Pattern (e.g. EMP-\d{5})" value={newRegexPattern} onChange={e=>setNewRegexPattern(e.target.value)} />
                <button className="btn-primary" onClick={handleAddRegex} disabled={!newRegexName || !newRegexPattern}>Add Rule</button>
              </div>
              <div className="policy-list">
                {customRegex.map(p => (
                  <div className="policy-item" key={p.id}>
                    <span className="regex-name">{p.name} <span className="regex-pattern">{p.pattern}</span></span>
                    <button className="btn-danger" onClick={() => handleDeleteRegex(p.id)}>Delete</button>
                  </div>
                ))}
                {customRegex.length === 0 && <span style={{color:'var(--text-muted)', fontSize:13}}>No custom rules defined.</span>}
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

/* ============================================================
   WRAP WITH TOAST PROVIDER
   ============================================================ */
function WrappedApp() {
  return (
    <ToastProvider>
      <App />
    </ToastProvider>
  );
}

export { WrappedApp };
