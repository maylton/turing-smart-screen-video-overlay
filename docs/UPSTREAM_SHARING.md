# Upstream sharing note

This document explains how this fork should be presented to the upstream
`turing-smart-screen-python` project and to users who discover the repository
publicly.

## Positioning

This repository is an **experimental Linux-focused fork**. It should not be
presented as a replacement for the upstream project and should not be presented
as a ready-to-merge upstream branch.

The right framing is:

> This fork explores a Linux GTK/Libadwaita desktop workflow, Theme Gallery,
> media preparation, generated-media tracking, and Rev. C video/storage support.
> If any ideas are useful upstream, they can be discussed and split into smaller
> upstream-friendly changes later.

## Why not open one huge pull request?

The fork has grown into a broad Linux-first application layer. It includes app
shell work, editor workflows, installer behavior, generated-media metadata,
media/video operations, and Rev. C-specific hardware paths.

A single upstream pull request would be too large and too opinionated because:

- upstream is a multi-OS Python system monitor and hardware abstraction project;
- this fork's main UI direction is GTK4/Libadwaita on Linux;
- some features are hardware-specific and validated only on one Rev. C profile;
- the fork includes user-facing workflows that may not match upstream's product
  direction;
- a large PR would be difficult to review, test, or partially accept.

## Recommended upstream message

If opening a GitHub issue or discussion upstream, use a short and respectful
message like this:

```markdown
Hi! First of all, thank you for turing-smart-screen-python.

I have been working on an experimental Linux-focused fork that builds on top of
this project and explores a GTK4/Libadwaita desktop workflow.

The fork includes:

- integrated GTK app shell;
- Theme Gallery / Theme Manager;
- embedded Theme Editor and Video Manager;
- media preparation tools;
- generated-media tracking;
- theme import/export with preflight validation;
- Linux installer readiness diagnostics;
- experimental Rev. C video/storage workflow validated on my 2.1-inch device.

Repository:
https://github.com/maylton/turing-smart-screen-video-overlay

This is not a request to merge the whole fork as-is. I am sharing it in case any
ideas, implementation details, or hardware findings are useful for the upstream
project.

If there is interest, I would be happy to discuss which parts could be split into
small upstream-friendly PRs.
```

## Candidate areas for future upstream-friendly PRs

These are the most likely areas to split out later, if upstream is interested:

1. Small pure bug fixes.
2. Diagnostics helpers.
3. Packaging/test improvements.
4. Safer path normalization or validation helpers.
5. Isolated hardware findings around Rev. C behavior.
6. Documentation clarifications.

Each upstream PR should be based on `mathoudebine/turing-smart-screen-python:main`,
not on this fork's feature branch stack.

## Areas that are probably fork-specific for now

These should not be pushed upstream without prior discussion:

- the full GTK4/Libadwaita app shell;
- Theme Gallery as implemented here;
- embedded editor/video-manager navigation stack;
- Linux-only installer workflow;
- generated-media manifest policy tied to this editor;
- Rev. C native video/storage workflows;
- any code that assumes the fork's route structure, app shell, or local roadmap.

## Vibe-coded / AI-assisted disclosure

When sharing this fork, mention that it was developed through a heavily
AI-assisted / vibe-coded workflow. This is not an apology for the work, but it is
important context for reviewers.

Suggested wording:

> This fork was built through an AI-assisted / vibe-coded process with many small
> manual validation checkpoints. I recommend treating it as experimental and
> reviewing any code carefully before reusing it upstream.

## Before making the repository public

Check the repository for:

- personal paths in committed docs/logs;
- local debug logs;
- screenshots with private information;
- generated media that should not be public;
- temporary files;
- credentials, tokens, API keys, or private config values;
- overly broad claims about hardware support.

Then preview the README on GitHub before sharing the repository link upstream.
