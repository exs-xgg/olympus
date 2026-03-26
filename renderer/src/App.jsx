import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useWebSocket } from './hooks/useWebSocket';
import { api } from './api';
import Dashboard from './components/Dashboard';
import TaskBoard from './components/TaskBoard';
import AgentInspector from './components/AgentInspector';
import InterventionPanel from './components/InterventionPanel';
import MCPIntegrations from './components/MCPIntegrations';
import AgentChat from './components/AgentChat';
import CreateTaskModal from './components/CreateTaskModal';
import TaskProgressModal from './components/TaskProgressModal';

const NAV_ITEMS = [
  { id: 'dashboard', label: 'Dashboard', icon: '▦' },
  { id: 'kanban', label: 'Task Kanban', icon: '▣' },
  { id: 'inspector', label: 'Agent Inspector', icon: '⚙' },
  { id: 'interventions', label: 'Intervention Panel', icon: '●' },
  { id: 'mcp', label: 'MCP Integrations', icon: '⌁' },
  { id: 'chat', label: 'Agent Chat', icon: '✦' },
];

export default function App() {
  const [activeView, setActiveView] = useState('dashboard');
  const [tasks, setTasks] = useState([]);
  const [agents, setAgents] = useState([]);
  const [logs, setLogs] = useState([]);
  const [search, setSearch] = useState('');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [selectedTask, setSelectedTask] = useState(null);
  const lastTaskStatusRef = useRef({});
  const notifiedEventKeysRef = useRef(new Set());
  const taskTitleRef = useRef({});

  const maybeNotify = useCallback((title, body, dedupeKey) => {
    if (!window.electronAPI?.showNotification || !dedupeKey) return;
    if (notifiedEventKeysRef.current.has(dedupeKey)) return;
    notifiedEventKeysRef.current.add(dedupeKey);
    window.electronAPI.showNotification(title, body);
  }, []);

  const loadTasks = useCallback(async () => {
    try {
      const data = await api.listTasks();
      setTasks(data);
    } catch (err) {
      console.error('Failed to load tasks:', err);
    }
  }, []);

  const loadAgents = useCallback(async () => {
    try {
      const data = await api.getAgentsStatus();
      setAgents(data);
    } catch (err) {
      console.error('Failed to load agents:', err);
    }
  }, []);

  useEffect(() => {
    loadTasks();
    loadAgents();
  }, [loadTasks, loadAgents]);

  const handleWSEvent = useCallback((event) => {
    switch (event.type) {
      case 'task_update':
        if (event.data?.id && event.data?.status) {
          const taskId = event.data.id;
          const nextStatus = event.data.status;
          const previousStatus = lastTaskStatusRef.current[taskId];
          if (event.data.title) {
            taskTitleRef.current[taskId] = event.data.title;
          }
          const title = taskTitleRef.current[taskId] || event.data.title || `Task ${taskId.slice(0, 8)}`;

          if (nextStatus === 'queued' && !previousStatus) {
            maybeNotify('Task Created', title, `${taskId}:status:queued`);
          } else if (nextStatus === 'completed' && previousStatus !== 'completed') {
            maybeNotify('Task Finished', title, `${taskId}:status:completed`);
          } else if (nextStatus === 'waiting_for_human' && previousStatus !== 'waiting_for_human') {
            maybeNotify(
              'Human Review Required',
              event.data.human_input_request?.substring(0, 100) || title,
              `${taskId}:status:waiting_for_human`
            );
          }

          lastTaskStatusRef.current[taskId] = nextStatus;
        }

        setTasks((prev) => {
          const idx = prev.findIndex((t) => t.id === event.data.id);
          if (idx >= 0) {
            const updated = [...prev];
            updated[idx] = { ...updated[idx], ...event.data };
            return updated;
          }
          loadTasks();
          return prev;
        });
        break;
      case 'agent_update':
        setAgents((prev) => {
          const idx = prev.findIndex((a) => a.name === event.data.name);
          if (idx >= 0) {
            const updated = [...prev];
            updated[idx] = { ...updated[idx], ...event.data };
            return updated;
          }
          return prev;
        });
        break;
      case 'log':
        setLogs((prev) => [...prev.slice(-199), { ...event.data, id: Date.now() }]);
        break;
      case 'hitl_request':
        maybeNotify(
          'Human Review Required',
          event.data.question?.substring(0, 100) || 'An agent needs your input',
          `${event.data.task_id}:status:waiting_for_human`
        );
        setActiveView('interventions');
        break;
      default:
        break;
    }
  }, [loadTasks, maybeNotify]);

  const { connected } = useWebSocket(handleWSEvent);

  const handleCreateTask = async (title, description) => {
    try {
      const task = await api.createTask(title, description);
      taskTitleRef.current[task.id] = task.title || title;
      setTasks((prev) => [task, ...prev]);
      setShowCreateModal(false);
    } catch (err) {
      alert(`Failed to create task: ${err.message}`);
    }
  };

  const handleResumeTask = async (taskId, humanInput) => {
    try {
      await api.resumeTask(taskId, humanInput);
    } catch (err) {
      alert(`Failed to resume task: ${err.message}`);
    }
  };

  const handleRejectTask = async (taskId, reason) => {
    try {
      await api.rejectTask(taskId, reason || 'Rejected by operator');
    } catch (err) {
      alert(`Failed to reject task: ${err.message}`);
    }
  };

  const kpis = useMemo(() => {
    const running = tasks.filter((t) => t.status === 'running').length;
    const waiting = tasks.filter((t) => t.status === 'waiting_for_human').length;
    const done = tasks.filter((t) => t.status === 'completed').length;
    const failed = tasks.filter((t) => t.status === 'failed').length;
    const successRate = done + failed === 0 ? 100 : (done / (done + failed)) * 100;
    return { activeAgents: agents.length, running, waiting, successRate: successRate.toFixed(1) };
  }, [tasks, agents]);

  const filteredTasks = useMemo(() => {
    const term = search.trim().toLowerCase();
    if (!term) return tasks;
    return tasks.filter((task) =>
      [task.id, task.title, task.description, task.assigned_agent].filter(Boolean).join(' ').toLowerCase().includes(term)
    );
  }, [tasks, search]);
  const selectedTaskLive = useMemo(() => {
    if (!selectedTask) return null;
    return tasks.find((t) => t.id === selectedTask.id) || selectedTask;
  }, [tasks, selectedTask]);

  return (
    <div className="h-screen bg-[#F7F8FA] text-[#101828] overflow-hidden flex">
      <aside className="w-[220px] border-r border-[#E6E8EC] bg-white flex flex-col">
        <div className="px-6 py-5 border-b border-[#E6E8EC]">
          <div className="text-[18px] font-semibold">Olympus</div>
          <div className="text-xs text-[#667085]">Enterprise</div>
        </div>
        <nav className="p-3 space-y-1">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.id}
              onClick={() => setActiveView(item.id)}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-md text-sm text-left transition ${
                activeView === item.id ? 'bg-[#F2F4F7] text-[#101828] font-medium' : 'text-[#344054] hover:bg-[#F9FAFB]'
              }`}
            >
              <span className="w-4 text-center">{item.icon}</span>
              <span>{item.label}</span>
              {item.id === 'interventions' && kpis.waiting > 0 && (
                <span className="ml-auto text-xs bg-[#F79009] text-white px-1.5 py-0.5 rounded">{kpis.waiting}</span>
              )}
            </button>
          ))}
        </nav>
        <div className="mt-auto p-4 border-t border-[#E6E8EC] text-sm">
          <div className="font-medium">John Doe</div>
          <div className="text-[#667085] text-xs">Admin</div>
        </div>
      </aside>

      <div className="flex-1 min-w-0 flex flex-col">
        <header className="h-[64px] bg-white border-b border-[#E6E8EC] px-6 flex items-center justify-between">
          <div className="text-sm text-[#667085]">
            Olympus / <span className="text-[#101828] font-medium">{NAV_ITEMS.find((i) => i.id === activeView)?.label}</span>
          </div>
          <div className="flex items-center gap-3">
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search tasks, agents..."
              className="w-[300px] border border-[#D0D5DD] rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#0B5FFF]/20"
            />
            <div className={`text-xs px-2 py-1 rounded-full border ${
              connected ? 'text-[#12B76A] border-[#A6F4C5] bg-[#ECFDF3]' : 'text-[#F04438] border-[#FECDCA] bg-[#FEF3F2]'
            }`}>
              {connected ? 'Live' : 'Offline'}
            </div>
            <button onClick={() => setShowCreateModal(true)} className="px-4 py-2 bg-[#0B5FFF] hover:bg-[#0A54E8] text-white text-sm rounded-md">
              New Task
            </button>
          </div>
        </header>

        <main className="flex-1 overflow-hidden">
          {activeView === 'dashboard' && <Dashboard tasks={filteredTasks} kpis={kpis} onOpenInterventions={() => setActiveView('interventions')} />}
          {activeView === 'kanban' && (
            <TaskBoard
              tasks={filteredTasks}
              onRefresh={loadTasks}
              onOpenInterventions={() => setActiveView('interventions')}
              onViewTaskProgress={(task) => setSelectedTask(task)}
            />
          )}
          {activeView === 'inspector' && <AgentInspector agents={agents} logs={logs} tasks={filteredTasks} onRefresh={loadAgents} />}
          {activeView === 'interventions' && (
            <InterventionPanel
              tasks={filteredTasks.filter((t) => t.status === 'waiting_for_human')}
              onResume={handleResumeTask}
              onReject={handleRejectTask}
            />
          )}
          {activeView === 'mcp' && <MCPIntegrations />}
          {activeView === 'chat' && <AgentChat agents={agents} />}
        </main>
      </div>

      {showCreateModal && <CreateTaskModal onSubmit={handleCreateTask} onClose={() => setShowCreateModal(false)} />}
      {selectedTaskLive && <TaskProgressModal task={selectedTaskLive} onClose={() => setSelectedTask(null)} />}
    </div>
  );
}
