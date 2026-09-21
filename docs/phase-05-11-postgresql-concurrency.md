# Phase 05.11: PostgreSQL concurrent claim verification

The unit tests use SQLite for fast state-machine coverage. SQLite does not
implement PostgreSQL's `FOR UPDATE SKIP LOCKED` behavior, so it cannot prove
that two worker processes will avoid claiming the same investigation job.

`tests/test_postgresql_claims.py` is an opt-in integration test using the real
PostgreSQL driver. It creates the project tables inside a uniquely named
temporary schema, releases two claim attempts concurrently, and verifies that
exactly one worker owns the job, the attempt count is one, and only one start
audit event exists. The temporary schema is dropped during fixture cleanup.
No migration or runtime code changes are part of this slice.

## Run it locally

The test deliberately uses `TEST_DATABASE_URL`, not `DATABASE_URL`, and skips
when that variable is absent. The configured database user must be allowed to
create and drop schemas. It is safe to point both variables at the same local
development database because the test uses an isolated random schema rather
than the product tables.

In Git Bash, after setting the existing product database URL:

```bash
export TEST_DATABASE_URL="$DATABASE_URL"
python -m pytest -q tests/test_postgresql_claims.py
```

Expected result:

```text
1 passed
```

Then run the complete suite with the integration variable still set:

```bash
python -m pytest -q
python -m alembic current
```

The suite should include the PostgreSQL test rather than reporting it as
skipped. The migration revision remains `phase05_0002`.

If the test process is force-terminated before fixture cleanup, it may leave a
schema named `test_claims_<random hex>`. Inspect the exact schema name before
dropping it manually; never delete the `public` schema or product tables.
