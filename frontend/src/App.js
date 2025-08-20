import React, { useState } from 'react';
import axios from 'axios';
import './App.css';

function App() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [processedImageUrl, setProcessedImageUrl] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleFileChange = (event) => {
    const file = event.target.files[0];
    if (file) {
      setSelectedFile(file);
      setPreviewUrl(URL.createObjectURL(file));
      setProcessedImageUrl(null);
      setError(null);
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) {
      setError('Please select an image first');
      return;
    }

    setLoading(true);
    setError(null);

    const formData = new FormData();
    formData.append('file', selectedFile);

    // Use environment variable for API URL or default to relative path
    const API_URL = process.env.REACT_APP_API_URL || '/api';

    try {
      const response = await axios.post(`${API_URL}/upload/`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      setProcessedImageUrl(`${API_URL}/processed/${response.data.filename}`);
    } catch (err) {
      console.error('Error uploading image:', err);
      setError(err.response?.data?.detail || 'Error processing image');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>PII Masking Application</h1>
        <p>Upload an image containing PII to automatically mask sensitive information</p>
      </header>

      <main className="App-main">
        <div className="upload-section">
          <input
            type="file"
            onChange={handleFileChange}
            accept="image/*"
            id="file-input"
            className="file-input"
          />
          <label htmlFor="file-input" className="file-label">
            Choose Image
          </label>
          <button 
            onClick={handleUpload} 
            disabled={!selectedFile || loading}
            className="upload-button"
          >
            {loading ? 'Processing...' : 'Process Image'}
          </button>
        </div>

        {error && <div className="error-message">{error}</div>}

        <div className="image-container">
          <div className="image-box">
            <h2>Original Image</h2>
            {previewUrl ? (
              <img src={previewUrl} alt="Preview" className="preview-image" />
            ) : (
              <div className="placeholder">No image selected</div>
            )}
          </div>

          <div className="image-box">
            <h2>Processed Image</h2>
            {processedImageUrl ? (
              <img src={processedImageUrl} alt="Processed" className="preview-image" />
            ) : (
              <div className="placeholder">
                {loading ? 'Processing...' : 'Upload an image to see the result'}
              </div>
            )}
          </div>
        </div>
      </main>

      <footer className="App-footer">
        <p>PII Masking Application - Powered by AI</p>
      </footer>
    </div>
  );
}

export default App;