"""
SQLAlchemy database models for esign
Integration phase - supports multi-source ingestion, exports, and automations
"""
# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportGeneralTypeIssues=false, reportOptionalMemberAccess=false, reportReturnType=false

from typing import Optional, cast

import enum

from sqlalchemy import Column, String, Integer, BigInteger, Boolean, Text, TIMESTAMP, ForeignKey, UUID, LargeBinary, ARRAY, CheckConstraint, Numeric, Date, Enum, Index, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import expression, func, text
import uuid

Base = declarative_base()


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    ANALYST = "analyst"
    REVIEWER = "reviewer"
    VIEWER = "viewer"


class User(Base):
    """App-specific user profile data linked to Firebase Auth"""
    __tablename__ = "users"

    id = Column(String(128), primary_key=True)  # Firebase UID
    email = Column(String(255), unique=True, nullable=False)
    phone_number = Column(String(32), unique=True, nullable=True)
    phone_verified_at = Column(TIMESTAMP(timezone=True), nullable=True)
    display_name = Column(String(255))
    photo_url = Column(Text)
    firm_id = Column(UUID(as_uuid=True), ForeignKey("firms.id", ondelete="SET NULL"), nullable=True)
    role = Column(
        Enum(UserRole, name="user_role", create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        server_default=UserRole.ANALYST.value,
    )
    title = Column(String(255), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    firm = relationship("Firm", back_populates="users")


class Firm(Base):
    """Accounting firm — top-level multi-tenancy boundary for analytics data."""
    __tablename__ = "firms"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    users = relationship("User", back_populates="firm")
    invite_code = relationship("FirmInviteCode", back_populates="firm", cascade="all, delete-orphan", uselist=False)


class FirmInviteCode(Base):
    """Six-character code that lets new users join an existing analytics firm."""

    __tablename__ = "firm_invite_codes"

    code = Column(String(6), primary_key=True)
    firm_id = Column(UUID(as_uuid=True), ForeignKey("firms.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    firm = relationship("Firm", back_populates="invite_code")


class EsignEnvelopeStatus(str, enum.Enum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    SEND_FAILED = "send_failed"
    SENT = "sent"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    DECLINED = "declined"
    VOIDED = "voided"
    EXPIRED = "expired"


class EsignSigningType(str, enum.Enum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"


class EsignRecipientRole(str, enum.Enum):
    SIGNER = "signer"
    CC = "cc"
    APPROVER = "approver"
    CERTIFIED_DELIVERY = "certified_delivery"
    AGENT = "agent"
    EDITOR = "editor"
    WITNESS = "witness"
    IN_PERSON_SIGNER = "in_person_signer"


class EsignRecipientStatus(str, enum.Enum):
    PENDING = "pending"
    NOTIFIED = "notified"
    VIEWED = "viewed"
    CONSENTED = "consented"
    SIGNED = "signed"
    APPROVED = "approved"
    DELIVERED = "delivered"
    MANAGED = "managed"
    DECLINED = "declined"


class EsignFieldType(str, enum.Enum):
    SIGNATURE = "signature"
    INITIALS = "initials"
    DATE_SIGNED = "date_signed"
    TEXT = "text"
    CHECKBOX = "checkbox"
    AUTO_FILL = "auto_fill"
    ATTACHMENT = "attachment"
    RADIO = "radio"
    DROPDOWN = "dropdown"
    FORMULA = "formula"
    STAMP = "stamp"
    DATE = "date"
    NUMBER = "number"
    FIRST_NAME = "first_name"
    LAST_NAME = "last_name"
    FULL_NAME = "full_name"
    EMAIL = "email"
    COMPANY = "company"
    TITLE = "title"
    NOTE = "note"


class EsignSignatureType(str, enum.Enum):
    DRAWN = "drawn"
    TYPED = "typed"
    UPLOADED = "uploaded"


class EsignEventType(str, enum.Enum):
    CREATED = "created"
    SENT = "sent"
    VIEWED = "viewed"
    CONSENT_GIVEN = "consent_given"
    SIGNED = "signed"
    DECLINED = "declined"
    VOIDED = "voided"
    COMPLETED = "completed"
    REMINDER_SENT = "reminder_sent"
    SEALED = "sealed"
    EXPIRED = "expired"
    EXPIRATION_WARNING = "expiration_warning"
    CORRECTED = "corrected"
    REASSIGNED = "reassigned"
    APPROVED = "approved"
    DELIVERED = "delivered"
    MANAGER_ACTION = "manager_action"
    WITNESS_CONFIGURED = "witness_configured"
    HOST_HANDOFF = "host_handoff"
    GUEST_INVITATION_EXCHANGED = "guest_invitation_exchanged"
    GUEST_CONSENT_GIVEN = "guest_consent_given"
    ROUTING_ADVANCED = "routing_advanced"
    SCHEDULED = "scheduled"
    UNSCHEDULED = "unscheduled"
    SEND_FAILED = "send_failed"
    ACCESS_GRANTED = "access_granted"
    ACCESS_REVOKED = "access_revoked"
    OWNERSHIP_TRANSFERRED = "ownership_transferred"
    SETTINGS_UPDATED = "settings_updated"
    WEBHOOK_TEST = "webhook.test"


def _esign_enum(enum_cls, type_name: str):
    return Enum(enum_cls, name=type_name, create_type=False, values_callable=lambda x: [e.value for e in x])

class EsignEnvelope(Base):
    """An e-signature envelope: one or more PDFs sent for signing.

    Once sent, envelopes are never hard-deleted (void instead) — the
    append-only esign_events audit trail references them with
    ondelete=RESTRICT, which is the legally correct retention behavior for
    signed documents. Drafts are the one exception: nothing has been signed,
    so they can be deleted outright (see migration 043).
    """
    __tablename__ = "esign_envelopes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(128), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    firm_id = Column(UUID(as_uuid=True), ForeignKey("firms.id", ondelete="RESTRICT"), nullable=True)
    source_type = Column(String(20), nullable=False, default="manual", server_default="manual")
    source_id = Column(UUID(as_uuid=True), nullable=True)
    template_id = Column(UUID(as_uuid=True), ForeignKey("esign_templates.id", ondelete="SET NULL"), nullable=True)
    template_version_id = Column(UUID(as_uuid=True), ForeignKey("esign_template_versions.id", ondelete="SET NULL"), nullable=True)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=True)
    status = Column(
        _esign_enum(EsignEnvelopeStatus, "esign_envelope_status"),
        nullable=False,
        server_default=EsignEnvelopeStatus.DRAFT.value,
    )
    signing_type = Column(
        _esign_enum(EsignSigningType, "esign_signing_type"),
        nullable=False,
        server_default=EsignSigningType.SEQUENTIAL.value,
    )
    # Sender-selected display format shared by editable dates and date-signed.
    date_format = Column(String(32), nullable=False, default="MM/DD/YYYY", server_default="MM/DD/YYYY")
    current_routing_order = Column(Integer, nullable=True)  # set when sent
    routing_version = Column(Integer, nullable=False, default=1, server_default="1")
    # Optimistic concurrency token for mutable draft authoring. This is
    # intentionally separate from routing_version, which protects sent
    # ceremony actions and recipient evidence.
    draft_revision = Column(Integer, nullable=False, default=1, server_default="1")
    allow_reassignment = Column(Boolean, nullable=False, default=False, server_default=expression.false())
    # Access policy is snapshotted per envelope so already-sent envelopes keep
    # their original account-authenticated ceremony after email-link signing
    # becomes the default.
    recipient_access_mode = Column(String(32), nullable=False, default="email_link", server_default="email_link")
    # Snapshot of the ESIGN/UETA consent disclosure shown to signers; immutable
    # per envelope so consent records can be tied to the exact text.
    consent_disclosure_text = Column(Text, nullable=False)
    expires_at = Column(TIMESTAMP(timezone=True), nullable=True)
    reminder_interval_hours = Column(Integer, nullable=True)
    last_reminder_at = Column(TIMESTAMP(timezone=True), nullable=True)
    expiration_warning_sent_at = Column(TIMESTAMP(timezone=True), nullable=True)
    voided_reason = Column(Text, nullable=True)
    sealed_gcs_object_name = Column(Text, nullable=True)
    sealed_sha256 = Column(String(64), nullable=True)
    certificate_gcs_object_name = Column(Text, nullable=True)
    # Completion is a durable state machine. An envelope remains in progress
    # until its sealed object has been uploaded and the seal worker commits.
    sealing_state = Column(String(24), nullable=False, default="not_ready", server_default="not_ready")
    sealing_last_error = Column(Text, nullable=True)
    sealing_started_at = Column(TIMESTAMP(timezone=True), nullable=True)
    sent_at = Column(TIMESTAMP(timezone=True), nullable=True)
    completed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    voided_at = Column(TIMESTAMP(timezone=True), nullable=True)
    scheduled_at = Column(TIMESTAMP(timezone=True), nullable=True)
    schedule_timezone = Column(String(64), nullable=True)
    schedule_claimed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    send_error_code = Column(String(64), nullable=True)
    send_error_message = Column(Text, nullable=True)
    brand_id = Column(UUID(as_uuid=True), ForeignKey("esign_brand_profiles.id", ondelete="SET NULL"), nullable=True)
    brand_snapshot = Column(MutableDict.as_mutable(JSONB), nullable=True)
    settings_snapshot = Column(MutableDict.as_mutable(JSONB), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    user = relationship("User")
    documents = relationship(
        "EsignDocument",
        back_populates="envelope",
        cascade="all, delete-orphan",
        order_by="EsignDocument.display_order",
    )
    recipients = relationship(
        "EsignRecipient",
        back_populates="envelope",
        cascade="all, delete-orphan",
        order_by="EsignRecipient.routing_order",
    )
    fields = relationship("EsignField", back_populates="envelope", cascade="all, delete-orphan")
    events = relationship(
        "EsignEvent",
        back_populates="envelope",
        order_by="EsignEvent.created_at",
    )
    grants = relationship("EsignEnvelopeGrant", back_populates="envelope", cascade="all, delete-orphan")
    email_deliveries = relationship("EsignEmailDelivery", cascade="all, delete-orphan")
    work_items = relationship("EsignWorkItem", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_esign_envelopes_user_created", "user_id", "created_at"),
        Index("ix_esign_envelopes_firm_sent", "firm_id", "sent_at"),
        Index("ix_esign_envelopes_firm_status_source", "firm_id", "status", "source_type"),
        Index("ix_esign_envelopes_schedule_due", "status", "scheduled_at"),
    )


class EsignDocument(Base):
    """A single PDF within an envelope. The original object is immutable."""
    __tablename__ = "esign_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    envelope_id = Column(UUID(as_uuid=True), ForeignKey("esign_envelopes.id", ondelete="CASCADE"), nullable=False)
    display_order = Column(Integer, nullable=False, default=0)
    original_filename = Column(Text, nullable=False)
    gcs_object_name = Column(Text, unique=True, nullable=False)
    original_sha256 = Column(String(64), nullable=False)
    flattened_gcs_object_name = Column(Text, nullable=True)
    flattened_sha256 = Column(String(64), nullable=True)
    page_count = Column(Integer, nullable=False)
    file_size_bytes = Column(BigInteger, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    envelope = relationship("EsignEnvelope", back_populates="documents")
    fields = relationship("EsignField", back_populates="document", cascade="all, delete-orphan")


class EsignRecipient(Base):
    """A signer or CC party on an envelope, keyed by lowercased email."""
    __tablename__ = "esign_recipients"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    envelope_id = Column(UUID(as_uuid=True), ForeignKey("esign_envelopes.id", ondelete="CASCADE"), nullable=False)
    email = Column(String(255), nullable=True)  # always lowercased; null for unresolved placeholders
    name = Column(String(255), nullable=True)
    # Resolved lazily on the recipient's first authenticated access.
    recipient_user_id = Column(String(128), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    role = Column(
        _esign_enum(EsignRecipientRole, "esign_recipient_role"),
        nullable=False,
        server_default=EsignRecipientRole.SIGNER.value,
    )
    routing_order = Column(Integer, nullable=False, default=1)
    role_label = Column(String(255), nullable=True)
    template_role_id = Column(UUID(as_uuid=True), nullable=True)
    private_message = Column(Text, nullable=True)
    managed_by_recipient_id = Column(
        UUID(as_uuid=True), ForeignKey("esign_recipients.id", ondelete="RESTRICT"), nullable=True
    )
    witness_for_recipient_id = Column(
        UUID(as_uuid=True), ForeignKey("esign_recipients.id", ondelete="RESTRICT"), nullable=True
    )
    witness_mode = Column(String(16), nullable=True)
    host_name = Column(String(255), nullable=True)
    host_email = Column(String(255), nullable=True)
    host_user_id = Column(String(128), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    allow_reassignment = Column(Boolean, nullable=False, default=False, server_default=expression.false())
    status = Column(
        _esign_enum(EsignRecipientStatus, "esign_recipient_status"),
        nullable=False,
        server_default=EsignRecipientStatus.PENDING.value,
    )
    viewed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    consented_at = Column(TIMESTAMP(timezone=True), nullable=True)
    signed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    declined_at = Column(TIMESTAMP(timezone=True), nullable=True)
    declined_reason = Column(Text, nullable=True)
    action_completed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    # Temporary adopted artifacts used by Finish Later. Cleared on submit.
    draft_marks = Column(MutableDict.as_mutable(JSONB), nullable=True)
    identity_changed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    envelope = relationship("EsignEnvelope", back_populates="recipients")
    fields = relationship("EsignField", back_populates="recipient", cascade="all, delete-orphan")
    signature_records = relationship("EsignSignatureRecord", back_populates="recipient")
    consent_records = relationship("EsignConsentRecord", back_populates="recipient")
    managed_by = relationship("EsignRecipient", remote_side=[id], foreign_keys=[managed_by_recipient_id])
    witness_for = relationship("EsignRecipient", remote_side=[id], foreign_keys=[witness_for_recipient_id])

    __table_args__ = (
        Index(
            "uq_esign_recipients_envelope_email", "envelope_id", "email", unique=True,
            postgresql_where=text("email IS NOT NULL"),
        ),
        Index("ix_esign_recipients_email", "email"),
        Index("ix_esign_recipients_template_role", "envelope_id", "template_role_id"),
    )


class EsignRecipientChange(Base):
    """Immutable recipient correction/reassignment evidence."""
    __tablename__ = "esign_recipient_changes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    envelope_id = Column(UUID(as_uuid=True), ForeignKey("esign_envelopes.id", ondelete="RESTRICT"), nullable=False)
    # Deliberately not an FK: removed recipients retain their immutable UUID in
    # the assignment chain without an ON DELETE mutation of this append-only row.
    recipient_id = Column(UUID(as_uuid=True), nullable=True)
    envelope_version = Column(Integer, nullable=False)
    change_type = Column(String(64), nullable=False)
    actor_user_id = Column(String(128), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    actor_email = Column(String(255), nullable=True)
    reason = Column(Text, nullable=False)
    before_snapshot = Column(JSONB, nullable=True)
    after_snapshot = Column(JSONB, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (Index("ix_esign_recipient_changes_envelope", "envelope_id", "created_at"),)


class EsignGuestInvitation(Base):
    """Hashed bearer invitation for a recipient ceremony or completed copy."""
    __tablename__ = "esign_guest_invitations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    envelope_id = Column(UUID(as_uuid=True), ForeignKey("esign_envelopes.id", ondelete="RESTRICT"), nullable=False)
    recipient_id = Column(UUID(as_uuid=True), nullable=False)
    purpose = Column(String(32), nullable=False, default="ceremony", server_default="ceremony")
    token_sha256 = Column(String(64), unique=True, nullable=False)
    routing_version = Column(Integer, nullable=False)
    expires_at = Column(TIMESTAMP(timezone=True), nullable=False)
    exchanged_at = Column(TIMESTAMP(timezone=True), nullable=True)
    revoked_at = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_esign_guest_invitations_recipient", "recipient_id"),
        Index(
            "uq_esign_guest_invitations_active_purpose",
            "recipient_id", "purpose", unique=True,
            postgresql_where=text("revoked_at IS NULL"),
        ),
    )


class EsignGuestSession(Base):
    """Hashed guest-cookie session with idle/absolute expiry and one-time completion."""
    __tablename__ = "esign_guest_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    envelope_id = Column(UUID(as_uuid=True), ForeignKey("esign_envelopes.id", ondelete="RESTRICT"), nullable=False)
    recipient_id = Column(UUID(as_uuid=True), nullable=False)
    invitation_id = Column(UUID(as_uuid=True), ForeignKey("esign_guest_invitations.id", ondelete="RESTRICT"), nullable=False)
    token_sha256 = Column(String(64), unique=True, nullable=False)
    csrf_sha256 = Column(String(64), nullable=False)
    routing_version = Column(Integer, nullable=False)
    last_seen_at = Column(TIMESTAMP(timezone=True), nullable=False)
    idle_expires_at = Column(TIMESTAMP(timezone=True), nullable=False)
    absolute_expires_at = Column(TIMESTAMP(timezone=True), nullable=False)
    consumed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    revoked_at = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (Index("ix_esign_guest_sessions_recipient", "recipient_id"),)


class EsignField(Base):
    """A placed input field. Coordinates are fractions of page size (0..1),
    top-left origin; page_number is a 0-based page index within the document."""
    __tablename__ = "esign_fields"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    envelope_id = Column(UUID(as_uuid=True), ForeignKey("esign_envelopes.id", ondelete="CASCADE"), nullable=False)
    document_id = Column(UUID(as_uuid=True), ForeignKey("esign_documents.id", ondelete="CASCADE"), nullable=False)
    recipient_id = Column(UUID(as_uuid=True), ForeignKey("esign_recipients.id", ondelete="CASCADE"), nullable=False)
    field_type = Column(_esign_enum(EsignFieldType, "esign_field_type"), nullable=False)
    page_number = Column(Integer, nullable=False)  # 0-based page index
    pos_x = Column(Numeric(12, 10), nullable=False)
    pos_y = Column(Numeric(12, 10), nullable=False)
    width = Column(Numeric(12, 10), nullable=False)
    height = Column(Numeric(12, 10), nullable=False)
    required = Column(Boolean, nullable=False, default=True, server_default=expression.true())
    label = Column(String(255), nullable=True)
    value = Column(Text, nullable=True)
    # In-progress value saved by the signer ("Finish Later"); cleared when the
    # final value is written at submit. Never part of the sealed evidence.
    draft_value = Column(Text, nullable=True)
    properties = Column(
        MutableDict.as_mutable(JSONB),
        nullable=False,
        default=dict,
        server_default=expression.text("'{}'::jsonb"),
    )
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    envelope = relationship("EsignEnvelope", back_populates="fields")
    document = relationship("EsignDocument", back_populates="fields")
    recipient = relationship("EsignRecipient", back_populates="fields")
    attachments = relationship("EsignSignerAttachment", back_populates="field")

    __table_args__ = (
        CheckConstraint("pos_x >= 0 AND pos_x <= 1", name="ck_esign_fields_pos_x"),
        CheckConstraint("pos_y >= 0 AND pos_y <= 1", name="ck_esign_fields_pos_y"),
        CheckConstraint("width > 0 AND width <= 1", name="ck_esign_fields_width"),
        CheckConstraint("height > 0 AND height <= 1", name="ck_esign_fields_height"),
        CheckConstraint("pos_x + width <= 1", name="ck_esign_fields_horizontal_bounds"),
        CheckConstraint("pos_y + height <= 1", name="ck_esign_fields_vertical_bounds"),
        CheckConstraint("page_number >= 0", name="ck_esign_fields_page_number"),
        Index("ix_esign_fields_envelope", "envelope_id"),
    )


class EsignSignerAttachment(Base):
    """Signer-supplied evidence retained with the completed envelope."""
    __tablename__ = "esign_signer_attachments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    envelope_id = Column(UUID(as_uuid=True), ForeignKey("esign_envelopes.id", ondelete="RESTRICT"), nullable=False)
    recipient_id = Column(UUID(as_uuid=True), ForeignKey("esign_recipients.id", ondelete="RESTRICT"), nullable=False)
    field_id = Column(UUID(as_uuid=True), ForeignKey("esign_fields.id", ondelete="RESTRICT"), nullable=False)
    gcs_object_name = Column(Text, nullable=False)
    original_filename = Column(Text, nullable=False)
    sha256 = Column(String(64), nullable=False)
    file_size_bytes = Column(BigInteger, nullable=False)
    content_type = Column(String(100), nullable=False)
    uploaded_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    field = relationship("EsignField", back_populates="attachments")

    __table_args__ = (Index("ix_esign_signer_attachments_envelope", "envelope_id"),)


class EsignSignatureRecord(Base):
    """The 'Adopt and Sign' artifact for one signer. Never updated/deleted."""
    __tablename__ = "esign_signature_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    envelope_id = Column(UUID(as_uuid=True), ForeignKey("esign_envelopes.id", ondelete="RESTRICT"), nullable=False)
    recipient_id = Column(UUID(as_uuid=True), ForeignKey("esign_recipients.id", ondelete="RESTRICT"), nullable=False)
    signature_type = Column(_esign_enum(EsignSignatureType, "esign_signature_type"), nullable=False)
    image_gcs_object_name = Column(Text, nullable=True)
    image_sha256 = Column(String(64), nullable=True)
    typed_text = Column(Text, nullable=True)
    typed_font = Column(String(100), nullable=True)
    # Adopted initials: text always recorded (explicit or derived at adoption);
    # image only when the signer uploaded/drew dedicated initials.
    initials_text = Column(String(20), nullable=True)
    initials_type = Column(_esign_enum(EsignSignatureType, "esign_signature_type"), nullable=True)
    initials_typed_font = Column(String(100), nullable=True)
    initials_image_gcs_object_name = Column(Text, nullable=True)
    initials_image_sha256 = Column(String(64), nullable=True)
    # Schema-v2 stamps are independent from the normal signature image.
    stamp_type = Column(_esign_enum(EsignSignatureType, "esign_signature_type"), nullable=True)
    stamp_image_gcs_object_name = Column(Text, nullable=True)
    stamp_image_sha256 = Column(String(64), nullable=True)
    adopted_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    recipient = relationship("EsignRecipient", back_populates="signature_records")


class EsignConsentRecord(Base):
    """ESIGN/UETA consent-to-electronic-records record. Never updated/deleted."""
    __tablename__ = "esign_consent_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    envelope_id = Column(UUID(as_uuid=True), ForeignKey("esign_envelopes.id", ondelete="RESTRICT"), nullable=False)
    recipient_id = Column(UUID(as_uuid=True), ForeignKey("esign_recipients.id", ondelete="RESTRICT"), nullable=False)
    consent_text_sha256 = Column(String(64), nullable=False)
    ip_address = Column(String(64), nullable=True)
    user_agent = Column(Text, nullable=True)
    consented_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    recipient = relationship("EsignRecipient", back_populates="consent_records")


class EsignEvent(Base):
    """Append-only audit trail. A Postgres trigger (migrations 039/043)
    raises on any UPDATE, and on DELETE unless the envelope is still a draft;
    the RESTRICT envelope FK means only drafts can ever be hard-deleted."""
    __tablename__ = "esign_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    envelope_id = Column(UUID(as_uuid=True), ForeignKey("esign_envelopes.id", ondelete="RESTRICT"), nullable=False)
    event_type = Column(_esign_enum(EsignEventType, "esign_event_type"), nullable=False)
    actor_user_id = Column(String(128), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    actor_email = Column(String(255), nullable=True)  # denormalized snapshot
    # Immutable recipient UUID snapshot. No FK: recipient correction may remove
    # an outstanding slot without mutating this append-only audit evidence.
    recipient_id = Column(UUID(as_uuid=True), nullable=True)
    ip_address = Column(String(64), nullable=True)
    user_agent = Column(Text, nullable=True)
    mfa_verified = Column(Boolean, nullable=True)
    mfa_method = Column(String(32), nullable=True)
    mfa_phone_last4 = Column(String(4), nullable=True)
    details = Column(JSONB, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    envelope = relationship("EsignEnvelope", back_populates="events")

    __table_args__ = (
        Index("ix_esign_events_envelope_created", "envelope_id", "created_at"),
    )


class EsignTemplate(Base):
    """Reusable envelope layout. Fields bind to a recipient role index which is
    materialized to concrete recipients when an envelope is instantiated."""
    __tablename__ = "esign_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(128), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    firm_id = Column(UUID(as_uuid=True), ForeignKey("firms.id", ondelete="CASCADE"), nullable=True)
    brand_id = Column(UUID(as_uuid=True), ForeignKey("esign_brand_profiles.id", ondelete="SET NULL"), nullable=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    title = Column(String(255), nullable=True)  # default envelope title
    message = Column(Text, nullable=True)  # default envelope message
    signing_type = Column(
        _esign_enum(EsignSigningType, "esign_signing_type"),
        nullable=False,
        server_default=EsignSigningType.SEQUENTIAL.value,
    )
    date_format = Column(String(32), nullable=False, default="MM/DD/YYYY", server_default="MM/DD/YYYY")
    draft_revision = Column(Integer, nullable=False, default=1, server_default="1")
    # Ordered list of recipient roles: [{"label": "Client", "role": "signer", "routing_order": 1}, ...]
    recipient_roles = Column(JSONB, nullable=False, default=list, server_default=expression.text("'[]'::jsonb"))
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    archived_at = Column(TIMESTAMP(timezone=True), nullable=True)

    user = relationship("User")
    documents = relationship(
        "EsignTemplateDocument",
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="EsignTemplateDocument.display_order",
    )
    fields = relationship("EsignTemplateField", back_populates="template", cascade="all, delete-orphan")
    versions = relationship("EsignTemplateVersion", back_populates="template", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_esign_templates_user", "user_id"),
    )


class EsignTemplateDocument(Base):
    __tablename__ = "esign_template_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id = Column(UUID(as_uuid=True), ForeignKey("esign_templates.id", ondelete="CASCADE"), nullable=False)
    display_order = Column(Integer, nullable=False, default=0)
    original_filename = Column(Text, nullable=False)
    gcs_object_name = Column(Text, unique=True, nullable=False)
    sha256 = Column(String(64), nullable=False)
    page_count = Column(Integer, nullable=False)
    file_size_bytes = Column(BigInteger, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    template = relationship("EsignTemplate", back_populates="documents")
    fields = relationship("EsignTemplateField", back_populates="document", cascade="all, delete-orphan")


class EsignTemplateField(Base):
    """Template field bound to recipient_index into EsignTemplate.recipient_roles."""
    __tablename__ = "esign_template_fields"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id = Column(UUID(as_uuid=True), ForeignKey("esign_templates.id", ondelete="CASCADE"), nullable=False)
    template_document_id = Column(UUID(as_uuid=True), ForeignKey("esign_template_documents.id", ondelete="CASCADE"), nullable=False)
    recipient_index = Column(Integer, nullable=False)
    # Stable role binding. recipient_index remains as a read-time compatibility
    # fallback for legacy mutable templates and immutable published snapshots.
    recipient_role_id = Column(UUID(as_uuid=True), nullable=True)
    field_type = Column(_esign_enum(EsignFieldType, "esign_field_type"), nullable=False)
    page_number = Column(Integer, nullable=False)  # 0-based page index
    pos_x = Column(Numeric(12, 10), nullable=False)
    pos_y = Column(Numeric(12, 10), nullable=False)
    width = Column(Numeric(12, 10), nullable=False)
    height = Column(Numeric(12, 10), nullable=False)
    required = Column(Boolean, nullable=False, default=True, server_default=expression.true())
    label = Column(String(255), nullable=True)
    properties = Column(
        MutableDict.as_mutable(JSONB),
        nullable=False,
        default=dict,
        server_default=expression.text("'{}'::jsonb"),
    )
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    template = relationship("EsignTemplate", back_populates="fields")
    document = relationship("EsignTemplateDocument", back_populates="fields")

    __table_args__ = (
        CheckConstraint("pos_x >= 0 AND pos_x <= 1", name="ck_esign_template_fields_pos_x"),
        CheckConstraint("pos_y >= 0 AND pos_y <= 1", name="ck_esign_template_fields_pos_y"),
        CheckConstraint("width > 0 AND width <= 1", name="ck_esign_template_fields_width"),
        CheckConstraint("height > 0 AND height <= 1", name="ck_esign_template_fields_height"),
        CheckConstraint("pos_x + width <= 1", name="ck_esign_template_fields_horizontal_bounds"),
        CheckConstraint("pos_y + height <= 1", name="ck_esign_template_fields_vertical_bounds"),
        CheckConstraint("page_number >= 0", name="ck_esign_template_fields_page_number"),
        CheckConstraint("recipient_index >= 0", name="ck_esign_template_fields_recipient_index"),
        Index("ix_esign_template_fields_role", "template_id", "recipient_role_id"),
    )


class EsignAiFieldPlacementRun(Base):
    """Durable, advisory AI field suggestions for one mutable draft target."""
    __tablename__ = "esign_ai_field_placement_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    target_type = Column(String(16), nullable=False)  # envelope | template
    envelope_id = Column(
        UUID(as_uuid=True), ForeignKey("esign_envelopes.id", ondelete="CASCADE"), nullable=True
    )
    template_id = Column(
        UUID(as_uuid=True), ForeignKey("esign_templates.id", ondelete="CASCADE"), nullable=True
    )
    requester_user_id = Column(
        String(128), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    status = Column(String(16), nullable=False, default="queued", server_default="queued")
    scope = Column(String(24), nullable=False)  # all_documents | active_document
    selected_document_ids = Column(JSONB, nullable=False, default=list, server_default=expression.text("'[]'::jsonb"))
    target_snapshot = Column(JSONB, nullable=False, default=dict, server_default=expression.text("'{}'::jsonb"))
    base_revision = Column(Integer, nullable=False)
    instructions = Column(Text, nullable=True)
    proposals = Column(JSONB, nullable=False, default=list, server_default=expression.text("'[]'::jsonb"))
    warnings = Column(JSONB, nullable=False, default=list, server_default=expression.text("'[]'::jsonb"))
    issues = Column(JSONB, nullable=False, default=list, server_default=expression.text("'[]'::jsonb"))
    # Private evidence; intentionally excluded from the public run serializer.
    analysis_diagnostics = Column(JSONB, nullable=False, default=dict, server_default=expression.text("'{}'::jsonb"))
    inference_attempted_at = Column(TIMESTAMP(timezone=True), nullable=True)
    model_response = Column(JSONB, nullable=True)
    processing_token = Column(UUID(as_uuid=True), nullable=True)
    processing_deadline = Column(TIMESTAMP(timezone=True), nullable=True)
    processing_attempts = Column(Integer, nullable=False, default=0, server_default="0")
    error = Column(Text, nullable=True)
    page_usage = Column(Integer, nullable=False, default=0, server_default="0")
    started_at = Column(TIMESTAMP(timezone=True), nullable=True)
    completed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    applied_at = Column(TIMESTAMP(timezone=True), nullable=True)
    discarded_at = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    requester = relationship("User")
    envelope = relationship("EsignEnvelope")
    template = relationship("EsignTemplate")

    __table_args__ = (
        CheckConstraint(
            "(target_type = 'envelope' AND envelope_id IS NOT NULL AND template_id IS NULL) "
            "OR (target_type = 'template' AND template_id IS NOT NULL AND envelope_id IS NULL)",
            name="ck_esign_ai_placement_target",
        ),
        CheckConstraint("page_usage >= 0", name="ck_esign_ai_placement_page_usage"),
        Index("ix_esign_ai_placement_envelope_created", "envelope_id", "created_at"),
        Index("ix_esign_ai_placement_template_created", "template_id", "created_at"),
        Index("ix_esign_ai_placement_status", "status", "created_at"),
        Index(
            "uq_esign_ai_placement_active_envelope_scope", "envelope_id", "scope", unique=True,
            postgresql_where=text("envelope_id IS NOT NULL AND status IN ('queued', 'processing')"),
        ),
        Index(
            "uq_esign_ai_placement_active_template_scope", "template_id", "scope", unique=True,
            postgresql_where=text("template_id IS NOT NULL AND status IN ('queued', 'processing')"),
        ),
    )


class EsignTemplateVersion(Base):
    """Immutable published snapshot used by every scaled-send workflow."""
    __tablename__ = "esign_template_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id = Column(UUID(as_uuid=True), ForeignKey("esign_templates.id", ondelete="CASCADE"), nullable=False)
    firm_id = Column(UUID(as_uuid=True), ForeignKey("firms.id", ondelete="CASCADE"), nullable=False)
    version = Column(Integer, nullable=False)
    snapshot = Column(JSONB, nullable=False)
    published_by_user_id = Column(String(128), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    published_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    template = relationship("EsignTemplate", back_populates="versions")
    __table_args__ = (
        Index("uq_esign_template_versions_number", "template_id", "version", unique=True),
        Index("ix_esign_template_versions_firm", "firm_id", "published_at"),
    )


class EsignBulkJob(Base):
    __tablename__ = "esign_bulk_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    firm_id = Column(UUID(as_uuid=True), ForeignKey("firms.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String(128), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    template_version_id = Column(UUID(as_uuid=True), ForeignKey("esign_template_versions.id", ondelete="RESTRICT"), nullable=False)
    status = Column(String(32), nullable=False, server_default="validating")
    kind = Column(String(20), nullable=False, default="bulk", server_default="bulk")
    default_schedule_at = Column(TIMESTAMP(timezone=True), nullable=True)
    default_schedule_timezone = Column(String(64), nullable=True)
    total_rows = Column(Integer, nullable=False, server_default="0")
    valid_rows = Column(Integer, nullable=False, server_default="0")
    invalid_rows = Column(Integer, nullable=False, server_default="0")
    processed_rows = Column(Integer, nullable=False, server_default="0")
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    confirmed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    completed_at = Column(TIMESTAMP(timezone=True), nullable=True)

    rows = relationship("EsignBulkRow", back_populates="job", cascade="all, delete-orphan")
    __table_args__ = (Index("ix_esign_bulk_jobs_firm_created", "firm_id", "created_at"),)


class EsignBulkRow(Base):
    __tablename__ = "esign_bulk_rows"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("esign_bulk_jobs.id", ondelete="CASCADE"), nullable=False)
    row_number = Column(Integer, nullable=False)
    idempotency_key = Column(String(64), nullable=False, unique=True)
    normalized_input = Column(JSONB, nullable=False)
    status = Column(String(32), nullable=False)
    attempts = Column(Integer, nullable=False, server_default="0")
    error_code = Column(String(64), nullable=True)
    error_message = Column(Text, nullable=True)
    scheduled_at = Column(TIMESTAMP(timezone=True), nullable=True)
    schedule_timezone = Column(String(64), nullable=True)
    envelope_id = Column(UUID(as_uuid=True), ForeignKey("esign_envelopes.id", ondelete="SET NULL"), nullable=True, unique=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    job = relationship("EsignBulkJob", back_populates="rows")
    __table_args__ = (
        Index("uq_esign_bulk_rows_job_row", "job_id", "row_number", unique=True),
        Index("ix_esign_bulk_rows_job_status", "job_id", "status"),
    )


class EsignPowerForm(Base):
    __tablename__ = "esign_powerforms"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    firm_id = Column(UUID(as_uuid=True), ForeignKey("firms.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String(128), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    template_version_id = Column(UUID(as_uuid=True), ForeignKey("esign_template_versions.id", ondelete="RESTRICT"), nullable=False)
    brand_id = Column(UUID(as_uuid=True), ForeignKey("esign_brand_profiles.id", ondelete="SET NULL"), nullable=True)
    name = Column(String(255), nullable=False)
    public_token_sha256 = Column(String(64), nullable=False, unique=True)
    state = Column(String(20), nullable=False, server_default="active")
    starts_at = Column(TIMESTAMP(timezone=True), nullable=True)
    ends_at = Column(TIMESTAMP(timezone=True), nullable=True)
    submission_cap = Column(Integer, nullable=True)
    submission_count = Column(Integer, nullable=False, server_default="0")
    role_config = Column(JSONB, nullable=False)
    public_fields = Column(JSONB, nullable=False, server_default=expression.text("'[]'::jsonb"))
    instructions = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (Index("ix_esign_powerforms_firm", "firm_id", "created_at"),)


class EsignPowerFormSubmission(Base):
    __tablename__ = "esign_powerform_submissions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    powerform_id = Column(UUID(as_uuid=True), ForeignKey("esign_powerforms.id", ondelete="RESTRICT"), nullable=False)
    status = Column(String(24), nullable=False, server_default="pending_verification")
    normalized_input = Column(JSONB, nullable=False)
    initiating_email = Column(String(255), nullable=False)
    verification_token_sha256 = Column(String(64), nullable=False, unique=True)
    verification_expires_at = Column(TIMESTAMP(timezone=True), nullable=False)
    verified_at = Column(TIMESTAMP(timezone=True), nullable=True)
    consumed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    envelope_id = Column(UUID(as_uuid=True), ForeignKey("esign_envelopes.id", ondelete="SET NULL"), nullable=True, unique=True)
    consent = Column(Boolean, nullable=False, server_default=expression.false())
    ip_address = Column(String(64), nullable=True)
    user_agent = Column(Text, nullable=True)
    attempt_count = Column(Integer, nullable=False, server_default="0")
    last_error = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (Index("ix_esign_powerform_submissions_form", "powerform_id", "created_at"),)


class EsignWorkItem(Base):
    """Transactional outbox item for durable envelope lifecycle work."""
    __tablename__ = "esign_work_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    firm_id = Column(UUID(as_uuid=True), ForeignKey("firms.id", ondelete="CASCADE"), nullable=True)
    envelope_id = Column(UUID(as_uuid=True), ForeignKey("esign_envelopes.id", ondelete="CASCADE"), nullable=False)
    kind = Column(String(32), nullable=False)
    idempotency_key = Column(String(255), nullable=False, unique=True)
    state = Column(String(24), nullable=False, default="queued", server_default="queued")
    attempt_count = Column(Integer, nullable=False, default=0, server_default="0")
    next_attempt_at = Column(TIMESTAMP(timezone=True), nullable=False, default=func.now(), server_default=func.now())
    claimed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)
    payload = Column(MutableDict.as_mutable(JSONB), nullable=False, default=dict, server_default=expression.text("'{}'::jsonb"))
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    completed_at = Column(TIMESTAMP(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("envelope_id", "kind", name="uq_esign_work_items_envelope_kind"),
        Index("ix_esign_work_items_due", "state", "next_attempt_at"),
    )


class EsignEmailDelivery(Base):
    """Durable, independently retryable outbound email delivery."""
    __tablename__ = "esign_email_deliveries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    firm_id = Column(UUID(as_uuid=True), ForeignKey("firms.id", ondelete="CASCADE"), nullable=True)
    envelope_id = Column(UUID(as_uuid=True), ForeignKey("esign_envelopes.id", ondelete="CASCADE"), nullable=True)
    recipient_id = Column(UUID(as_uuid=True), nullable=True)
    kind = Column(String(48), nullable=False)
    to_email = Column(String(255), nullable=False)
    subject = Column(Text, nullable=False)
    html_body = Column(Text, nullable=False)
    text_body = Column(Text, nullable=False)
    idempotency_key = Column(String(255), nullable=False, unique=True)
    state = Column(String(24), nullable=False, default="queued", server_default="queued")
    attempt_count = Column(Integer, nullable=False, default=0, server_default="0")
    next_attempt_at = Column(TIMESTAMP(timezone=True), nullable=False, default=func.now(), server_default=func.now())
    last_error = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    delivered_at = Column(TIMESTAMP(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_esign_email_deliveries_due", "state", "next_attempt_at"),
        Index("ix_esign_email_deliveries_envelope", "envelope_id", "created_at"),
    )


class EsignFirmSettings(Base):
    __tablename__ = "esign_firm_settings"

    firm_id = Column(UUID(as_uuid=True), ForeignKey("firms.id", ondelete="CASCADE"), primary_key=True)
    version = Column(Integer, nullable=False, default=1, server_default="1")
    default_brand_id = Column(UUID(as_uuid=True), ForeignKey("esign_brand_profiles.id", ondelete="SET NULL"), nullable=True)
    date_format = Column(String(32), nullable=False, server_default="MM/DD/YYYY")
    signing_type = Column(String(20), nullable=False, server_default="sequential")
    expiration_days = Column(Integer, nullable=True, server_default="30")
    reminder_interval_hours = Column(Integer, nullable=True, server_default="72")
    allow_reassignment = Column(Boolean, nullable=False, server_default=expression.true())
    sender_overrides = Column(MutableDict.as_mutable(JSONB), nullable=False, default=dict, server_default=expression.text("'{}'::jsonb"))
    features = Column(MutableDict.as_mutable(JSONB), nullable=False, default=dict, server_default=expression.text("'{}'::jsonb"))
    updated_by_user_id = Column(String(128), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class EsignBrandAsset(Base):
    __tablename__ = "esign_brand_assets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    firm_id = Column(UUID(as_uuid=True), ForeignKey("firms.id", ondelete="CASCADE"), nullable=False)
    gcs_object_name = Column(Text, nullable=False, unique=True)
    content_type = Column(String(32), nullable=False)
    sha256 = Column(String(64), nullable=False)
    file_size_bytes = Column(BigInteger, nullable=False)
    created_by_user_id = Column(String(128), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    __table_args__ = (Index("ix_esign_brand_assets_firm", "firm_id", "created_at"),)


class EsignBrandProfile(Base):
    __tablename__ = "esign_brand_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    firm_id = Column(UUID(as_uuid=True), ForeignKey("firms.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    logo_asset_id = Column(UUID(as_uuid=True), ForeignKey("esign_brand_assets.id", ondelete="RESTRICT"), nullable=True)
    primary_color = Column(String(7), nullable=False, server_default="#1D4ED8")
    accent_color = Column(String(7), nullable=False, server_default="#0F172A")
    email_header = Column(Text, nullable=True)
    email_footer = Column(Text, nullable=True)
    reply_to_address = Column(String(255), nullable=True)
    signing_welcome_text = Column(Text, nullable=True)
    support_url = Column(Text, nullable=True)
    active = Column(Boolean, nullable=False, server_default=expression.true())
    allowed_profile_ids = Column(ARRAY(UUID(as_uuid=True)), nullable=True)
    created_by_user_id = Column(String(128), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    __table_args__ = (UniqueConstraint("firm_id", "name", name="uq_esign_brand_profiles_firm_name"),)


class EsignPermissionProfile(Base):
    __tablename__ = "esign_permission_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    firm_id = Column(UUID(as_uuid=True), ForeignKey("firms.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    capabilities = Column(MutableDict.as_mutable(JSONB), nullable=False, default=dict)
    built_in_key = Column(String(32), nullable=True)
    locked = Column(Boolean, nullable=False, server_default=expression.false())
    created_by_user_id = Column(String(128), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    __table_args__ = (
        UniqueConstraint("firm_id", "name", name="uq_esign_permission_profiles_firm_name"),
        UniqueConstraint("firm_id", "built_in_key", name="uq_esign_permission_profiles_builtin"),
    )


class EsignPermissionAssignment(Base):
    __tablename__ = "esign_permission_assignments"

    firm_id = Column(UUID(as_uuid=True), ForeignKey("firms.id", ondelete="CASCADE"), primary_key=True)
    user_id = Column(String(128), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    profile_id = Column(UUID(as_uuid=True), ForeignKey("esign_permission_profiles.id", ondelete="RESTRICT"), nullable=False)
    assigned_by_user_id = Column(String(128), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class EsignEnvelopeGrant(Base):
    __tablename__ = "esign_envelope_grants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    envelope_id = Column(UUID(as_uuid=True), ForeignKey("esign_envelopes.id", ondelete="CASCADE"), nullable=False)
    firm_id = Column(UUID(as_uuid=True), ForeignKey("firms.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String(128), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    access_level = Column(String(16), nullable=False)
    granted_by_user_id = Column(String(128), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    envelope = relationship("EsignEnvelope", back_populates="grants")
    __table_args__ = (
        UniqueConstraint("envelope_id", "user_id", name="uq_esign_envelope_grants_user"),
        CheckConstraint("access_level IN ('view', 'manage')", name="ck_esign_envelope_grants_level"),
        Index("ix_esign_envelope_grants_user", "firm_id", "user_id"),
    )


class EsignWebhookConfiguration(Base):
    __tablename__ = "esign_webhook_configurations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    firm_id = Column(UUID(as_uuid=True), ForeignKey("firms.id", ondelete="CASCADE"), nullable=False)
    envelope_id = Column(UUID(as_uuid=True), ForeignKey("esign_envelopes.id", ondelete="CASCADE"), nullable=True)
    endpoint_url = Column(Text, nullable=False)
    enabled = Column(Boolean, nullable=False, server_default=expression.true())
    event_filters = Column(ARRAY(String(64)), nullable=False, default=list)
    include_completed_documents = Column(Boolean, nullable=False, server_default=expression.false())
    secret_current = Column(Text, nullable=False)
    secret_previous = Column(Text, nullable=True)
    secret_previous_expires_at = Column(TIMESTAMP(timezone=True), nullable=True)
    created_by_user_id = Column(String(128), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    disabled_at = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    __table_args__ = (Index("ix_esign_webhook_configurations_scope", "firm_id", "envelope_id", "enabled"),)


class EsignWebhookDelivery(Base):
    __tablename__ = "esign_webhook_deliveries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    configuration_id = Column(UUID(as_uuid=True), ForeignKey("esign_webhook_configurations.id", ondelete="RESTRICT"), nullable=False)
    event_id = Column(UUID(as_uuid=True), ForeignKey("esign_events.id", ondelete="RESTRICT"), nullable=False)
    firm_id = Column(UUID(as_uuid=True), ForeignKey("firms.id", ondelete="CASCADE"), nullable=False)
    envelope_id = Column(UUID(as_uuid=True), ForeignKey("esign_envelopes.id", ondelete="RESTRICT"), nullable=False)
    payload = Column(MutableDict.as_mutable(JSONB), nullable=False)
    status = Column(String(24), nullable=False, server_default="pending")
    attempt_count = Column(Integer, nullable=False, server_default="0")
    next_attempt_at = Column(TIMESTAMP(timezone=True), nullable=True, server_default=func.now())
    claimed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    completed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    terminal_at = Column(TIMESTAMP(timezone=True), nullable=True)
    manual_retry_by_user_id = Column(String(128), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    __table_args__ = (
        UniqueConstraint("configuration_id", "event_id", name="uq_esign_webhook_delivery_event"),
        Index("ix_esign_webhook_deliveries_due", "status", "next_attempt_at"),
        Index("ix_esign_webhook_deliveries_firm", "firm_id", "created_at"),
    )


class EsignWebhookAttempt(Base):
    __tablename__ = "esign_webhook_attempts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    delivery_id = Column(UUID(as_uuid=True), ForeignKey("esign_webhook_deliveries.id", ondelete="RESTRICT"), nullable=False)
    attempt_number = Column(Integer, nullable=False)
    started_at = Column(TIMESTAMP(timezone=True), nullable=False)
    completed_at = Column(TIMESTAMP(timezone=True), nullable=False)
    duration_ms = Column(Integer, nullable=False)
    result = Column(String(24), nullable=False)
    http_status = Column(Integer, nullable=True)
    response_excerpt = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    __table_args__ = (UniqueConstraint("delivery_id", "attempt_number", name="uq_esign_webhook_attempt_number"),)


class EsignAdminEvent(Base):
    __tablename__ = "esign_admin_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    firm_id = Column(UUID(as_uuid=True), ForeignKey("firms.id", ondelete="RESTRICT"), nullable=False)
    actor_user_id = Column(String(128), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    actor_email = Column(String(255), nullable=True)
    event_type = Column(String(64), nullable=False)
    target_type = Column(String(32), nullable=True)
    target_id = Column(String(128), nullable=True)
    details = Column(MutableDict.as_mutable(JSONB), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    __table_args__ = (Index("ix_esign_admin_events_firm_created", "firm_id", "created_at"),)
