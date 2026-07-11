import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { lookupCallSid } from './api'

export default function PhoneLookup() {
  const [phone, setPhone] = useState('')
  const [error, setError] = useState('')
  const navigate = useNavigate()

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    try {
      const callSid = await lookupCallSid(phone.trim())
      navigate(`/call/${callSid}`)
    } catch {
      setError('No active call found for that number.')
    }
  }

  return (
    <div className="card">
      <h1>Find your call</h1>
      <p className="muted">
        Didn't get a link? Enter the phone number you're calling from.
      </p>
      <form onSubmit={handleSubmit} className="form">
        <input
          type="tel"
          placeholder="+1 555 123 4567"
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
        />
        <button type="submit" className="button-primary">
          Find my call
        </button>
        {error && <p className="error">{error}</p>}
      </form>
    </div>
  )
}
