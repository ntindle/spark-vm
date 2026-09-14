# spark-vm

Setup + tooling for the **spark-vm** dev workhorse (Ubuntu 24.04, 8 vCPU,
15 GB RAM, 250 GB disk, tailnet `100.65.241.20`). Seeded 2026-09-14.

This repo is the source of truth for everything that makes spark-vm useful
beyond a stock Ubuntu install. It exists so a lost box (or a fresh one)
can be rebuilt without archaeology. **Private** — it describes internal
infrastructure.

## What's here

| Path | What it is |
|---|---|
| `cred` | Credential CLI (single-file Python, stdlib only). Deployed to `~/bin/cred` on the box. File backend at `~/.config/spark-credentials`, `SPARK_CRED_BACKEND` reserved for a future Bitwarden backend. |
| `SETUP.md` | Full box documentation: install inventory, cred usage + the missing-credential flow, browser automation, security notes. |
| `scripts/pw-test.py` | Playwright smoke test — headless Chromium loads example.com, prints title, saves screenshot. Run with `/home/ntindle/.venvs/pw/bin/python`. |
| `scripts/png-check.py` | Validates the smoke-test screenshot is a real PNG. |
| `scripts/push.sh` | Push box-side changes back to this repo (runs on spark-vm; see "Backups / pushing"). |

## Deployed state (2026-09-14)

- Docker 29.1.3 (Ubuntu build), daemon verified, `ntindle` in `docker` group
- Python 3.12.3, Node v22.23.2, git 2.43.0, gh 2.45.0
- Playwright 1.62.0 + Chromium in `/home/ntindle/.venvs/pw` (headless-tested)
- `cred` at `/home/ntindle/bin/cred` (also on PATH via `/usr/local/bin/cred`)
- Docs at `/home/ntindle/SETUP.md`

## Backups / pushing

On the box, `~/spark-vm` is a clone of this repo. After changing anything
worth keeping:

```bash
~/spark-vm/scripts/push.sh
```

It commits (`-m` message prompted or passed as an argument) and pushes to
`origin`. Auth comes from the credential store:

```bash
echo '<fine-grained-PAT>' | cred set github
```

The PAT needs **contents: write** on `ntindle/spark-vm`. No real secrets
are ever committed — `push.sh` refuses if it sees anything secret-shaped
in staged changes, and the credential store lives outside the repo.
