'use client'
import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useRouter } from 'next/navigation'
import { apiClient } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
export default function Onboarding() {
  const [name, setName] = useState(''); const [code, setCode] = useState(''); const [error, setError] = useState(''); const [busy, setBusy] = useState(false)
  const client = useQueryClient(); const router = useRouter()
  async function submit(kind: 'create' | 'join') { setBusy(true); setError(''); try { await apiClient.request('/api/team/' + kind, { method: 'POST', body: JSON.stringify(kind === 'create' ? { name } : { code }) }); await client.invalidateQueries(); router.replace('/envelopes') } catch (e) { setError(e instanceof Error ? e.message : 'Unable to continue') } finally { setBusy(false) } }
  return <section className="mx-auto max-w-lg space-y-6 py-10"><h1 className="text-3xl font-semibold">Set up your organization</h1><label className="block">Organization name<Input value={name} onChange={e => setName(e.target.value)} /></label><Button disabled={busy || !name.trim()} onClick={() => void submit('create')}>Create organization</Button><hr /><label className="block">Invitation code<Input value={code} onChange={e => setCode(e.target.value.toUpperCase())} maxLength={6} /></label><Button variant="outline" disabled={busy || code.length !== 6} onClick={() => void submit('join')}>Join organization</Button>{error && <p role="alert">{error}</p>}</section>
}
