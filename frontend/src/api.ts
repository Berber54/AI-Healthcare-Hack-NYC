const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'

export async function lookupCallSid(phone: string): Promise<string> {
  const form = new FormData()
  form.set('phone', phone)
  const res = await fetch(`${API_BASE}/input/lookup`, { method: 'POST', body: form })
  if (!res.ok) throw new Error('No active call found for that number.')
  const data = await res.json()
  return data.call_sid as string
}

export async function submitInput(callSid: string, text: string, file: File | null): Promise<void> {
  const form = new FormData()
  if (text.trim()) form.set('text', text.trim())
  if (file) form.set('file', file)
  const res = await fetch(`${API_BASE}/input/${callSid}`, { method: 'POST', body: form })
  if (!res.ok) throw new Error('Failed to send. Try again.')
}
