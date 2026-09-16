import { useState } from 'react';
import { apiClient } from '../api/client';
import './DocumentAnalysis.css';

const DocumentAnalysis = () => {
  const [uploadedDoc, setUploadedDoc] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState(null);
  const [query, setQuery] = useState('');
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisResult, setAnalysisResult] = useState(null);
  const [analysisError, setAnalysisError] = useState(null);

  const handleFileUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    // Check file size (25MB limit)
    const maxSize = 25 * 1024 * 1024; // 25MB in bytes
    if (file.size > maxSize) {
      setUploadError('File too large. Maximum size is 25MB.');
      return;
    }

    // Check file type
    const allowedTypes = ['.pdf', '.png', '.jpg', '.jpeg'];
    const fileExt = file.name.toLowerCase().substring(file.name.lastIndexOf('.'));
    if (!allowedTypes.includes(fileExt)) {
      setUploadError('Unsupported file type. Please upload PDF, PNG, JPG, or JPEG files.');
      return;
    }

    setUploading(true);
    setUploadError(null);

    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await apiClient.post('/documents/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      setUploadedDoc(response.data);
      setAnalysisResult(null); // Clear previous analysis
    } catch (err) {
      console.error('Upload error:', err);
      setUploadError(err.response?.data?.detail || 'Failed to upload document');
    } finally {
      setUploading(false);
    }
  };

  const handleAnalyze = async (e) => {
    e.preventDefault();
    
    if (!uploadedDoc || !query.trim()) {
      setAnalysisError('Please upload a document and enter a query');
      return;
    }

    setAnalyzing(true);
    setAnalysisError(null);

    try {
      const response = await apiClient.post('/documents/query', {
        document_id: uploadedDoc.document_id,
        query_text: query.trim()
      });

      setAnalysisResult(response.data);
    } catch (err) {
      console.error('Analysis error:', err);
      setAnalysisError(err.response?.data?.detail || 'Failed to analyze document');
    } finally {
      setAnalyzing(false);
    }
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleString();
  };

  return (
    <div className="document-analysis">
      <div className="document-header">
        <h1>📄 Document Analysis</h1>
        <p className="document-subtitle">Upload and analyze PDF, images, and financial documents with Qwen2-VL AI</p>
      </div>

      {/* File Upload Section */}
      <div className="upload-section">
        <h2>Upload Document</h2>
        <div className="upload-zone">
          <input
            type="file"
            id="fileInput"
            accept=".pdf,.png,.jpg,.jpeg"
            onChange={handleFileUpload}
            className="file-input"
            disabled={uploading}
          />
          <label htmlFor="fileInput" className={`upload-label ${uploading ? 'uploading' : ''}`}>
            {uploading ? (
              <>
                <div className="upload-spinner"></div>
                <span>Uploading...</span>
              </>
            ) : (
              <>
                <span className="upload-icon">📁</span>
                <span>Choose file or drag & drop</span>
                <span className="upload-hint">PDF, PNG, JPG, JPEG (max 25MB)</span>
              </>
            )}
          </label>
        </div>

        {uploadError && (
          <div className="error-message">
            ⚠️ {uploadError}
          </div>
        )}

        {uploadedDoc && (
          <div className="uploaded-doc-info">
            <div className="doc-success">
              ✅ <strong>{uploadedDoc.filename}</strong> uploaded successfully
            </div>
            <div className="doc-details">
              <span>Type: {uploadedDoc.file_type.toUpperCase()}</span>
              {uploadedDoc.page_count && <span>Pages: {uploadedDoc.page_count}</span>}
              <span>Uploaded: {formatDate(uploadedDoc.uploaded_at)}</span>
            </div>
          </div>
        )}
      </div>

      {/* Query Section */}
      {uploadedDoc && (
        <div className="query-section">
          <h2>Ask Questions About Your Document</h2>
          <form onSubmit={handleAnalyze} className="query-form">
            <textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Ask questions about your document...&#10;&#10;Examples:&#10;• What is the total revenue?&#10;• Summarize the key financial metrics&#10;• What are the main risks mentioned?&#10;• Calculate the profit margin"
              className="query-textarea"
              rows={4}
              disabled={analyzing}
            />
            <button
              type="submit"
              className={`analyze-button ${analyzing ? 'analyzing' : ''}`}
              disabled={analyzing || !query.trim()}
            >
              {analyzing ? (
                <>
                  <div className="button-spinner"></div>
                  Analyzing...
                </>
              ) : (
                <>
                  🔍 Analyze Document
                </>
              )}
            </button>
          </form>

          {analysisError && (
            <div className="error-message">
              ⚠️ {analysisError}
              {analysisError.includes('model failed to load') && (
                <p className="error-hint">
                  Document analysis uses Qwen2-VL model. The model will be downloaded automatically on first use.
                  <br />
                  This may take some time and requires sufficient disk space (~15GB).
                  <br />
                  For faster inference, ensure you have a CUDA-compatible GPU.
                </p>
              )}
            </div>
          )}
        </div>
      )}

      {/* Results Section */}
      {analysisResult && (
        <div className="results-section">
          <h2>Analysis Results</h2>
          <div className="analysis-card">
            <div className="answer-section">
              <h3>📝 Answer</h3>
              <p className="answer-text">{analysisResult.answer}</p>
            </div>

            {analysisResult.evidence && (
              <div className="evidence-section">
                <h3>📋 Evidence</h3>
                <p className="evidence-text">{analysisResult.evidence}</p>
              </div>
            )}

            {analysisResult.analysis && (
              <div className="analysis-section">
                <h3>🔍 Analysis</h3>
                <p className="analysis-text">{analysisResult.analysis}</p>
              </div>
            )}

            {analysisResult.calculation && (
              <div className="calculation-section">
                <h3>🧮 Calculation</h3>
                <p className="calculation-text">{analysisResult.calculation}</p>
              </div>
            )}

            {analysisResult.source && (
              <div className="source-section">
                <h3>🎯 Source</h3>
                <div className="source-details">
                  {analysisResult.source.page && (
                    <span className="source-tag">Page {analysisResult.source.page}</span>
                  )}
                  {analysisResult.source.section && (
                    <span className="source-tag">Section: {analysisResult.source.section}</span>
                  )}
                  {analysisResult.source.table && (
                    <span className="source-tag">Table: {analysisResult.source.table}</span>
                  )}
                  {analysisResult.source.figure && (
                    <span className="source-tag">Figure: {analysisResult.source.figure}</span>
                  )}
                </div>
              </div>
            )}

            {analysisResult.not_found && (
              <div className="not-found-notice">
                ℹ️ The requested information was not found in the document.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default DocumentAnalysis;