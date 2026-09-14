'use client'
import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useAuth } from '@/contexts/AuthContext'
import { useTeam } from '@/hooks/useTeam'
import { apiClient } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
export default function Team() {
  const query = useTeam(); const client = useQueryClient(); const { user } = useAuth(); const [error, setError] = useState(''); const [name, setName] = useState(''); const [successor, setSuccessor] = useState('')
  const admin = query.data?.members.find(m => m.user_id === user?.uid)?.role === 'admin'
  async function change(path: string, method: string, body?: unknown) { try { await apiClient.request('/api/team' + path, { method, ...(body ? { body: JSON.stringify(body) } : {}) }); setError(''); await client.invalidateQueries() } catch (e) { setError(e instanceof Error ? e.message : 'Unable to save') } }
  return <section className="space-y-6"><h1 className="text-3xl font-semibold">{query.data?.firm.name || 'Team'}</h1>{admin && <><label>Organization name<Input value={name} onChange={e => setName(e.target.value)} /></label><Button disabled={!name.trim()} onClick={() => void change('', 'PUT', { name })}>Rename</Button><p>Invitation code: <strong>{query.data?.invite_code}</strong></p><Button onClick={() => void change('/invite-code', 'POST')}>Replace invitation code</Button><label className="block">Custody successor when removing a member<select className="ml-3 rounded border p-2" value={successor} onChange={e => setSuccessor(e.target.value)}><option value="">Select a member</option>{query.data?.members.map(m => <option key={m.user_id} value={m.user_id}>{m.email}</option>)}</select></label></>}{query.data?.members.map(m => <div key={m.user_id} className="flex flex-wrap items-center gap-4 rounded border border-border p-4"><span className="grow">{m.display_name || m.email} — {m.role}</span>{admin && <><Button variant="outline" onClick={() => void change('/members/' + encodeURIComponent(m.user_id), 'PUT', { role: m.role === 'admin' ? 'member' : 'admin' })}>{m.role === 'admin' ? 'Make member' : 'Make administrator'}</Button><Button variant="outline" onClick={() => void change('/members/' + encodeURIComponent(m.user_id) + (successor ? '?successor_user_id=' + encodeURIComponent(successor) : ''), 'DELETE')}>Remove member</Button></>}</div>)}{error && <p role="alert">{error}</p>}</section>
}
