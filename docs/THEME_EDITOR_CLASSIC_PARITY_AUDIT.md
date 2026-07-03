# GTK vs Classic Theme Editor Parity Audit

This audit tracks whether the GTK Theme Editor can replace the original classic editor as the normal editing surface.

It follows the retirement policy documented in `docs/THEME_EDITOR_ROADMAP_STATUS.md`: the classic editor stays available behind `Advanced / Legacy Editor…` until remaining gaps are either migrated, intentionally replaced, or declared obsolete.

## Legend

| Status | Meaning |
| --- | --- |
| Covered in GTK | The workflow has a first-class GTK surface and should not require the classic editor. |
| Replaced by GTK/YAML access | The old workflow is no longer a dedicated classic-editor flow; GTK provides a safer replacement, often via guarded YAML/file access. |
| Still requires legacy fallback | Keep classic editor access until this is migrated or explicitly dropped. |
| Obsolete / safe to drop | The workflow should not block classic editor retirement. |
| Needs observation | Likely covered, but should be confirmed during normal editing sessions. |

## Executive summary

Current recommendation: **do not delete the classic editor yet**, but keep it demoted behind the advanced fallback gate.

The GTK editor already covers the main editing and media workflows. The remaining blockers are mostly audit/release-readiness concerns rather than obvious missing core features.

Estimated parity state after PR #42:

| Area | Status | Confidence |
| --- | --- | --- |
| Theme selection/opening | Covered in GTK | High |
| Theme save/save-as/rename | Covered in GTK | High |
| Property editing | Covered in GTK | High |
| Text styling and presets | Covered in GTK | Medium-high |
| Static image layout/transform | Covered in GTK | High |
| Video overlay and Video Inspector V2 | Covered in GTK | High |
| Generated media management | Covered in GTK | Medium-high |
| YAML/manual editing access | Replaced by GTK/YAML access | High |
| External-change safety/reload | Covered in GTK | High |
| Diagnostics/supportability | Covered in GTK | Medium |
| Full release regression checklist | Still requires validation | Medium |
| Unknown classic-only edge tools | Needs observation | Medium |

## Workflow audit

### Theme lifecycle

| Workflow | GTK status | Retirement decision | Notes |
| --- | --- | --- | --- |
| Open an existing theme | Covered in GTK | Safe to use GTK as default | Launching `theme-editor-gtk.py <theme>` loads the selected theme. |
| Save current theme | Covered in GTK | Safe to retire classic dependency | GTK save routes through `save_theme_data()` and external-change guards. |
| Save As | Covered in GTK | Safe to retire classic dependency | Available in overflow menu. |
| Rename Theme | Covered in GTK | Safe to retire classic dependency | Available in overflow menu. |
| Open theme folder | Covered in GTK | Safe to retire classic dependency | File-access polish adds direct folder action. |
| Copy theme folder/YAML paths | Covered in GTK | Safe to retire classic dependency | Added as explicit GTK actions. |
| Open theme folder in terminal | Covered in GTK | Safe to retire classic dependency | Useful for debugging without returning to classic editor. |
| Open theme.yaml externally | Replaced by GTK/YAML access | Safe to retire classic dependency | Guarded warning plus editor/terminal fallback. |
| Reload theme.yaml from disk | Covered in GTK | Safe to retire classic dependency | Required recovery path after external edits. |

### Session safety and conflict handling

| Workflow | GTK status | Retirement decision | Notes |
| --- | --- | --- | --- |
| Closing with unapplied property edits | Covered in GTK | Safe to retire classic dependency | Save / Discard / Cancel close guard. |
| Detect external `theme.yaml` edits before saving | Covered in GTK | Safe to retire classic dependency | Blocks accidental overwrite. |
| Recover after external YAML edit | Covered in GTK | Safe to retire classic dependency | `Reload Theme From Disk` rebuilds editor state. |
| Structural action save protection | Covered in GTK | Safe to retire classic dependency | Add/delete/reorder/layout flows are routed through guarded saves. |
| Force overwrite external changes | Not implemented | Do not add yet | Safer current policy is reload first, then save. |

### Element browsing and structure

| Workflow | GTK status | Retirement decision | Notes |
| --- | --- | --- | --- |
| Browse theme structure | Covered in GTK | Safe to retire classic dependency | Tree/list model with grouped elements. |
| Search elements | Covered in GTK | Safe to retire classic dependency | Search entry is available in the elements panel. |
| Filter visible/hidden/mixed/structure | Covered in GTK | Safe to retire classic dependency | State filter exists. |
| Expand/collapse groups | Covered in GTK | Safe to retire classic dependency | Dedicated controls exist. |
| Select element and inspect properties | Covered in GTK | Safe to retire classic dependency | Property rows are generated from the selected node. |
| Show/enable element | Covered in GTK | Safe to retire classic dependency | Action menu handles static/sensor/video states. |
| Hide/disable element | Covered in GTK | Safe to retire classic dependency | Action menu handles static/sensor/video states. |
| Add catalog element | Covered in GTK | Needs observation | Catalog flow exists; confirm all classic addable components are represented. |
| Duplicate custom element | Covered in GTK | Needs observation | Present for custom text/static images; verify parity with classic duplication behavior. |
| Delete element | Covered in GTK | Needs observation | Destructive flow exists with guard; confirm sensor/static semantics match desired policy. |
| Layer reordering | Covered in GTK | Safe to retire classic dependency | Move backward/forward/send-to-back/bring-to-front are present. |

### Property editing

| Workflow | GTK status | Retirement decision | Notes |
| --- | --- | --- | --- |
| Edit scalar values | Covered in GTK | Safe to retire classic dependency | Entry rows generated for editable scalar values. |
| Edit booleans | Covered in GTK | Safe to retire classic dependency | Switch rows generated. |
| Edit colors | Covered in GTK | Safe to retire classic dependency | GTK color selector fallback exists. |
| Edit list-like values | Covered in GTK | Needs observation | Comma-separated editing exists; validate complex list use cases. |
| Numeric parsing | Covered in GTK | Needs observation | Numeric fields parse to int/float according to existing value/key. |
| Property presets | Covered in GTK | Needs observation | Preset dropdowns exist; verify all classic preset conveniences are represented. |
| Text style presets | Covered in GTK | Needs observation | Text-style preset handling exists; validate against real theme text workflows. |
| Raw complex nested structures | Replaced by GTK/YAML access | Safe to retire classic dependency | Complex YAML remains accessible through guarded `Open Theme YAML`. |

### Text components

| Workflow | GTK status | Retirement decision | Notes |
| --- | --- | --- | --- |
| Show/hide text elements | Covered in GTK | Safe to retire classic dependency | Generic element actions cover this. |
| Edit text content/format | Covered in GTK | Needs observation | Property editor exposes `TEXT`/`FORMAT` when present. |
| Font and font size edits | Covered in GTK | Needs observation | `FONT` and `FONT_SIZE` are editable; presets should be checked. |
| Font color edits | Covered in GTK | Safe to retire classic dependency | Color handling covers `FONT_COLOR`. |
| Text effects/style presets | Covered in GTK | Needs observation | Present, but should be validated with real styled text examples. |
| Custom text creation | Covered in GTK | Needs observation | Catalog/add flow should be verified against classic custom-text flow. |

### Static image workflows

| Workflow | GTK status | Retirement decision | Notes |
| --- | --- | --- | --- |
| Add/select static image element | Covered in GTK | Needs observation | Catalog/add flow exists; confirm all expected image types. |
| Edit image path/reference | Covered in GTK | Needs observation | Property editor exposes path-like values. |
| Non-destructive image layout | Covered in GTK | Safe to retire classic dependency | Static image layout inspector is available. |
| Image transform preview | Covered in GTK | Safe to retire classic dependency | Transform preview/render flow exists. |
| Generated transformed asset tracking | Covered in GTK | Safe to retire classic dependency | Generated media report and manager cover tracking. |
| Missing image reference debugging | Covered in GTK | Safe to retire classic dependency | Theme Diagnostics lists likely missing asset references. |

### Video workflows

| Workflow | GTK status | Retirement decision | Notes |
| --- | --- | --- | --- |
| Enable/disable video node | Covered in GTK | Safe to retire classic dependency | Generic actions and property rows cover video states. |
| Open video tools | Covered in GTK | Safe to retire classic dependency | Video tools row appears for selected video node. |
| Video Inspector V2 controls | Covered in GTK | Safe to retire classic dependency | Mirror, trim, speed, loop, background, and preview are integrated. |
| Prepared local video detection | Covered in GTK | Safe to retire classic dependency | Uses the video inspector/background backend. |
| Preview background management | Covered in GTK | Safe to retire classic dependency | Video inspector/background tools cover this. |
| Manual video YAML edits | Replaced by GTK/YAML access | Safe to retire classic dependency | Guarded YAML access remains available. |

### Generated media management

| Workflow | GTK status | Retirement decision | Notes |
| --- | --- | --- | --- |
| Inspect generated media | Covered in GTK | Safe to retire classic dependency | `Tools -> Generated Media` exists. |
| Identify in-use/unused/orphaned/unmanaged media | Covered in GTK | Safe to retire classic dependency | Backend report classifies generated media. |
| Remove unused managed asset | Covered in GTK | Needs observation | Manager supports safe removal; verify UX on real unused assets. |
| Diagnose generated-media issues | Covered in GTK | Safe to retire classic dependency | Theme Diagnostics summarizes generated media issues. |
| Repair generated-media issues automatically | Not implemented | Do not block retirement | Keep this out of scope unless needed later. |

### Preview behavior

| Workflow | GTK status | Retirement decision | Notes |
| --- | --- | --- | --- |
| Refresh preview after property edits | Covered in GTK | Safe to retire classic dependency | Core property flows refresh preview. |
| Refresh preview after structural edits | Covered in GTK | Safe to retire classic dependency | Structural flows rebuild tree and refresh preview. |
| Live preview for video inspector controls | Covered in GTK | Safe to retire classic dependency | V2 reactive preview hooks are present. |
| Preview after external YAML reload | Covered in GTK | Safe to retire classic dependency | Reload rebuilds tree/properties/preview. |

### Diagnostics and supportability

| Workflow | GTK status | Retirement decision | Notes |
| --- | --- | --- | --- |
| Copy theme paths | Covered in GTK | Safe to retire classic dependency | File-access polish added copy actions. |
| Open terminal in theme folder | Covered in GTK | Safe to retire classic dependency | Useful for support/debugging. |
| Copy diagnostics report | Covered in GTK | Safe to retire classic dependency | Theme Diagnostics has `Copy Report`. |
| Inspect external-change state | Covered in GTK | Safe to retire classic dependency | Diagnostics shows whether loaded YAML changed externally. |
| Inspect missing references | Covered in GTK | Needs observation | Heuristic missing-reference scan exists; validate false positives. |
| Inspect generated-media health | Covered in GTK | Safe to retire classic dependency | Diagnostics summarizes generated-media records and issues. |

## Remaining uncertainty

The known remaining uncertainty is not a single obvious missing feature. It is whether real-world classic-editor workflows include small conveniences that have not been explicitly tested in GTK.

Watch these during normal editing sessions:

1. Does any theme edit still require opening the classic editor?
2. Does any add/duplicate/delete flow behave differently from the desired classic behavior?
3. Are there complex nested YAML edits that should become first-class GTK controls instead of remaining manual YAML work?
4. Do text style presets cover the common real themes?
5. Does generated media cleanup feel safe and clear enough without classic-editor help?
6. Does Theme Diagnostics produce useful reports without too many false positive missing references?

## Retirement decision gates

The classic editor can be removed from normal user-facing workflows when all of these are true:

- A full manual GTK release checklist passes on at least one real theme.
- One complete editing session finishes without needing the classic editor.
- Any classic-only workflows discovered during testing are listed here.
- Each discovered gap is marked as migrated, replaced by guarded YAML access, or obsolete.
- Theme Diagnostics and Reload Theme From Disk work during the same test session.
- Generated media workflows do not require classic editor access.

## Current blockers to deleting the classic editor

| Blocker | Severity | Owner action |
| --- | --- | --- |
| Release readiness checklist not yet documented | Medium | Create dedicated release checklist doc. |
| No final normal-session observation after diagnostics | Medium | Run a full real-theme editing session and record result. |
| Potential unknown classic-only conveniences | Low-medium | Keep `Advanced / Legacy Editor…` for one more cycle. |
| Missing-reference diagnostics may need tuning | Low | Observe reports from real themes. |

## Recommended next slices

1. **Release readiness checklist** — document exact manual validation steps before final retirement.
2. **Normal editing session observation** — run through a real edit without using the classic editor and record findings.
3. **Optional diagnostics polish** — tune missing-reference heuristics if real reports are noisy.
4. **Final classic editor removal PR** — only after the checklist and observation pass.

## Decision

Current decision: **keep the classic editor available, but only behind `Advanced / Legacy Editor…`.**

GTK is now the default editing surface. The remaining work is release validation, observation, and final retirement confidence, not major feature migration.
