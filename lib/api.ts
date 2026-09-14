import { getCurrentAuthToken } from './firebase'
import { buildEsignReportQuery } from './esign/reportFilters'
export class ApiError extends Error {
  constructor(public status: number, message: unknown, public body?: unknown) {
    super(typeof message === 'string' ? message : JSON.stringify(message)); this.name = 'ApiError'
  }
}
export interface EsignContext {
  firm: { id: string; name: string }
  profile: { id: string | null; name: string; capabilities: Record<string, boolean>; admin_override: boolean }
  features: Record<string, boolean>
  administrative_capabilities: Record<string, boolean>
}

export interface EsignAiFieldPlacementProposal {
  id: string
  target_id?: string | null
  target_source?: string | null
  document_id: string
  participant_id: string
  field_type: import('./api-types').components['schemas']['EsignAiFieldPlacementProposal']['field_type']
  dependency_ids?: string[]
  page_number: number
  pos_x: number
  pos_y: number
  width: number
  height: number
  required: boolean
  label?: string | null
  properties?: Record<string, unknown>
}

export interface EsignAiFieldPlacementRun {
  id: string
  target_type: 'envelope' | 'template'
  target_id: string
  status: 'queued' | 'processing' | 'completed' | 'failed' | 'applied' | 'discarded'
  scope: 'all_documents' | 'active_document'
  selected_document_ids: string[]
  base_revision: number
  instructions?: string | null
  proposals: EsignAiFieldPlacementProposal[]
  warnings: string[]
  issues?: EsignAiFieldPlacementIssue[]
  error?: string | null
  page_usage: number
  progress: number
  created_at: string
  updated_at: string
}

export interface EsignAiFieldPlacementIssue {
  document_id: string
  page_number: number
  target_id?: string | null
  label: string
  code: 'unassigned' | 'unsupported' | 'unresolved'
  reason: string
}

export interface EsignAiFieldPlacementAction {
  run: EsignAiFieldPlacementRun
  draft_revision: number
  fields_added: number
}

export interface EsignAdminOverview {
  envelopes: number
  users: number
  send_failures: number
  expiring_envelopes: number
  webhook_failures: number
  custody_issues: number
}

export interface EsignPermissionProfile {
  id: string; name: string; capabilities: Record<string, boolean>; built_in_key?: string | null; locked: boolean
}

export interface EsignWebhookConfiguration {
  id: string; envelope_id?: string | null; endpoint_url: string; enabled: boolean
  event_filters: string[]; include_completed_documents: boolean; secret?: string
}

export interface EsignPowerFormSubmission {
  id: string; status: string; initiating_email: string; envelope_id?: string | null
  verified_at?: string | null; created_at: string; attempt_count: number; last_error?: string | null
}

export interface EsignPowerFormUpgradePreview {
  compatible: boolean; current_version: number; target_version: number
  added_roles: string[]; removed_roles: string[]; changed_roles: string[]
  current_field_count: number; target_field_count: number; warnings: string[]
}

export interface EsignReportFilters {
  start: string; end: string; source?: string; status?: string; templateVersionId?: string
  senderUserId?: string; sourceId?: string
}

export interface EsignReportPoint { date: string; sent: number; completed: number }
export interface EsignWebhookAttempt {
  id: string; attempt_number: number; started_at: string; completed_at?: string | null
  duration_ms?: number | null; result: string; http_status?: number | null
  response_excerpt?: string | null; error?: string | null
}
export interface EsignCustodyIssue { asset_type: string; asset_id: string; recorded_owner_id: string; created_at?: string | null }
export interface EsignAuditFilters { eventType?: string; actorEmail?: string; targetType?: string; start?: string; end?: string }
export interface EsignAdminAuditEvent {
  id: string; event_type: string; actor_email?: string | null; target_type?: string | null
  target_id?: string | null; details?: Record<string, unknown> | null; created_at: string
}

function inferUploadContentType(file: File): string {
  if (file.type) return file.type
  const name = file.name.toLowerCase()
  if (name.endsWith('.pdf')) return 'application/pdf'
  if (name.endsWith('.docx')) return 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
  if (name.endsWith('.pptx')) return 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
  if (name.endsWith('.xlsx')) return 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
  if (name.endsWith('.zip')) return 'application/zip'
  if (name.endsWith('.csv')) return 'text/csv'
  return 'application/octet-stream'
}

export class ApiClient {
  private baseURL: string

  constructor(baseURL: string = '') {
    this.baseURL = baseURL
  }

  private async getAuthToken(): Promise<string | null> {
    return getCurrentAuthToken()
  }

  async request<T>(
    path: string,
    options: RequestInit = {}
  ): Promise<T> {
    const token = await this.getAuthToken()

    const response = await fetch(`${this.baseURL}${path}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(token && { Authorization: `Bearer ${token}` }),
        ...options.headers,
      },
    })

    if (!response.ok) {
      let body: any = null
      let message = `HTTP ${response.status}`
      try {
        body = await response.json()
        message = body?.detail || body?.message || message
      } catch {
        try {
          const text = await response.text()
          if (text) message = text
        } catch {
          // ignore
        }
      }
      throw new ApiError(response.status, message, body)
    }

    return response.json()
  }

  getTeamOnboardingStatus(): Promise<{ needs_onboarding: boolean }> { return this.request('/api/team/onboarding-status') }
  getTeam(): Promise<TeamDetail> { return this.request('/api/team') }
  checkPhoneNumberAvailability(phone: string): Promise<{ available: boolean }> { return this.request('/api/account/phone-availability?phone_number=' + encodeURIComponent(phone)) }
  syncUserProfile(): Promise<Record<string, unknown>> { return this.request('/api/account/sync', { method: 'POST' }) }
  private async requestMultipart<T>(path: string, formData: FormData, method: 'POST' | 'PUT' = 'POST'): Promise<T> {
    const token = await this.getAuthToken()
    const response = await fetch(`${this.baseURL}${path}`, {
      method,
      headers: {
        ...(token && { Authorization: `Bearer ${token}` }),
      },
      body: formData,
    })

    if (!response.ok) {
      let body: any = null
      let message = `HTTP ${response.status}`
      try {
        body = await response.json()
        message = body?.detail || body?.message || message
      } catch {
        try {
          const text = await response.text()
          if (text) message = text
        } catch {
          // ignore
        }
      }
      throw new ApiError(response.status, message, body)
    }

    return response.json()
  }

  async createEsignEnvelope(params: {
    title?: string
    message?: string
    signingType?: string
    expiresInDays?: number
    reminderIntervalHours?: number
    templateId?: string
    brandId?: string
    files?: File[]
  }): Promise<EsignEnvelopeCreateResponse> {
    const formData = new FormData()
    if (params.title) formData.append('title', params.title)
    if (params.message) formData.append('message', params.message)
    if (params.signingType) formData.append('signing_type', params.signingType)
    if (params.expiresInDays !== undefined) formData.append('expires_in_days', String(params.expiresInDays))
    if (params.reminderIntervalHours !== undefined) {
      formData.append('reminder_interval_hours', String(params.reminderIntervalHours))
    }
    if (params.templateId) formData.append('template_id', params.templateId)
    if (params.brandId) formData.append('brand_id', params.brandId)
    params.files?.forEach((file) => formData.append('files', file))
    return this.requestMultipart('/api/esign/envelopes', formData)
  }

  async listEsignEnvelopes(params: {
    limit?: number
    offset?: number
    status?: string
    sourceType?: 'manual' | 'bulk' | 'powerform'
    sourceId?: string
    templateVersionId?: string
    q?: string
    sortBy?: 'updated_at' | 'created_at' | 'sent_at' | 'completed_at' | 'title'
    sortDir?: 'asc' | 'desc'
    scope?: 'mine' | 'shared' | 'firm'
    ownerUserId?: string
  } = {}): Promise<EsignEnvelopeListResponse> {
    const searchParams = new URLSearchParams({
      limit: String(params.limit ?? 25),
      offset: String(params.offset ?? 0),
    })
    if (params.status) searchParams.set('status', params.status)
    if (params.sourceType) searchParams.set('source_type', params.sourceType)
    if (params.sourceId) searchParams.set('source_id', params.sourceId)
    if (params.templateVersionId) searchParams.set('template_version_id', params.templateVersionId)
    if (params.q) searchParams.set('q', params.q)
    if (params.sortBy) searchParams.set('sort_by', params.sortBy)
    if (params.sortDir) searchParams.set('sort_dir', params.sortDir)
    if (params.scope) searchParams.set('scope', params.scope)
    if (params.ownerUserId) searchParams.set('owner_user_id', params.ownerUserId)
    return this.request(`/api/esign/envelopes?${searchParams.toString()}`)
  }

  async getEsignContext(): Promise<EsignContext> {
    return this.request('/api/esign/context')
  }

  async getEsignAdminOverview(): Promise<EsignAdminOverview> {
    return this.request('/api/esign/admin/overview')
  }

  async getEsignAdminSettings(): Promise<Record<string, any>> {
    return this.request('/api/esign/admin/settings')
  }

  async updateEsignAdminSettings(payload: Record<string, any>): Promise<Record<string, any>> {
    return this.request('/api/esign/admin/settings', { method: 'PUT', body: JSON.stringify(payload) })
  }

  async listEsignPermissionProfiles(): Promise<{ profiles: EsignPermissionProfile[] }> {
    return this.request('/api/esign/admin/permission-profiles')
  }

  async createEsignPermissionProfile(payload: { name: string; capabilities: Record<string, boolean> }): Promise<EsignPermissionProfile> {
    return this.request('/api/esign/admin/permission-profiles', { method: 'POST', body: JSON.stringify(payload) })
  }

  async assignEsignPermissionProfile(userId: string, profileId: string): Promise<Record<string, any>> {
    return this.request(`/api/esign/admin/users/${userId}/permission-profile`, { method: 'PUT', body: JSON.stringify({ profile_id: profileId }) })
  }

  async listEsignBrands(): Promise<{ brands: Record<string, any>[] }> {
    return this.request('/api/esign/admin/brands')
  }

  async createEsignBrand(payload: Record<string, any>): Promise<Record<string, any>> {
    return this.request('/api/esign/admin/brands', { method: 'POST', body: JSON.stringify(payload) })
  }

  async listEsignFirmWebhooks(): Promise<{ configurations: EsignWebhookConfiguration[] }> {
    return this.request('/api/esign/admin/webhooks')
  }

  async createEsignFirmWebhook(payload: { endpoint_url: string; enabled?: boolean; event_filters?: string[]; include_completed_documents?: boolean }): Promise<EsignWebhookConfiguration> {
    return this.request('/api/esign/admin/webhooks', { method: 'POST', body: JSON.stringify(payload) })
  }

  async listEsignWebhookDeliveries(status?: string): Promise<{ deliveries: Record<string, any>[] }> {
    return this.request(`/api/esign/admin/webhook-deliveries${status ? `?status=${encodeURIComponent(status)}` : ''}`)
  }

  async replayEsignWebhook(deliveryId: string): Promise<Record<string, any>> {
    return this.request(`/api/esign/admin/webhook-deliveries/${deliveryId}/replay`, { method: 'POST' })
  }

  async getEsignEnvelopeAccess(envelopeId: string): Promise<{ owner_id: string; grants: Record<string, any>[] }> {
    return this.request(`/api/esign/envelopes/${envelopeId}/access`)
  }

  async grantEsignEnvelopeAccess(envelopeId: string, userId: string, accessLevel: 'view' | 'manage'): Promise<Record<string, any>> {
    return this.request(`/api/esign/envelopes/${envelopeId}/access`, { method: 'PUT', body: JSON.stringify({ user_id: userId, access_level: accessLevel }) })
  }

  async transferEsignEnvelope(envelopeId: string, successorUserId: string, retainPreviousOwnerView = true): Promise<Record<string, any>> {
    return this.request(`/api/esign/envelopes/${envelopeId}/transfer`, { method: 'POST', body: JSON.stringify({ successor_user_id: successorUserId, retain_previous_owner_view: retainPreviousOwnerView }) })
  }

  async getEsignEnvelope(envelopeId: string): Promise<EsignEnvelopeResponse> {
    return this.request(`/api/esign/envelopes/${envelopeId}`)
  }

  async updateEsignEnvelope(envelopeId: string, payload: EsignEnvelopeUpdateRequest): Promise<EsignEnvelopeResponse> {
    return this.request(`/api/esign/envelopes/${envelopeId}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    })
  }

  async updateEsignEnvelopeDeliverySettings(
    envelopeId: string,
    payload: EsignEnvelopeDeliverySettingsUpdateRequest,
  ): Promise<EsignEnvelopeResponse> {
    return this.request(`/api/esign/envelopes/${envelopeId}/delivery-settings`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    })
  }

  async deleteEsignEnvelope(envelopeId: string): Promise<{ message: string }> {
    return this.request(`/api/esign/envelopes/${envelopeId}`, {
      method: 'DELETE',
    })
  }

  async addEsignDocuments(envelopeId: string, files: File[]): Promise<EsignEnvelopeResponse> {
    const formData = new FormData()
    files.forEach((file) => formData.append('files', file))
    return this.requestMultipart(`/api/esign/envelopes/${envelopeId}/documents`, formData)
  }

  async deleteEsignDocument(envelopeId: string, documentId: string): Promise<EsignEnvelopeResponse> {
    return this.request(`/api/esign/envelopes/${envelopeId}/documents/${documentId}`, {
      method: 'DELETE',
    })
  }

  async reorderEsignDocuments(envelopeId: string, documentIds: string[]): Promise<EsignEnvelopeResponse> {
    return this.request(`/api/esign/envelopes/${envelopeId}/documents/order`, {
      method: 'PATCH',
      body: JSON.stringify({ document_ids: documentIds }),
    })
  }

  async inspectEsignPdfWidgets(envelopeId: string, documentId: string): Promise<EsignPdfWidgetInspectionResponse> {
    return this.request(`/api/esign/envelopes/${envelopeId}/documents/${documentId}/pdf-widgets`)
  }

  async convertEsignPdfWidgets(
    envelopeId: string,
    documentId: string,
    payload: EsignPdfWidgetConversionRequest,
  ): Promise<EsignEnvelopeResponse> {
    return this.request(`/api/esign/envelopes/${envelopeId}/documents/${documentId}/convert-pdf-fields`, {
      method: 'POST', body: JSON.stringify(payload),
    })
  }

  async replaceEsignRecipients(
    envelopeId: string,
    recipients: EsignRecipientInput[],
    templateId?: string,
    expectedRevision?: number,
  ): Promise<EsignEnvelopeResponse> {
    const query = templateId ? `?template_id=${encodeURIComponent(templateId)}` : ''
    return this.request(`/api/esign/envelopes/${envelopeId}/recipients${query}`, {
      method: 'PUT',
      body: JSON.stringify({ recipients, expected_revision: expectedRevision }),
    })
  }

  async replaceEsignFields(envelopeId: string, fields: EsignFieldInput[], expectedRevision?: number): Promise<EsignEnvelopeResponse> {
    return this.request(`/api/esign/envelopes/${envelopeId}/fields`, {
      method: 'PUT',
      body: JSON.stringify({ fields, expected_revision: expectedRevision }),
    })
  }

  async createEsignAiFieldPlacementRun(
    targetType: 'envelope' | 'template', targetId: string,
    payload: { scope: 'all_documents' | 'active_document'; document_id?: string; instructions?: string; expected_revision: number },
  ): Promise<EsignAiFieldPlacementRun> {
    const collection = targetType === 'envelope' ? 'envelopes' : 'templates'
    return this.request(`/api/esign/${collection}/${targetId}/ai-field-placement-runs`, { method: 'POST', body: JSON.stringify(payload) })
  }

  async listEsignAiFieldPlacementRuns(targetType: 'envelope' | 'template', targetId: string): Promise<{ runs: EsignAiFieldPlacementRun[] }> {
    const collection = targetType === 'envelope' ? 'envelopes' : 'templates'
    return this.request(`/api/esign/${collection}/${targetId}/ai-field-placement-runs`)
  }

  async getEsignAiFieldPlacementRun(runId: string): Promise<EsignAiFieldPlacementRun> {
    return this.request(`/api/esign/ai-field-placement-runs/${runId}`)
  }

  async applyEsignAiFieldPlacementRun(runId: string, acceptedProposalIds: string[], currentRevision: number): Promise<EsignAiFieldPlacementAction> {
    return this.request(`/api/esign/ai-field-placement-runs/${runId}/apply`, {
      method: 'POST', body: JSON.stringify({ accepted_proposal_ids: acceptedProposalIds, current_revision: currentRevision }),
    })
  }

  async discardEsignAiFieldPlacementRun(runId: string): Promise<EsignAiFieldPlacementAction> {
    return this.request(`/api/esign/ai-field-placement-runs/${runId}/discard`, { method: 'POST', body: '{}' })
  }

  async correctEsignFields(envelopeId: string, payload: { fields: EsignFieldInput[]; reason: string; expected_routing_version: number }): Promise<EsignEnvelopeResponse> {
    return this.request(`/api/esign/envelopes/${envelopeId}/corrections/fields`, {
      method: 'PUT', body: JSON.stringify(payload),
    })
  }

  async replaceActiveEsignDocument(envelopeId: string, documentId: string, file: File, reason: string, expectedRoutingVersion: number): Promise<EsignEnvelopeResponse> {
    const form = new FormData()
    form.append('file', file)
    form.append('reason', reason)
    form.append('expected_routing_version', String(expectedRoutingVersion))
    return this.requestMultipart(`/api/esign/envelopes/${envelopeId}/corrections/documents/${documentId}`, form, 'PUT')
  }

  async searchEsignAnchors(
    envelopeId: string,
    payload: { anchor: string; case_sensitive?: boolean; whole_word?: boolean; document_ids?: string[]; page_numbers?: number[]; match_mode?: 'first' | 'all'; relative_position?: 'auto' | 'center' | 'right' | 'left' | 'below' | 'above'; cross_axis_alignment?: 'auto' | 'start' | 'center' | 'end'; horizontal_alignment?: 'left' | 'center' | 'right' | 'after'; offset_x?: number; offset_y?: number; offset_unit?: 'point' | 'mm' | 'inch'; field_width?: number; field_height?: number },
  ): Promise<EsignAnchorSearchResponse> {
    return this.request(`/api/esign/envelopes/${envelopeId}/anchor-search`, {
      method: 'POST', body: JSON.stringify(payload),
    })
  }

  async searchEsignTemplateAnchors(
    templateId: string,
    payload: { anchor: string; case_sensitive?: boolean; whole_word?: boolean; document_ids?: string[]; page_numbers?: number[]; match_mode?: 'first' | 'all'; relative_position?: 'auto' | 'center' | 'right' | 'left' | 'below' | 'above'; cross_axis_alignment?: 'auto' | 'start' | 'center' | 'end'; horizontal_alignment?: 'left' | 'center' | 'right' | 'after'; offset_x?: number; offset_y?: number; offset_unit?: 'point' | 'mm' | 'inch'; field_width?: number; field_height?: number },
  ): Promise<EsignAnchorSearchResponse> {
    return this.request(`/api/esign/templates/${templateId}/anchor-search`, {
      method: 'POST', body: JSON.stringify(payload),
    })
  }

  async sendEsignEnvelope(envelopeId: string): Promise<EsignEnvelopeResponse> {
    return this.request(`/api/esign/envelopes/${envelopeId}/send`, { method: 'POST', body: '{}' })
  }

  async voidEsignEnvelope(envelopeId: string, reason: string): Promise<EsignEnvelopeResponse> {
    return this.request(`/api/esign/envelopes/${envelopeId}/void`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    })
  }

  async cloneAndVoidEsignEnvelope(
    envelopeId: string,
    reason: string,
    expectedRoutingVersion: number,
  ): Promise<{ original: EsignEnvelopeResponse; clone: EsignEnvelopeResponse }> {
    return this.request(`/api/esign/envelopes/${envelopeId}/clone-and-void`, {
      method: 'POST',
      body: JSON.stringify({ reason, expected_routing_version: expectedRoutingVersion }),
    })
  }

  async remindEsignEnvelope(envelopeId: string): Promise<{ reminded: string[] }> {
    return this.request(`/api/esign/envelopes/${envelopeId}/remind`, { method: 'POST', body: '{}' })
  }

  async saveEsignEnvelopeAsTemplate(
    envelopeId: string,
    name: string,
    description?: string
  ): Promise<EsignTemplateResponse> {
    return this.request(`/api/esign/envelopes/${envelopeId}/save-as-template`, {
      method: 'POST',
      body: JSON.stringify({ name, description }),
    })
  }

  async getEsignAuditTrail(envelopeId: string): Promise<EsignAuditTrailResponse> {
    return this.request(`/api/esign/envelopes/${envelopeId}/audit`)
  }

  async getEsignDocumentDownload(envelopeId: string, documentId: string): Promise<EsignDownloadResponse> {
    return this.request(`/api/esign/envelopes/${envelopeId}/documents/${documentId}/download`)
  }

  async getEsignSealedDownload(envelopeId: string): Promise<EsignDownloadResponse> {
    return this.request(`/api/esign/envelopes/${envelopeId}/sealed/download`)
  }

  async getEsignCertificateDownload(envelopeId: string): Promise<EsignDownloadResponse> {
    return this.request(`/api/esign/envelopes/${envelopeId}/certificate/download`)
  }

  async getEsignInbox(params: { q?: string; state?: 'pending' | 'completed' } = {}): Promise<EsignInboxResponse> {
    const searchParams = new URLSearchParams()
    if (params.q) searchParams.set('q', params.q)
    if (params.state) searchParams.set('state', params.state)
    const query = searchParams.toString()
    return this.request(`/api/esign/inbox${query ? `?${query}` : ''}`)
  }

  async getEsignSigningSession(envelopeId: string): Promise<EsignSigningSessionResponse> {
    return this.request(`/api/esign/sign/${envelopeId}`)
  }

  async recordEsignConsent(envelopeId: string, expectedRoutingVersion: number): Promise<EsignConsentResponse> {
    return this.request(`/api/esign/sign/${envelopeId}/consent`, {
      method: 'POST', body: JSON.stringify({ expected_routing_version: expectedRoutingVersion }),
    })
  }

  async saveEsignSigningProgress(
    envelopeId: string,
    fieldValues: { field_id: string; value?: string | null }[],
    expectedRoutingVersion: number,
    marks?: apiComponents['schemas']['EsignMarkBundle'],
  ): Promise<{ saved_count: number }> {
    return this.request(`/api/esign/sign/${envelopeId}/progress`, {
      method: 'PUT',
      body: JSON.stringify({ field_values: fieldValues, expected_routing_version: expectedRoutingVersion, marks }),
    })
  }

  async uploadEsignSignerAttachment(envelopeId: string, fieldId: string, file: File): Promise<EsignSignerAttachmentResponse> {
    const formData = new FormData()
    formData.append('field_id', fieldId)
    formData.append('file', file)
    return this.requestMultipart(`/api/esign/sign/${envelopeId}/attachments`, formData)
  }

  async deleteEsignSignerAttachment(envelopeId: string, attachmentId: string): Promise<{ message: string }> {
    return this.request(`/api/esign/sign/${envelopeId}/attachments/${attachmentId}`, { method: 'DELETE' })
  }

  async submitEsignSignature(envelopeId: string, payload: EsignSubmitRequest): Promise<EsignSubmitResponse> {
    return this.request(`/api/esign/sign/${envelopeId}/submit`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  }

  async declineEsignEnvelope(envelopeId: string, reason: string, expectedRoutingVersion: number): Promise<EsignSubmitResponse> {
    return this.request(`/api/esign/sign/${envelopeId}/decline`, {
      method: 'POST',
      body: JSON.stringify({ reason, expected_routing_version: expectedRoutingVersion }),
    })
  }

  async correctEsignRecipients(envelopeId: string, payload: EsignCorrectionRequest): Promise<EsignEnvelopeResponse> {
    return this.request(`/api/esign/envelopes/${envelopeId}/corrections`, {
      method: 'POST', body: JSON.stringify(payload),
    })
  }

  async reassignEsignRecipient(envelopeId: string, payload: EsignReassignRequest): Promise<EsignRecipientResponse> {
    return this.request(`/api/esign/sign/${envelopeId}/reassign`, {
      method: 'POST', body: JSON.stringify(payload),
    })
  }

  async approveEsignEnvelope(envelopeId: string, expectedRoutingVersion: number): Promise<EsignSubmitResponse> {
    return this.request(`/api/esign/sign/${envelopeId}/approve`, {
      method: 'POST', body: JSON.stringify({ expected_routing_version: expectedRoutingVersion }),
    })
  }

  async updateEsignManagedRecipients(envelopeId: string, payload: EsignManagedRecipientsRequest): Promise<EsignManagedRecipientsResponse> {
    return this.request(`/api/esign/sign/${envelopeId}/managed-recipients`, {
      method: 'PATCH', body: JSON.stringify(payload),
    })
  }

  async completeEsignManagerStep(envelopeId: string, expectedRoutingVersion: number): Promise<EsignSubmitResponse> {
    return this.request(`/api/esign/sign/${envelopeId}/manager-complete`, {
      method: 'POST', body: JSON.stringify({ expected_routing_version: expectedRoutingVersion }),
    })
  }

  async configureEsignWitness(envelopeId: string, payload: EsignWitnessRequest): Promise<EsignGuestInvitationResponse> {
    return this.request(`/api/esign/sign/${envelopeId}/witness`, {
      method: 'PUT', body: JSON.stringify(payload),
    })
  }

  async startEsignInPerson(envelopeId: string, payload: EsignInPersonStartRequest): Promise<EsignGuestInvitationResponse> {
    return this.request(`/api/esign/sign/${envelopeId}/in-person/start`, {
      method: 'POST', body: JSON.stringify(payload),
    })
  }

  async verifyEsignDocument(params: { envelopeId?: string; file?: File }): Promise<EsignVerifyResponse> {
    const formData = new FormData()
    if (params.envelopeId) formData.append('envelope_id', params.envelopeId)
    if (params.file) formData.append('file', params.file)
    return this.requestMultipart('/api/esign/verify', formData)
  }

  async createEsignTemplate(params: {
    name: string
    description?: string
    title?: string
    message?: string
    signingType?: string
    recipientRoles?: EsignTemplateRoleInput[]
    brandId?: string
    files: File[]
  }): Promise<EsignTemplateResponse> {
    const formData = new FormData()
    formData.append('name', params.name)
    if (params.description) formData.append('description', params.description)
    if (params.title) formData.append('title', params.title)
    if (params.message) formData.append('message', params.message)
    if (params.signingType) formData.append('signing_type', params.signingType)
    if (params.recipientRoles) formData.append('recipient_roles', JSON.stringify(params.recipientRoles))
    if (params.brandId) formData.append('brand_id', params.brandId)
    params.files.forEach((file) => formData.append('files', file))
    return this.requestMultipart('/api/esign/templates', formData)
  }

  async listEsignTemplates(includeArchived = false): Promise<EsignTemplateListResponse> {
    return this.request(`/api/esign/templates${includeArchived ? '?include_archived=true' : ''}`)
  }

  async getEsignTemplate(templateId: string): Promise<EsignTemplateResponse> {
    return this.request(`/api/esign/templates/${templateId}`)
  }

  async updateEsignTemplate(templateId: string, payload: EsignTemplateUpdateRequest): Promise<EsignTemplateResponse> {
    return this.request(`/api/esign/templates/${templateId}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    })
  }

  async deleteEsignTemplate(templateId: string): Promise<{ message: string }> {
    return this.request(`/api/esign/templates/${templateId}`, { method: 'DELETE' })
  }

  async getEsignTemplateDocumentDownload(templateId: string, documentId: string): Promise<EsignDownloadResponse> {
    return this.request(`/api/esign/templates/${templateId}/documents/${documentId}/download`)
  }

  async addEsignTemplateDocuments(templateId: string, files: File[]): Promise<EsignTemplateResponse> {
    const form = new FormData(); files.forEach(file => form.append('files', file))
    return this.requestMultipart(`/api/esign/templates/${templateId}/documents`, form)
  }

  async deleteEsignTemplateDocument(templateId: string, documentId: string): Promise<EsignTemplateResponse> {
    return this.request(`/api/esign/templates/${templateId}/documents/${documentId}`, { method: 'DELETE' })
  }

  async publishEsignTemplate(templateId: string, expectedRevision?: number): Promise<EsignTemplateVersionResponse> {
    const query = expectedRevision ? `?expected_revision=${expectedRevision}` : ''
    return this.request(`/api/esign/templates/${templateId}/versions${query}`, { method: 'POST', body: '{}' })
  }

  async listEsignTemplateVersions(templateId: string): Promise<EsignTemplateVersionListResponse> {
    return this.request(`/api/esign/templates/${templateId}/versions`)
  }

  async createEsignTemplateDraftFromVersion(versionId: string): Promise<EsignTemplateResponse> {
    return this.request(`/api/esign/template-versions/${versionId}/draft`, { method: 'POST', body: '{}' })
  }

  async downloadEsignBulkSample(versionId: string): Promise<Blob> {
    const token = await this.getAuthToken()
    const response = await fetch(`${this.baseURL}/api/esign/template-versions/${versionId}/bulk-sample.csv`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    if (!response.ok) throw new ApiError(response.status, 'Could not download the CSV sample')
    return response.blob()
  }

  async downloadEsignBulkErrors(jobId: string): Promise<Blob> {
    const token = await this.getAuthToken()
    const response = await fetch(`${this.baseURL}/api/esign/bulk-jobs/${jobId}/errors.csv`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    if (!response.ok) throw new ApiError(response.status, 'Could not download row errors')
    return response.blob()
  }

  async createEsignBulkJob(templateVersionId: string, file: File, defaultSchedule?: { at: string; timezone: string }): Promise<EsignBulkJobResponse> {
    const form = new FormData()
    form.append('template_version_id', templateVersionId)
    form.append('file', file)
    if (defaultSchedule) { form.append('default_schedule_at', defaultSchedule.at); form.append('default_schedule_timezone', defaultSchedule.timezone) }
    return this.requestMultipart('/api/esign/bulk-jobs', form)
  }

  async listEsignBulkJobs(): Promise<EsignBulkJobListResponse> {
    return this.request('/api/esign/bulk-jobs')
  }

  async getEsignBulkJob(jobId: string): Promise<EsignBulkJobResponse> {
    return this.request(`/api/esign/bulk-jobs/${jobId}`)
  }

  async confirmEsignBulkJob(jobId: string): Promise<EsignBulkJobResponse> {
    return this.request(`/api/esign/bulk-jobs/${jobId}/confirm`, { method: 'POST', body: '{}' })
  }

  async cancelEsignBulkJob(jobId: string): Promise<EsignBulkJobResponse> {
    return this.request(`/api/esign/bulk-jobs/${jobId}/cancel`, { method: 'POST', body: '{}' })
  }

  async retryEsignBulkJob(jobId: string): Promise<EsignBulkJobResponse> {
    return this.request(`/api/esign/bulk-jobs/${jobId}/retry`, { method: 'POST', body: '{}' })
  }

  async createEsignPowerForm(payload: EsignPowerFormCreateRequest): Promise<EsignPowerFormResponse> {
    return this.request('/api/esign/powerforms', { method: 'POST', body: JSON.stringify(payload) })
  }

  async listEsignPowerForms(): Promise<EsignPowerFormListResponse> {
    return this.request('/api/esign/powerforms')
  }

  async setEsignPowerFormState(id: string, state: 'active' | 'paused' | 'revoked'): Promise<EsignPowerFormResponse> {
    return this.request(`/api/esign/powerforms/${id}/state/${state}`, { method: 'POST', body: '{}' })
  }

  async rotateEsignPowerForm(id: string): Promise<EsignPowerFormResponse> {
    return this.request(`/api/esign/powerforms/${id}/rotate`, { method: 'POST', body: '{}' })
  }

  async listEsignPowerFormSubmissions(id: string): Promise<{ submissions: EsignPowerFormSubmission[] }> {
    return this.request(`/api/esign/powerforms/${id}/submissions`)
  }

  async retryEsignPowerFormSubmission(id: string, submissionId: string): Promise<EsignPowerFormSubmission> {
    return this.request(`/api/esign/powerforms/${id}/submissions/${submissionId}/retry`, { method: 'POST', body: '{}' })
  }

  async previewEsignPowerFormUpgrade(id: string, versionId: string): Promise<EsignPowerFormUpgradePreview> {
    return this.request(`/api/esign/powerforms/${id}/upgrade/${versionId}/preview`)
  }

  async upgradeEsignPowerForm(id: string, versionId: string): Promise<EsignPowerFormResponse> {
    return this.request(`/api/esign/powerforms/${id}/upgrade/${versionId}`, { method: 'POST', body: '{}' })
  }

  private esignReportQuery(params: EsignReportFilters): URLSearchParams {
    return buildEsignReportQuery(params)
  }

  async getEsignReportSummary(params: EsignReportFilters): Promise<EsignReportSummary> {
    const query = this.esignReportQuery(params)
    return this.request(`/api/esign/reports/summary?${query}`)
  }

  async getEsignReportTimeSeries(params: EsignReportFilters): Promise<{ points: EsignReportPoint[] }> {
    return this.request(`/api/esign/reports/time-series?${this.esignReportQuery(params)}`)
  }

  async downloadEsignReportDetails(params: EsignReportFilters): Promise<Blob> {
    const token = await this.getAuthToken(); const query = this.esignReportQuery(params)
    const response = await fetch(`${this.baseURL}/api/esign/reports/details.csv?${query}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
    if (!response.ok) throw new ApiError(response.status, 'Could not export report details')
    return response.blob()
  }

  async scheduleEsignEnvelope(envelopeId: string, payload: EsignScheduleRequest): Promise<EsignEnvelopeResponse> {
    return this.request(`/api/esign/envelopes/${envelopeId}/schedule`, { method: 'POST', body: JSON.stringify(payload) })
  }

  async unscheduleEsignEnvelope(envelopeId: string): Promise<EsignEnvelopeResponse> {
    return this.request(`/api/esign/envelopes/${envelopeId}/unschedule`, { method: 'POST', body: '{}' })
  }

  async retryFailedEsignSend(envelopeId: string): Promise<EsignEnvelopeResponse> {
    return this.request(`/api/esign/envelopes/${envelopeId}/retry-send`, { method: 'POST', body: '{}' })
  }

  async recoverFailedEsignSendDraft(envelopeId: string): Promise<EsignEnvelopeResponse> {
    return this.request(`/api/esign/envelopes/${envelopeId}/recover-draft`, { method: 'POST', body: '{}' })
  }

  async revokeEsignEnvelopeAccess(envelopeId: string, userId: string): Promise<{ success: boolean }> {
    return this.request(`/api/esign/envelopes/${envelopeId}/access/${encodeURIComponent(userId)}`, { method: 'DELETE' })
  }

  async updateEsignPermissionProfile(profileId: string, payload: { name: string; capabilities: Record<string, boolean> }): Promise<EsignPermissionProfile> {
    return this.request(`/api/esign/admin/permission-profiles/${profileId}`, { method: 'PUT', body: JSON.stringify(payload) })
  }

  async updateEsignBrand(brandId: string, payload: Record<string, any>): Promise<Record<string, any>> {
    return this.request(`/api/esign/admin/brands/${brandId}`, { method: 'PUT', body: JSON.stringify(payload) })
  }

  async uploadEsignBrandAsset(file: File): Promise<{ id: string; content_type: string; sha256: string; file_size_bytes: number }> {
    const form = new FormData(); form.append('file', file)
    return this.requestMultipart('/api/esign/admin/brand-assets', form)
  }

  async updateEsignWebhook(id: string, payload: { endpoint_url: string; enabled: boolean; event_filters: string[]; include_completed_documents: boolean }): Promise<EsignWebhookConfiguration> {
    return this.request(`/api/esign/admin/webhooks/${id}`, { method: 'PUT', body: JSON.stringify(payload) })
  }

  async rotateEsignWebhookSecret(id: string): Promise<{ id: string; secret: string; overlap_expires_at: string }> {
    return this.request(`/api/esign/admin/webhooks/${id}/rotate-secret`, { method: 'POST', body: '{}' })
  }

  async testEsignWebhook(id: string): Promise<{ delivery_id: string; status: string }> {
    return this.request(`/api/esign/admin/webhooks/${id}/test`, { method: 'POST', body: '{}' })
  }

  async disableEsignWebhook(id: string): Promise<{ success: boolean }> {
    return this.request(`/api/esign/admin/webhooks/${id}`, { method: 'DELETE' })
  }

  async getEsignWebhookAttempts(deliveryId: string): Promise<{ attempts: EsignWebhookAttempt[] }> {
    return this.request(`/api/esign/admin/webhook-deliveries/${deliveryId}/attempts`)
  }

  async getEsignCustodyReview(): Promise<{ assets: EsignCustodyIssue[] }> {
    return this.request('/api/esign/admin/custody-review')
  }

  async remediateEsignCustody(payload: { asset_type: EsignCustodyIssue['asset_type']; asset_id: string; successor_user_id: string }): Promise<Record<string, string>> {
    return this.request('/api/esign/admin/custody-review/remediate', { method: 'POST', body: JSON.stringify(payload) })
  }

  async getEsignAdminAudit(filters: EsignAuditFilters = {}): Promise<{ events: EsignAdminAuditEvent[] }> {
    const query = new URLSearchParams()
    if (filters.eventType) query.set('event_type', filters.eventType)
    if (filters.actorEmail) query.set('actor_email', filters.actorEmail)
    if (filters.targetType) query.set('target_type', filters.targetType)
    if (filters.start) query.set('start', filters.start)
    if (filters.end) query.set('end', filters.end)
    return this.request(`/api/esign/admin/audit?${query}`)
  }

  async downloadEsignAdminAudit(filters: EsignAuditFilters = {}): Promise<Blob> {
    const token = await this.getAuthToken(); const query = new URLSearchParams()
    if (filters.eventType) query.set('event_type', filters.eventType)
    if (filters.actorEmail) query.set('actor_email', filters.actorEmail)
    if (filters.targetType) query.set('target_type', filters.targetType)
    if (filters.start) query.set('start', filters.start)
    if (filters.end) query.set('end', filters.end)
    const response = await fetch(`${this.baseURL}/api/esign/admin/audit.csv?${query}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
    if (!response.ok) throw new ApiError(response.status, 'Could not export audit events')
    return response.blob()
  }

}
import type { components as apiComponents } from './api-types'

export type EsignEnvelopeResponse = apiComponents['schemas']['EsignEnvelopeResponse']
export type EsignEnvelopeCreateResponse = apiComponents['schemas']['EsignEnvelopeCreateResponse']
export type EsignEnvelopeListResponse = apiComponents['schemas']['EsignEnvelopeListResponse']
export type EsignEnvelopeListItem = apiComponents['schemas']['EsignEnvelopeListItem']
export type EsignEnvelopeUpdateRequest = apiComponents['schemas']['EsignEnvelopeUpdateRequest']
export type EsignEnvelopeDeliverySettingsUpdateRequest = apiComponents['schemas']['EsignEnvelopeDeliverySettingsUpdateRequest']
export type EsignRecipientInput = apiComponents['schemas']['EsignRecipientInput']
export type EsignRecipientResponse = apiComponents['schemas']['EsignRecipientResponse']
export type EsignFieldInput = apiComponents['schemas']['EsignFieldInput']
export type EsignFieldResponse = apiComponents['schemas']['EsignFieldResponse']
export type EsignAnchorSearchResponse = apiComponents['schemas']['EsignAnchorSearchResponse']
export type EsignDocumentResponse = apiComponents['schemas']['EsignDocumentResponse']
export type EsignAuditTrailResponse = apiComponents['schemas']['EsignAuditTrailResponse']
export type EsignEventResponse = apiComponents['schemas']['EsignEventResponse']
export type EsignDownloadResponse = apiComponents['schemas']['EsignDownloadResponse']
export type EsignInboxResponse = apiComponents['schemas']['EsignInboxResponse']
export type EsignInboxItem = apiComponents['schemas']['EsignInboxItem']
export type EsignSigningSessionResponse = apiComponents['schemas']['EsignSigningSessionResponse']
export type EsignSigningDocument = apiComponents['schemas']['EsignSigningDocument']
export type EsignSignerAttachmentResponse = apiComponents['schemas']['EsignSignerAttachmentResponse']
export type EsignConsentResponse = apiComponents['schemas']['EsignConsentResponse']
export type EsignSubmitRequest = apiComponents['schemas']['EsignSubmitRequest']
export type EsignFieldValueInput = apiComponents['schemas']['EsignFieldValueInput']
export type EsignFieldProperties = apiComponents['schemas']['EsignFieldProperties']
export type EsignPdfWidget = apiComponents['schemas']['EsignPdfWidget']
export type EsignPdfWidgetInspectionResponse = apiComponents['schemas']['EsignPdfWidgetInspectionResponse']
export type EsignPdfWidgetConversionRequest = apiComponents['schemas']['EsignPdfWidgetConversionRequest']
export type EsignSubmitResponse = apiComponents['schemas']['EsignSubmitResponse']
export type EsignSignatureInput = apiComponents['schemas']['EsignSignatureInput']
export type EsignCorrectionRequest = apiComponents['schemas']['EsignCorrectionRequest']
export type EsignReassignRequest = apiComponents['schemas']['EsignReassignRequest']
export type EsignManagedRecipientsRequest = apiComponents['schemas']['EsignManagedRecipientsRequest']
export type EsignManagedRecipientsResponse = apiComponents['schemas']['EsignManagedRecipientsResponse']
export type EsignWitnessRequest = apiComponents['schemas']['EsignWitnessRequest']
export type EsignInPersonStartRequest = apiComponents['schemas']['EsignInPersonStartRequest']
export type EsignGuestInvitationResponse = apiComponents['schemas']['EsignGuestInvitationResponse']
export type EsignVerifyResponse = apiComponents['schemas']['EsignVerifyResponse']
export type EsignTemplateResponse = apiComponents['schemas']['EsignTemplateResponse'] & { archived_at?: string | null }
export type EsignTemplateListResponse = Omit<apiComponents['schemas']['EsignTemplateListResponse'], 'templates'> & { templates: EsignTemplateResponse[] }
export type EsignTemplateRoleInput = apiComponents['schemas']['EsignTemplateRoleInput']
export type EsignTemplateUpdateRequest = apiComponents['schemas']['EsignTemplateUpdateRequest']
export type EsignTemplateFieldInput = apiComponents['schemas']['EsignTemplateFieldInput']
export type EsignTemplateVersionResponse = apiComponents['schemas']['EsignTemplateVersionResponse']
export type EsignTemplateVersionListResponse = apiComponents['schemas']['EsignTemplateVersionListResponse']
export type EsignBulkJobResponse = apiComponents['schemas']['EsignBulkJobResponse']
export type EsignBulkJobListResponse = apiComponents['schemas']['EsignBulkJobListResponse']
export type EsignPowerFormCreateRequest = apiComponents['schemas']['EsignPowerFormCreateRequest']
export type EsignPowerFormResponse = apiComponents['schemas']['EsignPowerFormResponse']
export type EsignPowerFormListResponse = apiComponents['schemas']['EsignPowerFormListResponse']
export type EsignReportSummary = apiComponents['schemas']['EsignReportSummary']
export type EsignScheduleRequest = apiComponents['schemas']['EsignScheduleRequest']

export const apiClient = new ApiClient()


export interface TeamMember { user_id: string; email: string; display_name: string | null; role: 'admin' | 'member' }
export interface TeamDetail { firm: { id: string; name: string }; members: TeamMember[]; invite_code: string | null }
