from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
PROMPTS_DIR = REPO_ROOT / "prompts"

EXPECTED_PROMPTS = (
    "01-root.md",
    "02-v00-constitution.md",
    "03-v01-foundations.md",
    "04-v02-prior-art-novelty.md",
    "05-v03-theory.md",
    "06-v04-mws.md",
    "07-v05-workload-ir.md",
    "08-v06-primitives.md",
    "09-v07-cost-model.md",
    "10-v08-search.md",
    "11-v09-codegen.md",
    "12-v10-runtime-adaptation.md",
    "13-v11-control-plane.md",
    "14-v12-terminal-ui.md",
    "15-v13-ai-copilot.md",
    "16-v14-benchmarking.md",
    "17-v15-research-evaluation.md",
    "18-v16-paper-patent.md",
    "19-v17-production.md",
    "20-v18-testing-ci.md",
    "21-v19-product-startup.md",
    "22-v20-docs-education.md",
    "23-v21-demo-competition.md",
    "24-v22-ecosystem.md",
    "25-v23-roadmap.md",
    "26-v24-reference-architecture.md",
    "27-v25-ai-build-protocol.md",
    "28-v26-audit.md",
    "29-v27-release-artifact.md",
    "30-grand-master.md",
    "31-v28-security.md",
    "32-v29-portability.md",
    "33-v30-hardware.md",
    "34-v31-advanced-primitives.md",
    "35-v32-composite-synthesis.md",
    "36-v33-distributed-edge.md",
    "37-v34-math-algorithms.md",
    "38-v35-contracts-tests-continuity.md",
    "39-grand-master-final.md",
)


def _read(relative: str) -> str:
    return (REPO_ROOT / relative).read_text(encoding="utf-8")


def test_canonical_prompt_directory_is_exactly_39_files() -> None:
    actual = tuple(sorted(path.name for path in PROMPTS_DIR.glob("*.md")))
    assert len(EXPECTED_PROMPTS) == 39
    assert actual == EXPECTED_PROMPTS


def test_true_final_and_checkpoint_markers_cannot_regress() -> None:
    final = _read("prompts/39-grand-master-final.md")
    checkpoint = _read("prompts/30-grand-master.md")
    root = _read("prompts/01-root.md")

    assert "canonical final integration prompt" in final.lower()
    assert "END OF THE CANONICAL 39-PROMPT MORPHEUS ENGINEERING BIBLE" in final
    assert "INTEGRATION CHECKPOINT" in checkpoint
    assert "END OF THE 30-PROMPT MORPHEUS ENGINEERING BIBLE" not in checkpoint
    assert "Prompt #39" in root
    assert "canonical final integration" in root.lower()


def test_index_and_entry_points_reference_true_final_and_every_prompt() -> None:
    index = _read("MASTER-INDEX.md")
    ai_start = _read("AI-START-HERE.md")
    readme = _read("README.md")
    checklist = _read("FINAL-CHECKLIST.md")
    corpus_manifest = _read("docs/CORPUS-MANIFEST.md")

    for filename in EXPECTED_PROMPTS:
        assert f"prompts/{filename}" in index, filename

    for document in (ai_start, readme, checklist, corpus_manifest):
        assert "prompts/39-grand-master-final.md" in document

    assert "39-prompt" in index.lower()
    assert "39-prompt" in corpus_manifest.lower()
    assert "39 canonical prompt" in checklist.lower()
    assert "30-volume Engineering Bible" not in readme


def test_prompt_numbers_are_contiguous_and_unique() -> None:
    numbers = [int(name[:2]) for name in EXPECTED_PROMPTS]
    assert numbers == list(range(1, 40))
    assert len(numbers) == len(set(numbers))