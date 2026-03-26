import { useEffect, useState } from 'react';
import { api } from '../api';

export default function MCPIntegrations() {
  const [servers, setServers] = useState([]);
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState({
    name: '',
    transport: 'stdio',
    command: 'npx',
    args: '',
    env: [{ key: '', value: '' }],
  });

  useEffect(() => {
    api.listMcpServers().then(setServers).catch(() => setServers([]));
  }, []);

  const onSave = async () => {
    if (!form.name.trim() || !form.command.trim()) return;
    const payload = {
      ...form,
      env: form.env.filter((e) => e.key.trim()),
    };
    const created = await api.createMcpServer(payload);
    setServers((prev) => [created, ...prev]);
    setShowModal(false);
    setForm({ name: '', transport: 'stdio', command: 'npx', args: '', env: [{ key: '', value: '' }] });
  };

  return (
    <div className="h-full p-6 overflow-auto">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-xl font-semibold">MCP Integrations</h2>
          <p className="text-sm text-[#667085]">Manage connector servers and runtime credentials.</p>
        </div>
        <button onClick={() => setShowModal(true)} className="px-4 py-2 bg-[#0B5FFF] text-white rounded-md text-sm">Add Server</button>
      </div>

      <div className="bg-white border border-[#E6E8EC] rounded-lg">
        <table className="w-full text-sm">
          <thead className="text-left text-[#667085]">
            <tr>
              <th className="px-4 py-3 font-medium">Name</th>
              <th className="px-4 py-3 font-medium">Transport</th>
              <th className="px-4 py-3 font-medium">Command</th>
              <th className="px-4 py-3 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {servers.map((srv) => (
              <tr key={srv.id} className="border-t border-[#F2F4F7]">
                <td className="px-4 py-3">{srv.name}</td>
                <td className="px-4 py-3">{srv.transport}</td>
                <td className="px-4 py-3 font-mono text-xs">{srv.command}</td>
                <td className="px-4 py-3"><span className="px-2 py-1 rounded bg-[#ECFDF3] text-[#067647] text-xs">Configured</span></td>
              </tr>
            ))}
            {servers.length === 0 && (
              <tr><td className="px-4 py-10 text-center text-[#667085]" colSpan={4}>No MCP servers configured.</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/30" onClick={() => setShowModal(false)} />
          <div className="relative w-[720px] bg-white rounded-lg border border-[#E6E8EC] shadow-2xl">
            <div className="px-5 py-4 border-b border-[#E6E8EC] flex justify-between">
              <h3 className="font-semibold text-lg">Add MCP Server</h3>
              <button onClick={() => setShowModal(false)} className="text-[#667085]">✕</button>
            </div>
            <div className="p-5 space-y-4">
              <Field label="Name">
                <input className="input" value={form.name} onChange={(e) => setForm((s) => ({ ...s, name: e.target.value }))} placeholder="e.g. postgres-db" />
              </Field>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Transport">
                  <select className="input" value={form.transport} onChange={(e) => setForm((s) => ({ ...s, transport: e.target.value }))}>
                    <option value="stdio">stdio</option>
                    <option value="sse">sse</option>
                    <option value="http">http</option>
                  </select>
                </Field>
                <Field label="Command">
                  <input className="input" value={form.command} onChange={(e) => setForm((s) => ({ ...s, command: e.target.value }))} />
                </Field>
              </div>
              <Field label="Arguments">
                <input className="input" value={form.args} onChange={(e) => setForm((s) => ({ ...s, args: e.target.value }))} placeholder="-y @modelcontextprotocol/server-postgres" />
              </Field>
              <div>
                <label className="block text-xs font-medium uppercase text-[#667085] mb-2">Environment Variables</label>
                <div className="space-y-2">
                  {form.env.map((row, idx) => (
                    <div className="grid grid-cols-[1fr_1fr_auto] gap-2" key={idx}>
                      <input className="input" placeholder="Key" value={row.key} onChange={(e) => setForm((s) => {
                        const env = [...s.env];
                        env[idx] = { ...env[idx], key: e.target.value };
                        return { ...s, env };
                      })} />
                      <input className="input" placeholder="Value" type="password" value={row.value} onChange={(e) => setForm((s) => {
                        const env = [...s.env];
                        env[idx] = { ...env[idx], value: e.target.value };
                        return { ...s, env };
                      })} />
                      <button className="px-3 border border-[#D0D5DD] rounded-md" onClick={() => setForm((s) => ({ ...s, env: s.env.filter((_, i) => i !== idx) }))}>🗑</button>
                    </div>
                  ))}
                </div>
                <button className="text-sm text-[#175CD3] mt-2" onClick={() => setForm((s) => ({ ...s, env: [...s.env, { key: '', value: '' }] }))}>+ Add Variable</button>
              </div>
            </div>
            <div className="px-5 py-4 border-t border-[#E6E8EC] flex justify-end gap-2">
              <button onClick={() => setShowModal(false)} className="px-4 py-2 border border-[#D0D5DD] rounded-md">Cancel</button>
              <button onClick={onSave} className="px-4 py-2 bg-[#0B5FFF] text-white rounded-md">Save Configuration</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Field({ label, children }) {
  return (
    <div>
      <label className="block text-xs font-medium uppercase text-[#667085] mb-1.5">{label}</label>
      {children}
    </div>
  );
}
