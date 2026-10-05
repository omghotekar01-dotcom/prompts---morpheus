# MORPHEUS deployment

MORPHEUS can be packaged as one container that serves the React Command Center and FastAPI control plane from the same origin. This is a **single-node local/startup pilot deployment path**, not evidence of HA, multi-tenant production readiness, benchmark superiority, security certification, or automatic-control authorization.

## Build

```bash
docker build -t morpheus:local .
```

The build runs the frontend production contract/build and installs the native C++ toolchain used by MORPHEUS verification. The runtime image executes as the dedicated non-root user `morpheus` (UID 10001). It does not trust arbitrary forwarded proxy headers by default.

## Local single-user run

For a local workstation evaluation, publish the container only on loopback:

```bash
docker run --rm \
  -p 127.0.0.1:8000:8000 \
  -v morpheus-state:/data \
  --name morpheus \
  morpheus:local
```

Open `http://localhost:8000`. The packaged UI uses same-origin `/api` requests, so no separate frontend proxy or CORS configuration is required.

This loopback mode is useful for a single-user local MVP. It is **not** the guarded network-pilot configuration because an API key and positive rate limit are not required by that command.

## Guarded single-node pilot configuration

Copy the tracked example to the ignored local environment file:

```bash
cp .env.example .env
```

Generate a fresh secret of at least 24 characters, for example:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Put that value in `.env` as `MORPHEUS_API_KEY`. Keep `MORPHEUS_RATE_LIMIT_PER_MINUTE` positive. Never commit the populated `.env`.

Start the packaged product on loopback:

```bash
docker run --rm \
  --env-file .env \
  -p 127.0.0.1:8000:8000 \
  -v morpheus-state:/data \
  --name morpheus \
  morpheus:local
```

The browser can reach `/api/health` without a credential. Protected `/api/*` routes require the configured `X-Morpheus-Key`. In the Command Center, open **Settings & diagnostics → Control-plane key**, enter the same key, and choose **Use for this tab**. The client keeps it in browser `sessionStorage` for the current origin/session and attaches it to protected requests; it is not written into MORPHEUS project files or returned by the API.

Browser session storage is still JavaScript-readable browser state, not a hardened secret vault or multi-user identity system. A network-exposed deployment still needs separately managed TLS, ingress identity/authorization and any required gateway/WAF controls.

## Verify after launch

Basic liveness remains intentionally unauthenticated:

```bash
curl http://localhost:8000/api/health
```

For guarded mode:

```bash
export MORPHEUS_KEY='<the same local key>'

curl -H "X-Morpheus-Key: $MORPHEUS_KEY" \
  http://localhost:8000/api/v2/system/startup-mvp-readiness

curl -H "X-Morpheus-Key: $MORPHEUS_KEY" \
  http://localhost:8000/api/v2/capabilities
```

For a correctly configured single-node pilot, the readiness payload should report local startup readiness and guarded pilot readiness while keeping:

- `production_deployment_authorized: false`
- `automatic_control_allowed: false`

Then use the Command Center to import or edit an MWS workload, optionally draft one query distribution from a bounded access trace, run synthesis, review uncertainty, run bounded local measurement when requested, verify generated C++20, inspect persisted evidence, resume prior runs, and export the decision brief.

## Persistent state

`/data` is mapped to `MORPHEUS_STATE_DIR` and contains the SQLite control-plane state, idempotency journal and content-addressed artifacts used by the single-node product. Use a persistent volume for any non-ephemeral pilot.

The image owns its built-in `/data` path as UID 10001. For a host bind mount, the operator is responsible for giving UID 10001 read/write access to the mounted directory. A named Docker volume avoids most host-permission mismatches.

## Proxy and browser-origin boundary

The image deliberately does **not** enable Uvicorn's universal forwarded-header trust. If an external reverse proxy is introduced, configure trusted proxy handling at a separately reviewed edge. Do not enable `--forwarded-allow-ips=*` merely to obtain client addresses; MORPHEUS process-local rate limiting must not trust attacker-supplied forwarding headers.

The packaged UI is same-origin. If a separate browser frontend is used for a pilot, configure exact origins through `MORPHEUS_PILOT_BROWSER_ORIGINS`; wildcard pilot origins are rejected.

## Repository guarded launcher vs packaged image

`python scripts/run_pilot.py` remains the stronger repository-checkout launcher: it performs the fail-closed pilot preflight and binds a startup-evidence receipt to the exact Git source revision before launching one worker.

The Docker path above is a packaged single-node path. CI builds, boots and probes the image, but the image intentionally excludes `.git`; therefore it must not be described as producing the same Git-backed startup-revision receipt as `scripts/run_pilot.py`.

## CI deployment gate

The main CI matrix includes a packaged-container smoke gate after backend, frontend and C++ jobs succeed. It verifies that the image:

- builds successfully;
- declares the non-root `morpheus` user and runs as UID 10001;
- becomes live on `/api/health`;
- rejects an unauthenticated protected request;
- accepts the configured `X-Morpheus-Key`;
- reports 100% local startup-MVP readiness and guarded single-node pilot readiness for the CI environment;
- preserves `production_deployment_authorized=false` and `automatic_control_allowed=false`;
- serves the React shell with the declared browser security headers.

That CI smoke is a packaging/contract check on a GitHub runner. It is not an external production, penetration-test, SLA or benchmark claim.

## Platform notes

The container image is Linux-based and includes `build-essential` and CMake. Local Windows development remains supported through `START-MORPHEUS.bat`; the Windows launcher selects free local ports dynamically and prints the actual UI/API URLs.

## Deployment truth boundary

A successful image build, health check, startup-readiness response, synthesis run, generated-artifact verification or CI container smoke establishes only the evidence class explicitly returned by MORPHEUS. It does not establish external production reliability, hosted multi-tenant readiness, universal performance superiority, scientific novelty, patentability, customer traction, regulatory/security certification, or permission for automatic production activation.


## Optional AI provider

AI is deliberately optional. With no AI environment variables, MORPHEUS remains fully functional in deterministic mode.

Supported provider modes:

- ollama — local/free model server using Ollama's chat API;
- openai_compatible — an operator-selected OpenAI-compatible chat-completions endpoint.

Server variables:

- MORPHEUS_AI_PROVIDER
- MORPHEUS_AI_MODEL
- MORPHEUS_AI_BASE_URL
- MORPHEUS_AI_API_KEY (optional for local Ollama, provider-dependent otherwise)
- MORPHEUS_AI_TIMEOUT_SECONDS

For Docker with Ollama running on the host, set the base URL to http://host.docker.internal:11434 and choose a model that is already installed on that host.

The browser never receives the AI provider key. The only browser-entered key is the separate MORPHEUS control-plane key.

AI remains bounded to language/drafting assistance:
- Copilot may use the provider to normalize intent and produce a presentation-only rewrite;
- the deterministic evidence answer is returned separately as authoritative_answer;
- plain-English workload drafting must pass the deterministic MWS parser before the UI can apply it;
- provider failure falls back to deterministic Copilot behavior;
- AI cannot authorize feature promotion, benchmark evidence, migration, deployment or runtime control.

## Hardened Compose profile

compose.yaml is the preferred repeatable local/private pilot launch:

- loopback host publishing only;
- read-only root filesystem;
- writable persistent /data volume;
- bounded writable /tmp for local compilation/verification;
- all Linux capabilities dropped;
- no-new-privileges;
- restart policy;
- host-gateway alias for an optional host-side local AI server.

CI parses this Compose profile and separately boots the image with equivalent hardening flags.

## Public HTTPS pilot profile

compose.public.yaml is a separate guarded public-pilot profile. It does not publish MORPHEUS port 8000 to the host. Caddy is the only internet-facing service and reverse-proxies the same-origin UI/API over HTTPS.

Before using it:
1. set MORPHEUS_DOMAIN in .env;
2. point DNS at the server;
3. allow inbound 80/443;
4. keep the MORPHEUS API key and positive process-local rate limit enabled.

The Caddy policy adds HSTS and pilot noindex headers. This profile is appropriate only for a small shared-key pilot. It is not multi-user identity, per-tenant authorization, HA or security certification.

For the exact launch sequence, smoke flow and rollback procedure, follow docs/TOMORROW-LAUNCH-RUNBOOK.md.
