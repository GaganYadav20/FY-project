import React, { useState, useRef } from "react";

export default function InputBox({ onSendMessage, disabled }) {
  const [text, setText] = useState("");
  const [attachments, setAttachments] = useState([]);
  const [isDragOver, setIsDragOver] = useState(false);
  const fileInputRef = useRef(null);

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      processFiles(Array.from(e.target.files));
    }
  };

  const processFiles = (fileList) => {
    fileList.forEach((file) => {
      const reader = new FileReader();
      reader.onload = (event) => {
        const base64Data = event.target.result;
        const isImage = file.type.startsWith("image/");
        const isPdf = file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");

        setAttachments((prev) => [
          ...prev,
          {
            id: `att_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`,
            name: file.name,
            type: file.type || (isPdf ? "application/pdf" : "text/plain"),
            size: file.size,
            data: base64Data,
            isImage,
            isPdf,
            preview: isImage ? base64Data : null,
          },
        ]);
      };
      reader.readAsDataURL(file);
    });

    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const removeAttachment = (id) => {
    setAttachments((prev) => prev.filter((a) => a.id !== id));
  };

  const handleSend = () => {
    const trimmed = text.trim();
    if ((!trimmed && attachments.length === 0) || disabled) return;

    onSendMessage(trimmed, attachments);
    setText("");
    setAttachments([]);
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      processFiles(Array.from(e.dataTransfer.files));
    }
  };

  const formatSize = (bytes) => {
    if (!bytes) return "0 KB";
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div
      className={`input-container ${isDragOver ? "dragover-input" : ""}`}
      onDragOver={(e) => {
        e.preventDefault();
        setIsDragOver(true);
      }}
      onDragLeave={() => setIsDragOver(false)}
      onDrop={handleDrop}
    >
      {/* ATTACHMENTS PREVIEW TRAY (ChatGPT style) */}
      {attachments.length > 0 && (
        <div className="attachments-tray">
          {attachments.map((att) => (
            <div className="attachment-chip" key={att.id}>
              {att.isImage ? (
                <div className="attachment-thumb-wrapper">
                  <img
                    src={att.preview}
                    alt={att.name}
                    className="attachment-thumb"
                  />
                </div>
              ) : (
                <span className="attachment-icon">
                  {att.isPdf ? "📕" : "📄"}
                </span>
              )}
              <div className="attachment-meta">
                <span className="attachment-filename" title={att.name}>
                  {att.name}
                </span>
                <span className="attachment-filesize">
                  {formatSize(att.size)}
                </span>
              </div>
              <button
                type="button"
                className="attachment-remove-btn"
                onClick={() => removeAttachment(att.id)}
                title="Remove attachment"
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="input-area">
        {/* HIDDEN NATIVE FILE INPUT */}
        <input
          type="file"
          ref={fileInputRef}
          style={{ display: "none" }}
          multiple
          accept="image/*,application/pdf,.csv,.txt,.docx,.xlsx"
          onChange={handleFileChange}
          disabled={disabled}
        />

        {/* ATTACH BUTTON (ChatGPT style) */}
        <button
          type="button"
          className="attach-btn"
          onClick={() => fileInputRef.current?.click()}
          disabled={disabled}
          title="Attach image or PDF directly from computer"
        >
          📎
        </button>

        <textarea
          placeholder={
            attachments.length > 0
              ? "Ask a question about the attached file(s) (e.g. 'Explain this image', 'Summarize this PDF')..."
              : "Message IRIUM AI (or attach an image or PDF to analyze)..."
          }
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          rows={1}
        />

        <button
          onClick={handleSend}
          disabled={disabled || (!text.trim() && attachments.length === 0)}
          title="Send message"
        >
          ➜
        </button>
      </div>
    </div>
  );
}