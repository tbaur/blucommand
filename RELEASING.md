# Releasing

Releases are fully automated with [release-please](https://github.com/googleapis/release-please). Versions, `CHANGELOG.md`, git tags, and GitHub Releases are derived from commit messages — nobody edits or creates them by hand.

This project is a local CLI (not published to PyPI or npm). A release is the git tag + GitHub Release notes only.

## Flow

1. A branch is created and changes are committed.
2. A PR is opened with a **Conventional Commit title**. The title determines the
   next version when the PR is squash-merged into `main`:

   | PR title prefix | Example | Version bump |
   |---|---|---|
   | `fix:` | `fix: handle offline device timeout` | patch (1.1.0 → 1.1.1) |
   | `feat:` | `feat: add group volume command` | minor (1.1.0 → 1.2.0) |
   | `feat!:` / `fix!:` or a `BREAKING CHANGE:` footer | `feat!: require Python 3.12` | major (1.1.0 → 2.0.0) |
   | `chore:`, `docs:`, `refactor:`, `test:`, `ci:` | `docs: fix typo` | no release |

3. The **Tests** workflow runs on the PR. The PR is squash-merged to `main`.
4. **release-please** opens or updates a **Release PR** titled
   `chore(main): release X.Y.Z`. It bumps the version in `pyproject.toml`,
   `constants.py`, and `.release-please-manifest.json`, and appends to
   `CHANGELOG.md`. Multiple code PRs merged before a release are batched into
   one Release PR.
5. Merging the Release PR triggers `release.yml` again, which:
   - creates the `vX.Y.Z` git tag,
   - publishes a GitHub Release with the changelog notes.

To ship a release: merge the code PR(s), approve the Release PR's checks, then merge the Release PR.

## Approve the Release PR checks

The Release PR is authored by `github-actions[bot]`, because `release.yml` passes `github.token` to release-please. GitHub creates its checks but holds them until a user with write access approves.

**Approve the held runs before merging.** Either click "Approve and run" on the Release PR's Checks tab, or approve them from the CLI:

```bash
sha=$(gh pr view <PR> --json headRefOid --jq .headRefOid)
gh api "repos/tbaur/blucommand/actions/runs?head_sha=$sha" --jq '.workflow_runs[] | select(.conclusion=="action_required" or .status=="action_required") | .id'
gh api -X POST repos/tbaur/blucommand/actions/runs/<RUN_ID>/approve
```

- Approve each run id that the list returns. A Release PR usually has two.
- The approval does not stick. It is needed on every release, and again whenever release-please updates an open Release PR.
- **Merging without approving turns the runs red.** They finalise as `failure` with zero jobs and no logs. That means nobody approved them, not that anything broke.

GitHub added this approval step in its [bot-created pull requests change](https://github.blog/changelog/2026-06-11-bot-created-pull-requests-can-run-workflows-if-approved/), and these repos got it in late August 2026. It applies to same-repo branches, not just forks, and has no repository-level opt-out. The only way to remove the step is to author the Release PR as a different identity, which needs a GitHub App or a PAT. This repo uses neither, and approving each release is cheaper.

## Branch protection

`main` should stay compatible with this flow:

- **Require a pull request before merging** (0 required approvals is fine for a
  solo maintainer).
- **Block force-pushes and deletions.**
- **No required status checks on the Release PR.** The Release PR's own checks are held for approval, so a required check there would sit unresolved until someone approves it. Code
  PRs still run Tests; review those before merging.

### Actions permission (required once)

Under **Settings → Actions → General → Workflow permissions**:

1. **Read and write permissions**
2. **Allow GitHub Actions to create and approve pull requests**

Without (2), release-please can update its branch but cannot open the Release PR
(`GitHub Actions is not permitted to create or approve pull requests`).

## Notes

- **PR titles drive releases.** With squash merges, the PR title becomes the
  commit release-please reads. `chore:` / `docs:` / `ci:` titles intentionally
  produce no release.
- **Version source of truth** is `.release-please-manifest.json`.
  `pyproject.toml` and `constants.__version__` are kept in sync — do not
  hand-edit them for routine releases.
- Behavior is configured in `release-please-config.json`.

## Manual fallback

Manual tagging bypasses changelog automation and manifest sync. Prefer the
Release PR flow. If unavoidable:

```bash
git tag -a vX.Y.Z -m "vX.Y.Z"
git push origin vX.Y.Z
gh release create vX.Y.Z --generate-notes
```
