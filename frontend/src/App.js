import React, { useState } from 'react';
import axios from 'axios';
import './App.css';

function App() {
  // State to hold the selected file
  const [file, setFile] = useState(null);
  
  // State to hold the URL of the original image for preview
  const [originalImage, setOriginalImage] = useState(null);
  
  // State to hold the URL of the processed image from the backend
  const [processedImage, setProcessedImage] = useState(null);
  
  // State for loading indicator
  const [isLoading, setIsLoading] = useState(false);

  // State for error messages
  const [error, setError] = useState('');

  /**
   * Handles the file selection from the input.
   */
  const handleFileChange = (event) => {
    const selectedFile = event.target.files[0];
    if (selectedFile) {
      setFile(selectedFile);
      // Create a temporary URL to display the selected image as a preview
      setOriginalImage(URL.createObjectURL(selectedFile));
      // Reset previous results
      setProcessedImage(null);
      setError('');
    }
  };

  /**
   * Handles the image upload and processing request.
   */
  const handleUpload = async () => {
    if (!file) {
      setError('Please select an image first.');
      return;
    }

    // Set loading state and clear previous errors
    setIsLoading(true);
    setError('');

    // Create a FormData object to send the file
    const formData = new FormData();
    formData.append('file', file);

    try {
      // THE FIX IS HERE: Use a relative URL for the API endpoint.
      // This works perfectly with `vercel dev` and when deployed to Vercel.
      const response = await axios.post('/api/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        // Tell Axios to expect the response as a binary blob
        responseType: 'blob',
      });
      
      // Create a URL from the binary image data returned by the API
      const processedImageUrl = URL.createObjectURL(response.data);
      setProcessedImage(processedImageUrl);

    } catch (err) {
      // This is where the "AxiosError" would be caught
      console.error('Error uploading image:', err);
      setError('Image processing failed. Please check the console and try again.');
    } finally {
      // Always turn off the loading indicator
      setIsLoading(false);
    }
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>PII Masking Application</h1>
        <p>Upload an image to automatically detect and mask sensitive information.</p>
      </header>
      
      <main className="App-main">
        <div className="controls">
          <input type="file" accept="image/*" onChange={handleFileChange} />
          <button onClick={handleUpload} disabled={!file || isLoading}>
            {isLoading ? 'Processing...' : 'Process Image'}
          </button>
        </div>

        {error && <p className="error-message">{error}</p>}

        <div className="image-container">
          <div className="image-box">
            <h2>Original Image</h2>
            {originalImage ? (
              <img src={originalImage} alt="Original upload" />
            ) : (
              <p>Select an image to see a preview.</p>
            )}
          </div>
          <div className="image-box">
            <h2>Processed Image</h2>
            {isLoading && <p>Loading...</p>}
            {processedImage ? (
              <img src={processedImage} alt="Processed with masked PII" />
            ) : (
              !isLoading && <p>Your masked image will appear here.</p>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;