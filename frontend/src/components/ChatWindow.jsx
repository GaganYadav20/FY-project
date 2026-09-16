import React, { useRef, useEffect } from "react";
import Message from "./Message";
import InputBox from "./InputBox";

export default function ChatWindow({
  messages,
  onSendMessage,
}) {
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  return (
    <main className="chat-window">
      <div className="chat-header">
        <h2>⚡ IRIUM Financial AI Assistant</h2>
      </div>

      <div className="messages">
        {messages.map((msg, index) => (
          <Message
            key={index}
            {...msg}
            isLatest={index === messages.length - 1}
            onStreamProgress={scrollToBottom}
          />
        ))}
        <div ref={messagesEndRef} />
      </div>

      <InputBox
        onSendMessage={onSendMessage}
        disabled={false}
      />
    </main>
  );
}
