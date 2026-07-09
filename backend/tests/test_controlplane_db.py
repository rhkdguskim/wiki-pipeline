from backend.controlplane import db
from sqlalchemy.engine.url import make_url


def test_init_db_passes_unmasked_password_to_alembic(monkeypatch):
    captured = {}

    class Engine:
        url = make_url("postgresql+psycopg://wpipe:secret@db:5432/wpipe")

    def fake_upgrade(url: str) -> bool:
        captured["url"] = url
        return True

    monkeypatch.setattr(db, "_is_unversioned_existing_schema", lambda _engine: False)
    monkeypatch.setattr(db, "_alembic_upgrade_to_head", fake_upgrade)
    monkeypatch.setattr(db, "_ensure_critical_columns", lambda _engine: 0)

    db.init_db(Engine())

    assert captured["url"] == "postgresql+psycopg://wpipe:secret@db:5432/wpipe"
    assert "***" not in captured["url"]


def test_init_db_stamps_unversioned_existing_schema_before_upgrade(monkeypatch):
    calls = []

    class Metadata:
        @staticmethod
        def create_all(_engine):
            calls.append("create_all")

    class Engine:
        url = make_url("sqlite:///legacy.sqlite")

    monkeypatch.setattr(db, "Base", type("Base", (), {"metadata": Metadata}))
    monkeypatch.setattr(db, "_is_unversioned_existing_schema", lambda _engine: True)
    monkeypatch.setattr(db, "_alembic_stamp_head", lambda _url: calls.append("stamp"))
    monkeypatch.setattr(db, "_alembic_upgrade_to_head", lambda _url: calls.append("upgrade") or True)
    monkeypatch.setattr(db, "_ensure_critical_columns", lambda _engine: calls.append("critical") or 0)

    db.init_db(Engine())

    assert calls == ["create_all", "stamp", "upgrade", "critical"]
