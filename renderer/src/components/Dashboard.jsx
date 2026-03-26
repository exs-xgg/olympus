export default function Dashboard({ tasks, kpis, onOpenInterventions }) {
  const recent = [...tasks]
    .sort((a, b) => new Date(b.updated_at || b.created_at) - new Date(a.updated_at || a.created_at))
    .slice(0, 8);

  const statusLabel = {
    queued: 'Queued',
    running: 'Running',
    waiting_for_human: 'Blocked (HITL)',
    completed: 'Completed',
    failed: 'Failed',
  };

  const statusClass = {
    queued: 'bg-[#F2F4F7] text-[#344054]',
    running: 'bg-[#EFF8FF] text-[#175CD3]',
    waiting_for_human: 'bg-[#FFFAEB] text-[#B54708]',
    completed: 'bg-[#ECFDF3] text-[#067647]',
    failed: 'bg-[#FEF3F2] text-[#B42318]',
  };

  return (
    <div className="h-full overflow-auto p-6 space-y-6">
      <div className="grid grid-cols-4 gap-4">
        <MetricCard label="Active Agents" value={kpis.activeAgents} hint="Online agents" />
        <MetricCard label="Tasks Running" value={kpis.running} hint="Across all pools" />
        <MetricCard label="HITL Queue" value={kpis.waiting} hint="Require review" emphasizeWarning />
        <MetricCard label="Success Rate" value={`${kpis.successRate}%`} hint="Last completed tasks" />
      </div>

      <div className="bg-white border border-[#E6E8EC] rounded-lg">
        <div className="px-4 py-3 border-b border-[#E6E8EC] flex items-center justify-between">
          <h2 className="font-semibold">Recent Activity</h2>
          <button onClick={onOpenInterventions} className="text-sm text-[#175CD3] hover:underline">View HITL Queue</button>
        </div>
        <table className="w-full text-sm">
          <thead className="text-left text-[#667085]">
            <tr>
              <th className="px-4 py-2 font-medium">Task ID</th>
              <th className="px-4 py-2 font-medium">Agent</th>
              <th className="px-4 py-2 font-medium">Description</th>
              <th className="px-4 py-2 font-medium">Status</th>
              <th className="px-4 py-2 font-medium">Updated</th>
            </tr>
          </thead>
          <tbody>
            {recent.map((task) => (
              <tr key={task.id} className="border-t border-[#F2F4F7]">
                <td className="px-4 py-2 font-mono text-xs">{task.id.slice(0, 10)}</td>
                <td className="px-4 py-2">{task.assigned_agent || 'Supervisor'}</td>
                <td className="px-4 py-2 max-w-[420px] truncate">{task.title}</td>
                <td className="px-4 py-2">
                  <span className={`px-2 py-1 rounded text-xs font-medium ${statusClass[task.status] || statusClass.queued}`}>
                    {statusLabel[task.status] || task.status}
                  </span>
                </td>
                <td className="px-4 py-2 text-[#667085]">{relativeTime(task.updated_at || task.created_at)}</td>
              </tr>
            ))}
            {recent.length === 0 && (
              <tr>
                <td className="px-4 py-8 text-center text-[#667085]" colSpan={5}>No task activity yet.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function MetricCard({ label, value, hint, emphasizeWarning = false }) {
  return (
    <div className={`bg-white border rounded-lg px-4 py-3 ${emphasizeWarning ? 'border-[#F79009]' : 'border-[#E6E8EC]'}`}>
      <div className="text-xs text-[#667085]">{label}</div>
      <div className="text-[32px] leading-none mt-2 font-semibold">{value}</div>
      <div className="text-xs mt-2 text-[#667085]">{hint}</div>
    </div>
  );
}

function relativeTime(value) {
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return '-';
  const sec = Math.floor((Date.now() - dt.getTime()) / 1000);
  if (sec < 60) return `${sec}s ago`;
  if (sec < 3600) return `${Math.floor(sec / 60)}m ago`;
  if (sec < 86400) return `${Math.floor(sec / 3600)}h ago`;
  return `${Math.floor(sec / 86400)}d ago`;
}
