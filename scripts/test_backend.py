"""Run every backend test in a new disposable local database, with no PG skips."""
import os
import subprocess
import sys
import uuid
from pathlib import Path
import psycopg2
from psycopg2 import sql
from sqlalchemy.engine import make_url
root = Path(__file__).resolve().parents[1]
url = make_url(os.getenv('ESIGN_TEST_ADMIN_URL', 'postgresql://esign:esign@127.0.0.1:55432/esign_dev'))
if url.host not in {'127.0.0.1', 'localhost'}:
    raise SystemExit('This runner only creates test databases on localhost')
name = 'esign_test_' + uuid.uuid4().hex
connection = psycopg2.connect(url.render_as_string(hide_password=False))
connection.autocommit = True
with connection.cursor() as cursor: cursor.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
try:
    test_url = url.set(database=name).render_as_string(hide_password=False)
    env = {**os.environ, 'ENVIRONMENT': 'test', 'DATABASE_URL': test_url, 'ESIGN_TEST_DATABASE_URL': test_url, 'STORAGE_BACKEND': 'local', 'TASK_BACKEND': 'local'}
    subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', 'head'], cwd=root/'backend', env=env, check=True)
    result = subprocess.run([sys.executable, '-m', 'pytest', 'tests', '-q', '-ra', *sys.argv[1:]], cwd=root/'backend', env=env)
finally:
    with connection.cursor() as cursor: cursor.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))
    connection.close()
raise SystemExit(result.returncode)
