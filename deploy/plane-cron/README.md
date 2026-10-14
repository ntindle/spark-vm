# plane-cron — plane-workspace cron-trigger contract + verification

(#1069, #1298 — the deploy half of the push lane's scheduled sweeps.)

The push lane's sweep *logic* lives in `hosted/` and is tested there.
This directory owns the other half: the exact cron-trigger declaration
the plane workspace deploys, the scheduled-handler dispatch contract,
the #1013-pattern manual ops triggers, and the post-deploy verification
that proves the trigger itself is registered.

## Files

- `CRON_TRIGGER_CONTRACT.md` — the contract: wrangler `[triggers]`
  declaration, scheduled-handler dispatch (`sweep_once` per minute,
  `gc_push_tables` daily, sender-loop pairing), manual ops triggers,
  D71 retirement rule, and the verification procedure.
- `verify_plane_cron.py` — the post-deploy check: lists the worker's
  registered cron triggers via the Cloudflare Workers API (read-only)
  and asserts every contract cron is present. `--fixture` for
  CI/offline mode. Exit 0 = all present, 1 = missing (names them),
  2 = usage/API error. The API token comes from `CF_API_TOKEN` env
  only and is never printed or logged.
- `test_verify_plane_cron.py` — hermetic fixture-based tests (27),
  including the silently-unwired failure mode: sweep cron missing from
  an otherwise-deployed worker.

## Operator quick-start

```bash
# after a plane deploy that touches triggers:
CF_API_TOKEN=... CF_ACCOUNT_ID=... \
  python3 deploy/plane-cron/verify_plane_cron.py --script-name sparkvm-control
```

A fixture pass (`--fixture`) asserts against a saved snapshot only —
it does not prove the triggers are registered on the worker; only the
live API call is deploy proof. The script labels fixture runs in its
output so a transcript can never be mistaken for live verification.

Security note: the token is env-only (never a CLI flag, never logged),
but typing it into an interactive shell lands it in `~/.bash_history`
— prefix the assignment with a space or use `read -s CF_API_TOKEN`.
Use a minimal-scoped Cloudflare token (read access to the worker is
all this script needs).

The silently-unwired failure this catches: the `scheduled` handler
deploys fine, the trigger is never registered, and nothing ever ticks.
A handler that runs proves nothing about registration — this check is
the proof.
