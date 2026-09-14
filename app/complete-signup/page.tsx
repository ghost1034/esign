'use client'
import { Suspense } from 'react'
import { useSearchParams } from 'next/navigation'
import AuthGuard from '@/components/auth/AuthGuard'
import PhoneVerificationForm from '@/components/auth/PhoneVerificationForm'
import { normalizeAuthRedirectPath } from '@/lib/auth-redirect'
function Enrollment() {
  const search = useSearchParams()
  return <AuthGuard><main className="mx-auto max-w-lg p-8"><h1 className="mb-6 text-2xl font-semibold">Add optional phone MFA</h1><PhoneVerificationForm mode="enroll" redirectTo={normalizeAuthRedirectPath(search.get('redirectTo'), '/account')} /></main></AuthGuard>
}
export default function Page() { return <Suspense><Enrollment /></Suspense> }
