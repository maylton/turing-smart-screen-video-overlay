# GTK Theme Editor Roadmap Status

This checkpoint records the current state of the GTK Theme Editor, Video Inspector V2, Safe Session Lifecycle, and Classic Editor retirement track after the validated work on `feature/theme-video-inspector-live-preview`.

## Current baseline

The GTK Theme Editor is now the primary theme editing surface. The classic editor remains available only as an advanced fallback through the overflow menu.

Recent completed milestones:

- PR #24 — Video Inspector V2 controls finalized.
- PR #25 — Classic editor retirement checkpoint added.
- PR #27 — Safe session close guard added.
- PR #29 — External `theme.yaml` change guard added.
- PR #31 — `Reload Theme From Disk` action added.
- PR #33 — Structural actions routed through the safe save guard.
- PR #35 — Guarded `Open Theme YAML` action added.
- PR #37 — Classic editor demoted to advanced/legacy fallback.

## Progress summary

| Area | Status | Progress | Notes |
| --- | --- | ---: | --- |
| Video Inspector V2 | Complete | 100% | Mirror, trim, playback speed, loop, background controls, and reactive preview are integrated. |
| Static image layout / transform inspector | Mostly complete | 90% | Non-destructive layout and transform flow is in GTK. Remaining work is polish and edge-case handling. |
| Generated Media Manager | Mostly complete | 85% | The manager is available from `Tools -> Generated Media`; diagnostics/export polish remains useful. |
| Elements panel / tree / actions / layer ordering | Mostly complete | 90% | Add, duplicate, delete, enable/disable, and layer ordering are present. Remaining work is final UX polish and parity audit. |
| Safe Session Lifecycle | Nearly complete | 95% | Close guard, external change detection, reload, guarded save paths, and structural save rollback are implemented. |
| YAML / theme-folder access | In progress | 75% | Open folder, open YAML, reload from disk, and external-edit warnings exist. Copy path and diagnostics actions are still pending. |
| Classic Editor retirement | In observation | 85% | The legacy editor is now an advanced fallback. It should remain temporarily until a parity audit confirms no critical gaps. |
| Documentation / release checkpointing | In progress | 70% | This document updates the roadmap. Release readiness and parity checklists still need dedicated docs. |
| Automated regression coverage | Partial | 70% | Python unit tests cover backend behavior. GTK workflows still need manual validation checklists and possibly smoke tests. |
| Release readiness | Partial | 60% | The editor is functional, but release readiness still needs packaging validation, final docs, and a classic-editor removal decision. |

Estimated overall readiness: **85%**.

## Completed capability map

### Video and media workflows

- Video Inspector V2 supports advanced conversion controls.
- Static image layout inspector supports non-destructive image placement and transform workflows.
- Generated media can be inspected through a GTK tool surface.

### Theme editing workflows

- Theme elements can be browsed, searched, filtered, added, duplicated, deleted, enabled, disabled, and reordered from GTK.
- Property edits are guarded on close.
- Header Save applies pending property edits before saving.
- Structural actions use the same safe save path as normal saves.

### File/session safety

- The editor records the loaded `theme.yaml` file signature.
- Saves are blocked when `theme.yaml` changes externally.
- `Reload Theme From Disk` lets users recover without closing the editor.
- `Open Theme YAML` warns users before external edits and handles terminal-based editors such as `micro.desktop`.

### Classic editor status

- The classic editor is no longer promoted in the main panel.
- The overflow action is now `Advanced / Legacy Editor…`.
- Launching the legacy editor requires confirmation.
- The classic editor should be treated as an escape hatch, not the default editor.

## Remaining work

### 1. YAML / theme-folder access polish

Recommended next implementation slice.

Add a compact, safer file-access group in the overflow menu:

- `Copy Theme YAML Path`
- `Copy Theme Folder Path`
- `Open Theme Folder`
- `Open Theme YAML`
- `Reload Theme From Disk`
- optional: `Open Theme Folder in Terminal`

Acceptance criteria:

- Copy actions use the GTK/GDK clipboard.
- Toasts confirm copied paths.
- Existing external-change guard remains unchanged.
- No action writes to `theme.yaml`.

### 2. Theme diagnostics surface

Add a read-only diagnostics dialog or generated report for the currently loaded theme.

Useful checks:

- current theme name and path;
- YAML path and last-known signature;
- number of visible/hidden elements;
- static image count;
- generated/managed media count;
- missing asset references;
- video overlay enabled/disabled status;
- whether the loaded file changed externally.

Acceptance criteria:

- Diagnostics must be read-only.
- It should help debug user reports without requiring manual shell commands.
- It should include copyable paths or a copy-report action.

### 3. GTK vs Classic parity audit

Before removing the classic editor completely, create a checklist comparing GTK coverage against the remaining classic editor capabilities.

Suggested buckets:

- theme creation/rename/save-as;
- text components;
- static images;
- sensors;
- video overlay;
- generated media;
- YAML/manual editing access;
- recovery/reload behavior;
- preview behavior;
- destructive actions.

Acceptance criteria:

- Every classic workflow is marked as one of:
  - covered in GTK;
  - intentionally replaced by YAML/manual access;
  - still requires legacy fallback;
  - obsolete and safe to drop.

### 4. Release readiness checklist

Create a release-facing checklist for validating the GTK editor before removing the classic editor from normal workflows.

Suggested checks:

- unit tests pass;
- `theme-editor-gtk.py` compiles;
- manual GTK checklist passes on at least one real theme;
- video inspector conversion works;
- image layout inspector works;
- generated media manager works;
- external YAML edit guard works;
- reload from disk works;
- legacy editor fallback still launches.

### 5. Classic editor removal decision

Do not delete the classic editor yet.

Removal should only happen after:

- the parity audit is complete;
- release readiness checklist passes;
- at least one normal editing session succeeds without needing the classic editor;
- any remaining classic-only features are either migrated or intentionally declared out of scope.

## Recommended next slices

### Slice A — YAML/theme-folder access polish

Best immediate next step. It is small, low risk, and complements the work already completed around `Open Theme YAML` and `Reload Theme From Disk`.

### Slice B — Theme diagnostics dialog

Good second step. It improves supportability and helps confirm release readiness.

### Slice C — GTK vs Classic parity audit document

Good third step. This prepares the final decision on whether to remove the classic editor or keep it hidden as an advanced fallback.

## Decision

Current recommendation: **keep the classic editor available behind the advanced fallback gate for now**.

The GTK editor is mature enough to be the default surface, but not yet documented/audited enough to remove the classic editor entirely.
