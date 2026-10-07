# MORPHEUS Tomorrow Launch Runbook

Status: guarded single-node pilot launch procedure.

This runbook is intentionally operational, not promotional. A successful launch proves that the declared MORPHEUS pilot stack starts and passes its scoped checks. It does not prove multi-tenant SaaS readiness, HA, external benchmark superiority, security certification, customer traction, or automatic production-control authority.

## 1. Choose the launch mode

### A. Local / private pilot

Use this for a workstation, demo machine, LAN test through a separate trusted tunnel, or prelaunch validation.

- Browser/API bind only to loopback.
- No public TLS ingress is opened by MORPHEUS.
- Best choice for the final prelaunch smoke test.

### B. Public HTTPS guarded pilot

Use this only for a small controlled pilot with one shared control-plane key.

- Caddy terminates HTTPS.
- MORPHEUS itself is not published directly to the host network.
- Protected API routes still require the MORPHEUS API key.
- The UI shell may be publicly reachable; API functionality remains locked until the browser session is given the key.
- This is not multi-user identity or tenant isolation.

## 2. Pull the exact code and create configuration

\`\`\`bash
git pull origin main
cp .env.example .env
\`\`\`

Generate a fresh control-plane key:

\`\`\`bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
\`\`\`

Set at minimum:

\`\`\`dotenv
MORPHEUS_API_KEY=<fresh-random-key>
MORPHEUS_RATE_LIMIT_PER_MINUTE=120
\`\`\`

Never commit the populated \`.env\`.

## 3. Optional AI integration

MORPHEUS works fully without AI. AI is an optional language/drafting layer only.

### Ollama / local model

Install and start Ollama on the Docker host, make sure the model you want is already installed, then configure:

\`\`\`dotenv
MORPHEUS_AI_PROVIDER=ollama
MORPHEUS_AI_MODEL=<your-installed-model>
MORPHEUS_AI_BASE_URL=http://host.docker.internal:11434
MORPHEUS_AI_TIMEOUT_SECONDS=20
\`\`\`

No model secret is required for normal local Ollama.

### OpenAI-compatible endpoint

\`\`\`dotenv
MORPHEUS_AI_PROVIDER=openai_compatible
MORPHEUS_AI_MODEL=<provider-model-id>
MORPHEUS_AI_BASE_URL=https://provider.example/v1
MORPHEUS_AI_API_KEY=<server-side-provider-key>
MORPHEUS_AI_TIMEOUT_SECONDS=20
\`\`\`

The provider key stays server-side. Do not enter it into the MORPHEUS browser UI.

Privacy boundary: when an OpenAI-compatible endpoint or any other remote provider is configured, the workload description, optional base MWS, Copilot question, and bounded deterministic evidence text used for rewriting are transmitted to that provider. Their handling is governed by the provider/operator policy. Use a genuinely local Ollama endpoint when that data must remain on the pilot host.

AI can:
- classify/normalize Copilot wording;
- produce an optional presentation rewrite of a deterministic Copilot answer;
- draft an MWS from a natural-language description;
- make one bounded repair attempt if the first MWS draft fails validation.

AI cannot:
- manufacture measurements;
- change feature maturity;
- authorize migration or deployment;
- trigger runtime control;
- bypass deterministic MWS validation;
- replace the authoritative persisted evidence answer.

## 4. Validate configuration before starting

Run the dependency-free MORPHEUS environment preflight first. It uses only the Python standard library and never prints configured secret values.

Local/private guarded profile:

\`\`\`bash
python scripts/validate_deployment_env.py --env-file .env
docker compose config
\`\`\`

Public HTTPS profile:

\`\`\`bash
python scripts/validate_deployment_env.py --env-file .env --public
docker compose -f compose.public.yaml config
\`\`\`

The preflight must exit \`0\`. Exit \`3\` means one or more configuration blockers remain; exit \`2\` means the env file itself could not be parsed/read. A successful static preflight does not replace runtime readiness after the container starts.

If either the MORPHEUS preflight or Compose validation fails, do not launch.

## 5A. Start local/private pilot

\`\`\`bash
docker compose build
docker compose up -d
\`\`\`

Open:

\`\`\`text
http://localhost:8000
\`\`\`

## 5B. Start public HTTPS pilot

Before starting:

1. Point the domain's A/AAAA DNS records at the pilot server.
2. Allow inbound TCP 80 and TCP/UDP 443 in the server/cloud firewall.
3. Do not expose container port 8000 publicly.
4. Set \`MORPHEUS_DOMAIN\` in \`.env\`.

Then:

\`\`\`bash
docker compose -f compose.public.yaml build
docker compose -f compose.public.yaml up -d
\`\`\`

Caddy obtains and renews the certificate automatically when DNS and inbound ports are correct. The public edge also rejects request bodies above 4 MB before they reach FastAPI; this leaves headroom for the bounded trace-intake workflow while limiting arbitrary public upload pressure.

Open:

\`\`\`text
https://<MORPHEUS_DOMAIN>
\`\`\`

The public profile adds HSTS and a pilot no-index header at the TLS edge.

## 6. Unlock the guarded browser session

Open **Settings & diagnostics → Control-plane key**.

Paste the \`MORPHEUS_API_KEY\` value and choose **Use for this tab**.

The key is kept in browser session storage for the current origin/session and attached as \`X-Morpheus-Key\` to protected requests. It is not the AI provider key.

## 7. Verify launch health

Liveness:

\`\`\`bash
curl -fsS http://127.0.0.1:8000/api/health
\`\`\`

For the public profile, use the HTTPS domain instead.

Protected readiness:

\`\`\`bash
export MORPHEUS_KEY='<control-plane-key>'

curl -fsS \
  -H "X-Morpheus-Key: $MORPHEUS_KEY" \
  http://127.0.0.1:8000/api/v2/system/startup-mvp-readiness
\`\`\`

Required pilot signals:

- \`ready: true\`
- \`startup_mvp_percent: 100.0\`
- \`pilot_ready: true\`
- \`state: STARTUP_MVP_READY_GUARDED_SINGLE_NODE_PILOT\`
- \`production_deployment_authorized: false\`
- \`automatic_control_allowed: false\`

AI status:

\`\`\`bash
curl -fsS \
  -H "X-Morpheus-Key: $MORPHEUS_KEY" \
  http://127.0.0.1:8000/api/v2/ai/status
\`\`\`

If AI is configured, use **Settings → Test AI provider**. Failure of optional AI should not block deterministic MORPHEUS.

Operational telemetry:

\`\`\`bash
curl -fsS \
  -H "X-Morpheus-Key: $MORPHEUS_KEY" \
  http://127.0.0.1:8000/api/v2/system/operational-metrics
\`\`\`

Idempotency health:

\`\`\`bash
curl -fsS \
  -H "X-Morpheus-Key: $MORPHEUS_KEY" \
  http://127.0.0.1:8000/api/v2/system/idempotency/status
\`\`\`

## 8. Required UI smoke before showing anyone

Run this sequence once after deployment:

1. Open Command Center.
2. Confirm backend shows Online, not Locked.
3. Open Workloads.
4. Import an MWS or use a preset.
5. If AI is configured, generate a plain-English MWS draft and verify assumptions are shown before applying it.
6. Run synthesis.
7. Open Decision Review and assess confidence.
8. If MORPHEUS requests bounded measurement and the workload is eligible, run it.
9. Run full C++20 verification.
10. Open Hot Path Doctor and run Hot Path Watch with one baseline and one fresh bounded trace window from the same route.
11. Confirm the Decision Freshness Passport state and export its JSON. If it is REVIEW REQUIRED, SUPERSEDED or BLOCKED, do not treat the old recommendation as deployment-ready.
12. Open the passport rollout/rollback ticket and verify the required evidence gates, stop conditions and rollback path are understood.
13. Download the decision brief.
14. Open Experiment History and resume the persisted run.
15. Ask Copilot why the design was selected.
16. If AI wording is displayed, expand **authoritative deterministic evidence answer** and verify it remains present.
17. Open Audit & Evidence and confirm the hash chain reports verified.
18. Open Runtime Observatory and confirm no unexpected 5xx surge.

Do not demo with a red/unknown evidence state that you cannot explain.

## 9. Back up state before and after the pilot

The Docker volume \`morpheus-state\` contains the single-node state/artifact store.

At minimum, take a volume snapshot/backup before a meaningful pilot and again after important evidence is created. Use the existing MORPHEUS backup/restore verification path when producing evidence that depends on backup claims.

Do not describe a volume copy as HA, replication, or disaster-recovery certification.

## 10. Logs and incident triage

Local:

\`\`\`bash
docker compose logs --tail=200 morpheus
\`\`\`

Public:

\`\`\`bash
docker compose -f compose.public.yaml logs --tail=200 morpheus caddy
\`\`\`

MORPHEUS request IDs are returned in \`X-Morpheus-Request-ID\`; use them when correlating a user-visible failure with server logs/metrics.

If a provider fails:
- verify \`/api/v2/ai/status\`;
- use **Test AI provider**;
- confirm model name/base URL;
- keep the product in deterministic mode until the provider is healthy.

If core readiness fails:
- do not bypass the gate;
- inspect the readiness blockers;
- fix the actual state/toolchain/security issue.

## 11. Rollback

For a bad application update:

\`\`\`bash
git log --oneline -n 10
git checkout <last-known-green-commit>
docker compose build --no-cache
docker compose up -d
\`\`\`

For the public profile, use \`-f compose.public.yaml\` on the Compose commands.

Preserve the \`morpheus-state\` volume unless the rollback procedure specifically requires restoring a verified backup. Do not delete evidence/state to make a failed health gate look green.

## 12. Tomorrow go/no-go

GO only when all are true:

- exact deployed revision is known;
- repository CI is green for that revision;
- container/Compose build succeeds;
- HTTPS is valid for a public pilot;
- control-plane API key is enabled for the guarded pilot;
- readiness reports 100% local startup scope and guarded pilot ready;
- evidence ledger integrity is valid;
- no unexplained 5xx errors appear in the smoke flow;
- one complete Workload → Synthesis → Review → Verify → Brief → Resume flow succeeds;
- optional AI either passes its probe or is explicitly left disabled.

NO-GO if:
- you need to disable auth/rate limits to make the demo work;
- the evidence ledger fails;
- artifact verification fails;
- the AI provider is required for the core workflow;
- public traffic reaches MORPHEUS directly over plain HTTP;
- you need to claim benchmark superiority, production reliability, multi-tenant isolation, patentability, or customer validation without corresponding external evidence.
