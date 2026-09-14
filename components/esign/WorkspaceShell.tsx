'use client'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/lib/api'
import { useAuth } from '@/contexts/AuthContext'
import AuthGuard from '@/components/auth/AuthGuard'
import { EsignWorkspaceNav } from './EsignWorkspaceNav'
import { EsignRouteGuard } from './EsignRouteGuard'
export function WorkspaceShell({ children }: { children: React.ReactNode }) {
  const { user, signOut } = useAuth(); const router = useRouter(); const path = usePathname()
  const status = useQuery({ queryKey: ['team-onboarding', user?.uid], queryFn: () => apiClient.getTeamOnboardingStatus(), enabled: !!user, retry: false })
  const needsTeam = path !== '/onboarding' && path !== '/account'
  useEffect(() => { if (needsTeam && status.data?.needs_onboarding) router.replace('/onboarding') }, [needsTeam, status.data, router])
  return <AuthGuard><header className="flex flex-wrap items-center gap-6 border-b border-border px-6 py-4"><Link className="text-xl font-semibold" href="/envelopes">esign</Link><Link href="/team">Team</Link><Link href="/account">Account</Link><button className="ml-auto" onClick={() => void signOut()}>Sign out</button></header><div className="mx-auto max-w-screen-2xl p-4 sm:p-8">{needsTeam && status.isError ? <p role="alert">Unable to load your organization. <button onClick={() => void status.refetch()}>Retry</button></p> : needsTeam && (!status.data || status.data.needs_onboarding) ? <p>Loading your workspace…</p> : !needsTeam ? children : <><EsignWorkspaceNav /><EsignRouteGuard>{children}</EsignRouteGuard></>}</div></AuthGuard>
}
