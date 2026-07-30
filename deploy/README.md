# Deploying Noesis

One vertical per deployment. The image serves the API + research console.

## Env vars

| Var | Purpose | Example |
|---|---|---|
| `NOESIS_ACTIVE_VERTICAL` | which installed vertical to activate | `regulatory` |
| `NOESIS_PROVIDER_MODE` | `replay` (offline/free) · `record` (real + save cassette) · `live` (real) | `live` in prod |
| `PORT` | HTTP port | `8000` (Railway sets this) |
| `ANTHROPIC_API_KEY` | LLM (record/live only) | secret |
| `OPENAI_API_KEY` | embeddings (record/live only) | secret |
| `TAVILY_API_KEY` | web search (record/live only) | secret |
| `NOESIS_LLM_MODEL` | override the Anthropic model | `claude-sonnet-5` |
| `NOESIS_CORPUS_DSN` | Postgres+pgvector DSN for the corpus (when wired) | `postgresql://…` |
| `NOESIS_CASSETTE_ROOT` | where cassettes live (replay/record) | `evals/cassettes` |

## Railway

1. New service from this repo (root `railway.toml` builds `deploy/Dockerfile`).
2. Set `NOESIS_ACTIVE_VERTICAL`, `NOESIS_PROVIDER_MODE=live`, and the API keys.
3. Add a Postgres (pgvector) service; set `NOESIS_CORPUS_DSN`.
4. Healthcheck is `/health`; the console is at `/`.

## Local

```bash
NOESIS_ACTIVE_VERTICAL=regulatory NOESIS_PROVIDER_MODE=replay \
  PYTHONPATH=packages/kernel:packages/vertical_regulatory:apps \
  .venv/bin/uvicorn api.app:create_app --factory --port 8000
```

## Notes / not-yet-wired
- The default corpus is the vertical's **fixture** until real ingestion → Postgres
  (with OpenAI embeddings) is wired; `/research` in `live` mode already produces
  real answers over it.
- `replay` needs recorded cassettes under `NOESIS_CASSETTE_ROOT`; `live` needs the
  API keys but no cassettes.
