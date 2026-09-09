import asyncio
import importlib
import sys
import types


class _FakeResponse:
    def __init__(self, data=None, count=None):
        self.data = data
        self.count = count


class _NotFilter:
    """Helper class to support .not_.is_() chaining pattern"""
    def __init__(self, query):
        self.query = query

    def is_(self, *args, **kwargs):
        return self.query._record("is_", *args, **kwargs)


class _FakeQuery:
    def __init__(self, table_name, events, responses):
        self.table_name = table_name
        self.events = events
        self.responses = responses
        self._not = _NotFilter(self)

    def _record(self, method, *args, **kwargs):
        self.events.append((self.table_name, method, args, kwargs))
        return self

    def select(self, *args, **kwargs):
        return self._record("select", *args, **kwargs)

    def eq(self, *args, **kwargs):
        return self._record("eq", *args, **kwargs)

    def neq(self, *args, **kwargs):
        return self._record("neq", *args, **kwargs)

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

    def delete(self, *args, **kwargs):
        return self._record("delete", *args, **kwargs)

    def upsert(self, *args, **kwargs):
        return self._record("upsert", *args, **kwargs)

    def gte(self, *args, **kwargs):
        return self._record("gte", *args, **kwargs)

    def in_(self, *args, **kwargs):
        return self._record("in_", *args, **kwargs)

    @property
    def not_(self):
        """Return a helper object that supports .is_() chaining"""
        return self._not

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
        'reel_title.ilike."*myquery*",reel_description.ilike."*myquery*"',
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
        'caption_title.ilike."*caption*",caption_description.ilike."*caption*"',
    )


def test_build_ilike_or_filter_escapes_postgrest_metacharacters(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)

    # Security regression test (audit finding P2-7): a raw comma/paren in the
    # search term used to let it break out of the ilike value and inject
    # extra filter clauses into the PostgREST `or=(...)` string. Wrapping the
    # value in double quotes (escaping embedded backslashes/quotes) keeps
    # those characters literal instead of structural.
    injected = 'x",other_column.eq.secret'
    result = supabase_request._build_ilike_or_filter(injected, ["title", "description"])

    assert result == (
        'title.ilike."*x\\",other_column.eq.secret*",'
        'description.ilike."*x\\",other_column.eq.secret*"'
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


def test_list_projects_applies_filters_and_pagination(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_PROJECTS_TABLE: [_FakeResponse(data=[{"id": "p1"}], count=4)]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    rows, total = asyncio.run(
        supabase_request.list_projects(
            user_id="u-1",
            page=2,
            page_size=10,
            project_type="reel",
            status="completed",
            query="name*",
        )
    )
    assert rows == [{"id": "p1"}]
    assert total == 4
    assert _event_args(fake_client.events, supabase_request.SUPABASE_PROJECTS_TABLE, "range") == (10, 19)
    eq_calls = [args for table, method, args, _ in fake_client.events if table == supabase_request.SUPABASE_PROJECTS_TABLE and method == "eq"]
    assert ("project_type", "reel") in eq_calls
    assert ("status", "completed") in eq_calls


def test_get_project_returns_first_or_none(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {
            supabase_request.SUPABASE_PROJECTS_TABLE: [
                _FakeResponse(data=[{"id": "p1"}]),
                _FakeResponse(data=[]),
            ]
        }
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)
    assert asyncio.run(supabase_request.get_project("p1", "u1")) == {"id": "p1"}
    assert asyncio.run(supabase_request.get_project("p2", "u1")) is None


def test_update_project_status_rejects_invalid_status(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    assert asyncio.run(supabase_request.update_project_status("", "completed")) is None
    assert asyncio.run(supabase_request.update_project_status("p1", "processing")) is None


def test_update_project_status_builds_payload(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient({supabase_request.SUPABASE_PROJECTS_TABLE: [_FakeResponse(data=[{"id": "p1", "status": "completed"}])]})
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    row = asyncio.run(supabase_request.update_project_status("p1", "completed"))
    assert row == {"id": "p1", "status": "completed"}
    payload = _event_args(fake_client.events, supabase_request.SUPABASE_PROJECTS_TABLE, "update")[0]
    assert payload["status"] == "completed"
    assert "completed_at" in payload
    assert "updated_at" in payload


def test_caption_status_value_defaults_to_termine(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    assert supabase_request.caption_status_value("en_cours") == "en_cours"
    assert supabase_request.caption_status_value("echec") == "echec"
    assert supabase_request.caption_status_value("other") == "termine"


def test_add_one_month_handles_december_and_month_end(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    from datetime import datetime

    # Test December to January
    dec = datetime(2024, 12, 15, 10, 30)
    result = supabase_request._add_one_month(dec)
    assert result.month == 1
    assert result.year == 2025
    assert result.day == 15

    # Test month-end handling (Jan 31 -> Feb 28)
    jan31 = datetime(2024, 1, 31, 10, 30)
    result = supabase_request._add_one_month(jan31)
    assert result.month == 2
    assert result.day == 29  # 2024 is a leap year


def test_insert_reels_returns_empty_for_empty_input(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    result = asyncio.run(supabase_request.insert_reels([]))
    assert result == []


def test_soft_delete_reel_returns_bool(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_REELS_TABLE: [_FakeResponse(data=[{"id": "r1"}])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    result = asyncio.run(supabase_request.soft_delete_reel("r1", "u1"))
    assert result is True


def test_get_reel_by_job_clip_returns_none_when_not_found(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_REELS_TABLE: [_FakeResponse(data=[])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    result = asyncio.run(supabase_request.get_reel_by_job_clip("job-x", 0))
    assert result is None


def test_update_reel_media_by_job_clip_returns_none_for_missing_params(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)

    # Missing reel_url
    result = asyncio.run(
        supabase_request.update_reel_media_by_job_clip("job-1", 0, "", None, None)
    )
    assert result is None

    # Missing job_id
    result = asyncio.run(
        supabase_request.update_reel_media_by_job_clip("", 0, "http://example.com/r.mp4", None, None)
    )
    assert result is None


def test_soft_delete_project_deletes_reels_captions_and_project(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient({
        supabase_request.SUPABASE_REELS_TABLE: [_FakeResponse(data=[])],
        supabase_request.SUPABASE_CAPTIONS_TABLE: [_FakeResponse(data=[])],
        supabase_request.SUPABASE_PROJECTS_TABLE: [_FakeResponse(data=[{"id": "p1"}])],
    })
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    result = asyncio.run(supabase_request.soft_delete_project("p1", "u1"))
    assert result is True


def test_get_reels_by_project_returns_empty_list_when_not_found(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_REELS_TABLE: [_FakeResponse(data=[])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    result = asyncio.run(supabase_request.get_reels_by_project("p-x"))
    assert result == []


def test_get_reels_by_project_returns_empty_for_empty_id(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    result = asyncio.run(supabase_request.get_reels_by_project(""))
    assert result == []


def test_get_captions_by_project_returns_empty_list(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_CAPTIONS_TABLE: [_FakeResponse(data=[])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    result = asyncio.run(supabase_request.get_captions_by_project("p-y"))
    assert result == []


def test_increment_project_output_count_increments_value(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient({
        supabase_request.SUPABASE_PROJECTS_TABLE: [
            _FakeResponse(data=[{"id": "p1", "output_count": 5}]),
            _FakeResponse(data=[{"id": "p1", "output_count": 6}]),
        ]
    })
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    result = asyncio.run(supabase_request.increment_project_output_count("p1"))
    assert result == {"id": "p1", "output_count": 6}


def test_increment_project_output_count_returns_none_when_not_found(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_PROJECTS_TABLE: [_FakeResponse(data=[])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    result = asyncio.run(supabase_request.increment_project_output_count("p-missing"))
    assert result is None


def test_insert_captions_returns_empty_for_empty_input(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    result = asyncio.run(supabase_request.insert_captions([]))
    assert result == []


def test_get_caption_returns_none_when_not_found(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_CAPTIONS_TABLE: [_FakeResponse(data=[])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    result = asyncio.run(supabase_request.get_caption("cap-missing", "u1"))
    assert result is None


def test_get_caption_by_job_clip_any_returns_none(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_CAPTIONS_TABLE: [_FakeResponse(data=[])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    result = asyncio.run(supabase_request.get_caption_by_job_clip_any("job-x", 0))
    assert result is None


def test_soft_delete_caption_returns_bool(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_CAPTIONS_TABLE: [_FakeResponse(data=[{"id": "c1"}])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    result = asyncio.run(supabase_request.soft_delete_caption("c1", "u1"))
    assert result is True


def test_get_transcription_by_job_clip_returns_none_for_missing_user(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    result = asyncio.run(supabase_request.get_transcription_by_job_clip("job-1", 0, ""))
    assert result is None


def test_upsert_transcription_returns_none_for_empty_row(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    result = asyncio.run(supabase_request.upsert_transcription(None))
    assert result is None


def test_upsert_transcription_returns_payload_when_no_response(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_TRANSCRIPTIONS_TABLE: [_FakeResponse(data=[])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    row = {"user_id": "u1", "job_id": "j1", "clip_index": 0}
    result = asyncio.run(supabase_request.upsert_transcription(row))
    assert result == row


def test_insert_style_edit_version_returns_none_for_empty_row(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    result = asyncio.run(supabase_request.insert_style_edit_version(None))
    assert result is None


def test_list_style_edit_versions_returns_empty_for_missing_params(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    result = asyncio.run(supabase_request.list_style_edit_versions("", 0, "u1"))
    assert result == []


def test_delete_style_edit_versions_returns_zero_for_missing_params(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    result = asyncio.run(supabase_request.delete_style_edit_versions("", 0, ""))
    assert result == 0


def test_list_abonnements_returns_data(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_ABONNEMENTS_TABLE: [_FakeResponse(data=[{"id": "a1"}])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    result = asyncio.run(supabase_request.list_abonnements())
    assert result == [{"id": "a1"}]


def test_get_abonnement_returns_none_when_not_found(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_ABONNEMENTS_TABLE: [_FakeResponse(data=[])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    result = asyncio.run(supabase_request.get_abonnement("a-missing"))
    assert result is None


def test_insert_souscription_builds_payload_with_dates(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_SOUSCRIPTION_TABLE: [_FakeResponse(data=[])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    result = asyncio.run(
        supabase_request.insert_souscription(
            user_id="u1",
            abonnement="plan-pro",
            payment_mode="stripe",
            payment_amount=99.99,
            payment_reference="ref-123",
            payment_status="confirmed",
        )
    )
    assert result["userid"] == "u1"
    assert result["abonnement"] == "plan-pro"
    assert "payment_start_date" in result
    assert "payment_end_date" in result


def test_get_souscription_by_reference_returns_none_for_empty(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    result = asyncio.run(supabase_request.get_souscription_by_reference(""))
    assert result is None


def test_get_souscription_by_reference_returns_none_when_not_found(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_SOUSCRIPTION_TABLE: [_FakeResponse(data=[])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    assert asyncio.run(supabase_request.get_souscription_by_reference("missing-ref")) is None


def test_get_user_abonnement_returns_none_when_not_found(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_SOUSCRIPTION_TABLE: [_FakeResponse(data=[])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    result = asyncio.run(supabase_request.get_user_abonnement("u-missing"))
    assert result is None


def test_get_latest_user_souscription_returns_none_for_empty_user_id(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    result = asyncio.run(supabase_request.get_latest_user_souscription(""))
    assert result is None


def test_get_latest_user_paid_subscription_returns_none_for_empty_user_id(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    result = asyncio.run(supabase_request.get_latest_user_paid_subscription(""))
    assert result is None


def test_list_user_souscriptions_returns_empty_for_empty_user_id(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    result = asyncio.run(supabase_request.list_user_souscriptions(""))
    assert result == []


def test_update_souscription_row_returns_none_for_empty_id(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    result = asyncio.run(supabase_request.update_souscription_row("", {"status": "cancelled"}))
    assert result is None


def test_get_job_record_returns_none_for_empty_id(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    result = asyncio.run(supabase_request.get_job_record(""))
    assert result is None


def test_get_latest_job_record_by_project_returns_none_for_empty_params(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    result = asyncio.run(supabase_request.get_latest_job_record_by_project("", "u1"))
    assert result is None


def test_append_job_log_does_nothing_for_empty_id(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    # Should not raise
    asyncio.run(supabase_request.append_job_log("", "INFO", "message"))


def test_list_job_logs_returns_empty_for_empty_id(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    result = asyncio.run(supabase_request.list_job_logs(""))
    assert result == []


def test_get_user_data_returns_none_for_empty_user_id(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    result = asyncio.run(supabase_request.get_user_data(""))
    assert result is None


def test_set_user_data_balance_returns_empty_dict_for_empty_user_id(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    result = asyncio.run(supabase_request.set_user_data_balance("", 100.0, 50.0))
    assert result == {"user_id": "", "credit": 0.0, "stockage": 0.0, "credit_max": 0.0, "stockage_max": 0.0}


def test_deduct_user_credits_returns_false_when_no_user_data(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_USER_DATA_TABLE: [_FakeResponse(data=[])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    result = asyncio.run(supabase_request.deduct_user_credits("u1", 10.0))
    assert result is False


def test_get_client_raises_when_not_configured(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    monkeypatch.setattr(supabase_request, "SUPABASE_URL", "")
    monkeypatch.setattr(supabase_request, "SUPABASE_SERVICE_ROLE_KEY", "")
    monkeypatch.setattr(supabase_request, "_client", None)

    try:
        asyncio.run(supabase_request.get_client())
        assert False, "Expected SupabaseNotConfiguredError"
    except supabase_request.SupabaseNotConfiguredError:
        pass


def test_insert_reels_returns_data_on_success(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient({supabase_request.SUPABASE_REELS_TABLE: [_FakeResponse(data=[{"id": "r-ok"}])]})
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    result = asyncio.run(supabase_request.insert_reels([{"reel_user_id": "u1"}]))
    assert result == [{"id": "r-ok"}]


def test_get_reel_returns_first_row_when_found(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient({supabase_request.SUPABASE_REELS_TABLE: [_FakeResponse(data=[{"id": "reel-1"}])]})
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    assert asyncio.run(supabase_request.get_reel("reel-1", "u1")) == {"id": "reel-1"}


def test_get_reel_by_job_clip_returns_first_row_when_found(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient({supabase_request.SUPABASE_REELS_TABLE: [_FakeResponse(data=[{"id": "reel-job"}])]})
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    assert asyncio.run(supabase_request.get_reel_by_job_clip("job-1", 0)) == {"id": "reel-job"}


def test_update_reel_media_by_job_clip_returns_none_when_update_empty(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient({supabase_request.SUPABASE_REELS_TABLE: [_FakeResponse(data=[])]})
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    result = asyncio.run(
        supabase_request.update_reel_media_by_job_clip("job-2", 1, "https://cdn.example/reel.mp4")
    )
    assert result is None


def test_update_project_returns_none_for_empty_project_id(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    result = asyncio.run(supabase_request.update_project("", "u1", {"name": "x"}))
    assert result is None


def test_get_captions_by_project_returns_empty_for_empty_project_id(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    assert asyncio.run(supabase_request.get_captions_by_project("")) == []


def test_increment_project_output_count_returns_none_for_empty_project_id(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    assert asyncio.run(supabase_request.increment_project_output_count("")) is None


def test_insert_captions_returns_rows_when_successful(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient({supabase_request.SUPABASE_CAPTIONS_TABLE: [_FakeResponse(data=[{"id": "cap-ok"}])]})
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    rows = asyncio.run(supabase_request.insert_captions([{"caption_user_id": "u1"}]))
    assert rows == [{"id": "cap-ok"}]


def test_get_caption_returns_first_row_when_found(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient({supabase_request.SUPABASE_CAPTIONS_TABLE: [_FakeResponse(data=[{"id": "cap-1"}])]})
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    assert asyncio.run(supabase_request.get_caption("cap-1", "u1")) == {"id": "cap-1"}


def test_get_caption_by_job_clip_returns_none_when_not_found(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient({supabase_request.SUPABASE_CAPTIONS_TABLE: [_FakeResponse(data=[])]})
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    assert asyncio.run(supabase_request.get_caption_by_job_clip("job-miss", 2, "u1")) is None


def test_update_caption_success_and_empty_id_paths(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    assert asyncio.run(supabase_request.update_caption("", "u1", {"caption_title": "x"})) is None

    fake_client = _FakeClient(
        {
            supabase_request.SUPABASE_CAPTIONS_TABLE: [
                _FakeResponse(data=[]),
                _FakeResponse(data=[{"id": "cap-2", "caption_title": "Updated"}]),
            ]
        }
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)
    row = asyncio.run(supabase_request.update_caption("cap-2", "u1", {"caption_title": "Updated"}))
    assert row == {"id": "cap-2", "caption_title": "Updated"}


def test_get_transcription_by_job_clip_returns_first_row(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient({supabase_request.SUPABASE_TRANSCRIPTIONS_TABLE: [_FakeResponse(data=[{"id": "tr-1"}])]})
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    assert asyncio.run(supabase_request.get_transcription_by_job_clip("job-1", 0, "u1")) == {"id": "tr-1"}


def test_update_transcription_translations_cache_paths(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    assert asyncio.run(
        supabase_request.update_transcription_translations_cache("", 0, "u1", {"fr": "x"})
    ) is None

    fake_client = _FakeClient({supabase_request.SUPABASE_TRANSCRIPTIONS_TABLE: [_FakeResponse(data=[])]})
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    async def _fake_get_transcription(job_id, clip_index, user_id):
        return {"job_id": job_id, "clip_index": clip_index, "user_id": user_id, "translations_cache": {"fr": "ok"}}

    monkeypatch.setattr(supabase_request, "get_transcription_by_job_clip", _fake_get_transcription)
    row = asyncio.run(
        supabase_request.update_transcription_translations_cache(
            "job-1", 2, "u1", {"fr": "ok"}, billing_details={"cost": 1}
        )
    )
    assert row["translations_cache"]["fr"] == "ok"


def test_style_edit_version_queries_success_paths(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {
            supabase_request.SUPABASE_STYLE_EDIT_VERSIONS_TABLE: [
                _FakeResponse(data=[{"id": "v1"}]),
                _FakeResponse(data=[{"id": "v1"}, {"id": "v2"}]),
                _FakeResponse(data=[{"id": "v1"}, {"id": "v2"}]),
            ]
        }
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    inserted = asyncio.run(supabase_request.insert_style_edit_version({"job_id": "j1", "clip_index": 0, "user_id": "u1"}))
    listed = asyncio.run(supabase_request.list_style_edit_versions("j1", 0, "u1"))
    deleted_count = asyncio.run(supabase_request.delete_style_edit_versions("j1", 0, "u1"))

    assert inserted == {"id": "v1"}
    assert listed == [{"id": "v1"}, {"id": "v2"}]
    assert deleted_count == 2


def test_subscription_read_paths_return_rows(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {
            supabase_request.SUPABASE_ABONNEMENTS_TABLE: [_FakeResponse(data=[{"id": "ab1"}])],
            supabase_request.SUPABASE_SOUSCRIPTION_TABLE: [
                _FakeResponse(data=[{"id": "sub-ref"}]),
                _FakeResponse(data=[{"id": "sub-active", "abonnement": "ab1"}]),
                _FakeResponse(data=[{"id": "sub-latest"}]),
                _FakeResponse(data=[{"id": "sub-paid"}]),
                _FakeResponse(data=[{"id": "sub-1"}, {"id": "sub-2"}]),
                _FakeResponse(data=[]),
                _FakeResponse(data=[{"id": "sub-updated"}]),
            ],
        }
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    assert asyncio.run(supabase_request.get_abonnement("ab1")) == {"id": "ab1"}

    async def _fake_get_abonnement(_ab_id):
        return {"id": "ab1", "priorite": "3"}

    monkeypatch.setattr(supabase_request, "get_abonnement", _fake_get_abonnement)
    assert asyncio.run(supabase_request.get_souscription_by_reference("ref-1")) == {"id": "sub-ref"}

    active = asyncio.run(supabase_request.get_user_abonnement("u1"))
    assert active["id"] == "sub-active"
    assert active["priorite"] == 3

    assert asyncio.run(supabase_request.get_latest_user_souscription("u1")) == {"id": "sub-latest"}
    assert asyncio.run(supabase_request.get_latest_user_paid_subscription("u1")) == {"id": "sub-paid"}
    assert asyncio.run(supabase_request.list_user_souscriptions("u1", limit=999)) == [{"id": "sub-1"}, {"id": "sub-2"}]
    assert asyncio.run(supabase_request.update_souscription_row("sub-1", {"payment_status": "cancelled"})) == {"id": "sub-updated"}


def test_get_user_abonnement_falls_back_to_priority_one_on_error(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_SOUSCRIPTION_TABLE: [_FakeResponse(data=[{"id": "sub-e", "abonnement": "ab-x"}])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    async def _boom(_ab_id):
        raise RuntimeError("lookup failed")

    monkeypatch.setattr(supabase_request, "get_abonnement", _boom)
    row = asyncio.run(supabase_request.get_user_abonnement("u1"))
    assert row["priorite"] == 1


def test_update_job_record_and_get_job_record_paths(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    assert asyncio.run(supabase_request.update_job_record("", {"status": "x"})) is None

    fake_client = _FakeClient(
        {
            supabase_request.SUPABASE_JOBS_TABLE: [
                _FakeResponse(data=[]),
                _FakeResponse(data=[{"id": "job-1", "status": "done"}]),
                _FakeResponse(data=[{"id": "job-1", "user_id": "u1"}]),
                _FakeResponse(data=[{"id": "job-1", "user_id": "u1"}]),
            ]
        }
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    updated = asyncio.run(supabase_request.update_job_record("job-1", {"status": "done"}))
    assert updated == {"id": "job-1", "status": "done"}

    row_any = asyncio.run(supabase_request.get_job_record("job-1"))
    row_scoped = asyncio.run(supabase_request.get_job_record("job-1", user_id="u1"))
    assert row_any == {"id": "job-1", "user_id": "u1"}
    assert row_scoped == {"id": "job-1", "user_id": "u1"}


def test_get_latest_job_record_by_project_match_and_none(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {
            supabase_request.SUPABASE_JOBS_TABLE: [
                _FakeResponse(data=[
                    {"id": "j0", "job_data": {"project_id": "p-x"}},
                    {"id": "j1", "job_data": {"project_id": "p-1"}},
                ]),
                _FakeResponse(data=[{"id": "j2", "job_data": {"project_id": "other"}}]),
            ]
        }
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    found = asyncio.run(supabase_request.get_latest_job_record_by_project("p-1", "u1"))
    not_found = asyncio.run(supabase_request.get_latest_job_record_by_project("p-missing", "u1"))

    assert found == {"id": "j1", "job_data": {"project_id": "p-1"}}
    assert not_found is None


def test_append_and_list_job_logs_paths(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {
            supabase_request.SUPABASE_JOB_LOGS_TABLE: [
                _FakeResponse(data=[]),
                _FakeResponse(data=[{"id": "l1", "level": "WARN"}], count=1),
            ]
        }
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    asyncio.run(supabase_request.append_job_log("job-1", "warn", "hello", {"step": 1}))
    rows = asyncio.run(supabase_request.list_job_logs("job-1", limit=9999))

    assert rows == [{"id": "l1", "level": "WARN"}]
    insert_payload = _event_args(fake_client.events, supabase_request.SUPABASE_JOB_LOGS_TABLE, "insert")[0]
    assert insert_payload["level"] == "WARN"
    assert insert_payload["metadata"] == {"step": 1}
    assert _event_args(fake_client.events, supabase_request.SUPABASE_JOB_LOGS_TABLE, "limit") == (1000,)


def test_list_recoverable_jobs_default_status_and_limit(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_JOBS_TABLE: [_FakeResponse(data=[{"id": "j-recover"}])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    rows = asyncio.run(supabase_request.list_recoverable_jobs("reels", limit=0))
    assert rows == [{"id": "j-recover"}]
    assert _event_args(fake_client.events, supabase_request.SUPABASE_JOBS_TABLE, "in_") == (
        "status", ["queued", "processing", "retry_wait"]
    )
    assert _event_args(fake_client.events, supabase_request.SUPABASE_JOBS_TABLE, "limit") == (1,)


def test_upsert_user_data_credits_existing_paths(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_USER_DATA_TABLE: [_FakeResponse(data=[{"user_id": "u1", "credit": 13.0}])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    async def _existing(_uid):
        return {
            "user_id": "u1",
            "credit": 10,
            "credit_debt": 5,
            "stockage": 2.0,
            "credit_max": 10,
            "stockage_max": 2.0,
        }

    bank_entry = types.SimpleNamespace(calls=[])

    async def _bank(**kwargs):
        bank_entry.calls.append(kwargs)
        return kwargs

    monkeypatch.setattr(supabase_request, "get_user_data", _existing)
    monkeypatch.setattr(supabase_request, "insert_user_credit_bank_entry", _bank)

    result = asyncio.run(
        supabase_request.upsert_user_data_credits(
            "u1",
            credit_delta=8,
            storage_delta=1.0,
            update_credit_max=True,
            update_stockage_max=True,
            operation_type="subscription",
            operation_id="sub-1",
        )
    )

    assert result["user_id"] == "u1"
    assert bank_entry.calls and bank_entry.calls[0]["direction"] == "debt_payment"


def test_upsert_user_data_credits_caps_credit_max_when_needed(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_USER_DATA_TABLE: [_FakeResponse(data=[{"user_id": "u2", "credit": 7.0}])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    async def _existing(_uid):
        return {
            "user_id": "u2",
            "credit": 5,
            "credit_debt": 0,
            "stockage": 1.0,
            "credit_max": 3,
            "stockage_max": 1.0,
        }

    monkeypatch.setattr(supabase_request, "get_user_data", _existing)
    monkeypatch.setattr(supabase_request, "insert_user_credit_bank_entry", lambda **_kwargs: None)

    asyncio.run(
        supabase_request.upsert_user_data_credits(
            "u2",
            credit_delta=2,
            storage_delta=0.0,
            update_credit_max=False,
            update_stockage_max=False,
        )
    )
    payload = _event_args(fake_client.events, supabase_request.SUPABASE_USER_DATA_TABLE, "update")[0]
    assert payload["credit"] == 7.0
    assert payload["credit_max"] == 7.0


def test_upsert_user_data_credits_create_user_path(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_USER_DATA_TABLE: [_FakeResponse(data=[])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    async def _missing(_uid):
        return None

    monkeypatch.setattr(supabase_request, "get_user_data", _missing)
    created = asyncio.run(supabase_request.upsert_user_data_credits("u3", 2.2, storage_delta=1.5))
    assert created["user_id"] == "u3"
    assert created["credit"] == 3
    assert created["stockage"] == 1.5


def test_set_user_data_balance_existing_and_insert_paths(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {
            supabase_request.SUPABASE_USER_DATA_TABLE: [
                _FakeResponse(data=[{"user_id": "u1", "credit": 7.0}]),
                _FakeResponse(data=[]),
            ]
        }
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    async def _existing(_uid):
        return {
            "user_id": "u1",
            "credit": 1,
            "credit_debt": 3,
            "stockage": 2.0,
            "credit_max": 2,
            "stockage_max": 2.0,
        }

    bank_calls = []

    async def _bank(**kwargs):
        bank_calls.append(kwargs)
        return kwargs

    monkeypatch.setattr(supabase_request, "get_user_data", _existing)
    monkeypatch.setattr(supabase_request, "insert_user_credit_bank_entry", _bank)
    updated = asyncio.run(supabase_request.set_user_data_balance("u1", credit=10, storage=3.0))
    assert updated["user_id"] == "u1"
    assert bank_calls and bank_calls[0]["direction"] == "debt_payment"

    async def _missing(_uid):
        return None

    monkeypatch.setattr(supabase_request, "get_user_data", _missing)
    inserted = asyncio.run(supabase_request.set_user_data_balance("u9", credit=4, storage=1.0))
    assert inserted["user_id"] == "u9"
    assert inserted["credit"] == 4


def test_deduct_user_credits_debt_and_storage_overage_paths(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_USER_DATA_TABLE: [_FakeResponse(data=[{"user_id": "u1"}])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    async def _existing_for_debt(_uid):
        return {
            "user_id": "u1",
            "credit": 2,
            "credit_debt": 1,
            "stockage": 0.0,
            "stockage_max": 10.0,
        }

    bank_calls = []

    async def _bank(**kwargs):
        bank_calls.append(kwargs)
        return kwargs

    monkeypatch.setattr(supabase_request, "get_user_data", _existing_for_debt)
    monkeypatch.setattr(supabase_request, "insert_user_credit_bank_entry", _bank)
    assert asyncio.run(supabase_request.deduct_user_credits("u1", credits=5, storage_delta=0.0)) is True
    assert bank_calls and bank_calls[0]["direction"] == "debt_increase"

    async def _existing_overage(_uid):
        return {
            "user_id": "u1",
            "credit": 100,
            "credit_debt": 0,
            "stockage": 0.0,
            "stockage_max": 10.0,
        }

    monkeypatch.setattr(supabase_request, "get_user_data", _existing_overage)
    assert asyncio.run(supabase_request.deduct_user_credits("u1", credits=1, storage_delta=-100.0)) is False


def test_insert_credit_bank_entry_and_user_history(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {
            supabase_request.SUPABASE_USER_CREDIT_BANK_TABLE: [_FakeResponse(data=[])],
            supabase_request.SUPABASE_USER_DATA_HISTORY_TABLE: [_FakeResponse(data=[])],
        }
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    entry = asyncio.run(
        supabase_request.insert_user_credit_bank_entry(
            user_id="u1",
            direction="  DEBT_PAYMENT  ",
            amount=-5,
            debt_balance_after=-1,
            operation_type="subscription",
            operation_id="op-1",
            metadata={"x": 1},
        )
    )
    history = asyncio.run(
        supabase_request.insert_user_data_history(
            user_id="u1",
            credit=2.2,
            storage=0.5,
            operation="output",
            operation_type="captions",
            operation_id="h-1",
        )
    )

    assert entry["direction"] == "debt_payment"
    assert entry["amount"] == 0.0
    assert entry["debt_balance_after"] == 0.0
    assert history["credit"] == 3
    assert history["operation_id"] == "h-1"


def test_get_user_data_history_query_and_pagination(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_USER_DATA_HISTORY_TABLE: [_FakeResponse(data=[{"id": "h1"}], count=4)]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    rows, total = asyncio.run(supabase_request.get_user_data_history("u1", page=0, page_size=999))
    assert rows == [{"id": "h1"}]
    assert total == 4
    assert _event_args(fake_client.events, supabase_request.SUPABASE_USER_DATA_HISTORY_TABLE, "range") == (0, 99)


def test_get_user_data_history_returns_empty_for_missing_user_id(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    rows, total = asyncio.run(supabase_request.get_user_data_history(""))
    assert rows == []
    assert total == 0




