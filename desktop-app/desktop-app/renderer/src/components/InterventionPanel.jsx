import { useEffect, useMemo, useState } from 'react';
import { api } from '../api';

export default function InterventionPanel({ tasks, onResume, onReject }) {
  const [selected, setSelected] = useState(null);
  const [filter, setFilter] = useState('');
  const [input, setInput] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [taskLogs, setTaskLogs] = useState([]);
  const [loadingLogs, setLoadingLogs] = useState(false);

  const orderedTasks = useMemo(() => {
    return [...tasks].sort(
      (a, b) => new Date(b.updated_at || b.created_at).getTime() - new Date(a.updated_at || a.created_at).getTime()
    );
  }, [tasks]);

  const filteredTasks = useMemo(() => {
    const term = filter.trim().toLowerCase();
    if (!term) return orderedTasks;
    return orderedTasks.filter((task) =>
      [task.id, task.title, task.assigned_agent, task.human_input_request].filter(Boolean).join(' ').toLowerCase().includes(term)
    );
  }, [orderedTasks, filter]);

  useEffect(() => {
    if (!orderedTasks.length) {
      setSelected(null);
      return;
    }
    if (!selected || !orderedTasks.some((task) => task.id === selected)) {
      setSelected(orderedTasks[0].id);
    }
  }, [orderedTasks, selected]);

  const current = orderedTasks.find((t) => t.id === selected) || orderedTasks[0] || null;

  useEffect(() => {
    if (!current?.id) {
      setTaskLogs([]);
      return;
    }
    let cancelled = false;
    setLoadingLogs(true);
    api.getTaskLogs(current.id)
      .then((logs) => {
        if (!cancelled) setTaskLogs(logs || []);
      })
      .catch(() => {
        if (!cancelled) setTaskLogs([]);
      })
      .finally(() => {
        if (!cancelled) setLoadingLogs(false);
      });

    return () => {
      cancelled = true;
    };
  }, [current?.id]);

  const latestOutput = useMemo(() => {
    const latestAgentOutput = [...taskLogs].reverse().find((log) => log.action === 'agent_output' && log.detail);
    if (latestAgentOutput) return latestAgentOutput.detail;
    const latestMeaningful = [...taskLogs].reverse().find((log) => log.detail);
    return latestMeaningful?.detail || current?.result || '';
  }, [taskLogs, current?.result]);

  const approvalChecklist = useMemo(() => {
    if (!current) return [];
    const request = current.human_input_request || 'Agent requested human input.';
    const output = latestOutput || 'No recent output captured yet.';
    const lowerOutput = output.toLowerCase();
    const needsRiskReview = /(delete|drop|overwrite|revoke|shutdown|terminate|production|payment|billing|credential|secret|token)/.test(lowerOutput);
    const needsClarification = /(unknown|unsure|cannot|missing|need more|insufficient)/.test(lowerOutput);
    return [
      `Confirm your answer resolves the current blocker: "${request}"`,
      needsRiskReview
        ? 'Output contains high-impact terms; verify scope and approvals before resume.'
        : 'No obvious high-impact keywords detected in latest output.',
      needsClarification
        ? 'Agent signaled uncertainty; provide exact constraints or missing context.'
        : 'Agent appears ready to continue once you provide final direction.',
    ];
  }, [current, latestOutput]);

  const suggestedResponses = [
    'Approved. Proceed exactly as proposed and report completion status.',
    'Approved with limits: do not modify production data; provide a dry-run summary first.',
    'Needs changes: revise plan with explicit rollback steps and then request approval again.',
  ];

  const approve = async () => {
    if (!current || !input.trim()) return;
    setSubmitting(true);
    try {
      await onResume(current.id, input.trim());
      setInput('');
    } finally {
      setSubmitting(false);
    }
  };

  const reject = async () => {
    if (!current) return;
    await onReject(current.id, input.trim() || 'Rejected by operator');
    setInput('');
  };

  if (!current) {
    return (
      <div className="h-full flex items-center justify-center text-[#667085]">No pending interventions.</div>
    );
  }

  return (
    <div className="h-full flex">
      <aside className="w-[320px] border-r border-[#E6E8EC] bg-white p-4">
        <div className="text-lg font-semibold">Intervention Panel</div>
        <div className="mt-1 text-xs text-[#B54708] bg-[#FFFAEB] inline-flex px-2 py-1 rounded">{tasks.length} Pending</div>
        <input
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="input mt-4"
          placeholder="Filter agents, tasks..."
        />
        <div className="mt-4 space-y-2">
          {filteredTasks.map((task) => (
            <button
              key={task.id}
              onClick={() => setSelected(task.id)}
              className={`w-full text-left border rounded-md p-3 ${
                task.id === current.id ? 'border-[#175CD3] bg-[#EFF8FF]' : 'border-[#E6E8EC] bg-white'
              }`}
            >
              <div className="text-xs text-[#667085]">{task.id.slice(0, 10)}</div>
              <div className="font-medium mt-1">{task.title}</div>
              <div className="text-sm text-[#667085] mt-1">{task.assigned_agent || 'Supervisor'}</div>
            </button>
          ))}
          {filteredTasks.length === 0 && (
            <div className="text-sm text-[#98A2B3] py-6 text-center">No tasks match this filter.</div>
          )}
        </div>
      </aside>

      <section className="flex-1 p-6 overflow-auto space-y-4">
        <div className="flex justify-between items-start">
          <div>
            <div className="text-xs text-[#B54708] bg-[#FFFAEB] inline-flex px-2 py-1 rounded">Review Required</div>
            <h2 className="text-[36px] leading-[40px] mt-2 font-semibold">{current.title}</h2>
            <div className="text-sm text-[#667085] mt-2">
              {current.assigned_agent || 'Supervisor'} • waiting for operator input
            </div>
          </div>
          <div className="flex gap-2">
            <button onClick={reject} className="px-4 py-2 border border-[#D0D5DD] rounded-md">Reject</button>
            <button
              onClick={approve}
              disabled={submitting || !input.trim()}
              className="px-4 py-2 bg-[#0B5FFF] text-white rounded-md disabled:opacity-50"
            >
              Approve & Resume Task
            </button>
          </div>
        </div>

        <Card title="What Needs Your Decision">
          <p className="text-sm">
            {current.human_input_request || 'The agent requires human validation before applying this operation.'}
          </p>
        </Card>

        <Card title="Latest Output Snapshot">
          {loadingLogs ? (
            <div className="text-sm text-[#667085]">Loading latest output...</div>
          ) : latestOutput ? (
            <pre className="bg-[#0F172A] text-[#E5E7EB] rounded p-3 text-sm font-mono overflow-auto whitespace-pre-wrap">
              {latestOutput}
            </pre>
          ) : (
            <div className="text-sm text-[#667085]">No output yet. Provide instruction based on the request above.</div>
          )}
        </Card>

        <Card title="Approval Checklist">
          <ul className="space-y-2 text-sm">
            {approvalChecklist.map((item) => (
              <li key={item} className="flex gap-2">
                <span className="text-[#175CD3]">•</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </Card>

        <Card title="Actionable Response">
          <div className="flex flex-wrap gap-2 mb-3">
            {suggestedResponses.map((value) => (
              <button
                key={value}
                type="button"
                onClick={() => setInput(value)}
                className="px-3 py-1.5 border border-[#D0D5DD] rounded-md text-xs bg-white hover:bg-[#F9FAFB]"
              >
                Use template
              </button>
            ))}
          </div>
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            rows={4}
            placeholder="Provide additional instructions or corrections before approval..."
            className="w-full border border-[#D0D5DD] rounded-md p-3 text-sm focus:outline-none focus:ring-2 focus:ring-[#0B5FFF]/20"
          />
          <div className="mt-2 text-xs text-[#667085]">
            Add your approval constraints or correction, then click <span className="font-medium">Approve & Resume Task</span>.
          </div>
        </Card>
      </section>
    </div>
  );
}

function Card({ title, children }) {
  return (
    <div className="bg-white border border-[#E6E8EC] rounded-lg">
      <div className="px-4 py-3 border-b border-[#E6E8EC] font-medium">{title}</div>
      <div className="p-4">{children}</div>
    </div>
  );
}
