import React, { useState, useEffect } from "react";
import ChartDisplay from "./ChartDisplay.jsx";
import DataTable from "./DataTable.jsx";

export default function Message({
  sender,
  text,
  attachments,
  charts,
  structured_data,
  metadata,
  isLatest,
  onStreamProgress,
}) {
  const shouldStream = sender === "bot" && isLatest;
  const [displayedText, setDisplayedText] = useState(shouldStream ? "" : text);
  const [selectedImage, setSelectedImage] = useState(null);
  const [isStreaming, setIsStreaming] = useState(false);

  useEffect(() => {
    if (!shouldStream) {
      setDisplayedText(text);
      setIsStreaming(false);
      return;
    }

    // Start streaming the response
    setIsStreaming(true);
    const words = text.split(" ");
    let index = 0;
    setDisplayedText("");

    const timer = setInterval(() => {
      if (index < words.length) {
        const word = words[index];
        setDisplayedText((prev) => (prev ? prev + " " + word : word));
        index++;
        if (onStreamProgress) onStreamProgress();
      } else {
        clearInterval(timer);
        setIsStreaming(false);
      }
    }, 20);

    return () => clearInterval(timer);
  }, [text, shouldStream]);

  const formatSize = (bytes) => {
    if (!bytes) return "";
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className={`message ${sender}`}>
      <div className="bubble" style={{ whiteSpace: "pre-wrap" }}>
        {/* RENDER ATTACHMENTS (Images / PDFs) IF PRESENT */}
        {attachments && attachments.length > 0 && (
          <div className="msg-attachments-container">
            {attachments.map((att, idx) => {
              const isImg =
                att.isImage ||
                att.type?.startsWith("image/") ||
                (att.data && att.data.startsWith("data:image/"));
              const isPdf =
                att.isPdf ||
                att.type === "application/pdf" ||
                att.name?.toLowerCase().endsWith(".pdf");

              if (isImg) {
                return (
                  <div className="msg-img-card" key={idx}>
                    <img
                      src={att.data || att.preview}
                      alt={att.name || "Attached image"}
                      className="msg-img-preview"
                      onClick={() => setSelectedImage(att.data || att.preview)}
                      title="Click to view full image"
                    />
                    <span className="msg-img-caption">{att.name}</span>
                  </div>
                );
              }

              return (
                <div className="msg-doc-pill" key={idx}>
                  <span className="msg-doc-icon">{isPdf ? "📕" : "📄"}</span>
                  <div className="msg-doc-details">
                    <span className="msg-doc-name" title={att.name}>
                      {att.name}
                    </span>
                    {att.size > 0 && (
                      <span className="msg-doc-size">
                        {formatSize(att.size)}
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {displayedText && (
          <div className="msg-text-content">
            {displayedText}
            {shouldStream && displayedText.length < text.length && (
              <span className="cursor-blink">▌</span>
            )}
          </div>
        )}

        {/* RENDER CHARTS */}
        {charts && charts.length > 0 && (
          <div className="msg-charts-container">
            {charts.map((chart, idx) => (
              <ChartDisplay key={idx} chartData={chart} />
            ))}
          </div>
        )}

        {/* RENDER STRUCTURED DATA TABLES */}
        {structured_data && structured_data.length > 0 && (
          <div className="msg-data-container">
            {structured_data.map((data, idx) => (
              <DataTable key={idx} structuredData={data} />
            ))}
          </div>
        )}

        {/* RENDER METADATA (Optional) */}
        {metadata && metadata.has_visuals && (
          <div className="msg-metadata">
            <small className="metadata-info">
              📊 {metadata.chart_count || 0} chart{(metadata.chart_count || 0) !== 1 ? 's' : ''} • 
              📋 {metadata.data_table_count || 0} table{(metadata.data_table_count || 0) !== 1 ? 's' : ''}
            </small>
          </div>
        )}
      </div>

      {/* FULL IMAGE MODAL VIEWER */}
      {selectedImage && (
        <div
          className="auth-modal-overlay img-preview-overlay"
          onClick={() => setSelectedImage(null)}
        >
          <div
            className="img-preview-container"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              className="auth-modal-close"
              onClick={() => setSelectedImage(null)}
            >
              ✕
            </button>
            <img
              src={selectedImage}
              alt="Full preview"
              className="img-full-view"
            />
          </div>
        </div>
      )}
    </div>
  );
}