# Plan H v3.4 Master Plan — `/gd` Runtime Activation (Bridge Self-Test Fixture Target)

GD_STANDARD: Project GD/prompts/gd-review-standard.md
GOAL_SOURCE: Project GD/docs/gd-v7-project-goal.md
TEMPLATE_KIND: gd-master-plan

日期：2026-05-12
状态：fixture-target（本文件仅用于 bridge self-test routing fixtures 的 target 引用，内容精简）

## PROJECT_GOAL
Project GD runtime activation: validate /gd review end-to-end with live Codex transport.

## SC-1: bridge self-test passes
verify: bash scripts/gd-codex-bridge-review.py self-test && exit 0

## SC-2: routing fixtures resolve target paths
verify: all v2-routing fixtures find their target files

## owned_paths
- scripts/
- fixtures/
- plans/
