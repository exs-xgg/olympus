import { useEffect, useMemo, useState } from 'react';
import { api } from '../api';

const BUILTIN_AGENTS = ['WorkflowAgent', 'CodingAgent', 'ReviewerAgent'];
const THREAD_STORAGE_KEY = 'agent-chat-thread-id';
const AGENT_STORAGE_KEY = 'agent-chat-selected-agent';

export default function AgentChat({ agents }) {
  const [selectedAgent, setSelectedAgent] = useState(() => localStorage.getItem(AGENT_STORAGE_KEY) || 'auto');
  const [threadId, setThreadId] = useState(null);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [messages, setMessages] = useState([]);

  const selectableAgents = useMemo(() => {
    const names = new Set(['auto', ...BUILTIN_AGENTS]);
    (agents || []).forEach((agent) => {
      if (agent?.name) names.add(agent.name);
    });
    return Array.from(names);
  }, [agents]);

  useEffect(() => {
    localStorage.setItem(AGENT_STORAGE_KEY, selectedAgent);
  }, [selectedAgent]);

  useEffect(() => {
    const savedThreadId = localStorage.getItem(THREAD_STORAGE_KEY);
    if (!savedThreadId) return;
    let cancelled = false;
    async function loadHistory() {
      try {
        const rows = await api.getAgentChatMessages(savedThreadId);
        if (cancelled) return;
        setThreadId(savedThreadId);
        setMessages(
          rows.map((row) => ({
            role: row.role,
            content: row.content,
            agentName: row.agent_name || undefined,
          }))
        );
      } catch (err) {
        console.error('Failed to load persisted chat thread:', err);
      }
    }
    loadHistory();
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleSend(e) {
    e.preventDefault();
    const text = input.trim();
    if (!text || sending) return;

    setSending(true);
    setMessages((prev) => [...prev, { role: 'user', content: text }]);
    setInput('');

    try {
      const res = await api.chatWithAgent({
        agent_name: selectedAgent,
        message: text,
        thread_id: threadId,
      });
      setThreadId(res.thread_id);
      localStorage.setItem(THREAD_STORAGE_KEY, res.thread_id);
      setMessages((prev) => [...prev, { role: 'agent', content: res.response, agentName: res.agent_name }]);
    } catch (err) {
      setMessages((prev) => [...prev, { role: 'system', content: `Error: ${err.message}` }]);
    } finally {
      setSending(false);
    }
  }

  function handleNewThread() {
    setThreadId(null);
    setMessages([]);
    localStorage.removeItem(THREAD_STORAGE_KEY);
  }

  return (
    <div className="h-full p-6">
      <div className="h-full bg-white border border-[#E6E8EC] rounded-lg flex flex-col overflow-hidden">
        <div className="px-4 py-3 border-b border-[#E6E8EC] flex items-center justify-between gap-4">
          <div>
            <div className="font-semibold">Agent Chat</div>
            <div className="text-xs text-[#667085]">Have a direct conversation with any configured agent.</div>
            {threadId && <div className="text-xs text-[#98A2B3] mt-1">Thread: {threadId}</div>}
          </div>
          <div className="flex items-center gap-2">
            <select
              value={selectedAgent}
              onChange={(e) => setSelectedAgent(e.target.value)}
              className="border border-[#D0D5DD] rounded-md px-3 py-2 text-sm bg-white"
            >
              {selectableAgents.map((name) => (
                <option key={name} value={name}>{name === 'auto' ? 'Auto (detect for me)' : name}</option>
              ))}
            </select>
            <button
              onClick={handleNewThread}
              className="px-3 py-2 text-sm border border-[#D0D5DD] rounded-md hover:bg-[#F9FAFB]"
            >
              New Thread
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-auto px-4 py-4 bg-[#FCFCFD] space-y-3">
          {messages.length === 0 && (
            <div className="text-sm text-[#667085]">
              Start by sending a message to <span className="font-medium">{selectedAgent === 'auto' ? 'Auto Router' : selectedAgent}</span>.
            </div>
          )}
          {messages.map((msg, idx) => (
            <div
              key={idx}
              className={`max-w-[85%] rounded-md px-3 py-2 text-sm whitespace-pre-wrap ${
                msg.role === 'user'
                  ? 'ml-auto bg-[#0B5FFF] text-white'
                  : msg.role === 'system'
                    ? 'bg-[#FEF3F2] text-[#B42318] border border-[#FECDCA]'
                    : 'bg-white text-[#101828] border border-[#E4E7EC]'
              }`}
            >
              {msg.role !== 'user' && (
                <div className="text-xs mb-1 text-[#667085]">
                  {msg.role === 'agent' ? msg.agentName || selectedAgent : 'System'}
                </div>
              )}
              {msg.content}
            </div>
          ))}
        </div>

        <form onSubmit={handleSend} className="border-t border-[#E6E8EC] p-3 flex items-end gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={`Message ${selectedAgent === 'auto' ? 'Auto Router' : selectedAgent}...`}
            className="flex-1 border border-[#D0D5DD] rounded-md px-3 py-2 text-sm resize-none h-20 focus:outline-none focus:ring-2 focus:ring-[#0B5FFF]/20"
          />
          <button
            type="submit"
            disabled={sending || !input.trim()}
            className="px-4 py-2 bg-[#0B5FFF] text-white rounded-md text-sm disabled:opacity-60"
          >
            {sending ? 'Sending...' : 'Send'}
          </button>
        </form>
      </div>
    </div>
  );
}
