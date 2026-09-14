import { test, expect } from '@playwright/test'
const user = { user_id: 'local-developer', email: 'local.developer@example.com', display_name: 'Local Developer', role: 'admin' }
const team = { firm: { id: 'test-team', name: 'Example organization' }, members: [user], invite_code: 'ABC123' }
const context = { firm: team.firm, profile: { id: null, name: 'Administrator', capabilities: {}, admin_override: true }, features: {}, administrative_capabilities: {} }

test('new account explicitly creates an organization and enters the workspace', async ({ page }) => {
  let created = false
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname
    if (path === '/api/team/onboarding-status') return route.fulfill({ json: { needs_onboarding: !created } })
    if (path === '/api/team/create') { expect(route.request().postDataJSON()).toEqual({ name: 'Example organization' }); created = true; return route.fulfill({ json: team }) }
    if (path === '/api/esign/context') return route.fulfill({ json: context })
    if (path === '/api/esign/envelopes') return route.fulfill({ json: { envelopes: [], total: 0 } })
    if (path === '/api/esign/inbox') return route.fulfill({ json: { pending: [], completed: [] } })
    return route.fulfill({ json: {} })
  })
  await page.goto('/envelopes')
  await expect(page.getByRole('heading', { name: 'Set up your organization' })).toBeVisible()
  await page.getByLabel('Organization name', { exact: true }).fill('Example organization')
  await page.getByRole('button', { name: 'Create organization', exact: true }).click()
  await expect(page).toHaveURL(/\/envelopes$/)
  await expect(page.getByRole('heading', { name: 'Envelopes', exact: true })).toBeVisible()
})

test('team member cannot see administrator controls', async ({ page }) => {
  await page.route('**/api/team/onboarding-status', route => route.fulfill({ json: { needs_onboarding: false } }))
  await page.route('**/api/team', route => route.fulfill({ json: { ...team, members: [{ ...user, role: 'member' }], invite_code: null } }))
  await page.route('**/api/esign/context', route => route.fulfill({ json: { ...context, profile: { ...context.profile, admin_override: false } } }))
  await page.goto('/team')
  await expect(page.getByRole('heading', { name: team.firm.name })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Replace invitation code' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Remove member' })).toHaveCount(0)
})

test('optional MFA does not redirect an authenticated account into enrollment', async ({ page }) => {
  await page.route('**/api/team/onboarding-status', route => route.fulfill({ json: { needs_onboarding: true } }))
  await page.goto('/account')
  await expect(page.getByRole('heading', { name: 'Optional phone MFA' })).toBeVisible()
  await expect(page).toHaveURL(/\/account$/)
  await expect(page.getByRole('button', { name: 'Save profile' })).toBeVisible()
})

test('expired guest invitation uses the standalone guest endpoint and shows the failure', async ({ page }) => {
  let requested = false
  await page.route('**/api/esign/guest/exchange', route => { requested = true; return route.fulfill({ status: 410, json: { detail: 'This invitation has expired' } }) })
  await page.goto('/guest?token=expired-test-token&continue=guest')
  await expect(page.getByText('This invitation has expired', { exact: true })).toBeVisible()
  expect(requested).toBe(true)
})

test('authenticated signing rejects an inaccessible envelope through the correct API', async ({ page }) => {
  let requested = false
  await page.route('**/api/esign/sign/*', route => { requested = true; return route.fulfill({ status: 403, json: { detail: 'You cannot access this envelope' } }) })
  await page.goto('/sign/11111111-1111-1111-1111-111111111111')
  await expect(page.getByText('You cannot access this envelope', { exact: true })).toBeVisible()
  expect(requested).toBe(true)
})

test('completed guest copy downloads its PDF using a standalone secure URL', async ({ page }) => {
  const session = { envelope_id: 'envelope', recipient_id: 'recipient', title: 'Example agreement', sender_email: 'sender@example.com', envelope_status: 'completed', recipient_status: 'signed', recipient_role: 'signer', routing_version: 1, is_my_turn: false, consent_required: false, consent_disclosure_text: 'Test', documents: [], fields: [], context_fields: [], attachments: [], available_actions: [], access_purpose: 'completed_copy', has_sealed_document: true, has_certificate: true }
  await page.route('**/api/esign/guest/sessions/test-session', route => route.fulfill({ json: session }))
  await page.route('**/api/esign/guest/sessions/test-session/completed/sealed', route => route.fulfill({ json: { url: 'http://127.0.0.1:3100/test-download.pdf' } }))
  await page.route('**/test-download.pdf', route => route.fulfill({ contentType: 'application/pdf', headers: { 'Content-Disposition': 'attachment; filename="agreement.pdf"' }, body: '%PDF-1.4\n%%EOF' }))
  await page.goto('/guest?session=test-session&continue=guest')
  await expect(page.getByRole('heading', { name: 'Completed: Example agreement' })).toBeVisible()
  const download = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Completed PDF', exact: true }).click()
  expect((await download).suggestedFilename()).toBe('agreement.pdf')
})

test('core stylesheet is processed and layout utilities are applied', async ({ page }) => {
  await page.route('**/api/team/onboarding-status', route => route.fulfill({ json: { needs_onboarding: true } }))
  await page.goto('/onboarding')
  const heading = page.getByRole('heading', { name: 'Set up your organization' })
  await expect(heading).toHaveCSS('font-size', '30px')
  await expect(page.getByRole('button', { name: 'Create organization', exact: true })).toHaveCSS('display', 'inline-flex')
})
