/**
 * Shared TypeScript type definitions — mirrors Pydantic schemas.
 * For compile-time safety in the renderer.
 */

export type TaskStatus = 'queued' | 'running' | 'waiting_for_human' | 'completed' | 'failed';

export interface Task {
  id: string;
  title: string;
  description: string;
  status: TaskStatus;
  assigned_agent: string | null;
  result: string | null;
  error: string | null;
  human_input_request: string | null;
  human_input_response: string | null;
  thread_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface TaskCreate {
  title: string;
  description: string;
}

export interface TaskResumeRequest {
  human_input: string;
}

export interface AgentStatus {
  name: string;
  role: string;
  status: 'idle' | 'busy' | 'error';
  capabilities: string[];
  tools: string[];
  current_task_id: string | null;
}

export interface ActionLog {
  id: string;
  task_id: string;
  agent_name: string | null;
  action: string;
  detail: string | null;
  timestamp: string;
}

export interface WSEvent {
  type: 'task_update' | 'agent_update' | 'log' | 'hitl_request';
  data: Record<string, unknown>;
}

export interface ElectronAPI {
  runCommand: (command: string, cwd?: string) => Promise<{
    success: boolean;
    stdout: string;
    stderr: string;
    exitCode: number;
    error: string | null;
  }>;
  readFile: (filePath: string) => Promise<{ success: boolean; content?: string; error?: string }>;
  writeFile: (filePath: string, content: string) => Promise<{ success: boolean; error?: string }>;
  showNotification: (title: string, body: string) => Promise<boolean>;
  onNotification: (callback: (data: unknown) => void) => () => void;
}

declare global {
  interface Window {
    electronAPI?: ElectronAPI;
  }
}
