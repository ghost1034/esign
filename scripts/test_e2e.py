"""Run live browser signing against disposable PostgreSQL, storage and signing keys.

Requires the local PostgreSQL and Mailpit services. No API responses are mocked.
"""
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time
import uuid
import zipfile

import httpx
import psycopg2
from psycopg2 import sql
import pymupdf
from sqlalchemy.engine import make_url


def main():
    root = Path(__file__).resolve().parents[1]
    url = make_url(os.getenv('ESIGN_TEST_ADMIN_URL', 'postgresql://esign:esign@127.0.0.1:55432/esign_dev'))
    if url.host not in {'127.0.0.1', 'localhost'}:
        raise SystemExit('E2E databases must be on localhost')
    # Never reuse an unrelated service or silently test the development database.
    for port in (8102, 8103, 3102):
        with socket.socket() as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            probe.bind(('127.0.0.1', port))
    httpx.get('http://127.0.0.1:8025/api/v1/info').raise_for_status()
    name = 'esign_e2e_' + uuid.uuid4().hex
    connection = psycopg2.connect(url.render_as_string(hide_password=False))
    connection.autocommit = True
    children = []
    try:
        with connection.cursor() as cursor:
            cursor.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
        with tempfile.TemporaryDirectory(prefix='esign-e2e-') as directory:
            temp = Path(directory)
            env = {
                **os.environ,
                'ENVIRONMENT': 'local', 'LOCAL_AUTH_BYPASS': 'true',
                'DATABASE_URL': url.set(database=name).render_as_string(hide_password=False),
                'STORAGE_BACKEND': 'local', 'TASK_BACKEND': 'local',
                'LOCAL_STORAGE_PATH': str(temp / 'storage'),
                'APP_BASE_URL': 'http://127.0.0.1:3102',
                'ESIGN_APP_BASE_URL': 'http://127.0.0.1:3102',
                'LOCAL_API_BASE_URL': 'http://127.0.0.1:8102',
                'PUBLIC_API_BASE_URL': 'http://127.0.0.1:8102',
                'LOCAL_WORKER_BASE_URL': 'http://127.0.0.1:8103',
                'LOCAL_AUTH_EMAIL': 'local.developer@example.com',
                'SMTP_HOST': '127.0.0.1', 'SMTP_PORT': '1025',
                'SMTP_SECURITY': 'none', 'SMTP_USERNAME': '', 'SMTP_PASSWORD': '',
                'SMTP_FROM': 'esign E2E <noreply@localhost>',
                'ESIGN_WEBHOOK_DISPATCH_ENABLED': 'false',
                'ESIGN_LOCAL_SIGNING_KEY_PATH': str(temp / 'signing-key.pem'),
                'ESIGN_SIGNING_CERT_PATH': str(temp / 'signing-cert.pem'),
                'ESIGN_SIGNING_CERT_PEM': '',
                'ESIGN_LOCAL_SIGNING_KEY_PEM': '', 'ESIGN_KMS_SIGNING_KEY_VERSION': '',
                'ESIGN_E2E_FIXTURES': str(temp),
            }
            subprocess.run([sys.executable, 'scripts/create_local_signer.py', '--output-dir', directory], cwd=root, check=True)
            with pymupdf.open() as pdf:
                page = pdf.new_page()
                page.insert_text((72, 72), 'Synthetic E2E fixture. No legal effect.')
                page.insert_text((72, 240), 'Signature:')
                page.insert_text((72, 320), 'Date:')
                pdf.save(temp / 'agreement.pdf')
            with zipfile.ZipFile(temp / 'attachment.docx', 'w') as docx:
                docx.writestr('[Content_Types].xml', '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
                docx.writestr('_rels/.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
                docx.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Synthetic Word conversion fixture. No legal effect.</w:t></w:r></w:p></w:body></w:document>')
            subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', 'head'], cwd=root / 'backend', env=env, check=True)
            with (temp / 'services.log').open('w+') as log:
                try:
                    for module, port in (('main', 8102), ('worker', 8103)):
                        child = subprocess.Popen([sys.executable, '-m', 'uvicorn', module + ':app', '--host', '127.0.0.1', '--port', str(port)], cwd=root / 'backend', env=env, stdout=log, stderr=log)
                        children.append(child)
                    deadline = time.monotonic() + 30
                    for port, path in ((8102, '/health'), (8103, '/openapi.json')):
                        while True:
                            if any(child.poll() is not None for child in children):
                                raise RuntimeError('E2E service exited during startup')
                            try:
                                httpx.get(f'http://127.0.0.1:{port}{path}', timeout=1).raise_for_status()
                                break
                            except httpx.HTTPError:
                                if time.monotonic() > deadline:
                                    raise RuntimeError('E2E service startup timed out')
                                time.sleep(0.2)
                    result = subprocess.run(['npx', 'playwright', 'test', '--config', 'playwright.e2e.config.ts', *sys.argv[1:]], cwd=root, env=env)
                    if result.returncode:
                        log.seek(0)
                        print(log.read()[-16000:])
                    return result.returncode
                finally:
                    for child in children:
                        child.terminate()
                    for child in children:
                        try:
                            child.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            child.kill()
                            child.wait()
    finally:
        with connection.cursor() as cursor:
            cursor.execute(sql.SQL('DROP DATABASE IF EXISTS {} WITH (FORCE)').format(sql.Identifier(name)))
        connection.close()


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(1))
    raise SystemExit(main())
