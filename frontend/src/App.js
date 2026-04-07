import React, { useState, useCallback, useRef } from 'react';
import './App.css';

// ── PII tag colour helper ──────────────────────────────────
const tagClass = (type) => {
  const known = [
    'aadhaar','phone','email','pan_card','passport','credit_card',
    'date_of_birth','pincode','vehicle_reg','name_field','address_field',
    'dob_field','gender_field'
  ];
  return known.includes(type) ? `report-tag tag-${type}` : 'report-tag tag-default';
};

const formatType = (t) =>
  t.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());

// ── Render masked text with highlighted tokens ─────────────
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

// ── Detection report component ─────────────────────────────
function DetectionReport({ report }) {
  if (!report) return null;
  return (
    <div className="report-section">
      <div className="report-header">
        <h3>
          <span>🔍</span> Detection Report
        </h3>
        <span className="report-count">
          {report.length} item{report.length !== 1 ? 's' : ''} found
        </span>
      </div>
      <div className="report-body">
        {report.length === 0 ? (
          <p className="report-empty">✓ No PII detected in this image.</p>
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
                {item.confidence !== undefined && (
                  <p className="report-conf">OCR confidence: {(item.confidence * 100).toFixed(1)}%</p>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

// ── Main App ───────────────────────────────────────────────
export default function App() {
  const [tab, setTab] = useState('image'); // 'image' | 'text'

  // Image tab state
  const [file, setFile] = useState(null);
  const [originalImage, setOriginalImage] = useState(null);
  const [processedImage, setProcessedImage] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [report, setReport] = useState(null);
  const [dragOver, setDragOver] = useState(false);

  // Text tab state
  const [inputText, setInputText] = useState('');
  const [textResult, setTextResult] = useState(null);
  const [textLoading, setTextLoading] = useState(false);
  const [textError, setTextError] = useState('');

  const fileInputRef = useRef(null);

  // ── Image Handling ─────────────────────────────────────
  const handleFileSelect = useCallback((selectedFile) => {
    if (!selectedFile) return;
    if (!selectedFile.type.startsWith('image/')) {
      setError('Please select a valid image file (JPEG, PNG, WebP, etc.)');
      return;
    }
    if (selectedFile.size > 10 * 1024 * 1024) {
      setError('File is too large. Maximum size is 10 MB.');
      return;
    }
    setFile(selectedFile);
    setOriginalImage(URL.createObjectURL(selectedFile));
    setProcessedImage(null);
    setReport(null);
    setError('');
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setDragOver(false);
    const dropped = e.dataTransfer.files[0];
    handleFileSelect(dropped);
  }, [handleFileSelect]);

  const handleDragOver = (e) => { e.preventDefault(); setDragOver(true); };
  const handleDragLeave = () => setDragOver(false);

  const handleProcess = async () => {
    if (!file) { setError('Please select an image first.'); return; }
    setIsLoading(true);
    setError('');
    setProcessedImage(null);
    setReport(null);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const apiUrl = process.env.REACT_APP_API_URL || '';
      const res = await fetch(`${apiUrl}/api/upload`, {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const errBody = await res.json().catch(() => ({ error: res.statusText }));
        throw new Error(errBody.error || 'Processing failed.');
      }

      // The server now returns the image binary directly
      const blob = await res.blob();
      setProcessedImage(URL.createObjectURL(blob));

      // PII report comes in response header
      const reportHeader = res.headers.get('X-PII-Report');
      if (reportHeader) {
        try { setReport(JSON.parse(reportHeader)); } catch (_) {}
      }
    } catch (err) {
      console.error('Upload error:', err);
      setError(err.message || 'Processing failed. Make sure the backend server is running.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleReset = () => {
    setFile(null);
    setOriginalImage(null);
    setProcessedImage(null);
    setReport(null);
    setError('');
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  // ── Text Handling ──────────────────────────────────────
  const handleMaskText = async () => {
    if (!inputText.trim()) { setTextError('Please enter some text to analyse.'); return; }
    setTextLoading(true);
    setTextError('');
    setTextResult(null);

    try {
      const apiUrl = process.env.REACT_APP_API_URL || '';
      const res = await fetch(`${apiUrl}/api/mask-text`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: inputText }),
      });

      if (!res.ok) {
        const errBody = await res.json().catch(() => ({ error: res.statusText }));
        throw new Error(errBody.error || 'Text analysis failed.');
      }

      setTextResult(await res.json());
    } catch (err) {
      console.error('Text mask error:', err);
      setTextError(err.message || 'Text analysis failed.');
    } finally {
      setTextLoading(false);
    }
  };

  // ── Render ─────────────────────────────────────────────
  return (
    <div className="App">
      <div className="bg-pattern" />

      {/* Header */}
      <header className="App-header">
        <div className="header-inner">
          <div className="header-badge">
            <span className="header-badge-dot" />
            Privacy Protection Tool
          </div>
          <h1>Mask <em>Sensitive</em> Information</h1>
          <p>
            Automatically detect and redact personally identifiable information
            from documents, images, and text using OCR and pattern recognition.
          </p>
          <div className="header-ornament">
            <span /><i>✦</i><span />
          </div>
        </div>
      </header>

      {/* Main */}
      <main className="App-main">

        {/* Tab nav */}
        <div className="tab-nav">
          <button
            className={`tab-btn${tab === 'image' ? ' active' : ''}`}
            onClick={() => setTab('image')}
          >
            <span className="tab-icon">🖼️</span> Image
          </button>
          <button
            className={`tab-btn${tab === 'text' ? ' active' : ''}`}
            onClick={() => setTab('text')}
          >
            <span className="tab-icon">✍️</span> Text
          </button>
        </div>

        {/* ── IMAGE TAB ── */}
        {tab === 'image' && (
          <div className="upload-section">
            <div
              className={`drop-zone${dragOver ? ' drag-over' : ''}${file ? ' has-file' : ''}`}
              onDrop={handleDrop}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                onChange={(e) => handleFileSelect(e.target.files[0])}
                className="file-input-hidden"
              />
              {file ? (
                <>
                  <span className="drop-icon">✅</span>
                  <p className="drop-title">Image ready</p>
                  <p className="drop-sub">Click to change file</p>
                  <span className="file-info">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                    {file.name} · {(file.size / 1024).toFixed(0)} KB
                  </span>
                </>
              ) : (
                <>
                  <span className="drop-icon">📄</span>
                  <p className="drop-title">Drop your image here</p>
                  <p className="drop-sub">Supports JPEG, PNG, WebP, BMP — up to 10 MB</p>
                  <span className="drop-browse">or click to browse files</span>
                </>
              )}
            </div>

            {error && (
              <div className="alert alert-error">
                <span className="alert-icon">⚠</span> {error}
              </div>
            )}

            <div className="btn-row">
              <button
                className="btn-primary"
                onClick={handleProcess}
                disabled={!file || isLoading}
              >
                {isLoading
                  ? <><div className="loader-ring" style={{ width: 18, height: 18, borderWidth: 2 }} /> Processing…</>
                  : <><span>🔒</span> Mask PII</>
                }
              </button>
              {(file || processedImage) && (
                <button className="btn-secondary" onClick={handleReset}>
                  ↺ Reset
                </button>
              )}
              {processedImage && (
                <a href={processedImage} download="masked_image.jpg" className="btn-download">
                  ⬇ Download
                </a>
              )}
            </div>

            {/* Image comparison */}
            {(originalImage || processedImage || isLoading) && (
              <div className="image-grid">
                <div className="image-card">
                  <div className="image-card-header">
                    <span className="image-card-title">
                      <span className="image-card-title-dot dot-original" />
                      Original
                    </span>
                    {file && <span style={{ fontSize: '11px', color: 'var(--charcoal-soft)' }}>{file.name}</span>}
                  </div>
                  <div className="image-card-body">
                    {originalImage
                      ? <img src={originalImage} alt="Original upload" />
                      : <div className="image-placeholder"><span className="image-placeholder-icon">🖼️</span><p>No image selected</p></div>
                    }
                  </div>
                </div>

                <div className="image-card">
                  <div className="image-card-header">
                    <span className="image-card-title">
                      <span className="image-card-title-dot dot-processed" />
                      Masked
                    </span>
                    {processedImage && (
                      <span style={{ fontSize: '11px', color: 'var(--sage)', fontWeight: 600 }}>PII redacted ✓</span>
                    )}
                  </div>
                  <div className="image-card-body">
                    {isLoading
                      ? <div className="loading-state"><div className="loader-ring" /><p>Scanning with OCR…</p></div>
                      : processedImage
                        ? <img src={processedImage} alt="Processed with PII masked" />
                        : <div className="image-placeholder"><span className="image-placeholder-icon">🔒</span><p>Masked result will appear here</p></div>
                    }
                  </div>
                </div>
              </div>
            )}

            {/* Detection report */}
            {report && !isLoading && <DetectionReport report={report} />}
          </div>
        )}

        {/* ── TEXT TAB ── */}
        {tab === 'text' && (
          <div className="text-section">
            <label>Enter text to scan and mask</label>
            <div className="text-input-wrap">
              <textarea
                placeholder="Paste any text here — e.g. 'My name is John Doe, born on 12/03/1990. My Aadhaar is 1234 5678 9012 and email is john@example.com.'"
                value={inputText}
                onChange={e => { setInputText(e.target.value); setTextResult(null); setTextError(''); }}
                rows={8}
              />
            </div>

            {textError && (
              <div className="alert alert-error">
                <span className="alert-icon">⚠</span> {textError}
              </div>
            )}

            <div className="btn-row">
              <button
                className="btn-primary"
                onClick={handleMaskText}
                disabled={!inputText.trim() || textLoading}
              >
                {textLoading
                  ? <><div className="loader-ring" style={{ width: 18, height: 18, borderWidth: 2 }} /> Scanning…</>
                  : <><span>🔍</span> Detect &amp; Mask</>
                }
              </button>
              {textResult && (
                <button className="btn-secondary" onClick={() => { setInputText(''); setTextResult(null); }}>
                  ↺ Clear
                </button>
              )}
            </div>

            {textResult && (
              <div className="text-result-card mt-md">
                <div className="text-result-header">
                  <span>Masked output</span>
                  <div className="report-tags">
                    {textResult.pii_types.map(t => (
                      <span key={t} className={tagClass(t)}>{formatType(t)}</span>
                    ))}
                  </div>
                </div>
                <div className="text-result-body">
                  {textResult.pii_found
                    ? <MaskedText text={textResult.masked} />
                    : <span style={{ color: 'var(--charcoal-soft)', fontStyle: 'italic' }}>No PII detected in this text.</span>
                  }
                </div>
                <div className="text-stats">
                  <span className="text-stat">
                    Detected: <strong>{textResult.count}</strong> type{textResult.count !== 1 ? 's' : ''}
                  </span>
                  {textResult.pii_found && (
                    <span className="text-stat">
                      Status: <strong style={{ color: 'var(--sage)' }}>Masked ✓</strong>
                    </span>
                  )}
                </div>
              </div>
            )}

            {!textResult && !textLoading && (
              <div className="divider mt-lg" />
            )}
          </div>
        )}

        {/* How it works */}
        <div className="how-section">
          <h2 className="how-title">How it works</h2>
          <p className="how-sub">Three steps to protect sensitive information</p>
          <div className="how-grid">
            {[
              { icon: '📤', step: 1, title: 'Upload or paste', desc: 'Provide an image of a document or paste text containing sensitive data.' },
              { icon: '🔍', step: 2, title: 'OCR & detection', desc: 'EasyOCR reads text from images. Regex patterns and keywords identify PII types.' },
              { icon: '🔒', step: 3, title: 'Mask & download', desc: 'Detected areas are blacked out in images or replaced with tokens in text.' },
            ].map(card => (
              <div className="how-card" key={card.step}>
                <span className="how-step-num">{card.step}</span>
                <span className="how-card-icon">{card.icon}</span>
                <h4>{card.title}</h4>
                <p>{card.desc}</p>
              </div>
            ))}
          </div>
        </div>

        {/* PII types detected */}
        <div className="pii-types-section mt-lg">
          <h3 className="pii-types-title">Detected PII types</h3>
          <p className="pii-types-sub">The following sensitive data patterns are identified and masked automatically</p>
          <div className="pii-types-grid">
            {[
              { icon: '🪪', label: 'Aadhaar Number' },
              { icon: '💳', label: 'PAN Card' },
              { icon: '🛂', label: 'Passport Number' },
              { icon: '📱', label: 'Phone Number' },
              { icon: '📧', label: 'Email Address' },
              { icon: '📅', label: 'Date of Birth' },
              { icon: '💳', label: 'Credit / Debit Card' },
              { icon: '📮', label: 'PIN Code' },
              { icon: '🚗', label: 'Vehicle Registration' },
              { icon: '👤', label: 'Name Field' },
              { icon: '🏠', label: 'Address Field' },
              { icon: '⚧', label: 'Gender Field' },
            ].map(item => (
              <span className="pii-type-chip" key={item.label}>
                <span className="pii-chip-icon">{item.icon}</span> {item.label}
              </span>
            ))}
          </div>
        </div>

      </main>

      <footer>
        <p>PII Masking App · Protect privacy, redact responsibly</p>
      </footer>
    </div>
  );
}
