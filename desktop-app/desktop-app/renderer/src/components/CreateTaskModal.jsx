import { useState } from 'react';

export default function CreateTaskModal({ onSubmit, onClose }) {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!title.trim() || !description.trim()) return;

    setSubmitting(true);
    try {
      await onSubmit(title.trim(), description.trim());
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div
        className="absolute inset-0 bg-black/30"
        onClick={onClose}
      />

      <div className="relative w-full max-w-lg bg-white border border-[#E6E8EC] rounded-xl shadow-2xl">
        <div className="p-6">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-semibold">Create New Task</h2>
            <button
              onClick={onClose}
              className="text-[#667085] hover:text-[#101828] text-lg"
            >
              ✕
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-[#344054] mb-1.5">
                Task Title
              </label>
              <input
                id="task-title-input"
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g., Build API endpoint for CSV upload"
                className="w-full border border-[#D0D5DD] rounded-lg px-4 py-2.5 text-sm placeholder-[#98A2B3] focus:outline-none focus:ring-2 focus:ring-[#0B5FFF]/20"
                autoFocus
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-[#344054] mb-1.5">
                Description
              </label>
              <textarea
                id="task-description-input"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Describe what needs to be built. Be specific about requirements, tech stack, and expected behavior..."
                rows={5}
                className="w-full border border-[#D0D5DD] rounded-lg px-4 py-3 text-sm placeholder-[#98A2B3] focus:outline-none focus:ring-2 focus:ring-[#0B5FFF]/20 resize-none"
              />
            </div>

            <div className="bg-[#F9FAFB] rounded-lg p-3 border border-[#EAECF0]">
              <h4 className="text-xs font-medium text-[#667085] mb-2">Example tasks:</h4>
              <div className="space-y-1">
                {[
                  'Build a REST API endpoint for CSV file upload with validation',
                  'Create a Python script to parse JSON logs and generate summary reports',
                  'Implement a rate limiter middleware for Express.js',
                ].map((example, i) => (
                  <button
                    key={i}
                    type="button"
                    onClick={() => {
                      setTitle(example);
                      setDescription(example + '\n\nPlease implement this with proper error handling, input validation, and tests.');
                    }}
                    className="block w-full text-left text-xs text-[#667085] hover:text-[#175CD3] py-0.5 transition-colors"
                  >
                    → {example}
                  </button>
                ))}
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 text-sm text-[#667085] hover:text-[#344054] transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={!title.trim() || !description.trim() || submitting}
                className="px-5 py-2.5 bg-[#0B5FFF] hover:bg-[#0A54E8] disabled:bg-[#EAECF0] disabled:text-[#98A2B3] text-white text-sm font-medium rounded-lg transition-colors"
              >
                {submitting ? 'Creating...' : 'Create & Execute'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
