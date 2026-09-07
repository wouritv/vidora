import asyncio
import importlib
import sys
import types


class _FakeResponse:
    def __init__(self, data=None, count=None):
        self.data = data
        self.count = count


class _FakeQuery:
    def __init__(self, table_name, events, responses):
        self.table_name = table_name
        self.events = events
        self.responses = responses

    def _record(self, method, *args, **kwargs):
        self.events.append((self.table_name, method, args, kwargs))
        return self

    def select(self, *args, **kwargs):
        return self._record("select", *args, **kwargs)

    def eq(self, *args, **kwargs):
        return self._record("eq", *args, **kwargs)

    def is_(self, *args, **kwargs):
        return self._record("is_", *args, **kwargs)

    def order(self, *args, **kwargs):
        return self._record("order", *args, **kwargs)

    def range(self, *args, **kwargs):
        return self._record("range", *args, **kwargs)

    def or_(self, *args, **kwargs):
        return self._record("or_", *args, **kwargs)

    def limit(self, *args, **kwargs):
        return self._record("limit", *args, **kwargs)

    def update(self, *args, **kwargs):
        return self._record("update", *args, **kwargs)

    def insert(self, *args, **kwargs):
        return self._record("insert", *args, **kwargs)

    async def execute(self):
        self.events.append((self.table_name, "execute", (), {}))
        if self.responses:
            return self.responses.pop(0)
        return _FakeResponse(data=[], count=0)


class _FakeClient:
    def __init__(self, response_map):
        self.events = []
        self.response_map = {key: list(value) for key, value in (response_map or {}).items()}

    def table(self, table_name):
        self.events.append((table_name, "table", (), {}))
        return _FakeQuery(table_name, self.events, self.response_map.setdefault(table_name, []))


def _event_args(events, table, method):
    for event_table, event_method, args, _kwargs in events:
        if event_table == table and event_method == method:
            return args
    return None


def _event_count(events, table, method):
    return sum(1 for event_table, event_method, _args, _kwargs in events if event_table == table and event_method == method)


def _patch_get_client(monkeypatch, supabase_request, fake_client):
    async def _fake_get_client():
        return fake_client

    monkeypatch.setattr(supabase_request, "get_client", _fake_get_client)


def _import_supabase_request_with_stubs(monkeypatch):
    supabase_mod = types.ModuleType("supabase")

    class _AsyncClient:
        pass

    async def _acreate_client(*args, **kwargs):
        return {"url": args[0], "key": args[1], "options": kwargs.get("options")}

    supabase_mod.AsyncClient = _AsyncClient
    supabase_mod.acreate_client = _acreate_client

    client_options_mod = types.ModuleType("supabase.lib.client_options")

    class _AsyncClientOptions:
        def __init__(self, postgrest_client_timeout):
            self.postgrest_client_timeout = postgrest_client_timeout

    client_options_mod.AsyncClientOptions = _AsyncClientOptions

    monkeypatch.setitem(sys.modules, "supabase", supabase_mod)
    monkeypatch.setitem(sys.modules, "supabase.lib.client_options", client_options_mod)

    if "supabase_request" in sys.modules:
        return importlib.reload(sys.modules["supabase_request"])
    return importlib.import_module("supabase_request")


def test_is_supabase_configured_reflects_module_settings(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)

    monkeypatch.setattr(supabase_request, "SUPABASE_URL", "https://db.example")
    monkeypatch.setattr(supabase_request, "SUPABASE_SERVICE_ROLE_KEY", "secret")
    assert supabase_request.is_supabase_configured() is True

    monkeypatch.setattr(supabase_request, "SUPABASE_SERVICE_ROLE_KEY", "")
    assert supabase_request.is_supabase_configured() is False


def test_ceil_credit_rounds_up_and_never_negative(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)

    assert supabase_request._ceil_credit(2.01) == 3
    assert supabase_request._ceil_credit(0) == 0
    assert supabase_request._ceil_credit(-10) == 0


def test_get_client_creates_singleton_once(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    monkeypatch.setattr(supabase_request, "SUPABASE_URL", "https://db.example")
    monkeypatch.setattr(supabase_request, "SUPABASE_SERVICE_ROLE_KEY", "secret")
    monkeypatch.setattr(supabase_request, "_client", None)

    client_1 = asyncio.run(supabase_request.get_client())
    client_2 = asyncio.run(supabase_request.get_client())

    assert client_1 == client_2


def test_list_reels_builds_expected_query_and_escapes_search(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_REELS_TABLE: [_FakeResponse(data=[{"id": "r1"}], count=7)]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    rows, total = asyncio.run(
        supabase_request.list_reels("user-1", page=0, page_size=999, status="termine", query="my*query")
    )

    assert rows == [{"id": "r1"}]
    assert total == 7
    assert _event_args(fake_client.events, supabase_request.SUPABASE_REELS_TABLE, "range") == (0, 99)
    assert _event_args(fake_client.events, supabase_request.SUPABASE_REELS_TABLE, "or_") == (
        "reel_title.ilike.*myquery*,reel_description.ilike.*myquery*",
    )


def test_list_captions_uses_caption_columns_and_filters(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_CAPTIONS_TABLE: [_FakeResponse(data=[{"id": "c1"}], count=2)]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    rows, total = asyncio.run(
        supabase_request.list_captions("user-2", page=2, page_size=20, status="en_cours", query="cap*tion")
    )

    assert rows == [{"id": "c1"}]
    assert total == 2
    assert _event_args(fake_client.events, supabase_request.SUPABASE_CAPTIONS_TABLE, "select") == (
        supabase_request.CAPTION_COLUMNS,
    )
    assert _event_args(fake_client.events, supabase_request.SUPABASE_CAPTIONS_TABLE, "range") == (20, 39)
    assert _event_args(fake_client.events, supabase_request.SUPABASE_CAPTIONS_TABLE, "or_") == (
        "caption_title.ilike.*caption*,caption_description.ilike.*caption*",
    )


def test_get_reel_returns_none_when_empty(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient({supabase_request.SUPABASE_REELS_TABLE: [_FakeResponse(data=[])]})
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    result = asyncio.run(supabase_request.get_reel("reel-x", "user-x"))

    assert result is None
    assert _event_args(fake_client.events, supabase_request.SUPABASE_REELS_TABLE, "limit") == (1,)


def test_update_reel_media_by_job_clip_builds_payload_and_casts_clip_index(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_REELS_TABLE: [_FakeResponse(data=[{"id": "row-1"}])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    row = asyncio.run(
        supabase_request.update_reel_media_by_job_clip(
            job_id="job-1",
            clip_index="3",
            reel_url="https://cdn.example/reel.mp4",
            reel_s3_key="reels/u/job-1/reel.mp4",
            reel_thumbnail_url="",
        )
    )

    assert row == {"id": "row-1"}
    update_payload = _event_args(fake_client.events, supabase_request.SUPABASE_REELS_TABLE, "update")[0]
    assert update_payload["reel_url"] == "https://cdn.example/reel.mp4"
    assert update_payload["reel_s3_key"] == "reels/u/job-1/reel.mp4"
    assert "reel_thumbnail_url" in update_payload
    assert "reel_updated_at" in update_payload

    eq_calls = [args for table, method, args, _ in fake_client.events if table == supabase_request.SUPABASE_REELS_TABLE and method == "eq"]
    assert ("reel_clip_index", 3) in eq_calls


def test_create_project_returns_payload_fallback_and_maps_fields(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient({supabase_request.SUPABASE_PROJECTS_TABLE: [_FakeResponse(data=[])]})
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    result = asyncio.run(
        supabase_request.create_project(
            user_id="user-p",
            name="Project A",
            project_type="reel",
            source_type="file",
            source_s3_key="uploads/a.mp4",
            source_size="1024",
            description="desc",
            source_url="https://example.com/a.mp4",
            source_duration=70,
            thumbnail_url="https://example.com/t.jpg",
            status="processing",
        )
    )

    assert result["user_id"] == "user-p"
    assert result["source_size"] == 1024
    assert result["output_count"] == 0
    assert result["status"] == "processing"
    assert "created_at" in result and "updated_at" in result


def test_update_project_adds_updated_at_and_returns_selected_row(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {
            supabase_request.SUPABASE_PROJECTS_TABLE: [
                _FakeResponse(data=[]),
                _FakeResponse(data=[{"id": "proj-1", "name": "Updated"}]),
            ]
        }
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    result = asyncio.run(
        supabase_request.update_project("proj-1", "user-9", {"name": "Updated", "status": "completed"})
    )

    assert result == {"id": "proj-1", "name": "Updated"}
    update_payload = _event_args(fake_client.events, supabase_request.SUPABASE_PROJECTS_TABLE, "update")[0]
    assert update_payload["name"] == "Updated"
    assert update_payload["status"] == "completed"
    assert "updated_at" in update_payload
    assert _event_count(fake_client.events, supabase_request.SUPABASE_PROJECTS_TABLE, "execute") == 2


def test_create_job_record_clamps_priority_and_attempts(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient({supabase_request.SUPABASE_JOBS_TABLE: [_FakeResponse(data=[])]})
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    payload = asyncio.run(
        supabase_request.create_job_record(
            job_id="job-raw",
            user_id="user-j",
            job_type="GENERATE_REELS",
            status="created",
            job_data={},
            queue_name="reels",
            pipeline_name="pipe",
            max_attempts=0,
            reserved_quota="1.5",
            estimated_cost_usd="0.25",
            priority=99,
        )
    )

    assert payload["max_attempts"] == 1
    assert payload["priority"] == 3
    assert payload["reserved_quota"] == 1.5
    assert payload["estimated_cost_usd"] == 0.25
    assert payload["current_step"] == "created"


def test_get_caption_by_job_clip_casts_index_and_returns_first_row(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_CAPTIONS_TABLE: [_FakeResponse(data=[{"id": "cap-x"}])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    row = asyncio.run(supabase_request.get_caption_by_job_clip("job-c", "4", "user-c"))

    assert row == {"id": "cap-x"}
    eq_calls = [args for table, method, args, _ in fake_client.events if table == supabase_request.SUPABASE_CAPTIONS_TABLE and method == "eq"]
    assert ("caption_clip_index", 4) in eq_calls
    assert _event_args(fake_client.events, supabase_request.SUPABASE_CAPTIONS_TABLE, "limit") == (1,)


