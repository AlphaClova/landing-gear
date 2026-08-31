"""Product-only prospectus enrichment. Never used on tax/institution/procedure/combined."""

from __future__ import annotations

from dataclasses import dataclass, field
import re

from app.agent.router import Intent
from app.api.schemas import Citation

PRODUCT_EVIDENCE_INTENTS: frozenset[str] = frozenset({"상품"})
BLOCKED_INTENTS: frozenset[str] = frozenset({"제도", "세제", "종합", "절차", "범위 밖"})

G033_FORBIDDEN_TAX_CLAIMS = (
    "법정외 퇴직금 재원은 과세가 발생하지 않습니다",
    "법정 외 퇴직금의 경우에는 IRP 추가 납입 시에는 과세가 발생하지만 퇴직금 재원은 과세가 발생하지 않습니다",
    "법정 외 퇴직금의 경우에는 IRP 추가 납입 시에는 과세가 발생하나 퇴직금 재원은 과세가 발생하지 않습니다",
)
G033_FORBIDDEN_TAX_CLAIM_RE = re.compile(
    r"법정외퇴직금.{0,160}(?:퇴직금)?재원.{0,24}과세가발생하지"
)

_RISK_SCALE = (
    "위험등급은 1등급이 매우 높은 위험, 2등급이 높은 위험, 3등급이 다소 높은 위험, "
    "4등급이 보통 위험, 5등급이 낮은 위험, 6등급이 매우 낮은 위험입니다."
)

_FEE_LINE = re.compile(
    r"수수료선취-오프라인\(A\)\s+(?:-\s+)?([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)"
    r"\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)",
)
_STRATEGY = re.compile(r"2\.\s*투자전략\s*투자전략\s*(.+?)\s*분류", re.S)
_AS_OF = re.compile(r"작성기준일\s*[:：]\s*(\d{4}년\s*\d{1,2}월\s*\d{1,2}일)")
_AUM = re.compile(
    r"(?:설정원본|순자산(?:총액)?)\s*[:：]?\s*([\d,\.]+)\s*(억|백만|만)?\s*원"
)
_RETURN_ROW = re.compile(
    r"(?:최근\s*)?(1|2|3)년(?:간)?\s*수익률(?!\s*변동성)\s*([+-]?\d+(?:\.\d+)?)\s*%"
)
_CLASS_RETURN_HINT = re.compile(r"(?:종류|클래스)\s*[A-Za-z가-힣0-9-]*")


@dataclass(frozen=True)
class FieldProvenance:
    product_id: str
    field: str
    value: str | None
    unit: str | None
    source_type: str
    document_id: str | None
    page: int | None
    evidence_id: str | None
    as_of_date: str | None = None


@dataclass(frozen=True)
class EvidenceValue:
    value: str
    unit: str | None
    document_id: str
    page: int | None
    evidence_id: str
    as_of_date: str | None = None
    source_type: str = "prospectus"


@dataclass
class ProductEvidenceBundle:
    product_id: str
    product_name: str
    product_fact: dict
    evidence_fields: dict[str, EvidenceValue] = field(default_factory=dict)
    unresolved_fields: list[str] = field(default_factory=list)
    citations: list[Citation] = field(default_factory=list)
    provenance: list[FieldProvenance] = field(default_factory=list)

    @property
    def status(self) -> str:
        return "RESOLVED"


class ProductEvidenceIsolationError(RuntimeError):
    """Raised when product enrichment is invoked outside the product-only path."""


def allows_product_evidence_enrichment(intent: Intent | str | None) -> bool:
    return str(intent or "") in PRODUCT_EVIDENCE_INTENTS


def assert_product_evidence_allowed(intent: Intent | str | None) -> None:
    if not allows_product_evidence_enrichment(intent):
        raise ProductEvidenceIsolationError(
            f"product evidence enrichment is forbidden for intent={intent!r}"
        )


def _compact(text: str) -> str:
    return re.sub(r"\s+", "", text)


def is_prospectus_citation(item: Citation) -> bool:
    return str(item.document_id).startswith("r2_") and not str(item.id).startswith("product-")


def _as_of(item: Citation) -> str | None:
    match = _AS_OF.search(item.excerpt)
    return re.sub(r"\s+", "", match.group(1)) if match else None


def citations_for_product(product: dict, evidence: list[Citation]) -> list[Citation]:
    name = _compact(str(product.get("product_name", "")))
    if not name:
        return []
    matched: list[Citation] = []
    for item in evidence:
        if not is_prospectus_citation(item):
            continue
        excerpt = _compact(item.excerpt)
        if name not in excerpt:
            continue
        # 초단기 prospectus must not attach to 단기 (and 중장기 not to 장기).
        if "초단기" in excerpt and "초단기" not in name:
            continue
        if "중장기" in excerpt and "중장기" not in name:
            continue
        matched.append(item)
    return matched


def _value(item: Citation, value: str, unit: str | None) -> EvidenceValue:
    return EvidenceValue(
        value=value,
        unit=unit,
        document_id=item.document_id,
        page=item.page,
        evidence_id=item.id,
        as_of_date=_as_of(item),
        source_type="prospectus",
    )


def extract_strategy(item: Citation) -> EvidenceValue | None:
    match = _STRATEGY.search(item.excerpt)
    if not match:
        return None
    text = re.sub(r"\s+", " ", match.group(1)).strip(" .")
    if len(text) < 12:
        return None
    if len(text) > 180:
        text = text[:177].rstrip() + "…"
    return _value(item, text, None)


def extract_class_fee(item: Citation) -> dict[str, EvidenceValue]:
    match = _FEE_LINE.search(item.excerpt)
    if not match:
        return {}
    return {
        "sales_class": _value(item, "수수료선취-오프라인(A)", None),
        "total_fee_rate_percent": _value(item, match.group(4), "percent"),
        "cost_example_10m_krw_1y": _value(item, match.group(5), "천원"),
        "cost_example_10m_krw_2y": _value(item, match.group(6), "천원"),
        "cost_example_10m_krw_3y": _value(item, match.group(7), "천원"),
        "cost_example_10m_krw_5y": _value(item, match.group(8), "천원"),
        "cost_example_10m_krw_10y": _value(item, match.group(9), "천원"),
    }


def extract_historical_returns(item: Citation) -> dict[str, EvidenceValue]:
    fields: dict[str, EvidenceValue] = {}
    if "VaR" in item.excerpt or "수익률 변동성" in item.excerpt.replace(" ", ""):
        # Volatility is not a historical return series.
        pass
    class_hint = _CLASS_RETURN_HINT.search(item.excerpt)
    basis = "class" if class_hint else "unspecified"
    for match in _RETURN_ROW.finditer(item.excerpt):
        year = match.group(1)
        key = f"historical_return_{year}y"
        label = f"{match.group(2)}% (과거 수익률, 기준={basis})"
        fields[key] = _value(item, label, "percent")
    return fields


def extract_aum(item: Citation) -> EvidenceValue | None:
    match = _AUM.search(item.excerpt)
    if not match:
        return None
    amount = match.group(1)
    if amount.replace(",", "").replace(".", "") in {"0", ""}:
        return None
    unit = match.group(2) or ""
    as_of = _as_of(item)
    text = f"{amount}{unit}원"
    if as_of:
        text = f"{text} (기준일 {as_of})"
    return _value(item, text, f"{unit}원" if unit else "원")


def _fact_provenance(product: dict, field: str, value: str | None, unit: str | None) -> FieldProvenance:
    return FieldProvenance(
        product_id=str(product.get("product_id") or ""),
        field=field,
        value=value,
        unit=unit,
        source_type="product_fact",
        document_id=product.get("document_id"),
        page=product.get("page"),
        evidence_id=None,
        as_of_date=None,
    )


def _ev_provenance(product: dict, field: str, item: EvidenceValue) -> FieldProvenance:
    return FieldProvenance(
        product_id=str(product.get("product_id") or ""),
        field=field,
        value=item.value,
        unit=item.unit,
        source_type=item.source_type,
        document_id=item.document_id,
        page=item.page,
        evidence_id=item.evidence_id,
        as_of_date=item.as_of_date,
    )


def build_product_evidence_bundles(
    products: list[dict],
    evidence: list[Citation],
    *,
    intent: Intent | str | None,
) -> list[ProductEvidenceBundle]:
    assert_product_evidence_allowed(intent)
    wanted = (
        "sales_class",
        "total_fee_rate_percent",
        "historical_return_1y",
        "historical_return_2y",
        "historical_return_3y",
        "aum",
        "investment_strategy",
    )
    bundles: list[ProductEvidenceBundle] = []
    for product in products:
        citations = citations_for_product(product, evidence)
        fields: dict[str, EvidenceValue] = {}
        provenance = [
            _fact_provenance(product, "asset_type", product.get("asset_type"), None),
            _fact_provenance(product, "risk_grade", str(product.get("risk_level")) if product.get("risk_level") is not None else None, None),
            _fact_provenance(product, "account_eligibility", str(product.get("plan_types")), None),
        ]
        for item in citations:
            if "investment_strategy" not in fields:
                strategy = extract_strategy(item)
                if strategy:
                    fields["investment_strategy"] = strategy
            for key, value in extract_class_fee(item).items():
                fields.setdefault(key, value)
            for key, value in extract_historical_returns(item).items():
                fields.setdefault(key, value)
            if "aum" not in fields:
                aum = extract_aum(item)
                if aum:
                    fields["aum"] = aum
        for key, value in fields.items():
            provenance.append(_ev_provenance(product, key, value))
        unresolved = [key for key in wanted if key not in fields]
        for key in unresolved:
            provenance.append(
                FieldProvenance(
                    product_id=str(product.get("product_id") or ""),
                    field=key,
                    value=None,
                    unit=None,
                    source_type="missing",
                    document_id=None,
                    page=None,
                    evidence_id=None,
                    as_of_date=None,
                )
            )
        bundles.append(
            ProductEvidenceBundle(
                product_id=str(product.get("product_id") or ""),
                product_name=str(product.get("product_name") or ""),
                product_fact=product,
                evidence_fields=fields,
                unresolved_fields=unresolved,
                citations=citations,
                provenance=provenance,
            )
        )
    return bundles


def render_cost_claim(bundle: ProductEvidenceBundle, *, intent: Intent | str | None) -> str | None:
    assert_product_evidence_allowed(intent)
    rate = bundle.evidence_fields.get("total_fee_rate_percent")
    y1 = bundle.evidence_fields.get("cost_example_10m_krw_1y")
    y2 = bundle.evidence_fields.get("cost_example_10m_krw_2y")
    y3 = bundle.evidence_fields.get("cost_example_10m_krw_3y")
    y5 = bundle.evidence_fields.get("cost_example_10m_krw_5y")
    y10 = bundle.evidence_fields.get("cost_example_10m_krw_10y")
    cls = bundle.evidence_fields.get("sales_class")
    if not (rate and y1 and y2 and y3 and y5 and y10 and cls):
        return None
    return (
        f"투자설명서의 {cls.value} 클래스 기준 총보수·비용 비율은 {rate.value}%입니다. "
        f"1,000만원 투자 시 총비용 예시는 1년 {y1.value}천원, 2년 {y2.value}천원, 3년 {y3.value}천원, "
        f"5년 {y5.value}천원, 10년 {y10.value}천원입니다. "
        "이는 총보수율(%)과 투자기간별 총비용 예시(천원)를 구분한 값입니다."
    )


def _same_risk(bundles: list[ProductEvidenceBundle]) -> bool:
    grades = {item.product_fact.get("risk_level") for item in bundles}
    return len(grades) == 1 and None not in grades


def render_product_comparison(
    question: str,
    products: list[dict],
    evidence: list[Citation],
    *,
    intent: Intent | str | None,
) -> tuple[str, list[Citation], list[str]]:
    assert_product_evidence_allowed(intent)
    bundles = build_product_evidence_bundles(products, evidence, intent=intent)
    lines = ["제공된 Product Fact와 투자설명서 기준 비교입니다.", _RISK_SCALE]
    used: list[Citation] = []
    seen_ids: set[str] = set()
    missing_strategy: list[str] = []
    missing_fee: list[str] = []
    missing_return: list[str] = []
    missing_aum: list[str] = []
    return_bases: set[str] = set()
    any_return = False

    for bundle in bundles:
        fact = bundle.product_fact
        lines.append(
            f"- {fact.get('product_name')}: 자산유형 {fact.get('asset_type')}, "
            f"위험등급 {fact.get('risk_level')}등급({fact.get('risk_label')}), "
            f"가입 가능 계좌 {fact.get('plan_types')}"
        )
        strategy = bundle.evidence_fields.get("investment_strategy")
        if strategy:
            lines.append(f"  · 투자전략: {strategy.value}")
        else:
            missing_strategy.append(bundle.product_name)
        cls = bundle.evidence_fields.get("sales_class")
        rate = bundle.evidence_fields.get("total_fee_rate_percent")
        y1 = bundle.evidence_fields.get("cost_example_10m_krw_1y")
        y3 = bundle.evidence_fields.get("cost_example_10m_krw_3y")
        if cls and rate and y1 and y3:
            lines.append(
                f"  · 클래스 {cls.value}, 총보수·비용 비율 {rate.value}%. "
                f"1,000만원 투자 시 총비용 예시 1년 {y1.value}천원, 3년 {y3.value}천원."
            )
        else:
            missing_fee.append(bundle.product_name)
        returns = [
            (label, bundle.evidence_fields.get(key))
            for label, key in (
                ("1년", "historical_return_1y"),
                ("2년", "historical_return_2y"),
                ("3년", "historical_return_3y"),
            )
            if bundle.evidence_fields.get(key)
        ]
        if returns:
            any_return = True
            joined = ", ".join(f"{label} {item.value}" for label, item in returns)
            lines.append(f"  · 과거 수익률({joined}). 과거 실적이며 미래 성과를 보장하지 않습니다.")
            for _, item in returns:
                if item and "기준=class" in item.value:
                    return_bases.add("class")
                elif item and "기준=unspecified" in item.value:
                    return_bases.add("unspecified")
        else:
            missing_return.append(bundle.product_name)
        aum = bundle.evidence_fields.get("aum")
        if aum:
            lines.append(f"  · 설정원본·순자산 {aum.value}.")
        else:
            missing_aum.append(bundle.product_name)
        for citation in bundle.citations:
            if citation.id not in seen_ids:
                used.append(citation)
                seen_ids.add(citation.id)

    limitations: list[str] = []
    def _axis_limit(missing: list[str], all_label: str, one_label: str) -> None:
        if not missing:
            return
        if len(missing) == len(bundles):
            limitations.append(
                f"[한계] {all_label} 요청 상품 모두 동일 기준 excerpt에서 확인되지 않아 이 축으로는 비교하지 않았습니다."
                if len(bundles) > 1 else f"[한계] {one_label} 현재 투자설명서 excerpt에서 확인되지 않습니다."
            )
        else:
            limitations.append(f"[한계] {one_label} 다음 상품 excerpt에서 확인되지 않습니다: {', '.join(missing)}.")

    _axis_limit(missing_strategy, "투자전략은", "투자전략은")
    _axis_limit(missing_fee, "총보수·비용은", "총보수·비용은")
    _axis_limit(missing_return, "과거 수익률은", "과거 수익률은")
    _axis_limit(missing_aum, "설정원본·순자산(AUM)은", "설정원본·순자산(AUM)은")
    if any_return and ("unspecified" in return_bases or len(return_bases) > 1):
        limitations.append("[한계] 클래스 수익률과 펀드 전체 수익률 기준이 서로 다르거나 확인되지 않아 과거 수익률로 순위를 매기지 않습니다.")
    if len(bundles) >= 2 and _same_risk(bundles) and any(x in question for x in ("안정", "안전한")):
        limitations.append("[한계] 위험등급이 같아도 그 사실만으로 셋 중 하나를 단정 추천하지 않습니다. 투자기간·금리 민감도·듀레이션은 현재 excerpt에서 확인되지 않습니다.")
    else:
        limitations.append("[한계] 상품명만으로 듀레이션·변동성이나 개인 적합성을 단정할 수 없습니다.")
    if any_return:
        limitations.append("[한계] 과거 수익률은 미래 성과를 보장하지 않습니다.")
    lines.extend(limitations)
    return "\n".join(lines), used, limitations
