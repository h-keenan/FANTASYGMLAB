# Webhook hostname occurrence ledger

Baseline: `6d379dcd38f1a87f501dafa119dc58d0f0d6134a`.
Every baseline line containing the stale hostname is listed below. A = executable/config/test authority; B = current documentation; C = historical evidence. Test references that parse the retained Blueprint identity stay unchanged; they are not public-host probe defaults.

| Baseline occurrence | Class | Disposition |
|---|---|---|
| `docs/RENDER_DEPLOYMENT.md:25` | B | Correct current host/runbook; defer Blueprint sync pending association verification |
| `docs/RENDER_DEPLOYMENT.md:30` | C | Retain historical target; label historical and no longer authoritative |
| `docs/STRIPE_TEST_MODE_SETUP.md:58` | B | Correct current host/runbook; defer Blueprint sync pending association verification |
| `docs/STRIPE_TEST_MODE_SETUP.md:59` | B | Correct current host/runbook; defer Blueprint sync pending association verification |
| `docs/STRIPE_TEST_MODE_SETUP.md:60` | B | Correct current host/runbook; defer Blueprint sync pending association verification |
| `docs/STRIPE_TEST_MODE_SETUP.md:61` | B | Correct current host/runbook; defer Blueprint sync pending association verification |
| `docs/founder-beta-launch-go-no-go-v2.md:17` | C | Retain historical target; label historical and no longer authoritative |
| `docs/founder-beta-launch-go-no-go-v2.md:34` | C | Retain historical target; label historical and no longer authoritative |
| `docs/founder-beta-launch-go-no-go-v2.md:95` | C | Retain historical target; label historical and no longer authoritative |
| `docs/founder-beta-launch-go-no-go-v2.md:172` | C | Retain historical target; label historical and no longer authoritative |
| `docs/founder-beta-launch-go-no-go.md:27` | C | Retain historical target; label historical and no longer authoritative |
| `docs/founder-beta-launch-go-no-go.md:158` | C | Retain historical target; label historical and no longer authoritative |
| `docs/p0-launch-blocker-clearance.md:32` | B | Correct current host/runbook; defer Blueprint sync pending association verification |
| `docs/p0-launch-blocker-clearance.md:111` | B | Correct current host/runbook; defer Blueprint sync pending association verification |
| `docs/p0-launch-blocker-clearance.md:114` | B | Correct current host/runbook; defer Blueprint sync pending association verification |
| `docs/p0-launch-blocker-clearance.md:115` | B | Correct current host/runbook; defer Blueprint sync pending association verification |
| `docs/prelaunch-production-release-gate.md:220` | C | Retain historical target; label historical and no longer authoritative |
| `docs/production-domain-cutover.md:33` | C | Retain historical target; label historical and no longer authoritative |
| `docs/production-domain-cutover.md:62` | B | Correct current host/runbook; defer Blueprint sync pending association verification |
| `docs/production-domain-cutover.md:143` | B | Correct current host/runbook; defer Blueprint sync pending association verification |
| `docs/production-launch-checklist.md:198` | B | Correct current host/runbook; defer Blueprint sync pending association verification |
| `docs/stripe-webhook-service-contract.md:13` | C | Retain historical target; label historical and no longer authoritative |
| `docs/stripe-webhook-service-contract.md:21` | B | Correct current host/runbook; defer Blueprint sync pending association verification |
| `docs/stripe-webhook-service-contract.md:33` | B | Correct current host/runbook; defer Blueprint sync pending association verification |
| `docs/stripe-webhook-service-contract.md:36` | B | Correct current host/runbook; defer Blueprint sync pending association verification |
| `docs/stripe-webhook-service-contract.md:37` | B | Correct current host/runbook; defer Blueprint sync pending association verification |
| `docs/stripe-webhook-service-contract.md:139` | B | Correct current host/runbook; defer Blueprint sync pending association verification |
| `docs/stripe-webhook-service-contract.md:142` | B | Correct current host/runbook; defer Blueprint sync pending association verification |
| `modules/founder_ops.py:54` | A | Explicit configuration; no default guessed endpoint |
| `render.yaml:65` | A | Historical Blueprint identity retained; association unverified |
| `scripts/founder_beta_ops_public_probe.py:28` | A | Explicit configuration; no default guessed endpoint |
| `scripts/verify_p0_launch_blockers.py:30` | A | Explicit configuration; no default guessed endpoint |
| `scripts/verify_p0_launch_blockers.py:165` | A | Explicit configuration; no default guessed endpoint |
| `scripts/verify_p0_launch_blockers.py:176` | A | Explicit configuration; no default guessed endpoint |
| `scripts/verify_p0_launch_blockers.py:182` | A | Explicit configuration; no default guessed endpoint |
| `scripts/verify_p0_launch_blockers.py:184` | A | Explicit configuration; no default guessed endpoint |
| `scripts/verify_production_domain_cutover.py:32` | A | Explicit configuration; no default guessed endpoint |
| `services/stripe_webhook_service.py:4` | A | Correct service metadata |
| `services/stripe_webhook_service.py:6` | A | Correct service metadata |
| `services/stripe_webhook_service.py:24` | A | Correct service metadata |
| `tests/test_cold_start_first_usable.py:51` | A | Historical Blueprint identity retained; association unverified |
| `tests/test_deployment_config.py:155` | A | Historical Blueprint identity retained; association unverified |
| `tests/test_founder_beta_launch_go_no_go.py:38` | A | Historical Blueprint identity retained; association unverified |
| `tests/test_founder_beta_launch_go_no_go_v2.py:42` | A | Historical Blueprint identity retained; association unverified |
| `tests/test_founder_beta_launch_ops.py:19` | A | Historical Blueprint identity retained; association unverified |
| `tests/test_founder_beta_launch_ops.py:27` | A | Historical Blueprint identity retained; association unverified |
| `tests/test_launch_verification.py:245` | A | Historical Blueprint identity retained; association unverified |
| `tests/test_launch_verification.py:248` | A | Historical Blueprint identity retained; association unverified |
| `tests/test_stripe_billing.py:726` | A | Historical Blueprint identity retained; association unverified |
| `tests/test_stripe_webhook_service_repair.py:27` | A | Historical Blueprint identity retained; association unverified |
| `tests/test_stripe_webhook_service_repair.py:30` | A | Historical Blueprint identity retained; association unverified |
| `tests/test_stripe_webhook_service_repair.py:31` | A | Historical Blueprint identity retained; association unverified |
| `tests/test_stripe_webhook_service_repair.py:125` | A | Replace fallback assumption with explicit not_configured contract |
| `tests/test_stripe_webhook_service_repair.py:133` | A | Replace fallback assumption with explicit not_configured contract |

The Blueprint name is intentionally retained with an explicit warning. No Render association, service creation, deployment, secret or billing setting was changed. New historical labels and this ledger do not make old probe results current evidence. See [current operations](webhook-operational-authority.md).
