# akd-ext

Misc extension to [akd-core](https://github.com/NASA-IMPACT/accelerated-discovery/).

## Documentation

- [Creating Agents](docs/development/creating_agents.md) — guide for building new agents on `OpenAIBaseAgent` or `PydanticAIBaseAgent`, including config, schemas, tools, capabilities, tests, and reference examples.

## Installation

### Using uv (recommended)

```bash
uv pip install git+https://github.com/NASA-IMPACT/akd-ext.git@develop
```

### For development

```bash
git clone https://github.com/NASA-IMPACT/akd-ext.git
cd akd-ext
git checkout develop
uv venv --python 3.12
uv sync  # preferred
source .venv/bin/activate
```

### Running scripts

The best way to execute scripts is with `uv run`:

```bash
uv run python your_script.py
```

## MCP server

This deployment exposes exactly two tools over MCP, both backed by the SDE search API:

| Tool | Purpose |
| --- | --- |
| `sde_search_tool` | Search NASA's Science Discovery Engine (`/api/search`) across all indexed document types. |
| `repository_search_tool` | Search code repositories (`/api/code/search`) and enrich GitHub hits with repository metadata and a reliability score. |

Run it locally:

```bash
uv run python -m akd_ext.mcp.server                  # stdio (default)
uv run python -m akd_ext.mcp.server --transport sse  # http/sse on :8000
```

### Deploying to FastMCP Cloud

Point a FastMCP Cloud project at this repository on branch `deploy/sde-repo-search`, with entrypoint
`akd_ext/mcp/server.py:mcp`, and set `GITHUB_ACCESS_TOKEN` (and optionally `SDE_BASE_URL`) in the
project's environment.

This branch ends with three `(deployment-only)` commits that trim the exposed tool set. They are not
meant for `NASA-IMPACT/akd-ext`; the upstream pull request is opened from
`fix/sde-search-endpoint-min-score`, which stops just below them. When those fixes change, rebase
this branch onto the new tip rather than editing it:

```bash
git rebase --onto fix/sde-search-endpoint-min-score <old-fix-tip> deploy/sde-repo-search
```

### Environment

| Variable | Required | Notes |
| --- | --- | --- |
| `SDE_BASE_URL` | No | SDE API host. Defaults to `https://dyejsbdumgpqz.cloudfront.net`. |
| `GITHUB_ACCESS_TOKEN` | Recommended | Without it GitHub throttles at 60 req/hour and `reliability_score` comes back `null`. |

### `min_score` and the SDE backend

Both tools send `min_score` on every request — `sde_search_tool` on `/api/search`,
`repository_search_tool` on `/api/code/search`. It is a lower bound on the `_score` each document is
returned with, and the endpoint applies a server-side default of `0.55` when the field is omitted,
which is above the score most documents receive — so omitting it silently returns nothing. The tools
default to `min_score=0.0` and expose it as a config field.

Measured against the current endpoint, for `"UF universal format weather radar .uf reader python
reflectivity"`:

| `min_score` | results |
| --- | --- |
| omitted (server default `0.55`) | 0 |
| `0.0` | 385 |

### Tool registration

Tools reach the MCP server through the `@mcp_tool` decorator, which registers a class at import
time. `akd_ext/tools/__init__.py` therefore determines what a given deployment exposes: importing a
tool there publishes it, and leaving it out keeps it off the server without touching its source.
