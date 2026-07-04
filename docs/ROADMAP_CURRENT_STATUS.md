# Current Roadmap Status

This checkpoint summarizes the current project state after the Theme Gallery app
shell, export preflight, installer readiness diagnostics, and public-facing fork
documentation work.

It is meant to be the quick operational roadmap: what is done, what is current,
and what should come next. Longer design context remains in:

- `docs/ROADMAP.md`
- `docs/ROADMAP_THEME_EDITOR_DETAILED.md`
- `docs/OFFICIAL_WINDOWS_PARITY_ROADMAP.md`
- `docs/THEME_APP_SHELL_MVP.md`
- `docs/THEME_APP_ARCHITECTURE_CHECKPOINT.md`
- `docs/UPSTREAM_SHARING.md`

## Ground rules

Continue using the established roadmap guardrails:

- one small feature branch per implementation step;
- pure/testable helper modules outside GTK when possible;
- no unrelated theme/config/generated-file drift;
- preserve Undo/Redo and atomic-save behavior;
- keep device-write flows explicit and guarded;
- do not bypass the YAML-first architecture;
- keep public documentation clear about the Linux-focused, experimental,
  AI-assisted / vibe-coded nature of this fork.

## Current base

```text
base branch: feature/theme-video-inspector-live-preview
latest merged stack:
  - Theme Gallery app shell stack
  - post-merge docs cleanup
  - export completeness preflight
  - installer readiness check mode
normal launcher: turing-smart-screen
integrated dev launcher: .venv/bin/python turing-smart-screen-main.py
legacy/runtime launcher: .venv/bin/python configure-gtk.py
```

## Completed checkpoints

### Runtime, packaging, and media foundation

- [x] Runtime and native-video foundation.
- [x] Installation and documentation readiness.
- [x] Media preparation editor MVP.
- [x] Advanced media preparation.
- [x] Multiple display profiles.
- [x] Automatic display detection.
- [x] Release-readiness foundation.
- [x] Installer `--check-only` readiness diagnostics.

### Theme editor and media tooling

- [x] Theme elements navigator.
- [x] Layer ordering foundation.
- [x] Theme property presets.
- [x] Theme text and effect presets.
- [x] Semantic visual preset engine foundation.
- [x] Component preset foundation.
- [x] Composition preset foundation.
- [x] Static image layout inspector.
- [x] Static image transform inspector.
- [x] Static image crop inspector.
- [x] Generated Media Manager.
- [x] Video Inspector with reactive playback preview.
- [x] Theme editor text/effect hardening.
- [x] True transparent native-video overlays.
- [x] Text effects over native-video themes.
- [x] Reliable Save As/theme cloning fixes.

### Integrated app shell / official-app parity cycle

- [x] Theme Gallery reusable module.
- [x] Theme Gallery integrated into the main app `Themes` page.
- [x] Current-theme detection and compatibility filtering.
- [x] Gallery diagnostics.
- [x] Set active/current theme from gallery.
- [x] Duplicate, rename, delete with confirmation.
- [x] Import from folder/archive.
- [x] Export selected theme to `.zip` archive.
- [x] Export completeness preflight for referenced/generated media.
- [x] Theme card action polish with overflow menu.
- [x] Embedded Theme Editor inside the main app stack.
- [x] Embedded Video Manager inside the main app stack.
- [x] Overview and Quick Actions route into embedded editor/video manager.
- [x] Rev. C offscreen bitmap clipping guard.
- [x] Overview animated preview for video themes.
- [x] Overview preview renderer aligned with Theme Editor/runtime `DisplayText` behavior.
- [x] Overview mock values aligned with the Theme Editor `HW_SENSORS=STATIC` preview basis.
- [x] Post-merge documentation cleanup.

### Public-facing fork readiness

- [x] README reframed as a Linux-focused experimental fork.
- [x] AI-assisted / vibe-coded development notice added.
- [x] Hardware validation scope documented.
- [x] Installation/readiness diagnostics documented.
- [x] Upstream-sharing posture documented.

## Current gap

The app is now stable enough to be presented publicly as an experimental
Linux-focused fork, but it still needs a final public-readiness pass before the
repository is made public and shared upstream.

The key remaining gap is not another large feature. It is **clarity and trust**:

- make sure public docs match the actual implemented feature set;
- avoid implying that untested hardware/media workflows are supported;
- make the AI-assisted / vibe-coded process explicit;
- make user risk and responsibility clear;
- provide a clean upstream-sharing note that does not ask the original maintainer
  to merge the whole fork.

## Current implementation — Phase 23: Public fork readiness

### Goal

Prepare the repository so it can be made public and shared with the upstream
author/community as an experimental Linux GTK fork.

### Target behavior

- [x] README clearly explains what the fork is.
- [x] README clearly explains that the fork is Linux-focused.
- [x] README clearly credits the upstream project.
- [x] README warns that the code was developed through an AI-assisted /
  vibe-coded workflow.
- [x] README documents user responsibility and hardware risk.
- [x] README documents validated hardware scope.
- [x] README links to installation, roadmap, media, and upstream-sharing docs.
- [x] Installation guide documents `--check-only` and device group diagnostics.
- [x] Roadmap status reflects the completed export preflight and installer
  readiness phases.
- [x] Upstream sharing note explains that this is not a request to merge the
  entire fork as-is.

### Non-goals for Phase 23

- [ ] No new device-write behavior.
- [ ] No feature refactor.
- [ ] No broad UI change.
- [ ] No repository visibility change from code.
- [ ] No upstream PR yet.

### Validation

```bash
python -m py_compile gtk-checkup.py
bash -n install.sh
./install.sh --check-only
git diff --check
git status --short
```

Recommended manual checks before making the repository public:

1. Review the README on GitHub preview.
2. Confirm no private paths, logs, keys, tokens, personal media, or generated
   test artifacts are present.
3. Run `./install.sh --check-only` with the display connected.
4. Run `./install.sh --no-deps` once from the final branch.
5. Launch `turing-smart-screen` and verify the app shell opens.
6. Confirm Theme Gallery, Theme Editor, Video Manager, and export preflight still
   work.

## Later roadmap

After public fork readiness:

1. Repository visibility change to public, done manually in GitHub settings.
2. Optional upstream issue/discussion introducing the fork.
3. Installer 1.0 polish:
   - optional interactive permission helper;
   - clearer non-Arch dependency install path;
   - updated docs for each package manager after external testing.
4. Embedded media-preparation workflow polish.
5. Device Manager / display-profile integration.
6. Unified sync/send-to-display plan.
7. Safe temporary preview-on-display flow.
8. Data source and visualization catalogs.
9. Data element creation wizard.
10. Canvas interaction model.
11. Canvas direct selection/drag.
12. Canvas resize/actions.

## Current decision

Finish **Phase 23: Public fork readiness** before making the repository public or
opening an upstream discussion.

Reason: the fork has grown into a Linux-focused experimental application with
hardware-specific media functionality. Public documentation must clearly explain
its scope, risks, upstream relationship, and AI-assisted development process
before new users or upstream maintainers review it.
