import type { Metadata } from 'next'
import localFont from 'next/font/local'
import './globals.css'
import { Providers } from './providers'
const signature = localFont({ src: '../backend/assets/fonts/DancingScript-Regular.ttf', variable: '--font-signature' })
const caveat = localFont({ src: '../backend/assets/fonts/Caveat-Regular.ttf', variable: '--font-signature-caveat' })
const greatVibes = localFont({ src: '../backend/assets/fonts/GreatVibes-Regular.ttf', variable: '--font-signature-great-vibes' })
const homemade = localFont({ src: '../backend/assets/fonts/HomemadeApple-Regular.ttf', variable: '--font-signature-homemade-apple' })
export const metadata: Metadata = { title: { default: 'esign', template: '%s | esign' }, description: 'Prepare, send, and sign documents securely.' }
export default function Layout({ children }: { children: React.ReactNode }) {
  return <html lang="en" className={`${signature.variable} ${caveat.variable} ${greatVibes.variable} ${homemade.variable}`}><body className="font-sans antialiased"><Providers>{children}</Providers></body></html>
}
