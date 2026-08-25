import React, { useState, useRef, useEffect } from 'react';
import { MessageSquare, X, Send, ChevronRight } from 'lucide-react';

// ─── OpenRouter API helper ───────────────────────────────────────────────────

// Read the key from the .env file in a Vite app
const OPENROUTER_API_KEY = import.meta.env.VITE_DEEPSEEK_API_KEY;
const OPENROUTER_MODEL   = 'deepseek/deepseek-chat';

async function callDeepseek(messages, systemPrompt) {
  const apiMessages = [
    { role: 'system', content: systemPrompt },
    ...messages.map(m => ({ role: m.role, content: m.content }))
  ];

  const response = await fetch('https://openrouter.ai/api/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${OPENROUTER_API_KEY}`,
      'HTTP-Referer': 'http://localhost:5173', // Optional, for OpenRouter tracking
      'X-Title': 'DatacenterOS' // Optional, for OpenRouter tracking
    },
    body: JSON.stringify({
      model: OPENROUTER_MODEL,
      messages: apiMessages,
      max_tokens: 1000
    })
  });

  const data = await response.json();
  if (data.error) throw new Error(data.error.message);
  return data.choices[0].message.content;
}

// ─── Dots loader ──────────────────────────────────────────────────────────

function LoadingDots() {
  return (
    <span className="inline-flex gap-1 items-center">
      {[0, 1, 2].map(i => (
        <span
          key={i}
          className="w-1.5 h-1.5 rounded-full bg-gray-400"
          style={{
            animation: `aiDotPulse 1.2s ease-in-out ${i * 0.2}s infinite`,
          }}
        />
      ))}
    </span>
  );
}

// ─── Message bubble ───────────────────────────────────────────────────────

function Bubble({ msg }) {
  const isUser = msg.role === 'user';
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-3`}>
      {!isUser && (
        <div
          className="flex-shrink-0 w-5 h-5 rounded-full flex items-center justify-center text-[9px] font-black text-black mr-2 mt-1"
          style={{ background: '#f0b429' }}
        >
          AI
        </div>
      )}
      <div
        className="max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed"
        style={{
          background: isUser ? '#f0b429' : '#0f1629',
          color: isUser ? '#000' : '#fff',
          border: isUser ? 'none' : '1px solid #1e2a45',
        }}
      >
        {msg.loading ? <LoadingDots /> : msg.content}
      </div>
    </div>
  );
}

// ─── Chip strip ───────────────────────────────────────────────────────────

function Chips({ questions, onSelect }) {
  if (!questions?.length) return null;
  return (
    <div className="flex gap-2 overflow-x-auto pb-1 mb-2" style={{ scrollbarWidth: 'none' }}>
      {questions.map(q => (
        <button
          key={q}
          onClick={() => onSelect(q)}
          className="flex-shrink-0 text-xs px-3 py-1.5 rounded-full border transition-all duration-200 whitespace-nowrap"
          style={{
            borderColor: '#f0b429',
            color: '#f0b429',
            background: 'transparent',
          }}
          onMouseEnter={e => {
            e.currentTarget.style.background = '#f0b429';
            e.currentTarget.style.color = '#000';
          }}
          onMouseLeave={e => {
            e.currentTarget.style.background = 'transparent';
            e.currentTarget.style.color = '#f0b429';
          }}
        >
          {q}
        </button>
      ))}
    </div>
  );
}

// ─── Chat body ────────────────────────────────────────────────────────────

function ChatBody({ messages, inputValue, setInputValue, onSend, isLoading, suggestedQuestions }) {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleKey = e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); onSend(inputValue); }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-3" style={{ maxHeight: 300, minHeight: 100 }}>
        {messages.length === 0 && (
          <p className="text-xs text-center mt-4" style={{ color: '#64748b' }}>
            Ask me anything about your facility setup.
          </p>
        )}
        {messages.map((m, i) => <Bubble key={i} msg={m} />)}
        <div ref={bottomRef} />
      </div>

      {/* Chips */}
      <div className="px-3">
        <Chips questions={suggestedQuestions} onSelect={q => onSend(q)} />
      </div>

      {/* Input */}
      <div className="flex gap-2 p-3 border-t" style={{ borderColor: '#1e2a45' }}>
        <input
          value={inputValue}
          onChange={e => setInputValue(e.target.value)}
          onKeyDown={handleKey}
          placeholder="Ask anything..."
          disabled={isLoading}
          className="flex-1 bg-transparent text-sm text-white outline-none placeholder-gray-600"
          style={{ borderBottom: '1px solid #1e2a45', paddingBottom: 4 }}
        />
        <button
          onClick={() => onSend(inputValue)}
          disabled={isLoading || !inputValue.trim()}
          className="w-8 h-8 rounded-full flex items-center justify-center transition-all"
          style={{
            background: inputValue.trim() ? '#f0b429' : '#1e2a45',
            color: inputValue.trim() ? '#000' : '#64748b',
          }}
        >
          <Send size={14} />
        </button>
      </div>
    </div>
  );
}

// ─── Main AIAgent ─────────────────────────────────────────────────────────

/**
 * Props:
 *   systemPrompt  — string prompt for Claude
 *   context       — plain object (serialised into first message if needed)
 *   placeholder   — input placeholder text
 *   suggestedQuestions — string[]
 *   compact       — boolean: floating mode vs inline
 *   onSelectOption — optional callback(field, value) for agentic wizard
 *   initialMessage — optional string: auto-send this on mount
 */
export default function AIAgent({
  systemPrompt = 'You are a helpful AI assistant.',
  context = null,
  placeholder = 'Ask anything...',
  suggestedQuestions = [],
  compact = false,
  onSelectOption = null,
  initialMessage = null,
}) {
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const hasAutoSent = useRef(false);

  // Auto-send initialMessage once on mount (for the AI summary panel in wizard)
  useEffect(() => {
    if (initialMessage && !hasAutoSent.current) {
      hasAutoSent.current = true;
      sendMessage(initialMessage);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const sendMessage = async (text) => {
    if (!text?.trim()) return;
    setInputValue('');

    const userMsg = { role: 'user', content: text, timestamp: Date.now() };
    const loadingMsg = { role: 'assistant', content: '', loading: true, timestamp: Date.now() };

    setMessages(prev => [...prev, userMsg, loadingMsg]);
    setIsLoading(true);

    try {
      // Build messages array for API (inject context as very first user msg)
      const history = [...messages, userMsg];
      let apiMessages = history.map(m => ({ role: m.role, content: m.content }));
      
      // Prepend context if provided and first message
      if (context && messages.length === 0) {
        apiMessages = [
          { role: 'user', content: `[Context]\n${JSON.stringify(context, null, 2)}\n\n[Question]\n${text}` },
        ];
      }

      const reply = await callDeepseek(apiMessages, systemPrompt);

      // Parse any agentic actions from reply
      if (onSelectOption) {
        const actionMatch = reply.match(/\{"action"\s*:\s*"selectOption"[^}]+\}/);
        if (actionMatch) {
          try {
            const action = JSON.parse(actionMatch[0]);
            if (action.field && action.value) onSelectOption(action.field, action.value);
          } catch {}
        }
      }

      setMessages(prev => [
        ...prev.slice(0, -1), // remove loading
        { role: 'assistant', content: reply, timestamp: Date.now() },
      ]);
    } catch (err) {
      setMessages(prev => [
        ...prev.slice(0, -1),
        { role: 'assistant', content: `Error: ${err.message || 'Could not reach AI. Please try again.'}`, timestamp: Date.now() },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  // ── INLINE MODE ──────────────────────────────────────────────────────────
  if (!compact) {
    return (
      <div
        className="rounded-2xl overflow-hidden"
        style={{ background: '#0f1629', border: '1px solid #1e2a45' }}
      >
        <div
          className="flex items-center gap-2 px-4 py-3 border-b"
          style={{ borderColor: '#1e2a45', background: '#0a0e1a' }}
        >
          <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
          <span className="text-xs font-mono font-bold text-green-400 uppercase tracking-widest">
            GreenCore AI Advisor
          </span>
        </div>
        <ChatBody
          messages={messages}
          inputValue={inputValue}
          setInputValue={setInputValue}
          onSend={sendMessage}
          isLoading={isLoading}
          suggestedQuestions={suggestedQuestions}
        />
      </div>
    );
  }

  // ── COMPACT / FLOATING MODE ──────────────────────────────────────────────
  return (
    <>
      {/* Floating button */}
      {!isOpen && (
        <button
          onClick={() => setIsOpen(true)}
          style={{
            position: 'fixed',
            bottom: 32,
            right: 32,
            width: 56,
            height: 56,
            borderRadius: '50%',
            background: '#f0b429',
            border: 'none',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 9000,
            boxShadow: '0 0 0 0 rgba(240,180,41,0.6)',
            animation: 'aiPulseGlow 2.5s ease-in-out infinite',
          }}
          title="GreenCore AI Assistant"
        >
          <MessageSquare size={22} color="#000" />
        </button>
      )}

      {/* Expanded panel */}
      {isOpen && (
        <div
          style={{
            position: 'fixed',
            bottom: 32,
            right: 32,
            width: 340,
            height: 440,
            borderRadius: 20,
            background: '#0f1629',
            border: '1px solid #1e2a45',
            display: 'flex',
            flexDirection: 'column',
            zIndex: 9000,
            boxShadow: '0 20px 60px rgba(0,0,0,0.5)',
            overflow: 'hidden',
          }}
        >
          {/* Panel header */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '12px 16px',
              borderBottom: '1px solid #1e2a45',
              background: '#0a0e1a',
              flexShrink: 0,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: '50%',
                  background: '#10b981',
                  boxShadow: '0 0 6px #10b981',
                  animation: 'aiDotPulse 2s ease-in-out infinite',
                }}
              />
              <span style={{ fontSize: 11, fontFamily: 'monospace', color: '#10b981', textTransform: 'uppercase', letterSpacing: '0.1em', fontWeight: 700 }}>
                GreenCore AI
              </span>
            </div>
            <button
              onClick={() => setIsOpen(false)}
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#64748b', padding: 4 }}
            >
              <X size={16} />
            </button>
          </div>

          {/* Chat area fills remaining height */}
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            <ChatBody
              messages={messages}
              inputValue={inputValue}
              setInputValue={setInputValue}
              onSend={sendMessage}
              isLoading={isLoading}
              suggestedQuestions={suggestedQuestions}
            />
          </div>
        </div>
      )}

      {/* Global keyframes injected once */}
      <style>{`
        @keyframes aiPulseGlow {
          0%, 100% { box-shadow: 0 0 0 0 rgba(240,180,41,0.5); }
          50% { box-shadow: 0 0 0 12px rgba(240,180,41,0); }
        }
        @keyframes aiDotPulse {
          0%, 100% { opacity: 0.3; transform: scale(0.8); }
          50% { opacity: 1; transform: scale(1); }
        }
      `}</style>
    </>
  );
}
