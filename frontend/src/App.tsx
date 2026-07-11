import { BrowserRouter, Routes, Route, useParams } from 'react-router-dom'
import InputBar from './InputBar'
import PhoneLookup from './PhoneLookup'
import './App.css'

function CallRoute() {
  const { callSid } = useParams()
  if (!callSid) return null
  return <InputBar callSid={callSid} />
}

function App() {
  return (
    <BrowserRouter>
      <main className="page">
        <Routes>
          <Route path="/" element={<PhoneLookup />} />
          <Route path="/call/:callSid" element={<CallRoute />} />
        </Routes>
      </main>
    </BrowserRouter>
  )
}

export default App
