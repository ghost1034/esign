"use client"
import { Suspense } from 'react'
import { useParams, useRouter, useSearchParams } from 'next/navigation'
import { useAuth } from '@/contexts/AuthContext'
import { EsignAccountGate } from '@/components/esign/EsignAccountGate'
import AuthenticatedSigningPage from '@/components/esign/sign/AuthenticatedSigningPage'
function Entry() {
  const { user, loading } = useAuth(); const params = useParams<{ envelopeId: string }>(); const search = useSearchParams(); const router = useRouter()
  if (loading) return <p className="p-8">Opening document…</p>
  if (user) return <AuthenticatedSigningPage />
  const token = search.get('guest_token')
  return <EsignAccountGate redirectTo={'/sign/' + encodeURIComponent(params.envelopeId)} onContinueAsGuest={token ? () => router.push('/guest?continue=guest&token=' + encodeURIComponent(token)) : undefined} />
}
export default function Page() { return <Suspense><Entry /></Suspense> }
