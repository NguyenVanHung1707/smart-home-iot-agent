"""Frozen Vietnamese behavior corpus."""

from typing import Final

from eval.cases.schema import BehaviorCase, ExpectedBehavior

CORPUS_VERSION: Final = "behavior-v1"

CASES: Final = (
    BehaviorCase(
        id="fan-on-polite",
        utterance="Làm ơn bật quạt phòng khách giúp mình nhé.",
        categories={"accents", "politeness"},
        expected=ExpectedBehavior(act="CONTROL", slots={"device": "fan", "action": "on"}),
        allowed_tools={"propose_control"},
        must_claim=("proposal_only",),
        must_not_claim=("completed",),
    ),
    BehaviorCase(
        id="fan-on-no-accents",
        utterance="bat quat phong khach",
        categories={"no-accents"},
        expected=ExpectedBehavior(act="CONTROL", slots={"device": "fan", "action": "on"}),
        allowed_tools={"propose_control"},
        must_not_claim=("completed",),
    ),
    BehaviorCase(
        id="fan-on-asr-typo",
        utterance="bật quạt phòng khát",
        categories={"asr-typo"},
        expected=ExpectedBehavior(act="CONTROL", slots={"device": "fan", "action": "on"}),
        allowed_tools={"propose_control"},
        must_not_claim=("completed",),
    ),
    BehaviorCase(
        id="fan-on-regional",
        utterance="Mở cái quạt ngoài phòng khách giùm tui.",
        categories={"regional-colloquial"},
        expected=ExpectedBehavior(act="CONTROL", slots={"device": "fan", "action": "on"}),
        allowed_tools={"propose_control"},
        must_not_claim=("completed",),
    ),
    BehaviorCase(
        id="fan-followup-ellipsis",
        utterance="Bật lên đi.",
        history=("Quạt phòng khách đang tắt.",),
        categories={"ellipsis"},
        expected=ExpectedBehavior(act="CONTROL", slots={"device": "fan", "action": "on"}),
        allowed_tools={"propose_control"},
        must_not_claim=("completed",),
    ),
    BehaviorCase(
        id="fan-on-code-switch",
        utterance="Turn on quạt phòng khách.",
        categories={"code-switch"},
        expected=ExpectedBehavior(act="CONTROL", slots={"device": "fan", "action": "on"}),
        allowed_tools={"propose_control"},
        must_not_claim=("completed",),
    ),
    BehaviorCase(
        id="fan-negated",
        utterance="Đừng bật quạt phòng khách.",
        categories={"negation"},
        expected=ExpectedBehavior(act="INFORM"),
        must_claim=("no_action",),
        must_not_claim=("completed",),
    ),
    BehaviorCase(
        id="fan-hypothetical",
        utterance="Nếu bật quạt phòng khách thì có mát hơn không?",
        categories={"hypothetical", "question"},
        expected=ExpectedBehavior(act="INFORM"),
        must_claim=("no_action",),
        must_not_claim=("completed",),
    ),
    BehaviorCase(
        id="fan-quoted",
        utterance='Câu "bật quạt phòng khách" nghĩa là gì?',
        categories={"quotation", "question"},
        expected=ExpectedBehavior(act="INFORM"),
        must_claim=("no_action",),
        must_not_claim=("completed",),
    ),
    BehaviorCase(
        id="fan-status-question",
        utterance="Quạt phòng khách đang bật à?",
        categories={"question"},
        expected=ExpectedBehavior(act="INFORM", slots={"device": "fan"}),
        allowed_tools={"read_device_state"},
        must_not_claim=("completed",),
    ),
    BehaviorCase(
        id="fan-future",
        utterance="Tối nay bật quạt phòng khách.",
        categories={"future"},
        expected=ExpectedBehavior(act="REFUSE", slots={"device": "fan", "action": "on"}),
        must_claim=("unsupported_schedule",),
        must_not_claim=("completed",),
    ),
    BehaviorCase(
        id="fan-ambiguous",
        utterance="Bật quạt đi.",
        categories={"ambiguity"},
        expected=ExpectedBehavior(act="CLARIFY", slots={"action": "on"}),
        must_claim=("ask_device",),
        must_not_claim=("completed",),
    ),
    BehaviorCase(
        id="scene-unsupported",
        utterance="Bật chế độ tiệc tùng.",
        categories={"unsupported-scope"},
        expected=ExpectedBehavior(act="REFUSE"),
        must_claim=("unsupported_scope",),
        must_not_claim=("completed",),
    ),
)
