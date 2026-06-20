#!/usr/bin/env python3
"""gd-validate-l1-command-contract.py — L1 /review1 command document contract.

SC-5: 固化 L1 "轻量第二意见" 使用场景为可测试合同,防止 L1 被误改成 L2/L3 缩水版.

检查 commands/review1.md 的稳定标记 (非自然语言理解):
  - discuss 默认模式: RECOMMENDATION: / 无 verdict / 不写 review-baseline
  - --review 模式: VERDICT: APPROVED|REQUIRES_CHANGES + 写 review-baseline
  - 保留 --no-stop-marker 路由 (防 stop hook 误判)
  - 继续引用 codex-consult.sh 与 review-result-writer.sh (writer 强制路由 = Claude 不手写裸 VERDICT)
  - 两种模式表格行完整
  - 不含 L2/L3 专属语义 (release gate / dual-lens / 双镜头 / multi-agent / 子 agent / controller)

用法: python3 gd-validate-l1-command-contract.py commands/review1.md
输出: L1_COMMAND_CONTRACT: pass  (exit 0) 或失败原因 (exit 1)
"""
import re
import sys
from pathlib import Path


def check(text: str) -> list[str]:
    errs: list[str] = []

    def must_contain(needle: str, desc: str) -> None:
        if needle not in text:
            errs.append(f"missing: {desc} (needle={needle!r})")

    # --- discuss default mode markers ---
    must_contain("RECOMMENDATION:", "discuss RECOMMENDATION marker")
    must_contain("无 verdict", "discuss no-verdict statement")
    must_contain("不写 review-baseline", "discuss no-baseline-write statement")

    # --- --review mode markers ---
    must_contain("VERDICT: APPROVED", "review APPROVED verdict")
    must_contain("REQUIRES_CHANGES", "review REQUIRES_CHANGES verdict")
    must_contain("写 review-baseline", "review baseline-write statement")

    # --- transport routing ---
    must_contain("--no-stop-marker", "--no-stop-marker routing")
    must_contain("codex-consult.sh", "codex-consult.sh reference")
    must_contain("review-result-writer.sh", "review-result-writer.sh reference")
    # writer 强制路由 = Claude 不得手写裸 VERDICT, 只展示 writer 摘要
    must_contain("Writer 强制路由", "writer-forced routing (Claude must not hand-write VERDICT)")

    # --- 两种模式 table rows intact (stable markers, not NL understanding) ---
    if not re.search(r"\|\s*\*\*讨论\*\*.*?RECOMMENDATION:.*?无 verdict.*?不写 review-baseline", text, re.S):
        errs.append("两种模式 table: discuss row marker mismatch")
    if not re.search(r"\|\s*\*\*审核\*\*.*?VERDICT: APPROVED.*?写 review-baseline", text, re.S):
        errs.append("两种模式 table: review row marker mismatch")

    # --- L1 must NOT carry L2/L3 exclusive semantics as its own description ---
    # These tokens are absent from a correct L1 doc (verified against current baseline).
    # "多 agent" is allowed because line 9 legitimately references L3 in the layer map.
    forbidden_tokens = [
        "release gate", "dual-lens", "双镜头",
        "multi-agent", "子 agent", "controller",
    ]
    for tok in forbidden_tokens:
        if tok in text:
            errs.append(f"forbidden L2/L3 token present: {tok!r}")

    return errs


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: gd-validate-l1-command-contract.py <review1.md>", file=sys.stderr)
        return 2
    path = Path(argv[1])
    if not path.is_file():
        print(f"L1_COMMAND_CONTRACT: fail — file not found: {path}")
        return 1
    text = path.read_text(encoding="utf-8")
    errs = check(text)
    if errs:
        print("L1_COMMAND_CONTRACT: fail")
        for e in errs:
            print(f"  - {e}")
        return 1
    print("L1_COMMAND_CONTRACT: pass")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
