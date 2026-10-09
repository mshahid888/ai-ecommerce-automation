# GitHub Setup — `ai-ecommerce-automation`

Status (Phase 8, 2026-10-09): **repository NOT yet created on GitHub.**
Automated creation from this VM was attempted **twice** and failed both times
with:

```
failed to create repository: POST https://api.github.com/user/repos:
403 Resource not accessible by integration
```

Attempts: (1) Phase 1, via the Muse GitHub-App `github` CLI; (2) Phase 8,
re-attempted with the same tool — same 403. `gh` on this VM is not logged in
(`gh auth login` needs Shahid's interactive sign-in), so there is no
workaround available here that respects the auth boundaries — deliberately
not attempted.

Cause: the Muse GitHub App integration on this VM is scoped to selected
repositories and is not permitted to create new repositories under
`mshahid888`. This is an account/permission limitation, not a code problem.
Nothing was pushed anywhere; the local git repository is initialized and
ready (5 commits through Phase 7; Phase 8 adds the deploy configs as the 6th).

## What Shahid needs to do (one time, ~3 minutes)

### Option A — create the repo on github.com (recommended)

1. Open https://github.com/new while signed in as **mshahid888**.
2. Repository name: `ai-ecommerce-automation`
3. Description (suggested): `AI E-Commerce Support & Order Automation — demo platform for German online stores`
4. Visibility: **Public**
5. Leave "Add a README file" **unchecked** (the local project already has one).
6. Click **Create repository**.

### Option B — create from his Mac terminal (he has the `muse-mac-pdfwandler` SSH key there)

```bash
gh repo create mshahid888/ai-ecommerce-automation --public \
  --description "AI E-Commerce Support & Order Automation — demo platform for German online stores"
```

(Requires `gh auth login` once on the Mac if not already done.)

## Push the local project (after creating the empty repo)

From a machine with push access to `mshahid888` (his Mac, or this VM after `gh auth login`):

```bash
cd ~/workspace/ai-ecommerce-automation   # or the synced copy on the Mac
git remote add origin git@github.com:mshahid888/ai-ecommerce-automation.git
git branch -M main
git push -u origin main
```

Notes:
- On his Mac, `~/.gitconfig` has a global `url.insteadOf` forcing HTTPS; if SSH push
  fails there, use the remote form `ssh://git@github.com/mshahid888/ai-ecommerce-automation.git`
  (this is the form the pdfwandler repo uses successfully).
- Never commit `.env`, `*.db`, `backend/.venv/`, `frontend/node_modules/`, or `.next/`
  — root `.gitignore` already excludes them.

## After the push

Verify: https://github.com/mshahid888/ai-ecommerce-automation shows the README.
Then delete this file's "not yet created" status note, or keep this file as the
contribution/push reference.
