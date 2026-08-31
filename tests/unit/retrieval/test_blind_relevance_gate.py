import pytest

from app.tools.retriever import retrieve_evidence


BLIND_CASES = [
    ("확정급여형과 확정기여형 운용 책임 차이는?", "pension_system", True),
    ("IRP 세액공제 최대 금액", "withdrawal_tax", True),
    ("퇴직소득세를 연금으로 받으면 감면되나요", "withdrawal_tax", True),
    ("솔로몬 단기 국공채 위험등급", "product", True),
    ("장기 국공채 펀드의 금리 위험", "product", True),
    ("개인형퇴직연금 중도인출 사유", None, True),
    ("퇴직연금 가입 대상 근속기간", "pension_system", True),
    ("DB 적립금은 누가 운용하나요", "pension_system", True),
    ("DC 퇴직급여 산정 방식", "pension_system", True),
    ("연금저축 공제율", "withdrawal_tax", True),
    ("IRP 계약이전 방법", None, True),
    ("퇴직금 연금수령 11년차 세율", "withdrawal_tax", True),
    ("국공채 펀드 총보수", "product", True),
    ("퇴직연금 개설 절차", None, True),
    ("연금소득세 과세 기준", "withdrawal_tax", True),
    ("연금 오늘 기온", None, False),
    ("세액공제 축구 순위", None, False),
    ("퇴직연금 영화 추천", None, False),
    ("IRP 야구 일정", None, False),
    ("펀드 저녁 요리법", None, False),
    ("퇴직소득세 파이썬 코드", None, False),
    ("국공채 제주도 날씨", None, False),
    ("상품 아이스크림 맛", None, False),
    ("DB 영어 번역", None, False),
    ("연금소득세 농구 결과", None, False),
    ("양자컴퓨터 오류 정정", None, False),
    ("화성 탐사선 착륙", None, False),
    ("김치찌개 조리 시간", None, False),
    ("파이썬 리스트 정렬", None, False),
    ("서울 지하철 노선", None, False),
]


@pytest.mark.parametrize("query,topic,expected", BLIND_CASES)
def test_blind_relevance_gate(query: str, topic: str | None, expected: bool) -> None:
    assert bool(retrieve_evidence(query, topic, 5)) is expected
