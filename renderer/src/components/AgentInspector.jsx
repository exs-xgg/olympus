import { useEffect, useMemo, useRef, useState } from 'react';
import { api } from '../api';

export default function AgentInspector({ agents, logs, tasks, onRefresh }) {
  const logContainerRef = useRef(null);
  const [customAgents, setCustomAgents] = useState([]);
  const [form, setForm] = useState({
    name: '',
    role: '',
    model: 'gpt-5-mini',
    temperature: '0.2',
    tools: 'run_shell_command,read_file,write_file,list_directory',
    system_prompt: '',
  });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [logs]);

  useEffect(() => {
    loadCustomAgents();
  }, []);

  const headline = agents[0] || { name: 'AGT-0000', status: 'idle', tools: [], capabilities: [] };
  const done = tasks.filter((t) => t.status === 'completed').length;
  const failed = tasks.filter((t) => t.status === 'failed').length;
  const successRate = done + failed === 0 ? '100.0' : ((done / (done + failed)) * 100).toFixed(1);
  const tokenUsage = useMemo(() => `${((headline.tokens_used || logs.length * 120) / 1000).toFixed(1)}k`, [headline.tokens_used, logs.length]);

  async function loadCustomAgents() {
    try {
      const rows = await api.listAgents();
      setCustomAgents(rows);
    } catch (err) {
      console.error('Failed to load custom agents:', err);
    }
  }

  async function handleCreateAgent(e) {
    e.preventDefault();
    if (!form.name.trim() || !form.role.trim() || !form.system_prompt.trim()) {
      alert('Name, role, and system prompt are required.');
      return;
    }
    setSaving(true);
    try {
      await api.createAgent({
        name: form.name.trim(),
        role: form.role.trim(),
        model: form.model.trim() || 'gpt-5-mini',
        temperature: Number(form.temperature || 0.2),
        tools: form.tools.split(',').map((x) => x.trim()).filter(Boolean),
        system_prompt: form.system_prompt.trim(),
      });
      setForm((prev) => ({ ...prev, name: '', role: '', system_prompt: '' }));
      await loadCustomAgents();
      await onRefresh?.();
    } catch (err) {
      alert(`Failed to create agent: ${err.message}`);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="h-full p-6 overflow-auto">
      <div className="flex items-center justify-between mb-4">
        <div className="text-2xl font-semibold">Agent: <span className="text-[#175CD3]">{headline.name}</span></div>
        <div className="flex gap-2">
          <button className="px-3 py-2 border border-[#D0D5DD] rounded-md text-sm">Halt Agent</button>
          <button onClick={onRefresh} className="px-3 py-2 bg-[#0B5FFF] text-white rounded-md text-sm">Restart</button>
        </div>
      </div>
      <div className="grid grid-cols-[360px_1fr] gap-4">
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <Stat title="Token Usage" value={tokenUsage} />
            <Stat title="Success Rate" value={`${successRate}%`} />
            <Stat title="Error Count" value={String(headline.error_count ?? failed)} />
            <Stat title="Tasks Done" value={String(headline.tasks_done ?? done)} />
          </div>

          <section className="bg-white border border-[#E6E8EC] rounded-lg">
            <div className="px-4 py-3 border-b border-[#E6E8EC] font-medium">Configuration</div>
            <div className="px-4 py-3 text-sm space-y-2">
              <Row label="Temperature" value={String(headline.temperature ?? 0.2)} />
              <Row label="Max Tokens" value={String(headline.max_tokens ?? 4096)} />
              <Row label="System Prompt" value="View Definition" />
              <div className="text-xs text-[#667085] mt-3">Active Tools</div>
              <div className="flex gap-2 flex-wrap">
                {(headline.tools || []).map((tool) => (
                  <span key={tool} className="px-2 py-1 text-xs bg-[#F2F4F7] rounded border border-[#EAECF0] font-mono">{tool}</span>
                ))}
              </div>
            </div>
          </section>
          <section className="bg-white border border-[#E6E8EC] rounded-lg">
            <div className="px-4 py-3 border-b border-[#E6E8EC] font-medium">Create Custom Agent</div>
            <form onSubmit={handleCreateAgent} className="p-4 space-y-2">
              <input className="w-full border border-[#D0D5DD] rounded px-2 py-1.5 text-sm" placeholder="Agent name" value={form.name} onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))} />
              <input className="w-full border border-[#D0D5DD] rounded px-2 py-1.5 text-sm" placeholder="Role" value={form.role} onChange={(e) => setForm((p) => ({ ...p, role: e.target.value }))} />
              <div className="grid grid-cols-2 gap-2">
                <input className="border border-[#D0D5DD] rounded px-2 py-1.5 text-sm" placeholder="Model" value={form.model} onChange={(e) => setForm((p) => ({ ...p, model: e.target.value }))} />
                <input className="border border-[#D0D5DD] rounded px-2 py-1.5 text-sm" placeholder="Temperature" value={form.temperature} onChange={(e) => setForm((p) => ({ ...p, temperature: e.target.value }))} />
              </div>
              <input className="w-full border border-[#D0D5DD] rounded px-2 py-1.5 text-sm font-mono" placeholder="tools comma-separated" value={form.tools} onChange={(e) => setForm((p) => ({ ...p, tools: e.target.value }))} />
              <textarea className="w-full h-24 border border-[#D0D5DD] rounded px-2 py-1.5 text-sm" placeholder="System prompt" value={form.system_prompt} onChange={(e) => setForm((p) => ({ ...p, system_prompt: e.target.value }))} />
              <button disabled={saving} className="w-full px-3 py-2 bg-[#0B5FFF] text-white rounded-md text-sm disabled:opacity-60">
                {saving ? 'Creating...' : 'Create Agent'}
              </button>
            </form>
          </section>
        </div>

        <div className="space-y-4">
          <section className="bg-white border border-[#E6E8EC] rounded-lg">
            <div className="px-4 py-3 border-b border-[#E6E8EC] flex justify-between">
              <div className="font-medium">Working Context (Memory Tree)</div>
              <button className="text-sm text-[#175CD3]">Copy JSON</button>
            </div>
            <pre className="p-4 text-xs overflow-auto font-mono">
{`{
  "agent_id": "${headline.name}",
  "status": "${headline.status}",
  "active_tasks": ${tasks.filter((t) => t.status === 'running').length},
  "capabilities": ${JSON.stringify(headline.capabilities || [])}
}`}
            </pre>
          </section>
          <section className="bg-[#0F172A] text-[#E5E7EB] border border-[#1D2939] rounded-lg">
            <div className="px-4 py-3 border-b border-[#1D2939] flex justify-between">
              <div className="font-medium">Real-Time Execution Logs</div>
              <div className="text-xs text-[#98A2B3]">Streaming</div>
            </div>
            <div ref={logContainerRef} className="h-[300px] overflow-auto p-4 font-mono text-xs space-y-1">
              {logs.map((log) => (
                <div key={log.id}>
                  <span className="text-[#98A2B3]">[{new Date(log.timestamp || Date.now()).toLocaleTimeString()}]</span>{' '}
                  <span className="text-[#2E90FA]">{log.agent_name || 'system'}</span>{' '}
                  <span>{log.action}</span>
                  {log.detail && <span className="text-[#98A2B3]"> - {log.detail}</span>}
                </div>
              ))}
              {logs.length === 0 && <div className="text-[#98A2B3]">No logs yet.</div>}
            </div>
          </section>
          <section className="bg-white border border-[#E6E8EC] rounded-lg">
            <div className="px-4 py-3 border-b border-[#E6E8EC] font-medium">Custom Agents ({customAgents.length})</div>
            <div className="p-3 space-y-2 max-h-[260px] overflow-auto">
              {customAgents.map((agent) => (
                <div key={agent.id} className="border border-[#EAECF0] rounded p-2">
                  <div className="text-sm font-semibold">{agent.name}</div>
                  <div className="text-xs text-[#667085]">{agent.role}</div>
                  <div className="text-xs mt-1 text-[#344054]">Model: {agent.model} · Temp: {agent.temperature}</div>
                </div>
              ))}
              {customAgents.length === 0 && <div className="text-sm text-[#98A2B3]">No custom agents yet.</div>}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}

function Stat({ title, value }) {
  return (
    <div className="bg-white border border-[#E6E8EC] rounded-lg p-3">
      <div className="text-xs text-[#667085] uppercase">{title}</div>
      <div className="text-[30px] leading-none mt-2 font-semibold">{value}</div>
    </div>
  );
}

function Row({ label, value }) {
  return (
    <div className="flex justify-between border-b border-[#F2F4F7] py-1.5">
      <span className="text-[#667085]">{label}</span>
      <span>{value}</span>
    </div>
  );
}
