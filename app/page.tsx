'use client'
import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/contexts/AuthContext'
import AuthModal from '@/components/auth/AuthModal'
import { Button } from '@/components/ui/button'
export default function Home() {
  const { user, loading } = useAuth(); const router = useRouter(); const [open, setOpen] = useState(false)
  useEffect(() => { if (user && !loading) router.replace('/envelopes') }, [user, loading, router])
  return <main className="mx-auto flex min-h-screen max-w-3xl flex-col justify-center px-6"><p className="text-primary">esign</p><h1 className="my-6 text-5xl font-semibold">Your documents. Ready to sign.</h1><p className="mb-8 text-lg text-foreground-muted">Prepare agreements, send them to your team and clients, and keep a verifiable record of every signature.</p><Button className="w-fit" onClick={() => setOpen(true)}>Sign in or create an account</Button><AuthModal isOpen={open} onClose={() => setOpen(false)} redirectTo="/envelopes" /></main>
}
