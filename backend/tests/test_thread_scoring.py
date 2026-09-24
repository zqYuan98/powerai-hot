from models import schema
from services.threads import keyword_affinity, score_for_threads


def _thread(name: str, weight: float, keywords: list[str]) -> schema.ResearchThread:
    return schema.ResearchThread(
        name=name,
        description=f"{name} 的研究范围。",
        keywords=keywords,
        weight=weight,
        status="active",
    )


def test_score_for_threads_selects_weighted_primary_and_uses_lower_id_for_ties(db):
    first = _thread("文档理解", 1.0, ["OCR"])
    second = _thread("边缘部署", 1.25, ["量化"])
    db.add_all([first, second])
    db.flush()

    result = score_for_threads(
        {"firsthand": 80, "utility": 70, "depth": 60},
        {str(first.id): 80, str(second.id): 64},
        [first, second],
        tier="T1",
        kind="论文",
    )

    assert result.primary_thread_id == first.id
    assert result.thread_score == 80
    assert result.learn_score == 75


def test_keyword_affinity_uses_unique_matches_and_ignores_paused_threads(db):
    active = _thread("文档理解", 1.0, ["OCR", "文档理解"])
    paused = _thread("电力", 1.0, ["电网"])
    paused.status = "paused"
    db.add_all([active, paused])
    db.flush()

    affinity = keyword_affinity(
        "OCR 文档理解实践",
        "OCR 在文档理解中的应用",
        "",
        [active, paused],
    )

    assert affinity == {str(active.id): 75}
