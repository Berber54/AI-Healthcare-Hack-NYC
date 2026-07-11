import { useState, type FormEvent } from 'react'
import { submitInput } from './api'

type Sent = { label: string; kind: 'text' | 'file' }

export default function InputBar({ callSid }: { callSid: string }) {
  const [text, setText] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [status, setStatus] = useState<'idle' | 'sending' | 'error'>('idle')
  const [sent, setSent] = useState<Sent[]>([])

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!text.trim() && !file) return
    setStatus('sending')
    try {
      await submitInput(callSid, text, file)
      setSent((prev) => [
        ...prev,
        ...(text.trim() ? [{ label: text.trim(), kind: 'text' as const }] : []),
        ...(file ? [{ label: file.name, kind: 'file' as const }] : []),
      ])
      setText('')
      setFile(null)
      setStatus('idle')
    } catch {
      setStatus('error')
    }
  }

  return (
    <div className="card">
      <span className="badge">On call</span>
      <h1>Share info with your call</h1>
      <p className="muted">
        Type or upload anything the agent should read — insurance member ID, ID photo,
        insurance card PDF. It shows up on the call immediately.
      </p>

      <form onSubmit={handleSubmit} className="form">
        <textarea
          rows={4}
          placeholder="e.g. insurance member ID: ABC123456"
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
        <label className="file-input">
          {file ? file.name : 'Attach PDF or photo'}
          <input
            type="file"
            accept=".pdf,.png,.jpg,.jpeg"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
        </label>
        <button type="submit" className="button-primary" disabled={status === 'sending'}>
          {status === 'sending' ? 'Sending…' : 'Send to agent'}
        </button>
        {status === 'error' && <p className="error">Failed to send. Try again.</p>}
      </form>

      {sent.length > 0 && (
        <ul className="sent-list">
          {sent.map((item, i) => (
            <li key={i}>
              <span className="dot" />
              {item.kind === 'file' ? `File: ${item.label}` : item.label}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
