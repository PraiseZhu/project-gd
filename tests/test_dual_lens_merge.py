"""SC-1 / SC-5 / SC-0 单元测试：双 lens 仲裁合并、lens env 协议、capsule 上下文字段。

无 live codex 依赖（纯函数 + 本地 capsule 构建）。
"""
from pathlib import Path

import pytest

# conftest 已预注册 gd_codex_bridge_review / gd_review_controller


def _mapped(decision: str, status: str = "completed", findings=None, raw="raw_a.json"):
    return {
        "template_kind": "plan_v1",
        "reviewer": "codex",
        "review_target": "/tmp/t.md",
        "review_kind": "plan",
        "review_run_status": status,
        "gd_review_decision": decision,
        "scope_checked": [{"facet": "x", "result": "pass"}],
        "findings": findings or [],
        "raw_result_path": raw,
        "merge_notes": {},
    }


# ---------------- SC-5: merge_dual_codex_mapped verdict 仲裁 ----------------


class TestMergeDualCodexMapped:
    def test_approved_plus_requires_changes_yields_requires_changes(self):
        from gd_codex_bridge_review import merge_dual_codex_mapped
        a = _mapped("APPROVED")
        b = _mapped("REQUIRES_CHANGES", findings=[{"file": "a.py", "line": 1,
                                                    "category": "sc", "severity": "P2"}])
        m = merge_dual_codex_mapped(a, b)
        assert m["gd_review_decision"] == "REQUIRES_CHANGES"
        assert m["review_run_status"] == "completed"
        assert m["reviewer"] == "codex"  # schema 枚举内；双 lens 标识走 merge_notes
        assert m["merge_notes"]["merge_strategy"] == "dual_lens_verdict_arbitration"

    def test_degraded_plus_approved_yields_failed(self):
        from gd_codex_bridge_review import merge_dual_codex_mapped
        a = _mapped("APPROVED")
        b = _mapped("FAILED", status="degraded")
        m = merge_dual_codex_mapped(a, b)
        assert m["gd_review_decision"] == "FAILED"
        assert m["review_run_status"] == "degraded"

    def test_double_approved_yields_approved(self):
        from gd_codex_bridge_review import merge_dual_codex_mapped
        a = _mapped("APPROVED")
        b = _mapped("APPROVED")
        m = merge_dual_codex_mapped(a, b)
        assert m["gd_review_decision"] == "APPROVED"
        assert m["review_run_status"] == "completed"

    def test_findings_union_dedup_with_source_lens(self):
        from gd_codex_bridge_review import merge_dual_codex_mapped
        # 同 (file,line±3,category) 不同 severity → 取高；带 source_lens
        fa = [{"file": "a.py", "line": 10, "category": "sc-conformance",
               "severity": "P2", "title": "A-lens"}]
        fb = [{"file": "a.py", "line": 11, "category": "sc-conformance",
               "severity": "P1", "title": "B-lens"}]
        a = _mapped("REQUIRES_CHANGES", findings=fa)
        b = _mapped("REQUIRES_CHANGES", findings=fb)
        m = merge_dual_codex_mapped(a, b)
        # 并集去重 → 1 条（窗口内），severity 取高 P1
        assert len(m["findings"]) == 1
        assert m["findings"][0]["severity"] == "P1"
        assert m["findings"][0]["source_lens"] in ("codex_A", "codex_B")
        assert m["merge_notes"]["lens_a"]["findings_count"] == 1
        assert m["merge_notes"]["lens_b"]["findings_count"] == 1


# ---------------- SC-1: lens env 协议 (bridge _lens_params_from_env) ----------------


class TestLensEnvProtocol:
    def test_tag_env_routes_to_l3(self, monkeypatch):
        from gd_codex_bridge_review import _lens_params_from_env
        monkeypatch.delenv("GD_REVIEW_LENS_TAG", raising=False)
        monkeypatch.delenv("GD_REVIEW_LENS_PRIORITY_TEXT", raising=False)
        monkeypatch.delenv("GD_REVIEW_LENS_EMPHASIS", raising=False)
        monkeypatch.setenv("GD_REVIEW_LENS_TAG", "codex_A")
        emphasis, lens_emphasis = _lens_params_from_env()
        assert lens_emphasis == "codex_A"
        assert emphasis is None

    def test_priority_text_only_no_tag(self, monkeypatch):
        from gd_codex_bridge_review import _lens_params_from_env
        monkeypatch.delenv("GD_REVIEW_LENS_TAG", raising=False)
        monkeypatch.delenv("GD_REVIEW_LENS_EMPHASIS", raising=False)
        monkeypatch.setenv("GD_REVIEW_LENS_PRIORITY_TEXT", "SC-conformance → ...")
        emphasis, lens_emphasis = _lens_params_from_env()
        assert lens_emphasis is None
        assert emphasis == "SC-conformance → ..."

    def test_legacy_emphasis_full_string_is_neutral_safe(self, monkeypatch):
        # G2 回归：旧实现把完整 priority 全文塞 GD_REVIEW_LENS_EMPHASIS → 必须落中立（不误分化）
        from gd_codex_bridge_review import _lens_params_from_env
        monkeypatch.delenv("GD_REVIEW_LENS_TAG", raising=False)
        monkeypatch.setenv("GD_REVIEW_LENS_EMPHASIS", "SC-conformance → boundary/path-violation → ...")
        emphasis, lens_emphasis = _lens_params_from_env()
        assert lens_emphasis is None  # 全文非 tag → 不分化（fail-closed 中立）

    def test_legacy_emphasis_tag_fallback(self, monkeypatch):
        # merge-loop 旧名传 tag 的兼容路径
        from gd_codex_bridge_review import _lens_params_from_env
        monkeypatch.delenv("GD_REVIEW_LENS_TAG", raising=False)
        monkeypatch.setenv("GD_REVIEW_LENS_EMPHASIS", "codex_B")
        emphasis, lens_emphasis = _lens_params_from_env()
        assert lens_emphasis == "codex_B"


# ---------------- SC-1: controller _normalize_lens_tag (值对齐 G2) ----------------


class TestNormalizeLensTag:
    def test_full_string_maps_to_tag(self):
        from gd_review_controller import _normalize_lens_tag, LENS_A_EMPHASIS, LENS_B_EMPHASIS
        assert _normalize_lens_tag(LENS_A_EMPHASIS) == "codex_A"
        assert _normalize_lens_tag(LENS_B_EMPHASIS) == "codex_B"

    def test_tag_passthrough(self):
        from gd_review_controller import _normalize_lens_tag
        assert _normalize_lens_tag("codex_A") == "codex_A"
        assert _normalize_lens_tag("codex_B") == "codex_B"

    def test_unknown_is_neutral(self):
        from gd_review_controller import _normalize_lens_tag
        assert _normalize_lens_tag("garbage full text") is None
        assert _normalize_lens_tag(None) is None


# ---------------- SC-0 + SC-1: capsule 字段 + lens 真分化 ----------------


def _build_plan_capsule(lens_emphasis=None, deep=False):
    """构建 v1 plan capsule（如模板缺失则 skip）。"""
    import tempfile
    from gd_codex_bridge_review import (
        build_capsule_text, _build_deep_plan_capsule, _DEEP_ALLOWED_COMMANDS_SECTION,
    )
    plan = Path(tempfile.mkstemp(suffix=".md")[1])
    plan.write_text("# plan\n\n- [ ] SC-1 do x\n\nverify: true\n", encoding="utf-8")
    try:
        capsule, *_ = build_capsule_text(
            "plan", plan, plan.parent, compat_v1=True, lens_emphasis=lens_emphasis,
        )
        if deep:
            capsule += _build_deep_plan_capsule("plan", plan, None)
            # deep allowed commands 在 dispatcher 追加，单测 helper 显式补
            capsule += _DEEP_ALLOWED_COMMANDS_SECTION
        return capsule
    except (ValueError, FileNotFoundError) as e:
        pytest.skip(f"v1 plan template unavailable in this env: {e}")


class TestCapsuleFields:
    def test_claude_md_context_present(self):
        cap = _build_plan_capsule()
        assert "CLAUDE_MD_CONTEXT" in cap
        assert "MANDATORY_READS" in cap
        # SC-0 内容：GD 权威源 + forbidden + 不新增 AGENTS.md
        assert "AGENTS.md" in cap
        assert "release" in cap  # forbidden 提及 release profiles

    def test_deep_allowed_commands_section(self):
        cap = _build_plan_capsule(deep=True)
        assert "允许的查证命令" in cap
        assert "rg" in cap and "git diff" in cap and "nl" in cap
        # 禁止项
        assert "git commit" in cap

    def test_lens_a_b_differentiate_not_neutral(self):
        # G1/G2 核心断言：A/B capsule 真分化，不落中立。
        # 用 lens 行独有的视角标记（句末括号）断言，避免与 GOAL 文本「权威目标链」误撞。
        cap_a = _build_plan_capsule(lens_emphasis="codex_A")
        cap_b = _build_plan_capsule(lens_emphasis="codex_B")
        assert "REVIEW_LENS_EMPHASIS: codex_A" in cap_a
        assert "REVIEW_LENS_EMPHASIS: codex_B" in cap_b
        # A=结构与符合性视角；B=对抗与边角视角 —— 互斥
        assert "结构与符合性视角" in cap_a
        assert "对抗与边角视角" not in cap_a
        assert "对抗与边角视角" in cap_b
        assert "结构与符合性视角" not in cap_b


# ---------------- SC-5 part 2: plan 直连路双 lens dispatch wiring ----------------


class TestPlanDirectDualLensGate:
    """_is_plan_direct_dual_lens gate：仅 plan+deep+非 controller 直连才双镜头。"""

    def _ns(self, kind, deep):
        import types
        return types.SimpleNamespace(kind=kind, deep=deep)

    def test_plan_deep_direct_enables_dual_lens(self, monkeypatch):
        import gd_codex_bridge_review as B
        monkeypatch.delenv(B._GD_ROUTER_INVOCATION_ENV, raising=False)
        assert B._is_plan_direct_dual_lens(self._ns("plan", True), True) is True

    def test_code_diff_never_dual_lens(self, monkeypatch):
        # G8 硬约束：code_diff 走 controller（已有双调度），bridge 不双调度
        import gd_codex_bridge_review as B
        monkeypatch.delenv(B._GD_ROUTER_INVOCATION_ENV, raising=False)
        assert B._is_plan_direct_dual_lens(self._ns("code_diff", True), True) is False

    def test_non_deep_plan_not_dual_lens(self, monkeypatch):
        import gd_codex_bridge_review as B
        monkeypatch.delenv(B._GD_ROUTER_INVOCATION_ENV, raising=False)
        assert B._is_plan_direct_dual_lens(self._ns("plan", False), False) is False

    def test_controller_invoked_plan_not_dual_lens(self, monkeypatch):
        # controller 已 dispatch codex_A/B，bridge 再双调度 → 嵌套 2→4（G8）
        import gd_codex_bridge_review as B
        monkeypatch.setenv(B._GD_ROUTER_INVOCATION_ENV, "ctrl-123")
        assert B._is_plan_direct_dual_lens(self._ns("plan", True), True) is False


class TestPlanDirectDualLensWiring:
    """_run_plan_direct_dual_lens stub smoke：dispatch 两次 + merge（monkeypatch writer）。"""

    def test_dispatches_twice_and_merges(self, monkeypatch, tmp_path):
        import types
        import gd_codex_bridge_review as B
        plan = tmp_path / "plan.md"
        plan.write_text("# p\n\n- [ ] SC-1 do x\n\nverify: true\n", encoding="utf-8")
        try:
            B.build_capsule_text("plan", plan, tmp_path, compat_v1=True, lens_emphasis="codex_A")
        except (ValueError, FileNotFoundError):
            pytest.skip("v1 plan template unavailable")

        calls = []

        def fake_dispatch(capsule_text, *, run_id, gd_baseline_key, kind, target_str,
                          run_cwd, compat_v1, deep):
            # codex_A run_id 带 -A → APPROVED；codex_B 带 -B → REQUIRES_CHANGES
            verdict = "APPROVED" if run_id.endswith("-A") else "REQUIRES_CHANGES"
            lens = "codex_A" if run_id.endswith("-A") else "codex_B"
            calls.append((lens, verdict))
            assert lens in capsule_text  # lens 文案内联进了 capsule
            return ({
                "reviewer": "codex", "review_kind": "plan", "review_target": target_str,
                "review_run_status": "completed", "gd_review_decision": verdict,
                "scope_checked": [], "findings": [], "merge_notes": {},
            }, f"/tmp/fake-{run_id}.md")

        monkeypatch.setattr(B, "_run_lens_dispatch", fake_dispatch)
        monkeypatch.setattr(B, "_run_l3_content_evidence", lambda *a, **k: None)

        out = tmp_path / "out.json"
        args = types.SimpleNamespace(
            queue_job_id=None, target_role=None, plan_file=None,
        )
        rc = B._run_plan_direct_dual_lens(
            args, plan, tmp_path, out, str(plan), "rid", True, None,
        )

        # 跑了 codex_A + codex_B 两次（不嵌套成 4）
        assert [c[0] for c in calls] == ["codex_A", "codex_B"]
        # 合并：APPROVED + REQUIRES_CHANGES → REQUIRES_CHANGES（从严）
        import json
        merged = json.loads(out.read_text(encoding="utf-8"))
        assert merged["gd_review_decision"] == "REQUIRES_CHANGES"
        # reviewer 用 schema 枚举内的 "codex"；双 lens 标识走 merge_notes.merge_strategy
        assert merged["reviewer"] == "codex"
        assert merged["merge_notes"]["merge_strategy"] == "dual_lens_verdict_arbitration"
        # 非 APPROVED → 非零退出（fail-closed exit code）
        assert rc == 1

    def test_dispatch_failure_aborts_fail_closed(self, monkeypatch, tmp_path):
        import types
        import gd_codex_bridge_review as B
        plan = tmp_path / "plan.md"
        plan.write_text("# p\n\n- [ ] SC-1 do x\n\nverify: true\n", encoding="utf-8")
        try:
            B.build_capsule_text("plan", plan, tmp_path, compat_v1=True, lens_emphasis="codex_A")
        except (ValueError, FileNotFoundError):
            pytest.skip("v1 plan template unavailable")

        def fake_dispatch(capsule_text, *, run_id, gd_baseline_key, kind, target_str,
                          run_cwd, compat_v1, deep):
            raise B._LensDispatchFailed(
                B._failed_mapped("codex", kind, target_str, "writer FAILED exit=1"),
                None, 1)

        monkeypatch.setattr(B, "_run_lens_dispatch", fake_dispatch)
        monkeypatch.setattr(B, "_run_l3_content_evidence", lambda *a, **k: None)

        out = tmp_path / "out.json"
        args = types.SimpleNamespace(queue_job_id=None, target_role=None, plan_file=None)
        rc = B._run_plan_direct_dual_lens(
            args, plan, tmp_path, out, str(plan), "rid", True, None,
        )
        # 单 lens dispatch 失败 → fail-closed 立即终止，不合并
        assert rc == 1
        import json
        m = json.loads(out.read_text(encoding="utf-8"))
        assert m["gd_review_decision"] == "FAILED"


# ---------------- ABC 修复回归：真实 plan 污染路径（T0-T7 + REVIEW_FOCUS 散提 SC-conformance）----------------


class TestReviewableIdExtractionPollution:
    """Issue1/2/3: target ID 提取必须结构化，正文散提（REVIEW_FOCUS 的 SC-conformance）不进 ID 集。"""

    _POLLUTED_PLAN = (
        "# plan\n\n"
        "## REVIEW_FOCUS\nSC-conformance lens；A/B 真分化不落中立。SC-1 也在正文提了。\n\n"
        "## T0 统一 L2 capsule 契约\n## T1 修 lens 断线\n## T2 副本机制\n"
        "## T3 --deep 入口\n## T4 code 路双镜头\n## T5 plan 双镜头\n## T6 复测\n## T7 文档\n\n"
        "- [ ] SC-conformance\n"  # checklist 形式（结构化）—— 这个该进 ID 集
    )

    def test_structured_excludes_prose_sc(self):
        # Issue1: REVIEW_FOCUS 正文里的 SC-1 散提不进 target ID 集；checklist SC-conformance 进
        from lib.sc_extraction import extract_reviewable_ids
        ids = extract_reviewable_ids(self._POLLUTED_PLAN)
        assert "SC-1" not in ids, "正文散提 SC-1 不该进结构化 ID 集"
        assert "SC-conformance" in ids, "checklist 形式的 SC-conformance 该进"
        assert {"T0", "T1", "T2", "T3", "T4", "T5", "T6", "T7"} <= ids

    def test_polluted_plan_capsule_expected_sc_ids(self):
        # Issue2: capsule EXPECTED_SC_IDS 不含正文 SC-1，含 T0-T7 + checklist SC-conformance
        import importlib.util, tempfile
        from pathlib import Path
        spec = importlib.util.spec_from_file_location(
            "b", "scripts/gd-codex-bridge-review.py")
        m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        plan = Path(tempfile.mkstemp(suffix=".md")[1])
        plan.write_text(self._POLLUTED_PLAN, encoding="utf-8")
        try:
            cap, *_ = m.build_capsule_text("plan", plan, plan.parent, compat_v1=True)
        except (ValueError, FileNotFoundError):
            pytest.skip("v1 plan template unavailable")
        exp_line = next(l for l in cap.splitlines() if l.startswith("EXPECTED_SC_IDS:"))
        ids_str = exp_line.split(":", 1)[1].strip()
        assert "SC-1" not in ids_str, "正文散提 SC-1 不该进 capsule EXPECTED_SC_IDS"
        assert "SC-conformance" in ids_str
        for t in ("T0", "T1", "T2", "T3", "T4", "T5", "T6", "T7"):
            assert t in ids_str

    def test_t_plan_approved_scope_not_rejected(self):
        # Issue3: T0-T7 覆盖的 APPROVED review 不再因 missing scope 被拒
        import importlib.util, tempfile
        from pathlib import Path
        plan = Path(tempfile.mkstemp(suffix=".md")[1])
        plan.write_text("# p\n## T0\n## T1\n## T2\n## T3\n## T4\n## T5\n## T6\n## T7\n", encoding="utf-8")
        rev = (
            "# Review\nVERDICT: APPROVED\nREVIEW_DOMAIN: ai_infra\n"
            "## Scope Checked\n"
            + "\n".join(f"| T{i} | pass | ok |" for i in range(8)) + "\n"
            "## Findings\nnone\n## Residual Risk\nnone\n"
        )
        spec = importlib.util.spec_from_file_location(
            "v", "scripts/gd-validate-review-content-evidence.py")
        v = importlib.util.module_from_spec(spec); spec.loader.exec_module(v)
        errs = []
        missing = v._check_scope_coverage(
            rev, v._extract_target_ids(plan.read_text()), "APPROVED", errs)
        assert missing == set(), f"T0-T7 全覆盖不该有 missing: {missing}"
        assert errs == [], f"不该报错: {errs}"

    def test_placeholder_sc_id_filtered_in_review_extract(self):
        # Fix C: codex 填的 placeholder「SC-ID」不被当引用 ID
        from lib.sc_extraction import extract_referenced_ids
        ids = extract_referenced_ids("finding: SC: SC-ID\nscope: | T0 | pass |")
        assert "SC-ID" not in ids, "placeholder SC-ID 该被过滤"
        assert "T0" in ids
