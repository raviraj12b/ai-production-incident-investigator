# Phase 05.12: authenticated reviewer decision

This slice adds the human decision boundary after a worker produces a report.
It deliberately does not accept a reviewer name in the request body. The
reviewer identity and bearer credential are configured in the API process as
`REVIEWER_ID` and `REVIEWER_API_KEY`; the key must contain at least 32
characters and is compared in constant time. Reviewer IDs are limited to 1–120
letters, digits, `.`, `_`, `@`, `+`, or `-`, beginning with a letter or digit.

The local MVP supports one configured reviewer identity. This is smaller and
safer than inventing JWT claims without an identity provider. It is not a
replacement for product-wide OAuth/OIDC: incident, evidence, and report routes
remain unauthenticated and must not be exposed publicly.

## Review contract

`PUT /api/v1/investigations/{id}/review` accepts:

```json
{
  "decision": "INCONCLUSIVE",
  "comment": "Deployment evidence is still required."
}
```

Allowed decisions are `ACCEPTED`, `REJECTED`, and `INCONCLUSIVE`. A decision is
accepted only when the investigation is `AWAITING_REVIEW` and has a report.
The transaction locks the investigation, creates its single review, changes
the investigation to `COMPLETED`, and records `INVESTIGATION_REVIEWED` with
the authenticated reviewer as the audit actor. It does not close the incident:
accepting an analysis is not proof that the operational incident is resolved.

An exact retry by the same reviewer returns the existing review. A changed
decision or comment returns 409 rather than overwriting audit history.
`GET /api/v1/investigations/{id}/review` requires the same authentication.

## Configure and verify locally

Generate a random key locally and copy it without committing it:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

In the Git Bash terminal used to start the backend API, set the identity and
paste the generated value without echoing it:

```bash
export REVIEWER_ID='rajesh-local'
read -rsp 'Reviewer API key: ' REVIEWER_API_KEY; export REVIEWER_API_KEY; echo
python -m uvicorn backend.main:app --port 8000
```

Set the same two variables in the curl terminal. For an investigation that is
already `AWAITING_REVIEW`, run:

```bash
curl -i -X PUT http://127.0.0.1:8000/api/v1/investigations/INVESTIGATION_ID/review \
  -H "Authorization: Bearer $REVIEWER_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"decision":"INCONCLUSIVE","comment":"Deployment evidence is still required."}'

curl -i http://127.0.0.1:8000/api/v1/investigations/INVESTIGATION_ID/review \
  -H "Authorization: Bearer $REVIEWER_API_KEY"

curl -i http://127.0.0.1:8000/api/v1/investigations/INVESTIGATION_ID
```

The PUT and review GET should return 200. The review must show
`reviewer: "rajesh-local"`, and the investigation must be `COMPLETED`. Repeating
the exact PUT must return the same review ID. Missing or incorrect credentials
return 401. Missing server configuration returns 503.

Run the complete suite with the existing PostgreSQL integration variable set:

```bash
export TEST_DATABASE_URL="$DATABASE_URL"
python -m pytest -q
python -m alembic current
```

The migration remains `phase05_0002`; this slice uses the existing `reviews`
table.
