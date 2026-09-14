"""Standalone boundaries: identity, team ownership, SMTP, and baseline integrity."""
import os
import uuid
from unittest.mock import patch
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import inspect, text
from main import app
from core.database import db_config
from dependencies.auth import verify_firebase_token
from models.db_models import Base, EsignEnvelope, User, UserRole
from services.esign.audit_service import extract_request_meta
from services.email_service import EmailService
from starlette.requests import Request

@pytest.fixture
def client():
    uid = 'standalone-' + uuid.uuid4().hex
    identity = {'uid': uid, 'email': uid+'@example.com', 'email_verified': True}
    app.dependency_overrides[verify_firebase_token] = lambda: identity
    with TestClient(app) as client:
        yield client, identity
    app.dependency_overrides.clear()

def test_explicit_onboarding_and_last_admin(client):
    c, identity = client
    assert c.get('/api/team/onboarding-status').json() == {'needs_onboarding': True}
    assert c.get('/api/esign/context').status_code == 403
    response = c.post('/api/team/create', json={'name': 'Standalone team'})
    assert response.status_code == 200, response.text
    assert c.get('/api/team/onboarding-status').json() == {'needs_onboarding': False}
    assert c.get('/api/esign/context').status_code == 200
    assert c.put('/api/team/members/'+identity['uid'], json={'role':'member'}).status_code == 400
    assert c.delete('/api/team/members/'+identity['uid']).status_code == 400
    assert c.post('/api/team/create', json={'name':'Duplicate'}).status_code == 409

def test_join_membership_is_not_an_admin_and_cannot_cross_teams(client):
    c, identity = client
    first_uid, first_email = identity['uid'], identity['email']
    first = c.post('/api/team/create', json={'name':'First team'}).json()
    identity.update(uid='join-'+uuid.uuid4().hex, email='join-'+uuid.uuid4().hex+'@example.com')
    joined = c.post('/api/team/join', json={'code':first['invite_code']})
    assert joined.status_code == 200, joined.text
    assert joined.json()['invite_code'] is None
    assert c.post('/api/team/invite-code').status_code == 403
    assert c.put('/api/team', json={'name':'Unauthorized rename'}).status_code == 403
    second_uid = identity['uid']
    identity.update(uid=first_uid, email=first_email)
    assert c.put('/api/team/members/'+second_uid, json={'role':'admin'}).status_code == 200
    assert c.delete('/api/team/members/'+second_uid).status_code == 200
    identity.update(uid=second_uid, email='join-'+uuid.uuid4().hex+'@example.com')
    with db_config.get_session() as db:
        user = db.query(User).filter_by(id=second_uid).one()
        assert user.firm_id is None and user.role != UserRole.ADMIN
    assert c.get('/api/esign/context').status_code == 403

def test_offboarding_requires_and_transfers_custody(client):
    c, identity = client
    owner_uid, owner_email = identity['uid'], identity['email']
    team = c.post('/api/team/create', json={'name':'Custody team'}).json()
    identity.update(uid='successor-'+uuid.uuid4().hex, email='successor-'+uuid.uuid4().hex+'@example.com')
    assert c.post('/api/team/join', json={'code':team['invite_code']}).status_code == 200
    successor = identity['uid']
    identity.update(uid=owner_uid,email=owner_email)
    assert c.put('/api/team/members/'+successor,json={'role':'admin'}).status_code == 200
    with db_config.get_session() as db:
        envelope = EsignEnvelope(user_id=owner_uid, firm_id=uuid.UUID(team['firm']['id']), title='Owned draft', consent_disclosure_text='Test disclosure')
        db.add(envelope);db.commit();envelope_id=envelope.id
    assert c.delete('/api/team/members/'+owner_uid).status_code == 409
    assert c.delete('/api/team/members/'+owner_uid,params={'successor_user_id':successor}).status_code == 200
    with db_config.get_session() as db:
        assert db.query(EsignEnvelope).filter_by(id=envelope_id).one().user_id == successor

def test_firebase_tokens_without_mfa_are_accepted_and_evidence_is_accurate():
    import asyncio
    from dependencies.auth import verify_firebase_token as verify
    from fastapi.security import HTTPAuthorizationCredentials
    token={'uid':'example', 'email':'example@example.com', 'firebase':{}}
    with patch.dict(os.environ, {'ENVIRONMENT':'production'}, clear=True), patch('dependencies.auth.init_firebase'), patch('dependencies.auth.firebase_auth.verify_id_token', return_value=token):
        decoded=asyncio.run(verify(HTTPAuthorizationCredentials(scheme='Bearer',credentials='test-token')))
    request=Request({'type':'http','headers':[], 'client':('127.0.0.1',1234)})
    assert extract_request_meta(request,decoded).mfa_verified is False
    assert extract_request_meta(request,{**decoded,'firebase':{'sign_in_second_factor':'phone'}}).mfa_verified is True

def test_smtp_preserves_multipart_content_and_reports_failure():
    with patch.dict(os.environ, {'ENVIRONMENT':'local','SMTP_SECURITY':'none'}, clear=True), patch('services.email_service.smtplib.SMTP') as smtp:
        smtp.return_value.__enter__.return_value.send_message.return_value={}
        assert EmailService().send_html_email('recipient@example.com','Test','<b>Test</b>','Test', inline_images=[('logo',b'png','image/png','logo.png')], attachments=[('record.pdf',b'pdf','application/pdf')])
        message=smtp.return_value.__enter__.return_value.send_message.call_args.args[0]
        assert any(p.get_filename()=='record.pdf' for p in message.walk())
        assert any(p.get('Content-ID')=='<logo>' for p in message.walk())
        smtp.return_value.__enter__.return_value.send_message.side_effect=OSError('connection failed')
        assert not EmailService().send_email('recipient@example.com','Test','Test')

def test_fresh_baseline_contains_only_app_tables_and_evidence_triggers():
    expected={'users','firms','firm_invite_codes'}
    assert all(name.startswith('esign_') or name in expected for name in Base.metadata.tables)
    with db_config.engine.connect() as conn:
        triggers={r[0] for r in conn.execute(text("SELECT tgname FROM pg_trigger WHERE NOT tgisinternal"))}
    assert {'trg_esign_events_append_only','trg_esign_recipient_changes_append_only','trg_esign_template_versions_immutable','trg_esign_admin_events_append_only','trg_esign_webhook_attempts_append_only'} <= triggers

def test_guest_cookie_is_scoped_to_the_actual_guest_api():
    from models.esign import EsignGuestExchangeResponse
    result=EsignGuestExchangeResponse(envelope_id='envelope',recipient_id='recipient',session_id='session',csrf_token='csrf',routing_version=1)
    with patch('routes.esign.esign_recipient_service.exchange_invitation',return_value=(result,'session-secret',None)):
        c=TestClient(app,base_url='https://testserver')
        response=c.post('/api/esign/guest/exchange',json={'invitation_token':uuid.uuid4().hex})
    assert response.status_code == 200, response.text
    cookie=response.headers['set-cookie']
    assert 'Path=/api/esign/guest/sessions/session' in cookie
    assert 'HttpOnly' in cookie and 'SameSite=strict' in cookie
