import { NextRequest } from 'next/server'
export const dynamic = 'force-dynamic'
export const runtime = 'nodejs'
async function proxy(request: NextRequest) {
  const origin = process.env.API_INTERNAL_URL || (process.env.NEXT_PUBLIC_APP_ENV === 'production' ? undefined : 'http://127.0.0.1:8100')
  if (!origin) return Response.json({ detail: 'API origin is not configured' }, { status: 503 })
  const headers = new Headers(request.headers)
  for (const name of ['host', 'connection', 'content-length']) headers.delete(name)
  const response = await fetch(new URL(request.nextUrl.pathname + request.nextUrl.search, origin), {
    method: request.method, headers,
    body: ['GET', 'HEAD'].includes(request.method) ? undefined : await request.arrayBuffer(),
    redirect: 'manual', cache: 'no-store',
  })
  const returned = new Headers(response.headers)
  for (const name of ['content-encoding', 'content-length', 'transfer-encoding', 'connection']) returned.delete(name)
  return new Response(response.body, { status: response.status, headers: returned })
}
export { proxy as GET, proxy as POST, proxy as PUT, proxy as PATCH, proxy as DELETE, proxy as HEAD, proxy as OPTIONS }
