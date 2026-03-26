const COLUMNS = [
  { id: 'queued', label: 'QUEUED', color: 'border-[#E6E8EC]' },
  { id: 'running', label: 'RUNNING', color: 'border-[#2E90FA]' },
  { id: 'waiting_for_human', label: 'BLOCKED / HITL', color: 'border-[#F79009]' },
  { id: 'completed', label: 'DONE', color: 'border-[#12B76A]' },
];

export default function TaskBoard({ tasks, onRefresh, onOpenInterventions, onViewTaskProgress }) {
  return (
    <div className="h-full flex flex-col">
      <div className="px-6 py-4 border-b border-[#E6E8EC] bg-white flex justify-between">
        <div className="text-sm text-[#667085]">Task Kanban</div>
        <button onClick={onRefresh} className="text-sm text-[#175CD3]">Refresh</button>
      </div>
      <div className="flex-1 overflow-x-auto p-5 flex gap-4">
        {COLUMNS.map((col) => {
          const colTasks = tasks.filter((task) => task.status === col.id);
          return (
            <div key={col.id} className={`w-[320px] shrink-0 bg-white rounded-lg border ${col.color} flex flex-col`}>
              <div className="px-4 py-3 border-b border-[#E6E8EC] flex justify-between">
                <span className="text-xs font-semibold tracking-wide">{col.label}</span>
                <span className="text-xs bg-[#F2F4F7] px-2 py-0.5 rounded">{colTasks.length}</span>
              </div>
              <div className="p-3 space-y-3 overflow-y-auto">
                {colTasks.map((task) => (
                  <article key={task.id} className="border border-[#E6E8EC] rounded-md p-3">
                    <div className="flex justify-between text-xs text-[#667085]">
                      <span>{task.id.slice(0, 8)}</span>
                      <span>{relativeTime(task.updated_at || task.created_at)}</span>
                    </div>
                    <h4 className="mt-2 text-[20px] leading-6 font-semibold">{task.title}</h4>
                    <div className="text-sm mt-2 text-[#667085]">Agent: {task.assigned_agent || 'Unassigned'}</div>
                    {task.status === 'running' && (
                      <div className="mt-2 text-sm text-[#175CD3]">In Progress</div>
                    )}
                    {task.status === 'waiting_for_human' && (
                      <button
                        onClick={onOpenInterventions}
                        className="mt-3 w-full border border-[#F79009] bg-[#FFFAEB] text-[#B54708] text-sm py-2 rounded"
                      >
                        Review Required
                      </button>
                    )}
                    <button
                      onClick={() => onViewTaskProgress?.(task)}
                      className="mt-2 w-full border border-[#D0D5DD] bg-white text-[#344054] text-sm py-2 rounded hover:bg-[#F9FAFB]"
                    >
                      View Progress
                    </button>
                  </article>
                ))}
                {colTasks.length === 0 && <div className="text-center text-sm text-[#98A2B3] py-8">No tasks</div>}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function relativeTime(value) {
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return '-';
  const sec = Math.floor((Date.now() - dt.getTime()) / 1000);
  if (sec < 60) return `${sec}s`;
  if (sec < 3600) return `${Math.floor(sec / 60)}m`;
  return `${Math.floor(sec / 3600)}h`;
}
