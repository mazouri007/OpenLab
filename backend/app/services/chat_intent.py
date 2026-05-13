from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


ChatAction = Literal["answer", "review", "test", "review_and_test"]

REVIEW_KEYWORDS = {
    "审查",
    "代码审查",
    "review",
    "风险",
    "规范",
    "安全",
    "漏洞",
    "bug",
    "缺陷",
    "符合",
}
TEST_KEYWORDS = {
    "测试",
    "单测",
    "补测试",
    "测试用例",
    "pytest",
    "junit",
    "test",
    "unit test",
    "coverage",
}


@dataclass(frozen=True)
class ChatIntent:
    action: ChatAction
    reason: str


def detect_chat_intent(explicit_action: str, question: str) -> ChatIntent:
    if explicit_action and explicit_action != "auto":
        if explicit_action == "review_and_test":
            return ChatIntent(action="review_and_test", reason="explicit_action")
        if explicit_action in {"answer", "review", "test"}:
            return ChatIntent(action=explicit_action, reason="explicit_action")  # type: ignore[arg-type]

    normalized = question.lower()
    wants_review = any(keyword in normalized for keyword in REVIEW_KEYWORDS)
    wants_test = any(keyword in normalized for keyword in TEST_KEYWORDS)
    if wants_review and wants_test:
        return ChatIntent(action="review_and_test", reason="review_and_test_keywords")
    if wants_test:
        return ChatIntent(action="test", reason="test_keywords")
    if wants_review:
        return ChatIntent(action="review", reason="review_keywords")
    return ChatIntent(action="answer", reason="default_answer")
