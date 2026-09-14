import { test, expect, type APIRequestContext, type APIResponse } from '@playwright/test'
import { readFile } from 'node:fs/promises'
import path from 'node:path'
import type { components } from '../../lib/api-types'

type Envelope = components['schemas']['EsignEnvelopeResponse']
const authorization = { Authorization: 'Bearer esign-local-development' }

async function json<T>(response: APIResponse): Promise<T> {
  expect(response.ok(), await response.text()).toBe(true)
  return response.json() as Promise<T>
}

async function capturedLink(request: APIRequestContext, email: string, completed = false): Promise<string> {
  let link = ''
  await expect.poll(async () => {
    const inbox = await json<{ messages: Array<{ ID: string; Subject: string; To: Array<{ Address: string }> }> }>(
      await request.get('http://127.0.0.1:8025/api/v1/messages'),
    )
    const message = inbox.messages.find(item => item.To.some(to => to.Address === email)
      && (completed ? /complete/i.test(item.Subject) : !/complete/i.test(item.Subject)))
    if (!message) return false
    const body = await json<{ Text: string }>(await request.get(`http://127.0.0.1:8025/api/v1/message/${message.ID}`))
    link = body.Text.match(/http:\/\/127\.0\.0\.1:3102\/sign\/\S+/)?.[0] ?? ''
    return !!link
  }, { timeout: 30000 }).toBe(true)
  return link
}

test('live upload, Word conversion, guest signing, sealing, downloads and tamper verification', async ({ page, request }) => {
  test.skip(!process.env.ESIGN_E2E_FIXTURES, 'Run npm run test:e2e to start the isolated services')
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  await json(await request.post('/api/team/create', { headers: authorization, data: { name: 'Synthetic E2E organization' } }))
  const fixtures = process.env.ESIGN_E2E_FIXTURES!
  let envelope = (await json<{ envelope: Envelope }>(await request.post('/api/esign/envelopes', {
    headers: authorization,
    multipart: {
      title: 'Synthetic E2E signing test',
      message: 'Software verification only. No legal effect.',
      files: { name: 'agreement.pdf', mimeType: 'application/pdf', buffer: await readFile(path.join(fixtures, 'agreement.pdf')) },
    },
  }))).envelope
  const endpoint = `/api/esign/envelopes/${envelope.id}`
  envelope = await json<Envelope>(await request.post(`${endpoint}/documents`, {
    headers: authorization,
    multipart: { files: { name: 'attachment.docx', mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', buffer: await readFile(path.join(fixtures, 'attachment.docx')) } },
  }))
  expect(envelope.documents).toHaveLength(2)
  expect(envelope.documents.every(document => document.page_count === 1)).toBe(true)
  const email = `e2e-${envelope.id}@example.com`
  envelope = await json<Envelope>(await request.put(`${endpoint}/recipients`, {
    headers: authorization,
    data: { expected_revision: envelope.draft_revision, recipients: [{ name: 'Test Signer', email, role: 'signer', routing_order: 1 }] },
  }))
  const fieldBase = { document_id: envelope.documents[0].id, recipient_id: envelope.recipients[0].id, page_number: 0, pos_x: 0.25, width: 0.25, height: 0.05, required: true }
  envelope = await json<Envelope>(await request.put(`${endpoint}/fields`, {
    headers: authorization,
    data: { expected_revision: envelope.draft_revision, fields: [
      { ...fieldBase, field_type: 'signature', pos_y: 0.25 },
      { ...fieldBase, field_type: 'date_signed', pos_y: 0.4 },
    ] },
  }))
  // A stale editor must not overwrite the draft saved by another request.
  expect((await request.put(`${endpoint}/fields`, { headers: authorization, data: { expected_revision: envelope.draft_revision - 1, fields: [] } })).status()).toBe(409)
  await json(await request.post(`${endpoint}/send`, { headers: authorization }))
  await page.goto(await capturedLink(request, email))
  await page.getByRole('button', { name: 'Continue as guest', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Electronic records and signatures', exact: true })).toBeVisible()
  const sessionId = new URL(page.url()).searchParams.get('session')
  expect(sessionId).toBeTruthy()
  expect((await page.request.post(`/api/esign/guest/sessions/${sessionId}/consent`, { data: { expected_routing_version: 1 } })).status()).toBe(403)
  await page.getByRole('button', { name: 'I agree to use electronic records and signatures', exact: true }).click()
  await expect(page.locator('canvas').first()).toBeVisible()
  await page.getByRole('button', { name: 'Sign here', exact: true }).click()
  await page.getByRole('button', { name: 'Adopt and Sign', exact: true }).click()
  await page.getByRole('button', { name: 'Finish Later', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Progress saved', exact: true })).toBeVisible()
  await page.reload()
  await page.getByRole('button', { name: 'Continue as guest', exact: true }).click()
  await page.getByRole('button', { name: 'Finish signing', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Signature recorded', exact: true })).toBeVisible()
  await expect.poll(async () => (await json<Envelope>(await request.get(endpoint, { headers: authorization }))).status, { timeout: 30000 }).toBe('completed')
  await page.goto(await capturedLink(request, email, true))
  await page.getByRole('button', { name: 'Continue as guest', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Completed: Synthetic E2E signing test', exact: true })).toBeVisible()
  const downloadPromise = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Completed PDF', exact: true }).click()
  const download = await downloadPromise
  const sealed = await readFile((await download.path())!)
  expect(sealed.subarray(0, 5).toString()).toBe('%PDF-')
  const certificatePromise = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Certificate', exact: true }).click()
  const certificate = await readFile((await (await certificatePromise).path())!)
  expect(certificate.subarray(0, 5).toString()).toBe('%PDF-')
  const verification = await json<components['schemas']['EsignVerifyResponse']>(await request.post('/api/esign/verify', {
    headers: authorization, multipart: { envelope_id: envelope.id, file: { name: 'sealed.pdf', mimeType: 'application/pdf', buffer: sealed } },
  }))
  expect(verification).toMatchObject({ hash_match: true, signature_found: true, signature_valid: true })
  const tampered = Buffer.from(sealed)
  // Changing the PDF header version preserves syntax while invalidating its digest.
  const position = tampered.indexOf(Buffer.from('/ByteRange'))
  expect(position).toBeGreaterThan(0)
  const headerPosition = tampered.indexOf(Buffer.from('%PDF-')) + 7
  tampered[headerPosition] = tampered[headerPosition] === 55 ? 54 : 55
  const invalid = await json<components['schemas']['EsignVerifyResponse']>(await request.post('/api/esign/verify', {
    headers: authorization, multipart: { envelope_id: envelope.id, file: { name: 'tampered.pdf', mimeType: 'application/pdf', buffer: tampered } },
  }))
  expect(invalid.hash_match).toBe(false)
  expect(invalid.signature_valid).not.toBe(true)
  const audit = await json<{ events: Array<{ event_type: string }> }>(await request.get(`${endpoint}/audit`, { headers: authorization }))
  expect(audit.events.map(event => event.event_type)).toEqual(expect.arrayContaining(['sent', 'consent_given', 'signed', 'sealed', 'completed']))
  expect(errors).toEqual([])
})
