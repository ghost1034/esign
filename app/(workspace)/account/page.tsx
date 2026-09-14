'use client'
import Link from 'next/link'
import { useState } from 'react'
import { multiFactor, sendPasswordResetEmail, updateProfile } from 'firebase/auth'
import { useAuth } from '@/contexts/AuthContext'
import { auth, isLocalDevelopment } from '@/lib/firebase'
import { apiClient } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
export default function Account() {
  const { user, refreshCurrentUser, sendCurrentUserEmailVerification } = useAuth(); const [name, setName] = useState(user?.displayName || ''); const [message, setMessage] = useState('')
  const factors = user && !isLocalDevelopment ? multiFactor(user).enrolledFactors : []
  async function action(fn: () => Promise<unknown>) { try { await fn(); await refreshCurrentUser(); setMessage('Saved. For security-sensitive changes, sign in again if prompted.') } catch (e) { setMessage(e instanceof Error ? e.message : 'Unable to update account') } }
  return <section className="max-w-xl space-y-6"><h1 className="text-3xl font-semibold">Account</h1><p>{user?.email}</p><label className="block">Display name<Input value={name} onChange={e => setName(e.target.value)} /></label><Button onClick={() => void action(async () => { if (user && !isLocalDevelopment) await updateProfile(user, { displayName: name }); await apiClient.request('/api/account', { method: 'PUT', body: JSON.stringify({ display_name: name }) }) })}>Save profile</Button><div className="flex gap-4"><Button variant="outline" onClick={() => void action(sendCurrentUserEmailVerification)}>Verify email</Button><Button variant="outline" disabled={isLocalDevelopment} onClick={() => void action(() => sendPasswordResetEmail(auth, user!.email!))}>Reset password</Button></div><h2 className="text-xl font-semibold">Optional phone MFA</h2><p>Require a phone verification code when you sign in. Guest recipients can still sign without an account.</p>{factors.length ? factors.map(f => <Button key={f.uid} variant="outline" onClick={() => void action(() => multiFactor(user!).unenroll(f.uid))}>Remove phone MFA</Button>) : <Button asChild disabled={isLocalDevelopment}><Link href="/complete-signup?redirectTo=%2Faccount">Add phone MFA</Link></Button>}{isLocalDevelopment && <p>Local development identity is enabled. Connect an independent Firebase project to test phone MFA.</p>}{message && <p role="status">{message}</p>}</section>
}
