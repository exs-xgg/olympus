import { useEffect, useState } from 'react';
import { api } from '../api';

export default function TaskProgressModal({ task, onClose }) {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    async function load() {
      if (!task?.id) return;
      setLoading(true);
      setError('');
      try {
        const data = await api.getTaskLogs(task.id);
        if (!cancelled) setLogs(data);
      } catch (err) {
        if (!cancelled) setError(err.message || 'Failed to load task logs');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    const timer = setInterval(load, 2000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [task?.id]);

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-6">
      <div className="w-[1000px] max-h-[90vh] overflow-hidden bg-white rounded-xl border border-[#E6E8EC] shadow-xl flex flex-col">
        <div className="px-5 py-4 border-b border-[#E6E8EC] flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold">Task Progress</h3>
            <p className="text-sm text-[#667085]">{task.title}</p>
          </div>
          <button onClick={onClose} className="px-3 py-1.5 text-sm border border-[#D0D5DD] rounded-md">Close</button>
        </div>
        <div className="grid grid-cols-[320px_1fr] min-h-0 flex-1">
          <aside className="border-r border-[#E6E8EC] p-4 space-y-2 overflow-auto">
            <Row label="Task ID" value={task.id} mono />
            <Row label="Status" value={task.status} />
            <Row label="Agent" value={task.assigned_agent || 'Unassigned'} />
            <Row label="Created" value={toLocal(task.created_at)} />
            <Row label="Updated" value={toLocal(task.updated_at)} />
            {task.result && <Block label="Final Output" value={task.result} />}
            {task.error && <Block label="Error" value={task.error} danger />}
            <Block label="Original Request" value={task.description} />
          </aside>
          <section className="min-h-0 flex flex-col">
            <div className="px-4 py-3 border-b border-[#E6E8EC] flex items-center justify-between">
              <div className="font-medium">Execution Timeline</div>
              <div className="text-xs text-[#667085]">{logs.length} events</div>
            </div>
            <div className="flex-1 overflow-auto p-4 bg-[#0F172A] text-[#E5E7EB] font-mono text-xs space-y-2">
              {loading && <div className="text-[#98A2B3]">Loading progress events...</div>}
              {!loading && error && <div className="text-[#FCA5A5]">{error}</div>}
              {!loading && !error && logs.length === 0 && (
                <div className="text-[#98A2B3]">No events yet. Task may still be initializing.</div>
              )}
              {logs.map((log) => (
                <div key={log.id} className="border border-[#1D2939] rounded p-2">
                  <div className="text-[#98A2B3]">{toLocal(log.timestamp)}</div>
                  <div className="text-[#93C5FD]">{log.agent_name || 'system'} :: {log.action}</div>
                  {log.detail && <pre className="mt-1 whitespace-pre-wrap break-words">{log.detail}</pre>}
                </div>
              ))}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}

function Row({ label, value, mono = false }) {
  return (
    <div className="text-sm">
      <div className="text-[#667085]">{label}</div>
      <div className={mono ? 'font-mono break-all' : ''}>{value || '-'}</div>
    </div>
  );
}

function Block({ label, value, danger = false }) {
  return (
    <div className={`mt-4 p-3 border rounded ${danger ? 'border-[#FECDCA] bg-[#FEF3F2]' : 'border-[#E6E8EC] bg-[#F9FAFB]'}`}>
      <div className="text-xs uppercase tracking-wide text-[#667085] mb-1">{label}</div>
      <pre className={`text-xs whitespace-pre-wrap break-words ${danger ? 'text-[#B42318]' : ''}`}>{value}</pre>
    </div>
  );
}

function toLocal(value) {
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return '-';
  return dt.toLocaleString();
}
