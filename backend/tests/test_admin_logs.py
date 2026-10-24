from contextlib import contextmanager
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.api import admin_logs, auth
from app.services import logging_service


def test_admin_access_and_date_pagination_validation(monkeypatch):
    app = FastAPI()
    app.include_router(admin_logs.router, prefix='/api')
    role = [None]
    def user():
        if role[0] is None:
            raise HTTPException(401, 'Sign in required.')
        return {'id':1,'role':role[0]}
    app.dependency_overrides[auth.current_user] = user
    seen = []
    def logs(*args):
        seen.append(args)
        return {'status':'available','items':[],'total':0,'message':'Connected'}
    monkeypatch.setattr(admin_logs,'recent_analysis_logs',logs)
    with TestClient(app) as client:
        assert client.get('/api/admin/logs').status_code == 401
        role[0] = 'user'
        assert client.get('/api/admin/logs').status_code == 403
        assert seen == []
        role[0] = 'admin'
        response = client.get('/api/admin/logs?start_date=2026-10-01&end_date=2026-10-24&offset=20&limit=20')
        assert response.status_code == 200 and response.headers['cache-control'] == 'no-store'
        assert seen[-1] == (datetime(2026,10,1,tzinfo=timezone.utc),
                            datetime(2026,10,24,23,59,59,999999,tzinfo=timezone.utc),20,20)
        for query in ('offset=-1','limit=101','start_date=bad','start_date=2026-10-24&end_date=2026-10-01'):
            assert client.get('/api/admin/logs?'+query).status_code == 422
        assert len(seen) == 1


def test_disabled_logs_do_not_connect(monkeypatch):
    monkeypatch.delenv('DATABASE_URL', raising=False)
    def fail():
        raise AssertionError('Disabled logs must not connect')
    monkeypatch.setattr(logging_service,'engine',fail)
    result = logging_service.recent_analysis_logs()
    assert result['status'] == 'disabled' and result['items'] == []


def test_connection_failure_hides_credentials(monkeypatch):
    monkeypatch.setenv('DATABASE_URL','postgresql://user:private-password@private-host/db')
    def fail():
        raise RuntimeError('private-password private-host document text')
    monkeypatch.setattr(logging_service,'engine',fail)
    result = logging_service.recent_analysis_logs()
    assert result['status'] == 'unavailable' and result['items'] == []
    assert 'private-password' not in str(result) and 'private-host' not in str(result)


@pytest.mark.parametrize('table_exists',[False,True])
def test_log_queries_are_read_only_and_exclude_source_content(monkeypatch, table_exists):
    monkeypatch.setenv('DATABASE_URL','postgresql://configured')
    calls = []
    safe_row = {'id':1,'created_at':datetime(2026,10,24,tzinfo=timezone.utc),'character_count':500,
                'prediction':'Human','confidence':0.75,'model_mode':'model'}
    class Result:
        def __init__(self, value): self.value = value
        def scalar(self): return self.value
        def mappings(self): return self
        def all(self): return self.value
    class Engine:
        @contextmanager
        def connect(self): yield self
        def execute(self, query, args=None):
            sql = str(query)
            calls.append((sql,args))
            assert sql.startswith('SELECT')
            assert 'text_sha256' not in sql and 'evidence' not in sql and 'SELECT *' not in sql
            if 'to_regclass' in sql: return Result('lexitrace_analysis' if table_exists else None)
            if 'COUNT' in sql: return Result(1)
            return Result([safe_row])
    monkeypatch.setattr(logging_service,'engine',lambda:Engine())
    start,end = datetime(2026,10,1,tzinfo=timezone.utc),datetime(2026,10,24,tzinfo=timezone.utc)
    result = logging_service.recent_analysis_logs(start,end,20,20)
    assert result['status'] == 'available'
    if table_exists:
        assert result['items'] == [safe_row] and result['total'] == 1
        sql,args = calls[-1]
        assert 'created_at >= :start_at' in sql and 'created_at <= :end_at' in sql
        assert 'LIMIT :limit OFFSET :offset' in sql
        assert args == {'start_at':start,'end_at':end,'limit':20,'offset':20}
    else:
        assert result['items'] == [] and len(calls) == 1
