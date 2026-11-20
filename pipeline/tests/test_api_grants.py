"""The web app reads through Supabase's API roles, so they need table grants that don't
depend on the project's default privileges (the hosted project had none: the review
queue came back empty). RLS still decides which rows a signed-in user sees."""

from conftest import REPO_ROOT

MIGRATION = REPO_ROOT / "supabase" / "migrations" / "0009_api_grants.sql"
TABLES = "select c.oid::regclass::text from pg_class c join pg_namespace n on n.oid = c.relnamespace " \
         "where n.nspname = 'public' and c.relkind = 'r'"


def _missing(db, role: str, privs: list[str]) -> list[str]:
    out = []
    for (table,) in db.execute(TABLES).fetchall():
        for p in privs:
            if not db.execute("select has_table_privilege(%s, %s, %s)", (role, table, p)).fetchone()[0]:
                out.append(f"{role} {p} {table}")
    return out


def _held(db, role: str) -> list[str]:
    out = []
    for (table,) in db.execute(TABLES).fetchall():
        for p in ["select", "insert", "update", "delete"]:
            if db.execute("select has_table_privilege(%s, %s, %s)", (role, table, p)).fetchone()[0]:
                out.append(f"{role} {p} {table}")
    return out


def _check(db):
    assert _missing(db, "service_role", ["select", "insert", "update", "delete"]) == []
    assert _missing(db, "authenticated", ["select", "insert", "update"]) == []
    assert _held(db, "anon") == []


def test_api_roles_have_table_grants_and_anon_has_none(db):
    _check(db)


def test_grants_migration_repairs_a_project_with_no_default_grants(db):
    db.execute("revoke all on all tables in schema public from anon, authenticated, service_role")
    db.execute(MIGRATION.read_text())
    _check(db)
