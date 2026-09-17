# MORPHEUS deployment

MORPHEUS can be packaged as one container that serves the React Command Center and FastAPI control plane from the same origin. This is a **single-node engineering/pilot deployment path**, not evidence of HA, multi-tenant production readiness, benchmark superiority, security certification, or automatic-control authorization.

## Build

```bash
docker build -t morpheus:local .
```

The build runs the frontend production contract/build and installs the native C++ toolchain used by MORPHEUS verification.

## Run

```bash
docker run --rm \
  -p 8000:8000 \
  -v morpheus-state:/data \
  --name morpheus \
  morpheus:local
```

Open `http://localhost:8000`. The UI uses same-origin `/api` requests, so no separate frontend proxy is required in the packaged deployment.

## Verify after launch

```bash
curl http://localhost:8000/api/health
curl http://localhost:8000/api/v2/system/startup-mvp-readiness
```

Then use the Command Center to run the included workload, inspect the selected physical plan, run full C++20 compile + behavior verification, inspect persisted evidence, and ask Copilot about the persisted run.

## Persistent state

`/data` is mapped to `MORPHEUS_STATE_DIR` and contains the SQLite control-plane database and content-addressed artifact store. Use a persistent volume for any non-ephemeral deployment.

## Platform notes

The container image is Linux-based and includes `build-essential` and CMake. Local Windows development remains supported through `START-MORPHEUS.bat`; that launcher still uses dynamically selected local ports and Vite's development proxy.

## Deployment truth boundary

A successful image build, health check, startup-readiness response, synthesis run, or generated-artifact verification establishes only the evidence class explicitly returned by MORPHEUS. It does not establish external production reliability, hosted multi-tenant readiness, universal performance superiority, scientific novelty, patentability, or permission for automatic production activation.
