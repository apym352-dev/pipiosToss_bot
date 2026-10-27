# -*- coding: utf-8 -*-
"""
# MODIFIED: quant_engine.py
순수 롱(SOXL) 전용 '8%(12.5분할) 황금비율 정액제 기반 정량 산출기(min(1회분 예산 상한 주수, 기준가 고정 정량) 이중 캡핑 Case 67 탑재) ·
온디맨드 예비시드 수혈금(injected_reserve_usd)을 제외한 순수 코어 총자산(core_equity) 기반 8% 정량 스케일 보존 ·
자투리 절약금 및 세후 실물 수익금 실시간 시드 풀 무리셋 연속 복리 산입 ·
최종 확정 진화 챔피언(🌟 POCKET_ALLIN / 🔥 GRID_L1_ALLIN × 💉 05_RESV_6P_GUARD30 × 🔓 06_STEP2X_15PCT_C20 · 기본값 NONE[OFF]) 보유 회차별 4단 와이드 점진 활주로
(1~4회 -1.0% / 5~8회 -2.0% / 9~10회 -3.5% / 11회+ -5.5% 및 골든포켓 +1.50% / 1층 +1.50% / 2~7층 +1.00%) ·
미동부 프리장 황금시간대(07:00 ~ 07:50 EST & 1분봉 Wilder RSI(14) <= 19.0) 가용 현금 시드 100% 전액 추가매수 판정기(evaluate_golden_allin_signal · Case 80) &
독립 골든포켓(GoldenAllInPocket · +1.50% 익절) 분리회계 구조체 ·
3중 안전문(보유 2개층 이하 & 가용현금 비중 20.0%+ & 저점대비 2.0배+ 대반등) 통과 시 활성 1층 단가 대비 -15.0% 조건부 스텝업 저가 해금 판정기(evaluate_step_up_2x_dip_signal · Case 76) ·
30% 자투리 1주 승격 방지 가드(GUARD30) & 토스 실계좌 여유자금(1회분 이상) 감지 기반 최대 +6회분 온디맨드 예비시드 자동 수혈 판정기(evaluate_guard30_and_reserve_injection · Case 77) ·
0주 전량 졸업 시 예비시드 원금 자동 상환 및 6회분 한도 복구 연산기(compute_reserve_repayment_on_zero · Case 77) ·
상단 그리드(2층 ~ 7층) 보유 중 1층 공석 시 60초(1분) 타임쉴드 주기 눌림목(-1.00%) OR 상승돌파(+1.00%) 하이브리드 독립 1층(REENTRY_1FL) 재장전 판정기 &
현재가 > 2층 단가(min_upper_tier_price) 시 1층 > 2층 단가 역전 원천 차단(HOLD_PREVENT_INVERSION · Case 73) 가드 ·
1층 ~ 7층 순수 원가 골디락스 멀티 그리드 관리(MAX_GRID_TIERS_7 = 7 : 1층 공격수 + 2~6층 개별 완충층[5개] + 통합 7층 본대[GRID_L7] ·
REENTRY_1FL 독립 1층 배치 vs TOPUP_1FL 기존 1층 무승격 원자적 합산[Case 78] vs DIP_1FL/GOLDEN_L1 2~6층 개별 승격 및 8회차 이상 최상단 6층+7층 통합 7층 병합 ·
수동 매수 시 단가 비교 오름차순 층간 스마트 편입 & 수동 매도 시 층별/포켓별 순수원가 1:1 매칭 정산기 탑재 · Case 53 하드 캡핑 · Case 63, Case 69, Case 71 ~ 80) ·
2층 ~ 7층 통합 이동평균(wma_2_to_7) 산출 및 4중 다중 익절 판정(① 독립 골든포켓 +1.50% / ② 1층 +1.50% / ③ 2~6층 개별 및 통합 7층 +1.00% / ④ 2~7층 통합 이동평균 +1.00% · Case 71, Case 72, Case 80) ·
순수 실물 원가 무결성(book_price == actual_avg_price · 리앵커링 원가 차감 영구 폐기 · Case 69, Case 71) ·
정적 기억 최저 매수가(cycle_min_buy_price) 기본 잠금/조건부 스텝업 및 당일 프리장~정규장 시드보호 패스(daily_seed_protect_pass_cnt · Case 74) 요약 · TDD 검증' 코어 모듈 (Step 05 / 10)
- 제1헌법 ~ 제6헌법 및 Case 01 ~ 80 완벽 준수
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

import toss_api
from toss_api import safe_float, safe_int

logger = logging.getLogger("toss_sniper.quant_engine")

# toss_api.py 내부 상수 존재 여부와 무관하게 100% 안전하게 작동하는 자립형 폴백 상수 정의
DEFAULT_INITIAL_SEED_USD: float = float(
    getattr(toss_api, "DEFAULT_INITIAL_SEED_USD", 10000.0)
)
PORTION_RATIO_LOCKED: float = float(
    getattr(toss_api, "PORTION_RATIO_LOCKED", 0.08)
)
REANCHOR_NET_BUFFER_MULT: float = float(
    getattr(toss_api, "REANCHOR_NET_BUFFER_MULT", 0.994)
)
ROUND_TRIP_FEE_RATE_PCT: float = float(
    getattr(toss_api, "ROUND_TRIP_FEE_RATE_PCT", 0.14)
)

# 8%(12.5분할) 황금비율 기준 기본 분할 회차 및 1~7층 골디락스 멀티 그리드 최대 층수 상수 (Case 72)
BASE_MAX_LOTS_8PCT: int = 12
MAX_GRID_TIERS_7: int = int(getattr(toss_api, "MAX_GRID_TIERS_7", 7))
MAX_GRID_TIERS: int = MAX_GRID_TIERS_7
# 타 모듈 AST 심볼 임포트 호환을 위해 MAX_GRID_TIERS_12 별칭을 7 로 동시 유지
MAX_GRID_TIERS_12: int = MAX_GRID_TIERS_7

# 🎯 4 & Case 59, Case 71, Case 72, Case 73: 상단 그리드(2~7층) 보유 중 1층 공석 시 60초 주기 눌림목/상승돌파 임계치(%)
REENTRY_PULLBACK_DROP_PCT: float = -1.00
REENTRY_BREAKOUT_RISE_PCT: float = 1.00

# Case 76: 🔓 06_STEP2X_15PCT_C20 3중 안전문 기반 조건부 스텝업 저가 해금 상수
DEFAULT_UNLOCK_MODE: str = str(
    getattr(toss_api, "DEFAULT_UNLOCK_MODE", "STEP2X_15PCT_C20")
)
STEP_UP_2X_MIN_REBOUND_MULT: float = float(
    getattr(toss_api, "STEP_UP_2X_MIN_REBOUND_MULT", 2.0)
)
STEP_UP_2X_MAX_TIERS: int = int(
    getattr(toss_api, "STEP_UP_2X_MAX_TIERS", 2)
)
STEP_UP_2X_MIN_CASH_RATIO: float = float(
    getattr(toss_api, "STEP_UP_2X_MIN_CASH_RATIO", 0.20)
)
STEP_UP_2X_DROP_PCT: float = float(
    getattr(toss_api, "STEP_UP_2X_DROP_PCT", 15.0)
)

# Case 77: 💉 05_RESV_6P_GUARD30 (30% 자투리 승격 방지 가드 & 최대 +6회분 온디맨드 예비시드 자동 수혈) 상수
MAX_RESERVE_PORTIONS: int = int(
    getattr(toss_api, "MAX_RESERVE_PORTIONS", 6)
)
MIN_DIP_BUDGET_RATIO: float = float(
    getattr(toss_api, "MIN_DIP_BUDGET_RATIO", 0.30)
)
MIN_DIP_VS_L1_RATIO: float = float(
    getattr(toss_api, "MIN_DIP_VS_L1_RATIO", 0.30)
)
RESERVE_DEPOSIT_TOLERANCE_RATIO: float = float(
    getattr(toss_api, "RESERVE_DEPOSIT_TOLERANCE_RATIO", 0.95)
)

# NEW [Case 80]: 미동부 프리장 황금시간대(07:00 ~ 07:50 EST & RSI(14) <= 19.0) 가용현금 100% 전액 추가매수 상수
# 사용자 지시에 따라 기본값은 반드시 "NONE" (OFF) 으로 고정!
GOLDEN_ALLIN_MODES: Tuple[str, ...] = tuple(
    getattr(
        toss_api,
        "GOLDEN_ALLIN_MODES",
        ("NONE", "POCKET_ALLIN", "GRID_L1_ALLIN"),
    )
)
DEFAULT_GOLDEN_ALLIN_MODE: str = str(
    getattr(toss_api, "DEFAULT_GOLDEN_ALLIN_MODE", "NONE")
)
GOLDEN_WINDOW_START_HM: int = int(
    getattr(toss_api, "GOLDEN_WINDOW_START_HM", 700)
)
GOLDEN_WINDOW_END_HM: int = int(
    getattr(toss_api, "GOLDEN_WINDOW_END_HM", 750)
)
GOLDEN_RSI_MAX_THRESHOLD: float = float(
    getattr(toss_api, "GOLDEN_RSI_MAX_THRESHOLD", 19.0)
)
GOLDEN_POCKET_RISE_PCT: float = float(
    getattr(toss_api, "GOLDEN_POCKET_RISE_PCT", 1.50)
)


def get_golden_allin_mode_label(mode: str) -> str:
    """
    # NEW [Case 80 : 황금시간대(07:00 ~ 07:50 EST & RSI <= 19.0) 전액매수 모드 한글 상태 라벨]:
    전술 제어반(/settlement), 레이더(/avwap), 지시서(/sync)에서 표출할 직관적인 모드명을 반환한다.
    """
    m = str(mode or DEFAULT_GOLDEN_ALLIN_MODE).upper().strip()
    if m == "POCKET_ALLIN":
        return "🌟 독립 골든포켓 100% (ON·권장)"
    if m == "GRID_L1_ALLIN":
        return "🔥 7층 그리드 1층편입 100% (ON)"
    return "⚪ 사용 안 함 (OFF·기본챔피언)"


# ---------------------------------------------------------------------------
# [핵심 1] StratumBucket & GoldenAllInPocket : 순수 실물 매수 원가(book_price == actual_avg_price) 구조체 (Case 46 ~ 80)
# ---------------------------------------------------------------------------
@dataclass
class StratumBucket:
    """
    🎯 3 & Case 46 ~ 80:
    SOXL 1층 ~ 7층 골디락스 멀티 그리드(1층 공격수 L1 / 2층 ~ 6층 개별 완충층 GRID_L2 ~ GRID_L6 / 통합 7층 본대 GRID_L7) 데이터 구조체.
    - qty              : 보유 정수 주식 수 (주)
    - book_price       : 목표 탈출 기준 단가 ($, 순수 원가 모드에서는 actual_avg_price 와 100% 동일)
    - book_invested_usd: 장부상 투자금 ($, 순수 원가 모드에서는 actual_cost_usd 와 100% 동일)
    - actual_cost_usd  : 실제 가용 현금 시드에서 지출된 순수 매수 원금 ($, 회계 항등식 보존용)
    - lot_count        : 해당 그리드 층에 포함된 누적 매수 회차 수 (1~6층은 개별 회차, 7층은 7회차 이상 통합 회차 수)
    - lot_type         : 지층 성격 태그 ("REENTRY_1FL", "TOPUP_1FL", "DIP_1FL", "GOLDEN_L1", "QUOTA_L1", "MANUAL_SYNC_L1", "GRID_L2" ~ "GRID_L7")
    """

    qty: int
    book_price: float
    book_invested_usd: float
    actual_cost_usd: float
    lot_count: int = 1
    lot_type: str = "QUOTA_L1"

    @property
    def actual_avg_price(self) -> float:
        if self.qty <= 0:
            return 0.0
        return round(self.actual_cost_usd / float(self.qty), 4)

    def to_dict(self) -> Dict[str, Any]:
        q_int = max(1, safe_int(self.qty, 1))
        a_cost = round(
            max(
                0.01 * float(q_int),
                safe_float(
                    self.actual_cost_usd,
                    safe_float(
                        self.book_invested_usd,
                        float(q_int) * safe_float(self.book_price, 0.01),
                    ),
                ),
            ),
            4,
        )
        pure_p = round(max(0.0001, a_cost / float(q_int)), 4)
        l_cnt = max(1, safe_int(self.lot_count, 1))
        return {
            "qty": q_int,
            "book_price": pure_p,
            "book_invested_usd": a_cost,
            "actual_cost_usd": a_cost,
            "lot_count": l_cnt,
            "lot_type": str(self.lot_type or "QUOTA_L1").upper().strip(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Optional["StratumBucket"]:
        if not isinstance(data, dict):
            return None
        q_int = safe_int(data.get("qty"), 0)
        if q_int <= 0:
            return None
        raw_p = safe_float(
            data.get("book_price"), safe_float(data.get("buy_price"), 0.0)
        )
        raw_bi = safe_float(
            data.get("book_invested_usd"), float(q_int) * max(0.0, raw_p)
        )
        a_cost = safe_float(data.get("actual_cost_usd"), raw_bi)
        if a_cost <= 0.0 and raw_p > 0.0:
            a_cost = float(q_int) * raw_p
        if a_cost <= 0.0:
            return None
        # Case 69, Case 71 & Case 72: 순수 매수 원가(a_cost) 기준으로 단가와 장부원금을 100% 일치시켜 원가 훼손 원천 차단
        clean_cost = round(a_cost, 4)
        pure_p = round(clean_cost / float(q_int), 4)
        l_cnt = max(1, safe_int(data.get("lot_count"), 1))
        l_type = str(data.get("lot_type") or "QUOTA_L1").upper().strip()
        return cls(
            qty=q_int,
            book_price=pure_p,
            book_invested_usd=clean_cost,
            actual_cost_usd=clean_cost,
            lot_count=l_cnt,
            lot_type=l_type,
        )


@dataclass
class GoldenAllInPocket:
    """
    # NEW [Case 80 : 미동부 프리장 황금시간대(07:00 ~ 07:50 EST & RSI <= 19.0) 독립 골든포켓 분리회계 구조체]:
    7층 그리드(buckets)의 층수·회차·기억저가를 전혀 오염시키지 않고 독립 관리되는
    가용시드 100% 전액매수 전용 포켓 (목표 익절률 +1.50% 고정).
    """

    qty: int = 0
    book_price: float = 0.0
    book_invested_usd: float = 0.0
    actual_cost_usd: float = 0.0
    entry_ts: float = 0.0
    order_date: str = ""

    @property
    def is_active(self) -> bool:
        return bool(self.qty > 0 and self.actual_cost_usd > 0.0)

    @property
    def actual_avg_price(self) -> float:
        if self.qty <= 0:
            return 0.0
        return round(self.actual_cost_usd / float(self.qty), 4)

    def target_sell_price(
        self, rise_pct: float = GOLDEN_POCKET_RISE_PCT
    ) -> float:
        if not self.is_active:
            return 0.0
        pure_p = self.actual_avg_price
        return round(
            math.ceil((pure_p * (1.0 + rise_pct / 100.0) - 1e-9) * 100.0)
            / 100.0,
            2,
        )

    def to_dict(self) -> Dict[str, Any]:
        if self.qty <= 0:
            return {
                "qty": 0,
                "book_price": 0.0,
                "book_invested_usd": 0.0,
                "actual_cost_usd": 0.0,
                "entry_ts": 0.0,
                "order_date": "",
            }
        q_int = max(1, safe_int(self.qty, 1))
        a_cost = round(
            max(
                0.01 * float(q_int),
                safe_float(
                    self.actual_cost_usd,
                    float(q_int) * safe_float(self.book_price, 0.01),
                ),
            ),
            4,
        )
        pure_p = round(max(0.01, a_cost / float(q_int)), 4)
        return {
            "qty": q_int,
            "book_price": pure_p,
            "book_invested_usd": a_cost,
            "actual_cost_usd": a_cost,
            "entry_ts": round(max(0.0, safe_float(self.entry_ts, 0.0)), 4),
            "order_date": str(self.order_date or "").strip(),
        }

    @classmethod
    def from_dict(cls, data: Any) -> "GoldenAllInPocket":
        if isinstance(data, GoldenAllInPocket):
            return cls.from_dict(data.to_dict())
        if not isinstance(data, dict):
            return cls()
        q_int = safe_int(data.get("qty"), 0)
        if q_int <= 0:
            return cls()
        raw_p = safe_float(
            data.get("book_price"), safe_float(data.get("buy_price"), 0.0)
        )
        raw_bi = safe_float(
            data.get("book_invested_usd"), float(q_int) * max(0.0, raw_p)
        )
        a_cost = safe_float(data.get("actual_cost_usd"), raw_bi)
        if a_cost <= 0.0 and raw_p > 0.0:
            a_cost = float(q_int) * raw_p
        if a_cost <= 0.0:
            return cls()
        clean_cost = round(max(0.01 * float(q_int), a_cost), 4)
        pure_p = round(max(0.01, clean_cost / float(q_int)), 4)
        return cls(
            qty=q_int,
            book_price=pure_p,
            book_invested_usd=clean_cost,
            actual_cost_usd=clean_cost,
            entry_ts=round(max(0.0, safe_float(data.get("entry_ts"), 0.0)), 4),
            order_date=str(data.get("order_date") or "").strip(),
        )


def pocket_from_dict(raw_data: Any) -> GoldenAllInPocket:
    return GoldenAllInPocket.from_dict(raw_data)


def pocket_to_dict(pocket: Any) -> Dict[str, Any]:
    if isinstance(pocket, GoldenAllInPocket):
        return pocket.to_dict()
    return GoldenAllInPocket.from_dict(pocket).to_dict()


def has_active_golden_pocket(pocket_or_state: Any) -> bool:
    if isinstance(pocket_or_state, GoldenAllInPocket):
        return pocket_or_state.is_active
    if isinstance(pocket_or_state, dict) and "golden_pocket" in pocket_or_state:
        return GoldenAllInPocket.from_dict(
            pocket_or_state.get("golden_pocket")
        ).is_active
    return GoldenAllInPocket.from_dict(pocket_or_state).is_active


def buckets_from_dicts(
    raw_list: Sequence[Dict[str, Any]],
) -> List[StratumBucket]:
    out: List[StratumBucket] = []
    if not isinstance(raw_list, (list, tuple)):
        return out
    for item in raw_list:
        b_obj = StratumBucket.from_dict(item)
        if b_obj is not None:
            out.append(b_obj)
    return out


def buckets_to_dicts(
    buckets: Sequence[StratumBucket],
) -> List[Dict[str, Any]]:
    return [
        b.to_dict()
        for b in (buckets or [])
        if isinstance(b, StratumBucket) and b.qty > 0
    ]


# ---------------------------------------------------------------------------
# [핵심 1-B · Case 69, Case 71 & Case 72] 그리드 층 판별기 & 진성 손익분기점(순수 원가) 하한선 정규화기
# ---------------------------------------------------------------------------
def is_upper_grid_tier(bucket_or_lot_type: Any) -> bool:
    """
    🚨 [Case 71 & Case 72 상단 그리드(2층 ~ 7층) 여부 결정론적 판별기]:
    - lot_type 이 "MERGED_UPPER" 이거나 "GRID_L2" ~ "GRID_L7" (즉, "GRID_L" 로 시작하되 "GRID_L1" 이 아닌 경우)이면
      상단 그리드(2층 ~ 7층) 버킷이므로 True 를 반환한다.
    - "REENTRY_1FL", "TOPUP_1FL", "DIP_1FL", "GOLDEN_L1", "QUOTA_L1", "MANUAL_SYNC_L1", "SYNCED_1FL", "GRID_L1" 등은
      최하단 활성 공격수 1층이므로 False 를 반환한다.
    """
    if isinstance(bucket_or_lot_type, StratumBucket):
        tag = str(bucket_or_lot_type.lot_type or "").upper().strip()
    elif isinstance(bucket_or_lot_type, dict):
        tag = str(bucket_or_lot_type.get("lot_type") or "").upper().strip()
    else:
        tag = str(bucket_or_lot_type or "").upper().strip()

    if tag == "MERGED_UPPER":
        return True
    if tag.startswith("GRID_L") and tag != "GRID_L1":
        return True
    return False


def has_active_l1_bucket(buckets: Sequence[StratumBucket]) -> bool:
    """
    🚨 [Case 71 & Case 72 활성 1층 공격수 보유 여부 판별기]:
    - buckets 가 비어 있지 않고 맨 앞(buckets[0])이 상단 그리드(GRID_L2 ~ GRID_L7 / MERGED_UPPER)가 아니면
      현재 활성 1층 공격수가 존재하는 상태(True)이다.
    - 만약 1층이 익절되어 빠져나가고 buckets[0] 이 GRID_L2(또는 MERGED_UPPER)라면
      현재 1층이 공석이고 상단 2층 ~ 7층 그리드만 보유 중인 상태(False)이다!
    """
    valid = [
        b
        for b in (buckets or [])
        if isinstance(b, StratumBucket) and b.qty > 0
    ]
    if not valid:
        return False
    return not is_upper_grid_tier(valid[0])


def relabel_upper_grid_tiers(
    upper_buckets: Sequence[StratumBucket],
    max_tiers: int = MAX_GRID_TIERS_7,
) -> List[StratumBucket]:
    """
    🚨 [Case 71 & Case 72 상단 그리드(2층 ~ 6층 개별 완충층 + 통합 7층 본대) 번호 정규화 및 합병기]:
    1층(공격수)을 제외한 상단 그리드 버킷 리스트를 받아:
    - max_upper_cnt = max_tiers - 1 (기본 6개 : GRID_L2 ~ GRID_L7) 기준으로
    - 2층 ~ 6층(GRID_L2 ~ GRID_L6, 5개 완충층)은 개별 순수 원가를 100% 분리 보존하고,
    - 7층을 초과하는 물량(valid[5:])은 최상단 '통합 7층 본대(GRID_L7)'로 가중평균 합병(Case 53 하드 캡핑 적용)하여 반환한다.
    """
    valid = [
        b
        for b in (upper_buckets or [])
        if isinstance(b, StratumBucket) and b.qty > 0
    ]
    if not valid:
        return []

    max_upper_cnt = max(1, safe_int(max_tiers, MAX_GRID_TIERS_7) - 1)
    if len(valid) > max_upper_cnt:
        kept = valid[: max_upper_cnt - 1]
        overflow = valid[max_upper_cnt - 1 :]
        tot_q = sum(b.qty for b in overflow)
        tot_cost = round(sum(b.actual_cost_usd for b in overflow), 4)
        tot_lots = sum(max(1, b.lot_count) for b in overflow)
        overall_book_avg = (
            sum(float(b.qty) * b.book_price for b in overflow) / float(tot_q)
        )
        raw_avg_p = max(0.01, tot_cost / float(tot_q))
        capped_avg_p = round(min(raw_avg_p, overall_book_avg), 4)
        merged_top = StratumBucket(
            qty=tot_q,
            book_price=capped_avg_p,
            book_invested_usd=tot_cost,
            actual_cost_usd=tot_cost,
            lot_count=tot_lots,
            lot_type=f"GRID_L{max_upper_cnt + 1}",
        )
        valid = kept + [merged_top]

    out: List[StratumBucket] = []
    for idx, b in enumerate(valid):
        tier_no = min(max_upper_cnt + 1, idx + 2)
        pure_cost = round(max(0.01 * float(b.qty), b.actual_cost_usd), 4)
        pure_p = round(max(0.01, pure_cost / float(b.qty)), 4)
        out.append(
            StratumBucket(
                qty=b.qty,
                book_price=pure_p,
                book_invested_usd=pure_cost,
                actual_cost_usd=pure_cost,
                lot_count=max(1, b.lot_count),
                lot_type=f"GRID_L{tier_no}",
            )
        )
    return out


def enforce_true_breakeven_floor_on_buckets(
    buckets: Sequence[StratumBucket],
    max_allowed_discount_usd: Optional[float] = None,
) -> List[StratumBucket]:
    """
    🚨 [Case 69, Case 71 & Case 72 진성 손익분기점(순수 매수 원가) 하한선 강제]:
    인위적 리앵커링 차감을 수행하지 않으므로,
    모든 보유 지층(1층 ~ 7층)의 book_invested_usd 와 book_price 가 실제 매수 원금(actual_cost_usd / actual_avg_price)
    밑으로 절대 내려가지 못하도록 100% 순수 원가 하한선을 강제한다.
    """
    valid = [
        b
        for b in (buckets or [])
        if isinstance(b, StratumBucket) and b.qty > 0
    ]
    if not valid:
        return []

    adjusted: List[StratumBucket] = []
    for b in valid:
        pure_cost = round(max(0.01 * float(b.qty), b.actual_cost_usd), 4)
        pure_p = round(max(0.01, pure_cost / float(b.qty)), 4)
        adjusted.append(
            StratumBucket(
                qty=b.qty,
                book_price=pure_p,
                book_invested_usd=pure_cost,
                actual_cost_usd=pure_cost,
                lot_count=max(1, b.lot_count),
                lot_type=str(b.lot_type or "QUOTA_L1").upper().strip(),
            )
        )
    return adjusted


# ---------------------------------------------------------------------------
# [핵심 2] 8%(12.5분할) 정량 주수 · 100% 전액매수 주수 · GUARD30 판정 · 온디맨드 수혈/상환기 (🎯 1 & Case 25 ~ 35, 67, 77, 80)
# ---------------------------------------------------------------------------
def compute_golden8_quota_qty(
    anchor_price: float,
    current_total_equity: float,
    initial_seed_usd: float = DEFAULT_INITIAL_SEED_USD,
    portion_mode: str = "COMP_08PCT",
    exec_price: Optional[float] = None,
) -> Tuple[int, float]:
    """
    🎯 1 & Case 25 ~ 35, Case 67 & Case 77:
    직전 매매 기준가(anchor_price)를 기반으로 8%(12.5분할) 황금비율 1회분 예산(portion_budget)과
    고정 목표 매수 주수(anchor_quota_qty)를 산출하되, 실제 매수 지정가(exec_price)가 제공된 경우
    상승 돌파 등으로 인해 1회분(8%) 예산을 초과하지 않도록 min(budget_cap_qty, anchor_quota_qty)로 캡핑한다.
    반환값: (target_qty, portion_budget)
    """
    init_seed = max(
        100.0, safe_float(initial_seed_usd, DEFAULT_INITIAL_SEED_USD)
    )
    tot_eq = max(init_seed, safe_float(current_total_equity, init_seed))
    mode = str(portion_mode or "COMP_08PCT").upper().strip()

    if mode == "FIXED_800":
        portion_budget = round(init_seed * PORTION_RATIO_LOCKED, 4)
    else:
        portion_budget = round(tot_eq * PORTION_RATIO_LOCKED, 4)

    ref_p = max(0.01, safe_float(anchor_price, 0.01))
    anchor_quota_qty = max(1, int(math.floor((portion_budget + 1e-9) / ref_p)))

    # 🚨 Case 67: 실제 매수가(exec_price)가 기준가보다 높을 때 1회분(8%) 예산 초과 원천 차단!
    if exec_price is not None and safe_float(exec_price, 0.0) > 0.0:
        eff_exec_p = max(0.01, safe_float(exec_price, ref_p))
        budget_cap_qty = max(
            1, int(math.floor((portion_budget + 1e-9) / eff_exec_p))
        )
        target_qty = min(budget_cap_qty, anchor_quota_qty)
    else:
        target_qty = anchor_quota_qty

    return target_qty, portion_budget


def resolve_affordable_buy_qty(
    target_qty: int,
    price_t: float,
    free_cash_usd: float,
    broker_buying_power_usd: Optional[float] = None,
    max_portion_budget_usd: Optional[float] = None,
) -> Tuple[int, float]:
    """
    🚨 Case 25 ~ 35 & Case 67:
    직전 기준가로 산출된 목표 정량(target_qty)을 실제 주문가(price_t)로 매수하기 직전:
    1) max_portion_budget_usd(1회분 8% 예산) 상한 주수(budget_cap_qty)와 target_qty 중 작은 값으로 캡핑한다.
    2) 왕복 수수료 버퍼(0.14%)를 감안한 가용 현금(free_cash_usd) 및 토스 실계좌 매수가능금액 한도 내로 캡핑한다.
    반환값: (buy_qty, actual_spent_usd)
    """
    t_qty = max(0, safe_int(target_qty, 0))
    exec_p = safe_float(price_t, 0.0)
    if t_qty <= 0 or exec_p <= 0.0:
        return 0, 0.0

    # 🚨 Case 67: 1회분(8%) 예산 상한 주수(budget_cap_qty) 하드 캡핑
    if (
        max_portion_budget_usd is not None
        and safe_float(max_portion_budget_usd, 0.0) > 0.0
    ):
        p_bud = safe_float(max_portion_budget_usd, 0.0)
        budget_cap_qty = max(1, int(math.floor((p_bud + 1e-9) / exec_p)))
        t_qty = min(budget_cap_qty, t_qty)

    avail_cash = max(0.0, safe_float(free_cash_usd, 0.0))
    if broker_buying_power_usd is not None:
        bp_val = safe_float(broker_buying_power_usd, 0.0)
        if bp_val >= 0.0:
            avail_cash = min(avail_cash, bp_val)

    fee_mult = 1.0 + (ROUND_TRIP_FEE_RATE_PCT / 100.0)
    unit_cost_with_fee = exec_p * fee_mult
    if avail_cash < unit_cost_with_fee:
        return 0, 0.0

    max_affordable = int(math.floor((avail_cash + 1e-9) / unit_cost_with_fee))
    buy_qty = max(0, min(t_qty, max_affordable))
    actual_spent_usd = (
        round(float(buy_qty) * exec_p, 4) if buy_qty > 0 else 0.0
    )
    return buy_qty, actual_spent_usd


def resolve_allin_affordable_buy_qty(
    price_t: float,
    free_cash_usd: float,
    broker_buying_power_usd: Optional[float] = None,
) -> Tuple[int, float]:
    """
    # NEW [Case 80 : 황금시간대(07:00 ~ 07:50 EST & RSI <= 19.0) 가용 현금 시드 100% 전액 매수 주수 산출기]:
    왕복 수수료 버퍼(0.14%)를 감안하여 현재 가용 현금(free_cash_usd)과 토스 실계좌 주문가능 달러(broker_buying_power_usd) 중
    작은 금액의 100% 전액으로 매수할 수 있는 최대 정수 주식 수(allin_qty)와 실투입 원금(actual_spent_usd)을 반환한다.
    """
    exec_p = safe_float(price_t, 0.0)
    if exec_p <= 0.0:
        return 0, 0.0

    avail_cash = max(0.0, safe_float(free_cash_usd, 0.0))
    if broker_buying_power_usd is not None:
        bp_val = safe_float(broker_buying_power_usd, 0.0)
        if bp_val > 0.0:
            avail_cash = min(avail_cash, bp_val)

    fee_mult = 1.0 + (ROUND_TRIP_FEE_RATE_PCT / 100.0)
    unit_cost_with_fee = exec_p * fee_mult
    if avail_cash < unit_cost_with_fee:
        return 0, 0.0

    allin_qty = max(0, int(math.floor((avail_cash + 1e-9) / unit_cost_with_fee)))
    actual_spent_usd = (
        round(float(allin_qty) * exec_p, 4) if allin_qty > 0 else 0.0
    )
    return allin_qty, actual_spent_usd


def evaluate_golden_allin_signal(
    hm: int,
    rsi_14: float,
    live_price: float,
    golden_allin_mode: str = DEFAULT_GOLDEN_ALLIN_MODE,
    today_str: str = "",
    last_golden_allin_date: str = "",
    golden_pocket: Optional[Any] = None,
    rsi_ready: bool = True,
) -> Dict[str, Any]:
    """
    # NEW [Case 80 : 미동부 프리장 황금시간대(07:00 ~ 07:50 EST) & RSI(14) <= 19.0 가용시드 100% 전액 추가매수 판정기]:
    1) 제어반 선택 모드(golden_allin_mode)가 "NONE" (기본값 OFF)이면 즉시 should_buy=False ("MODE_OFF")를 반환한다.
    2) 미동부 프리장 07:00 ~ 07:50 EST (700 <= hm <= 750) 구간인지 확인한다.
    3) 당일 이미 황금시간 전액매수를 실행했는지(last_golden_allin_date == today_str) 확인한다(1일 최대 1회).
    4) POCKET_ALLIN 모드인 경우 현재 미청산 골든포켓 물량(gp.qty > 0)이 남아 있으면 중복 진입을 차단한다.
    5) 1분봉 Wilder's RSI(14)가 유효(rsi_ready == True)하고 0.0 < rsi_14 <= 19.0 (GOLDEN_RSI_MAX_THRESHOLD) 이하이면
       전액 매수(lot_type="GOLDEN_POCKET" 또는 "GOLDEN_L1")를 승인한다!
    """
    mode = str(golden_allin_mode or DEFAULT_GOLDEN_ALLIN_MODE).upper().strip()
    if mode not in GOLDEN_ALLIN_MODES:
        mode = DEFAULT_GOLDEN_ALLIN_MODE

    hm_int = safe_int(hm, 0)
    rsi_val = round(safe_float(rsi_14, 50.0), 2)
    lp = safe_float(live_price, 0.0)
    in_window = bool(GOLDEN_WINDOW_START_HM <= hm_int <= GOLDEN_WINDOW_END_HM)
    gp = pocket_from_dict(golden_pocket)
    lot_tag = "GOLDEN_POCKET" if mode == "POCKET_ALLIN" else "GOLDEN_L1"

    if mode == "NONE":
        return {
            "should_buy": False,
            "mode": mode,
            "lot_type": "",
            "reason": "MODE_OFF",
            "in_window": in_window,
            "rsi_14": rsi_val,
            "rsi_threshold": GOLDEN_RSI_MAX_THRESHOLD,
        }

    if not in_window:
        return {
            "should_buy": False,
            "mode": mode,
            "lot_type": lot_tag,
            "reason": "OUTSIDE_GOLDEN_WINDOW",
            "in_window": False,
            "rsi_14": rsi_val,
            "rsi_threshold": GOLDEN_RSI_MAX_THRESHOLD,
        }

    if (
        today_str
        and str(last_golden_allin_date or "").strip() == str(today_str).strip()
    ):
        return {
            "should_buy": False,
            "mode": mode,
            "lot_type": lot_tag,
            "reason": "ALREADY_EXECUTED_TODAY",
            "in_window": True,
            "rsi_14": rsi_val,
            "rsi_threshold": GOLDEN_RSI_MAX_THRESHOLD,
        }

    if mode == "POCKET_ALLIN" and gp.is_active:
        return {
            "should_buy": False,
            "mode": mode,
            "lot_type": lot_tag,
            "reason": "GOLDEN_POCKET_ALREADY_HELD",
            "in_window": True,
            "rsi_14": rsi_val,
            "rsi_threshold": GOLDEN_RSI_MAX_THRESHOLD,
        }

    if lp <= 0.0 or not rsi_ready or rsi_val <= 0.0:
        return {
            "should_buy": False,
            "mode": mode,
            "lot_type": lot_tag,
            "reason": "RSI_OR_PRICE_NOT_READY",
            "in_window": True,
            "rsi_14": rsi_val,
            "rsi_threshold": GOLDEN_RSI_MAX_THRESHOLD,
        }

    if rsi_val <= GOLDEN_RSI_MAX_THRESHOLD:
        return {
            "should_buy": True,
            "mode": mode,
            "lot_type": lot_tag,
            "reason": f"GOLDEN_{mode}_RSI_{rsi_val:.1f}",
            "in_window": True,
            "rsi_14": rsi_val,
            "rsi_threshold": GOLDEN_RSI_MAX_THRESHOLD,
        }

    return {
        "should_buy": False,
        "mode": mode,
        "lot_type": lot_tag,
        "reason": "HOLD_RSI_ABOVE_19",
        "in_window": True,
        "rsi_14": rsi_val,
        "rsi_threshold": GOLDEN_RSI_MAX_THRESHOLD,
    }


def evaluate_guard30_and_reserve_injection(
    free_cash_usd: float,
    broker_bp_usd: Optional[float],
    exec_price: float,
    portion_budget: float,
    l1_actual_cost_usd: float = 0.0,
    is_dip_promotion: bool = False,
    used_reserve_portions_cnt: int = 0,
    max_reserve_portions: int = MAX_RESERVE_PORTIONS,
    min_dip_budget_ratio: float = MIN_DIP_BUDGET_RATIO,
    min_dip_vs_l1_ratio: float = MIN_DIP_VS_L1_RATIO,
    deposit_tolerance_ratio: float = RESERVE_DEPOSIT_TOLERANCE_RATIO,
) -> Dict[str, Any]:
    """
    # [Case 77 : 💉 05_RESV_6P_GUARD30 — 30% 자투리 1주 승격 방지 가드 & 토스 실계좌 여유자금 감지 기반 최대 +6회분 온디맨드 예비시드 자동 수혈 판정기]:
    매수 타점(0주 진입 / 황금시간 전액매수 / 1층 공석 재장전 / 10분 와이드·스텝업 추매) 도달 시:
    1) [30% 자투리 승격 방지 가드 최소 필요 현금(min_req_cash) 산출]:
       - 추매(is_dip_promotion == True) 시:
         min_req_cash = max(1주 수수료포함 비용, portion_budget * 0.30, l1_actual_cost_usd * 0.30)
       - 1층 공석 재장전, 황금시간 전액매수 또는 0주 진입(is_dip_promotion == False) 시:
         min_req_cash = max(1주 수수료포함 비용, portion_budget * 0.30)
    2) [정상 진행 판정 (PROCEED_NORMAL)]
    3) [온디맨드 예비시드 자동 수혈 판정 (INJECT_AND_PROCEED)]
    4) [미입금 시 자투리 매수 차단 및 입금 요청 알림 트리거 (BLOCK_AND_ALERT_DEPOSIT)]
    """
    f_cash = max(0.0, safe_float(free_cash_usd, 0.0))
    ex_p = max(0.01, safe_float(exec_price, 0.01))
    p_bud = max(0.01, safe_float(portion_budget, 800.0))
    l1_cost = max(0.0, safe_float(l1_actual_cost_usd, 0.0))
    used_cnt = max(0, safe_int(used_reserve_portions_cnt, 0))
    max_res = max(0, safe_int(max_reserve_portions, MAX_RESERVE_PORTIONS))
    rem_portions = max(0, max_res - used_cnt)

    fee_mult = 1.0 + (ROUND_TRIP_FEE_RATE_PCT / 100.0)
    one_share_cost = ex_p * fee_mult

    bud_ratio = max(0.0, safe_float(min_dip_budget_ratio, MIN_DIP_BUDGET_RATIO))
    l1_ratio = max(0.0, safe_float(min_dip_vs_l1_ratio, MIN_DIP_VS_L1_RATIO))
    tol_ratio = max(
        0.50,
        min(
            1.0,
            safe_float(
                deposit_tolerance_ratio, RESERVE_DEPOSIT_TOLERANCE_RATIO
            ),
        ),
    )

    if is_dip_promotion:
        min_req_cash = max(
            one_share_cost,
            p_bud * bud_ratio,
            l1_cost * l1_ratio,
        )
    else:
        min_req_cash = max(one_share_cost, p_bud * bud_ratio)

    eff_bp = (
        safe_float(broker_bp_usd, -1.0) if broker_bp_usd is not None else -1.0
    )

    # 1) 현재 가용현금이 min_req_cash 이상이고 실계좌 예수금도 충분한 경우 -> 정상 매수 진행
    if f_cash >= min_req_cash and (eff_bp < 0.0 or eff_bp >= min_req_cash):
        return {
            "action": "PROCEED_NORMAL",
            "should_proceed": True,
            "is_dust_blocked": False,
            "inject_portions": 0,
            "inject_usd": 0.0,
            "min_req_cash": round(min_req_cash, 4),
            "rem_portions_before": rem_portions,
            "rem_portions_after": rem_portions,
            "unallocated_deposit_usd": round(
                max(0.0, eff_bp - f_cash) if eff_bp >= 0.0 else 0.0, 4
            ),
            "recommended_deposit_usd": 0.0,
            "minimum_shortfall_usd": 0.0,
        }

    # 2) f_cash < min_req_cash (시드고갈 / 30% 자투리 가드 감지) -> 온디맨드 예비시드 수혈 가능 여부 확인
    shortfall_for_guard = max(0.0, min_req_cash - f_cash)
    needed_portions = max(
        1, int(math.ceil((shortfall_for_guard - 1e-9) / p_bud))
    )
    unallocated_deposit_usd = (
        max(0.0, eff_bp - f_cash) if eff_bp >= 0.0 else 0.0
    )
    required_inj_usd = round(float(needed_portions) * p_bud, 4)

    if (
        rem_portions >= needed_portions
        and eff_bp >= min_req_cash
        and unallocated_deposit_usd >= (required_inj_usd * tol_ratio)
    ):
        # 사용자가 토스 계좌에 1회분 이상 여유자금을 입금해 둔 상태 -> 즉시 자동 수혈 승인!
        if unallocated_deposit_usd >= required_inj_usd:
            actual_inj_usd = required_inj_usd
        else:
            actual_inj_usd = round(unallocated_deposit_usd, 4)

        if (f_cash + actual_inj_usd) >= min_req_cash:
            return {
                "action": "INJECT_AND_PROCEED",
                "should_proceed": True,
                "is_dust_blocked": False,
                "inject_portions": needed_portions,
                "inject_usd": actual_inj_usd,
                "min_req_cash": round(min_req_cash, 4),
                "rem_portions_before": rem_portions,
                "rem_portions_after": rem_portions - needed_portions,
                "unallocated_deposit_usd": round(unallocated_deposit_usd, 4),
                "recommended_deposit_usd": 0.0,
                "minimum_shortfall_usd": 0.0,
            }

    # 3) 토스 계좌에 아직 여유자금이 입금되지 않았거나 예비 한도(6회분)가 모두 소진된 경우 -> 자투리 차단 & 입금 요청
    is_dust_blocked = bool(f_cash >= one_share_cost)
    eff_bp_nonneg = max(0.0, eff_bp) if eff_bp >= 0.0 else f_cash
    min_shortfall_usd = round(max(0.0, min_req_cash - eff_bp_nonneg), 2)
    rec_deposit_usd = round(
        max(p_bud, required_inj_usd - unallocated_deposit_usd), 2
    )

    return {
        "action": "BLOCK_AND_ALERT_DEPOSIT",
        "should_proceed": False,
        "is_dust_blocked": is_dust_blocked,
        "inject_portions": 0,
        "inject_usd": 0.0,
        "needed_portions": needed_portions,
        "min_req_cash": round(min_req_cash, 4),
        "rem_portions_before": rem_portions,
        "rem_portions_after": rem_portions,
        "unallocated_deposit_usd": round(unallocated_deposit_usd, 4),
        "recommended_deposit_usd": rec_deposit_usd,
        "minimum_shortfall_usd": min_shortfall_usd,
    }


def compute_reserve_repayment_on_zero(
    initial_seed_usd: float,
    cumulative_realized_net_usd: float,
    injected_reserve_usd: float,
    used_reserve_portions_cnt: int,
    max_reserve_portions: int = MAX_RESERVE_PORTIONS,
) -> Dict[str, Any]:
    """
    # [Case 77 : 0주 전량 졸업 시 온디맨드 예비시드 원금 자동 상환 및 6회분 한도 복구 연산기]:
    스나이퍼 자동 매도 또는 수동 전량 청산으로 보유 지층 및 골든포켓이 0주가 되었을 때:
    - 수혈받았던 예비시드 잔액(injected_reserve_usd > 0.0)이 존재하면,
      상환 전 총 현금 풀(total_cash_before = initial_seed_usd + cumulative_realized_net_usd + injected_reserve_usd)에서
      기본 시드(initial_seed_usd)를 초과하는 여유 현금 범위 내에서 injected_reserve_usd 를 즉시 분리 상환한다.
    - 전액 상환 완료 시 injected_reserve_usd = 0.0 및 used_reserve_portions_cnt = 0 으로 초기화하여
      6/6회분 예비 한도를 100% 원상 복구한다!
    """
    init_seed = max(
        100.0, safe_float(initial_seed_usd, DEFAULT_INITIAL_SEED_USD)
    )
    cum_net = round(safe_float(cumulative_realized_net_usd, 0.0), 4)
    inj_usd = round(max(0.0, safe_float(injected_reserve_usd, 0.0)), 4)
    used_cnt = max(0, safe_int(used_reserve_portions_cnt, 0))
    max_res = max(1, safe_int(max_reserve_portions, MAX_RESERVE_PORTIONS))

    total_cash_before = round(max(0.0, init_seed + cum_net + inj_usd), 4)
    if inj_usd <= 0.0:
        return {
            "did_repay": False,
            "repaid_usd": 0.0,
            "rem_injected_reserve_usd": 0.0,
            "rem_used_reserve_portions_cnt": 0,
            "avail_reserve_portions": max_res,
            "free_cash_after_repay_usd": total_cash_before,
        }

    repayable_surplus = max(0.0, total_cash_before - init_seed)
    repaid_usd = round(min(inj_usd, repayable_surplus), 4)
    rem_inj_usd = round(max(0.0, inj_usd - repaid_usd), 4)

    if rem_inj_usd <= 0.01:
        rem_inj_usd = 0.0
        rem_used_cnt = 0
    else:
        est_portion_unit = max(1.0, (init_seed + max(0.0, cum_net)) * 0.08)
        rem_used_cnt = max(
            1,
            min(
                used_cnt if used_cnt > 0 else max_res,
                int(math.ceil(rem_inj_usd / est_portion_unit)),
            ),
        )

    free_cash_after = round(max(0.0, init_seed + cum_net + rem_inj_usd), 4)
    return {
        "did_repay": bool(repaid_usd > 0.0),
        "repaid_usd": repaid_usd,
        "rem_injected_reserve_usd": rem_inj_usd,
        "rem_used_reserve_portions_cnt": rem_used_cnt,
        "avail_reserve_portions": max(0, max_res - rem_used_cnt),
        "free_cash_after_repay_usd": free_cash_after,
    }


# ---------------------------------------------------------------------------
# [핵심 3] 보유 회차별 4단 와이드 점진 단차 · 하이브리드 1층 재장전 · STEP2X_15PCT_C20 스텝업 해금 판정기 (Case 36 ~ 76)
# ---------------------------------------------------------------------------
def get_golden8_prog_thresholds(
    held_lots: int,
    threshold_mode: str = "WIDE_RUNWAY",
) -> Tuple[float, float, float]:
    """
    🎯 2 & Case 36 ~ 45, 60, 71, 72 : 4단 와이드 점진 활주로:
    현재 보유 중인 총 투입 회차(held_lots)에 따른:
    1) 10분 시드보호 매수 게이트 요구 하락률(drop_buy_pct):
       -  1 ~  4회차 보유 중 : -1.00%
       -  5 ~  8회차 보유 중 : -2.00%
       -  9 ~ 10회차 보유 중 : -3.50%
       - 11회차 이상 보유 중 : -5.50%
    2) 실시간 스나이퍼 매도 모니터 목표 상승률(rise_sell_l1_pct, rise_sell_upper_pct):
       - 1층(공격수) 및 골든포켓 +1.50% / 2층 ~ 7층(개별 완충층·통합 7층 및 상단 통합 이동평균) +1.00%
    반환값: (drop_buy_pct, rise_sell_l1_pct, rise_sell_upper_pct)
    """
    lots = max(1, safe_int(held_lots, 1))
    if lots <= 4:
        drop_buy_pct = -1.00
    elif lots <= 8:
        drop_buy_pct = -2.00
    elif lots <= 10:
        drop_buy_pct = -3.50
    else:
        drop_buy_pct = -5.50

    mode = str(threshold_mode or "WIDE_RUNWAY").upper().strip()
    if mode == "01_PROG_LOT":
        prog_rise = 1.00 if lots <= 6 else (1.50 if lots <= 11 else 2.00)
        return drop_buy_pct, prog_rise, prog_rise
    return drop_buy_pct, 1.50, 1.00


def evaluate_l2_only_hybrid_reentry_signal(
    live_price: float,
    anchor_price: float,
    l2_book_price: float = 0.0,
    min_upper_tier_price: float = 0.0,
) -> Dict[str, Any]:
    """
    # [🎯 4 & Case 59, Case 67, Case 71, Case 72, Case 73]:
    1층이 실물 익절되어 장부에 상단 그리드(2층 ~ 7층)만 남아 1층이 공석일 때,
    매도 후 60.0초 타임쉴드 및 매 60.0초(1분) 타임쉴드 주기마다 호출되는 하이브리드 독립 1층 재장전 판정기:
    1) 🛡️ [Case 73 단가 역전 원천 차단 가드 (HOLD_PREVENT_INVERSION · 후자)]:
       실시간 현재가(lp)가 상단 최하단 층인 2층 단가(ceil_p = min_upper_tier_price)보다 높으면
       (lp > ceil_p + 1e-6), 새로 매수할 1층 공격수 단가가 2층 단가보다 비싸지는 단가 역전(1층 > 2층) 및
       고점 중복 매수를 막기 위해 즉시 매수를 패스(should_buy = False, signal_type = "HOLD_PREVENT_INVERSION")하고
       실시간 매도 모니터가 수익권에 들어선 2층(+1.00%)을 익절하도록 위임한다!
    2) 🎯 [현재가 <= 2층 단가 안전 영역 내 눌림목(-1.00%) OR 상승돌파(+1.00%) 타점 판정]:
       - 조건 A (눌림목 재장전 : chg_from_exit <= -1.00% & lp <= ceil_p) -> PULLBACK_RELOAD
       - 조건 B (상승돌파 재장전 : chg_from_exit >= +1.00% & lp <= ceil_p) -> BREAKOUT_RELOAD
       충족 시에만 상단 2층 ~ 7층 비병합 독립 실물 1층(REENTRY_1FL) 재장전을 승인한다.
    """
    lp = safe_float(live_price, 0.0)
    anc = safe_float(anchor_price, 0.0)
    b2_p = safe_float(l2_book_price, 0.0)
    ceil_p = safe_float(min_upper_tier_price, 0.0)
    if ceil_p <= 0.0 and b2_p > 0.0:
        ceil_p = b2_p

    ref_anchor = (
        anc
        if anc > 0.0
        else (ceil_p if ceil_p > 0.0 else (b2_p if b2_p > 0.0 else lp))
    )

    pullback_target_p = (
        round(ref_anchor * (1.0 + REENTRY_PULLBACK_DROP_PCT / 100.0), 2)
        if ref_anchor > 0.0
        else 0.0
    )
    breakout_target_p = (
        round(ref_anchor * (1.0 + REENTRY_BREAKOUT_RISE_PCT / 100.0), 2)
        if ref_anchor > 0.0
        else 0.0
    )

    if lp <= 0.0 or ref_anchor <= 0.0:
        return {
            "should_buy": False,
            "signal_type": "NO_PRICE",
            "ref_anchor": round(ref_anchor, 4),
            "quota_ref_price": round(ref_anchor, 4),
            "chg_from_exit_pct": 0.0,
            "pullback_target_price": pullback_target_p,
            "breakout_target_price": breakout_target_p,
            "l2_ceiling_price": round(ceil_p, 4),
        }

    chg_from_exit_pct = ((lp - ref_anchor) / ref_anchor) * 100.0

    # 🚨 [Case 73 핵심 방어 : 현재가 > 2층 단가(ceil_p) 시 1층 > 2층 단가 역전 원천 차단 (후자)]
    if ceil_p > 0.0 and lp > (ceil_p + 1e-6):
        return {
            "should_buy": False,
            "signal_type": "HOLD_PREVENT_INVERSION",
            "ref_anchor": round(ref_anchor, 4),
            "quota_ref_price": round(ref_anchor, 4),
            "chg_from_exit_pct": round(chg_from_exit_pct, 2),
            "pullback_target_price": pullback_target_p,
            "breakout_target_price": breakout_target_p,
            "l2_ceiling_price": round(ceil_p, 4),
        }

    if chg_from_exit_pct <= REENTRY_PULLBACK_DROP_PCT:
        return {
            "should_buy": True,
            "signal_type": "PULLBACK_RELOAD",
            "ref_anchor": round(ref_anchor, 4),
            "quota_ref_price": round(ref_anchor, 4),
            "chg_from_exit_pct": round(chg_from_exit_pct, 2),
            "pullback_target_price": pullback_target_p,
            "breakout_target_price": breakout_target_p,
            "l2_ceiling_price": round(ceil_p, 4),
        }

    if chg_from_exit_pct >= REENTRY_BREAKOUT_RISE_PCT:
        return {
            "should_buy": True,
            "signal_type": "BREAKOUT_RELOAD",
            "ref_anchor": round(ref_anchor, 4),
            "quota_ref_price": round(ref_anchor, 4),
            "chg_from_exit_pct": round(chg_from_exit_pct, 2),
            "pullback_target_price": pullback_target_p,
            "breakout_target_price": breakout_target_p,
            "l2_ceiling_price": round(ceil_p, 4),
        }

    return {
        "should_buy": False,
        "signal_type": "HOLD_WAIT_GATE",
        "ref_anchor": round(ref_anchor, 4),
        "quota_ref_price": round(ref_anchor, 4),
        "chg_from_exit_pct": round(chg_from_exit_pct, 2),
        "pullback_target_price": pullback_target_p,
        "breakout_target_price": breakout_target_p,
        "l2_ceiling_price": round(ceil_p, 4),
    }


def evaluate_step_up_2x_dip_signal(
    live_price: float,
    buckets: Sequence[StratumBucket],
    anchor_price: float,
    cycle_min_buy_price: float,
    drop_buy_pct: float,
    free_cash_usd: float,
    realized_equity_usd: float,
    step_up_drop_pct: float = STEP_UP_2X_DROP_PCT,
    min_cash_ratio: float = STEP_UP_2X_MIN_CASH_RATIO,
    min_rebound_mult: float = STEP_UP_2X_MIN_REBOUND_MULT,
    max_tiers_for_unlock: int = STEP_UP_2X_MAX_TIERS,
) -> Dict[str, Any]:
    """
    # [🎯 2 Step 1 & Case 60, Case 72, Case 76 : 🔓 06_STEP2X_15PCT_C20 3중 안전문 기반 조건부 스텝업 저가 해금 판정기]:
    활성 1층 보유 중(has_active_l1_bucket(buckets) == True) 04:07 EST 기점 10분 고정 매수 게이트 도래 시:
    1) [제1경로 : 기본 정적 신저가 추매 판정]
    2) [제2경로 : 정적 신저가 미달 시 🔓 06_STEP2X_15PCT_C20 3중 안전문 스텝업 해금 판정]
    """
    valid = [
        b
        for b in (buckets or [])
        if isinstance(b, StratumBucket) and b.qty > 0
    ]
    lp = safe_float(live_price, 0.0)
    anc = safe_float(anchor_price, 0.0)
    c_min = safe_float(cycle_min_buy_price, 0.0)
    req_drop = safe_float(drop_buy_pct, -1.0)
    f_cash = max(0.0, safe_float(free_cash_usd, 0.0))
    r_eq = max(1.0, safe_float(realized_equity_usd, DEFAULT_INITIAL_SEED_USD))

    if not valid or not has_active_l1_bucket(valid):
        return {
            "should_buy": False,
            "is_step_up_unlock": False,
            "trigger_tag": "NO_ACTIVE_L1",
            "quota_ref_price": round(c_min if c_min > 0.0 else lp, 4),
            "ref_static_anchor": round(c_min if c_min > 0.0 else lp, 4),
            "chg_static_pct": 0.0,
            "step_up_eligible": False,
            "stepped_min_price": 0.0,
            "stepped_trigger_price": 0.0,
            "chg_from_l1_pct": 0.0,
            "rebound_mult": 0.0,
            "cash_ratio_pct": round((f_cash / r_eq) * 100.0, 2),
            "next_cycle_min_price": round(c_min, 4),
        }

    l1_p = valid[0].book_price
    valid_refs = [p for p in (l1_p, anc, c_min) if p > 0.0]
    ref_static_anchor = min(valid_refs) if valid_refs else l1_p
    eff_min_p = c_min if c_min > 0.0 else ref_static_anchor

    chg_static_pct = (
        ((lp - ref_static_anchor) / ref_static_anchor) * 100.0
        if (lp > 0.0 and ref_static_anchor > 0.0)
        else 0.0
    )
    chg_from_l1_pct = (
        ((lp - l1_p) / l1_p) * 100.0 if (lp > 0.0 and l1_p > 0.0) else 0.0
    )

    rebound_mult = l1_p / max(0.01, eff_min_p) if eff_min_p > 0.0 else 1.0
    cash_ratio = f_cash / r_eq
    tiers_cnt = len(valid)

    s_drop = safe_float(step_up_drop_pct, STEP_UP_2X_DROP_PCT)
    m_cash = safe_float(min_cash_ratio, STEP_UP_2X_MIN_CASH_RATIO)
    m_reb = safe_float(min_rebound_mult, STEP_UP_2X_MIN_REBOUND_MULT)
    m_tiers = max(1, safe_int(max_tiers_for_unlock, STEP_UP_2X_MAX_TIERS))

    step_up_eligible = bool(
        s_drop > 0.0
        and tiers_cnt <= m_tiers
        and cash_ratio >= (m_cash - 1e-9)
        and rebound_mult >= (m_reb - 1e-9)
    )
    stepped_min_p = (
        round(l1_p * (1.0 - s_drop / 100.0), 4) if step_up_eligible else 0.0
    )
    stepped_trigger_p = (
        round(math.floor((stepped_min_p + 1e-9) * 100.0) / 100.0, 2)
        if stepped_min_p > 0.0
        else 0.0
    )

    if lp <= 0.0:
        return {
            "should_buy": False,
            "is_step_up_unlock": False,
            "trigger_tag": "NO_LIVE_PRICE",
            "quota_ref_price": round(ref_static_anchor, 4),
            "ref_static_anchor": round(ref_static_anchor, 4),
            "chg_static_pct": 0.0,
            "step_up_eligible": step_up_eligible,
            "stepped_min_price": stepped_min_p,
            "stepped_trigger_price": stepped_trigger_p,
            "chg_from_l1_pct": 0.0,
            "rebound_mult": round(rebound_mult, 2),
            "cash_ratio_pct": round(cash_ratio * 100.0, 2),
            "next_cycle_min_price": round(eff_min_p, 4),
        }

    # 1) 제1경로 : 기본 정적 최저가 대비 4단 와이드 신저가 도달 시 최우선 승인
    if chg_static_pct <= req_drop:
        return {
            "should_buy": True,
            "is_step_up_unlock": False,
            "trigger_tag": "STATIC_NEW_LOW",
            "quota_ref_price": round(ref_static_anchor, 4),
            "ref_static_anchor": round(ref_static_anchor, 4),
            "chg_static_pct": round(chg_static_pct, 2),
            "step_up_eligible": step_up_eligible,
            "stepped_min_price": 0.0,
            "stepped_trigger_price": stepped_trigger_p,
            "chg_from_l1_pct": round(chg_from_l1_pct, 2),
            "rebound_mult": round(rebound_mult, 2),
            "cash_ratio_pct": round(cash_ratio * 100.0, 2),
            "next_cycle_min_price": round(min(eff_min_p, lp), 4),
        }

    if s_drop <= 0.0:
        return {
            "should_buy": False,
            "is_step_up_unlock": False,
            "trigger_tag": "HOLD_STATIC_LOCK",
            "quota_ref_price": round(ref_static_anchor, 4),
            "ref_static_anchor": round(ref_static_anchor, 4),
            "chg_static_pct": round(chg_static_pct, 2),
            "step_up_eligible": False,
            "stepped_min_price": 0.0,
            "stepped_trigger_price": 0.0,
            "chg_from_l1_pct": round(chg_from_l1_pct, 2),
            "rebound_mult": round(rebound_mult, 2),
            "cash_ratio_pct": round(cash_ratio * 100.0, 2),
            "next_cycle_min_price": round(eff_min_p, 4),
        }

    if l1_p <= 0.0 or lp >= l1_p:
        return {
            "should_buy": False,
            "is_step_up_unlock": False,
            "trigger_tag": "HOLD_ABOVE_L1",
            "quota_ref_price": round(ref_static_anchor, 4),
            "ref_static_anchor": round(ref_static_anchor, 4),
            "chg_static_pct": round(chg_static_pct, 2),
            "step_up_eligible": step_up_eligible,
            "stepped_min_price": stepped_min_p,
            "stepped_trigger_price": stepped_trigger_p,
            "chg_from_l1_pct": round(chg_from_l1_pct, 2),
            "rebound_mult": round(rebound_mult, 2),
            "cash_ratio_pct": round(cash_ratio * 100.0, 2),
            "next_cycle_min_price": round(eff_min_p, 4),
        }

    # 2) 제2경로 : 3중 안전문(step_up_eligible) 통과 & 현재가가 활성 1층 대비 -15.0%(stepped_min_p) 이하 도달 시 스텝업 해금 승인!
    if step_up_eligible and stepped_min_p > 0.0 and lp <= stepped_min_p:
        tag_str = (
            f"UNLOCK_STEP2X_{int(round(s_drop))}P_"
            f"C{int(round(m_cash * 100))}"
        )
        return {
            "should_buy": True,
            "is_step_up_unlock": True,
            "trigger_tag": tag_str,
            "quota_ref_price": stepped_min_p,
            "ref_static_anchor": round(ref_static_anchor, 4),
            "chg_static_pct": round(chg_static_pct, 2),
            "step_up_eligible": True,
            "stepped_min_price": stepped_min_p,
            "stepped_trigger_price": stepped_trigger_p,
            "chg_from_l1_pct": round(chg_from_l1_pct, 2),
            "rebound_mult": round(rebound_mult, 2),
            "cash_ratio_pct": round(cash_ratio * 100.0, 2),
            "next_cycle_min_price": round(min(stepped_min_p, lp), 4),
        }

    return {
        "should_buy": False,
        "is_step_up_unlock": False,
        "trigger_tag": "HOLD_STEP_UP_2X",
        "quota_ref_price": round(ref_static_anchor, 4),
        "ref_static_anchor": round(ref_static_anchor, 4),
        "chg_static_pct": round(chg_static_pct, 2),
        "step_up_eligible": step_up_eligible,
        "stepped_min_price": stepped_min_p,
        "stepped_trigger_price": stepped_trigger_p,
        "chg_from_l1_pct": round(chg_from_l1_pct, 2),
        "rebound_mult": round(rebound_mult, 2),
        "cash_ratio_pct": round(cash_ratio * 100.0, 2),
        "next_cycle_min_price": round(eff_min_p, 4),
    }


# ---------------------------------------------------------------------------
# [핵심 4 · Case 63, Case 71 ~ 80] 1층 ~ 7층 골디락스 순수 멀티 그리드 배치 & 매도 층/포켓 원가 매칭 정산기
# ---------------------------------------------------------------------------
def vrev_add_quota_lot_and_merge_2tier(
    queue: Sequence[StratumBucket],
    buy_qty: int,
    buy_price: float,
    actual_spent_usd: Optional[float] = None,
    lot_type: str = "QUOTA_L1",
    max_tiers: int = MAX_GRID_TIERS_7,
) -> List[StratumBucket]:
    """
    🎯 3 & 🎯 4 & Case 46 ~ 80 (함수명은 타 모듈 AST 호환을 위해 유지하되 내부는 1~7층 골디락스 멀티 그리드로 작동):
    신규 정량 매수(또는 GRID_L1_ALLIN 모드 1층 전액편입 GOLDEN_L1) 체결 시
    최대 7개 지층(1층 공격수 + 2~6층 개별 완충층[5개] + 통합 7층 본대[GRID_L7])을 관리한다.
    """
    q_int = max(1, safe_int(buy_qty, 1))
    p_val = round(max(0.0001, safe_float(buy_price, 0.01)), 4)
    spent = (
        round(
            max(0.01, safe_float(actual_spent_usd, float(q_int) * p_val)), 4
        )
        if actual_spent_usd is not None
        else round(float(q_int) * p_val, 4)
    )
    pure_p = round(max(0.0001, spent / float(q_int)), 4)
    tag = str(lot_type or "QUOTA_L1").upper().strip()
    if is_upper_grid_tier(tag):
        tag = "QUOTA_L1"

    new_l1 = StratumBucket(
        qty=q_int,
        book_price=pure_p,
        book_invested_usd=spent,
        actual_cost_usd=spent,
        lot_count=1,
        lot_type=(tag if tag != "TOPUP_1FL" else "REENTRY_1FL"),
    )

    existing = [
        b
        for b in (queue or [])
        if isinstance(b, StratumBucket) and b.qty > 0
    ]
    if not existing:
        return [new_l1]

    eff_max_tiers = max(2, safe_int(max_tiers, MAX_GRID_TIERS_7))

    # 🚨 Case 59, Case 71, Case 72, Case 73 & Case 80: 상단 그리드(2층 ~ 7층)만 보유 중(1층 공석) REENTRY_1FL / GOLDEN_L1 유입 시 상단 비병합 독립 1층 배치!
    if not has_active_l1_bucket(existing) and tag in (
        "REENTRY_1FL",
        "TOPUP_1FL",
        "GOLDEN_L1",
    ):
        preserved_uppers = relabel_upper_grid_tiers(
            existing, max_tiers=eff_max_tiers
        )
        return [new_l1] + preserved_uppers

    # 🚨 [Case 78]: 활성 1층 보유 중 미체결 잔량 보충(TOPUP_1FL) 체결 시
    # 지층 승격(GRID_L2) 및 회차(lot_count) 증가 없이 기존 1층(existing[0])에 그대로 원자적 가중평균 합산!
    if tag == "TOPUP_1FL" and has_active_l1_bucket(existing):
        old_b1 = existing[0]
        comb_qty = old_b1.qty + q_int
        comb_cost = round(old_b1.actual_cost_usd + spent, 4)
        comb_p = round(max(0.0001, comb_cost / float(comb_qty)), 4)
        keep_tag = (
            old_b1.lot_type
            if not is_upper_grid_tier(old_b1.lot_type)
            else "REENTRY_1FL"
        )
        merged_l1 = StratumBucket(
            qty=comb_qty,
            book_price=comb_p,
            book_invested_usd=comb_cost,
            actual_cost_usd=comb_cost,
            lot_count=max(1, old_b1.lot_count),
            lot_type=keep_tag,
        )
        preserved_uppers = relabel_upper_grid_tiers(
            existing[1:], max_tiers=eff_max_tiers
        )
        return [merged_l1] + preserved_uppers

    # 2-Layer 레거시 모드 호환 분기
    if eff_max_tiers <= 2:
        old_total_qty = sum(b.qty for b in existing)
        old_actual_cost = round(sum(b.actual_cost_usd for b in existing), 4)
        old_lot_cnt = sum(max(1, b.lot_count) for b in existing)
        old_overall_avg = (
            sum(float(b.qty) * b.book_price for b in existing)
            / float(old_total_qty)
        )
        raw_upper_p = old_actual_cost / float(old_total_qty)
        capped_upper_p = round(min(raw_upper_p, old_overall_avg), 4)
        merged_l2 = StratumBucket(
            qty=old_total_qty,
            book_price=capped_upper_p,
            book_invested_usd=old_actual_cost,
            actual_cost_usd=old_actual_cost,
            lot_count=old_lot_cnt,
            lot_type="GRID_L2",
        )
        return [new_l1, merged_l2]

    # 🚨 [Case 63 & Case 72 : 단가 비교 오름차순(저가 1층 ➔ 고가 7층) 층간 중간 편입]
    # 단, GOLDEN_L1 은 백테스트 GRID_L1_ALLIN 규격대로 항상 새 1층(index 0)으로 편입하고 기존 지층을 승격시킨다.
    if tag != "GOLDEN_L1" and pure_p > existing[0].book_price + 1e-6:
        combined = list(existing) + [new_l1]
        combined.sort(key=lambda b: round(b.book_price, 4))
        lowest_b = combined[0]
        if is_upper_grid_tier(lowest_b.lot_type):
            lowest_b = StratumBucket(
                qty=lowest_b.qty,
                book_price=lowest_b.book_price,
                book_invested_usd=lowest_b.book_invested_usd,
                actual_cost_usd=lowest_b.actual_cost_usd,
                lot_count=max(1, lowest_b.lot_count),
                lot_type=tag,
            )
        sorted_uppers = relabel_upper_grid_tiers(
            combined[1:], max_tiers=eff_max_tiers
        )
        return [lowest_b] + sorted_uppers

    shifted_uppers = relabel_upper_grid_tiers(
        existing, max_tiers=eff_max_tiers
    )
    return [new_l1] + shifted_uppers


def match_and_remove_sold_buckets_7tier(
    buckets: Sequence[StratumBucket],
    delta_remove_qty: int,
    sell_exec_price: float = 0.0,
    max_tiers: int = MAX_GRID_TIERS_7,
    golden_pocket: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    # MODIFIED [Case 63, Case 69, Case 71, Case 72 & Case 80 : 매도 수량 층/골든포켓 판별 및 순수 원가 1:1 매칭 정산기]:
    수동 매도(전량 또는 부분 매도)로 보유 수량이 delta_remove_qty 만큼 줄었을 때:
    1) 독립 골든포켓(golden_pocket)이 존재하고 수량이 일치하거나 단가가 하단 층 이하일 때 골든포켓부터(또는 하단 층부터)
       순차 차감하여 골든포켓과 1층 ~ 7층 각 레이어의 고유 순수 원가를 100% 보존한다.
    2) 실제로 차감된 물량의 고유 순수 매수 원금(sold_actual_cost_usd)만 적용하여
       calc_sell_realized_pnl() 로 세후 실현수익(net_pnl_usd)을 정밀 산출한다.
    """
    valid = [
        b
        for b in (buckets or [])
        if isinstance(b, StratumBucket) and b.qty > 0
    ]
    gp = pocket_from_dict(golden_pocket)
    rem_to_cut = max(0, safe_int(delta_remove_qty, 0))
    exec_p = round(max(0.0, safe_float(sell_exec_price, 0.0)), 4)

    if (not valid and not gp.is_active) or rem_to_cut <= 0:
        return {
            "rem_buckets": valid,
            "rem_golden_pocket": gp.to_dict(),
            "sold_pocket_qty": 0,
            "sold_buckets": [],
            "sold_qty": 0,
            "sold_actual_cost_usd": 0.0,
            "sold_avg_cost_price": 0.0,
            "sold_tier_desc": "없음",
            "sold_l1_completely": False,
            "sold_upper_tier": False,
            "pnl_info": calc_sell_realized_pnl(0, exec_p, 0.0),
        }

    sold_pocket_qty = 0
    sold_pocket_cost = 0.0
    rem_gp = pocket_from_dict(gp.to_dict())
    sold_tier_parts: List[str] = []

    def _cut_from_golden_pocket(cut_q: int) -> int:
        nonlocal sold_pocket_qty, sold_pocket_cost, rem_gp
        if not rem_gp.is_active or cut_q <= 0:
            return 0
        if cut_q >= rem_gp.qty:
            taken = rem_gp.qty
            sold_pocket_qty += taken
            sold_pocket_cost = round(
                sold_pocket_cost + rem_gp.actual_cost_usd, 4
            )
            sold_tier_parts.append(
                f"골든포켓({taken}주@${rem_gp.book_price:.2f})"
            )
            rem_gp = GoldenAllInPocket()
            return taken
        taken = cut_q
        keep_q = rem_gp.qty - taken
        unit_p = rem_gp.actual_avg_price
        part_cost = round(float(taken) * unit_p, 4)
        keep_cost = round(
            max(0.01 * float(keep_q), rem_gp.actual_cost_usd - part_cost), 4
        )
        sold_pocket_qty += taken
        sold_pocket_cost = round(sold_pocket_cost + part_cost, 4)
        sold_tier_parts.append(f"골든포켓부분({taken}주@${unit_p:.2f})")
        rem_gp = GoldenAllInPocket(
            qty=keep_q,
            book_price=round(keep_cost / float(keep_q), 4),
            book_invested_usd=keep_cost,
            actual_cost_usd=keep_cost,
            entry_ts=rem_gp.entry_ts,
            order_date=rem_gp.order_date,
        )
        return taken

    # 골든포켓 수량과 정확히 일치하거나 골든포켓 단가가 최저 그리드 층 단가 이하(또는 그리드가 비어 있음)면 골든포켓 우선 차감
    if rem_gp.is_active and (
        not valid
        or rem_to_cut == rem_gp.qty
        or rem_gp.book_price <= valid[0].book_price + 1e-6
    ):
        cut_done = _cut_from_golden_pocket(rem_to_cut)
        rem_to_cut -= cut_done

    was_active_l1 = has_active_l1_bucket(valid)
    rem_buckets: List[StratumBucket] = []
    sold_buckets: List[StratumBucket] = []
    removed_first_tier_completely = False
    sold_upper_tier = False

    for idx, b in enumerate(valid):
        tier_label = (
            "1층"
            if (idx == 0 and was_active_l1)
            else f"{idx + 1 if was_active_l1 else idx + 2}층"
        )
        if rem_to_cut <= 0:
            rem_buckets.append(b)
            continue

        if rem_to_cut >= b.qty:
            sold_buckets.append(b)
            sold_tier_parts.append(
                f"{tier_label}({b.qty}주@${b.book_price:.2f})"
            )
            rem_to_cut -= b.qty
            if idx == 0 and was_active_l1:
                removed_first_tier_completely = True
            else:
                sold_upper_tier = True
        else:
            sold_q_part = rem_to_cut
            keep_q = b.qty - rem_to_cut
            rem_to_cut = 0

            pure_unit_p = b.actual_avg_price
            sold_cost_part = round(float(sold_q_part) * pure_unit_p, 4)
            keep_cost_part = round(
                max(0.01 * float(keep_q), b.actual_cost_usd - sold_cost_part),
                4,
            )

            sold_buckets.append(
                StratumBucket(
                    qty=sold_q_part,
                    book_price=round(sold_cost_part / float(sold_q_part), 4),
                    book_invested_usd=sold_cost_part,
                    actual_cost_usd=sold_cost_part,
                    lot_count=1,
                    lot_type=b.lot_type,
                )
            )
            rem_buckets.append(
                StratumBucket(
                    qty=keep_q,
                    book_price=round(keep_cost_part / float(keep_q), 4),
                    book_invested_usd=keep_cost_part,
                    actual_cost_usd=keep_cost_part,
                    lot_count=max(1, b.lot_count),
                    lot_type=b.lot_type,
                )
            )
            sold_tier_parts.append(
                f"{tier_label}부분({sold_q_part}주@${pure_unit_p:.2f})"
            )
            if not (idx == 0 and was_active_l1):
                sold_upper_tier = True

    if rem_to_cut > 0 and rem_gp.is_active:
        cut_done = _cut_from_golden_pocket(rem_to_cut)
        rem_to_cut -= cut_done

    eff_max_t = max(2, safe_int(max_tiers, MAX_GRID_TIERS_7))
    if rem_buckets:
        if was_active_l1 and not removed_first_tier_completely:
            active_b1 = rem_buckets[0]
            re_uppers = relabel_upper_grid_tiers(
                rem_buckets[1:], max_tiers=eff_max_t
            )
            rem_buckets = [active_b1] + re_uppers
        else:
            rem_buckets = relabel_upper_grid_tiers(
                rem_buckets, max_tiers=eff_max_t
            )

    sold_qty_total = sum(b.qty for b in sold_buckets) + sold_pocket_qty
    sold_cost_total = round(
        sum(b.actual_cost_usd for b in sold_buckets) + sold_pocket_cost, 4
    )
    sold_avg_cost_p = (
        round(sold_cost_total / float(sold_qty_total), 4)
        if sold_qty_total > 0
        else 0.0
    )
    eff_sell_p = exec_p if exec_p > 0.0 else sold_avg_cost_p
    pnl_info = calc_sell_realized_pnl(
        sold_qty=sold_qty_total,
        sell_exec_price=eff_sell_p,
        sold_actual_cost_usd=sold_cost_total,
    )

    return {
        "rem_buckets": rem_buckets,
        "rem_golden_pocket": rem_gp.to_dict(),
        "sold_pocket_qty": sold_pocket_qty,
        "sold_buckets": sold_buckets,
        "sold_qty": sold_qty_total,
        "sold_actual_cost_usd": sold_cost_total,
        "sold_avg_cost_price": sold_avg_cost_p,
        "sold_tier_desc": (
            " + ".join(sold_tier_parts) if sold_tier_parts else "없음"
        ),
        "sold_l1_completely": removed_first_tier_completely,
        "sold_upper_tier": sold_upper_tier,
        "pnl_info": pnl_info,
    }


def compute_upper_2_to_12_moving_avg(
    buckets: Sequence[StratumBucket],
    rise_upper_pct: float = 1.00,
) -> Dict[str, Any]:
    """
    🚨 [Case 71 & Case 72 상단 2층 ~ 7층 통합 이동평균법(수량 가중평균) 단가 및 목표가 산출기]:
    (타 모듈 AST 임포트 호환을 위해 함수명 compute_upper_2_to_12_moving_avg 를 유지하며 compute_upper_2_to_7_moving_avg 별칭 동시 제공)
    """
    valid = [
        b
        for b in (buckets or [])
        if isinstance(b, StratumBucket) and b.qty > 0
    ]
    active_l1 = has_active_l1_bucket(valid)
    upper_list = valid[1:] if active_l1 else valid[:]

    if not upper_list:
        return {
            "has_active_l1": active_l1,
            "upper_tier_count": 0,
            "upper_qty": 0,
            "upper_lots": 0,
            "upper_actual_cost_usd": 0.0,
            "upper_wma_price": 0.0,
            "upper_wma_target_price": 0.0,
            "min_indiv_upper_price": 0.0,
            "min_indiv_upper_target_price": 0.0,
            "upper_buckets": [],
        }

    u_qty = sum(b.qty for b in upper_list)
    u_lots = sum(max(1, b.lot_count) for b in upper_list)
    u_cost = round(sum(b.actual_cost_usd for b in upper_list), 4)
    wma_p = round(u_cost / float(u_qty), 4) if u_qty > 0 else 0.0
    wma_target_p = (
        round(
            math.ceil(
                (wma_p * (1.0 + rise_upper_pct / 100.0) - 1e-9) * 100.0
            )
            / 100.0,
            2,
        )
        if wma_p > 0.0
        else 0.0
    )

    min_indiv_p = min(b.book_price for b in upper_list)
    min_indiv_target_p = round(
        math.ceil(
            (min_indiv_p * (1.0 + rise_upper_pct / 100.0) - 1e-9) * 100.0
        )
        / 100.0,
        2,
    )

    return {
        "has_active_l1": active_l1,
        "upper_tier_count": len(upper_list),
        "upper_qty": u_qty,
        "upper_lots": u_lots,
        "upper_actual_cost_usd": u_cost,
        "upper_wma_price": wma_p,
        "upper_wma_target_price": wma_target_p,
        "min_indiv_upper_price": round(min_indiv_p, 4),
        "min_indiv_upper_target_price": min_indiv_target_p,
        "upper_buckets": upper_list,
    }


compute_upper_2_to_7_moving_avg = compute_upper_2_to_12_moving_avg


def evaluate_multi_grid_sell_targets(
    buckets: Sequence[StratumBucket],
    live_price: float,
    rise_l1_pct: float = 1.50,
    rise_upper_pct: float = 1.00,
    golden_pocket: Optional[Any] = None,
    rise_pocket_pct: float = GOLDEN_POCKET_RISE_PCT,
) -> Dict[str, Any]:
    """
    🚨 MODIFIED [Case 70, Case 71, Case 72 & Case 80 : 매수 후 60초 타임쉴드 뒤 매 1.5초 실시간 4중 다중 익절 스나이퍼 매도 판정기]:
    매 1.5초 실시간 현재가(live_price)로 아래 4가지 매도 조건을 동시에 스캔하여 조건이 충족된 모든 물량을 반환한다:
    1) [조건 ① : 독립 골든포켓(golden_pocket) +1.50% 이상 도래 (Case 80)]
       gp.is_active == True 이고 live_price >= gp.target_sell_price(rise_pocket_pct) 이면
       sell_pocket_qty = gp.qty 를 매도 물량에 즉시 포함!
    2) [조건 ② : 활성 1층(buckets[0]) 개별 +1.50% 이상 도래]
       has_active_l1 == True 이고 live_price >= ceil(buckets[0].book_price * 1.015 * 100) / 100 이면
       인덱스 0 (1층)을 매도 목록에 추가!
    3) [조건 ③ : 상단 2층 ~ 7층 통합 이동평균(wma_2_to_7) +1.00% 이상 도래]
       상단 그리드(2층 ~ 7층)가 존재하고 live_price >= ceil(wma_2_to_7 * 1.010 * 100) / 100 이면
       상단 2층 ~ 7층 전 지층 인덱스를 일괄 매도 목록에 추가!
       (이때 활성 1층도 본전 이상 live_price >= round(buckets[0].book_price, 2) 이면 인덱스 0 도 포함하여 전량 동시 졸업!).
    4) [조건 ④ : 상단 2층 ~ 6층 개별 완충층 및 통합 7층 본대 +1.00% 이상 도래]
       상단 2층 ~ 7층 통합 이동평균이 아직 +1.00% 에 도달하지 않았더라도,
       상단 개별 층 buckets[k] 중 live_price >= ceil(buckets[k].book_price * 1.010 * 100) / 100 에 도달한
       모든 개별 층 인덱스 k 를 즉시 매도 목록에 추가!
    """
    valid = [
        b
        for b in (buckets or [])
        if isinstance(b, StratumBucket) and b.qty > 0
    ]
    gp = pocket_from_dict(golden_pocket)
    lp = safe_float(live_price, 0.0)
    if (not valid and not gp.is_active) or lp <= 0.0:
        return {
            "should_sell": False,
            "sold_indices": [],
            "sell_pocket_qty": 0,
            "grid_sell_qty": 0,
            "sell_qty": 0,
            "min_floor_price": 0.0,
            "reason_tag": "NONE",
            "hit_golden_pocket": False,
            "hit_l1": False,
            "hit_indiv_grid": False,
            "hit_wma_grad": False,
        }

    sold_idx_set: Set[int] = set()
    floor_candidates: List[float] = []
    hit_golden_pocket = False
    sell_pocket_qty = 0
    hit_l1 = False
    hit_indiv_grid = False
    hit_wma_grad = False

    # ① 독립 골든포켓(+1.50%) 익절 판정 (Case 80)
    if gp.is_active:
        gp_target_p = gp.target_sell_price(rise_pct=rise_pocket_pct)
        if gp_target_p > 0.0 and lp >= gp_target_p:
            hit_golden_pocket = True
            sell_pocket_qty = gp.qty
            floor_candidates.append(gp_target_p)

    active_l1 = has_active_l1_bucket(valid)
    # ② 활성 1층(index 0) +1.50% 개별 익절 판정
    if active_l1 and valid:
        b1 = valid[0]
        min_l1_target_p = (
            math.ceil(
                (b1.book_price * (1.0 + rise_l1_pct / 100.0) - 1e-9) * 100.0
            )
            / 100.0
        )
        if lp >= min_l1_target_p:
            sold_idx_set.add(0)
            floor_candidates.append(min_l1_target_p)
            hit_l1 = True
        upper_start_idx = 1
    else:
        upper_start_idx = 0

    # ③ & ④ 상단 2층 ~ 7층 통합 이동평균(+1.00%) 및 개별 그리드(+1.00%) 판정
    if len(valid) > upper_start_idx:
        wma_info = compute_upper_2_to_12_moving_avg(
            valid, rise_upper_pct=rise_upper_pct
        )
        wma_target_p = safe_float(wma_info.get("upper_wma_target_price"), 0.0)

        if wma_target_p > 0.0 and lp >= wma_target_p:
            for k in range(upper_start_idx, len(valid)):
                sold_idx_set.add(k)
            floor_candidates.append(wma_target_p)
            hit_wma_grad = True
            if active_l1 and valid and lp >= round(valid[0].book_price, 2):
                sold_idx_set.add(0)
                floor_candidates.append(round(valid[0].book_price, 2))
        else:
            for k in range(upper_start_idx, len(valid)):
                bk = valid[k]
                bk_target_p = (
                    math.ceil(
                        (bk.book_price * (1.0 + rise_upper_pct / 100.0) - 1e-9)
                        * 100.0
                    )
                    / 100.0
                )
                if lp >= bk_target_p:
                    sold_idx_set.add(k)
                    floor_candidates.append(bk_target_p)
                    hit_indiv_grid = True

    if not sold_idx_set and sell_pocket_qty <= 0:
        return {
            "should_sell": False,
            "sold_indices": [],
            "sell_pocket_qty": 0,
            "grid_sell_qty": 0,
            "sell_qty": 0,
            "min_floor_price": 0.0,
            "reason_tag": "NONE",
            "hit_golden_pocket": False,
            "hit_l1": False,
            "hit_indiv_grid": False,
            "hit_wma_grad": False,
        }

    sorted_indices = sorted(sold_idx_set)
    grid_sell_qty = sum(valid[idx].qty for idx in sorted_indices)
    total_sell_qty = grid_sell_qty + sell_pocket_qty
    min_floor_p = max(floor_candidates) if floor_candidates else round(lp, 2)

    if hit_golden_pocket and not sorted_indices:
        reason_tag = "SELL_GOLDEN_POCKET"
    elif hit_golden_pocket and sorted_indices:
        if len(sorted_indices) == len(valid):
            reason_tag = "SELL_ALL_GRAD"
        else:
            reason_tag = "SELL_POCKET_AND_GRID"
    elif len(sorted_indices) == len(valid):
        reason_tag = (
            "SELL_ALL_GRAD"
            if hit_wma_grad or len(valid) > 1
            else "SELL_L1_ONLY"
        )
    elif hit_wma_grad:
        reason_tag = "SELL_WMA_UPPER"
    elif hit_l1 and hit_indiv_grid:
        reason_tag = "SELL_L1_AND_GRID"
    elif hit_indiv_grid:
        reason_tag = "SELL_GRID_INDIV"
    else:
        reason_tag = "SELL_L1_ONLY"

    return {
        "should_sell": True,
        "sold_indices": sorted_indices,
        "sell_pocket_qty": sell_pocket_qty,
        "grid_sell_qty": grid_sell_qty,
        "sell_qty": total_sell_qty,
        "min_floor_price": round(min_floor_p, 2),
        "reason_tag": reason_tag,
        "hit_golden_pocket": hit_golden_pocket,
        "hit_l1": hit_l1,
        "hit_indiv_grid": hit_indiv_grid,
        "hit_wma_grad": hit_wma_grad,
    }


def vrev_reanchor_single_tier_quota(
    queue: Sequence[StratumBucket],
    net_realized_cash_profit: float,
    max_allowed_total_discount_usd: Optional[float] = None,
    enable_reanchor: bool = False,
) -> Tuple[List[StratumBucket], float]:
    """
    하위 호환 심볼 유지용 함수:
    챔피언에서는 리앵커링 원가 차감을 수행하지 않으므로 기본값(enable_reanchor=False) 호출 시
    원가를 100% 그대로 보존하고 (existing, 0.0)을 반환한다.
    """
    existing = [
        b
        for b in (queue or [])
        if isinstance(b, StratumBucket) and b.qty > 0
    ]
    if not enable_reanchor or len(existing) != 1:
        return existing, 0.0

    rem = existing[0]
    net_profit = safe_float(net_realized_cash_profit, 0.0)
    if net_profit <= 0.0 or rem.qty <= 0:
        return existing, 0.0

    credit_usd = max(0.0, net_profit * REANCHOR_NET_BUFFER_MULT)
    old_book_p = rem.book_price
    min_floor_inv = 0.01 * float(rem.qty)
    if (
        max_allowed_total_discount_usd is not None
        and safe_float(max_allowed_total_discount_usd, -1.0) >= 0.0
    ):
        allowed_disc = max(0.0, safe_float(max_allowed_total_discount_usd, 0.0))
        min_floor_inv = max(
            min_floor_inv, round(rem.actual_cost_usd - allowed_disc, 4)
        )

    new_book_inv = round(
        max(min_floor_inv, rem.book_invested_usd - credit_usd), 4
    )
    new_book_p = round(
        min(old_book_p, max(0.01, new_book_inv / float(rem.qty))), 4
    )
    price_drop = round(max(0.0, old_book_p - new_book_p), 4)
    updated_bucket = StratumBucket(
        qty=rem.qty,
        book_price=new_book_p,
        book_invested_usd=round(new_book_p * float(rem.qty), 4),
        actual_cost_usd=rem.actual_cost_usd,
        lot_count=rem.lot_count,
        lot_type=rem.lot_type,
    )
    return [updated_bucket], price_drop


def calc_sell_realized_pnl(
    sold_qty: int,
    sell_exec_price: float,
    sold_actual_cost_usd: float,
) -> Dict[str, float]:
    """
    매도 체결 수량(sold_qty), 실제 체결 단가(sell_exec_price), 매도 지층/포켓들의 실제 매수 원금 합계(sold_actual_cost_usd)를
    기반으로 왕복 수수료(0.14%) 차감 후 세후 실현 손익을 정밀 산출한다.
    """
    q_int = max(0, safe_int(sold_qty, 0))
    exec_p = max(0.0, safe_float(sell_exec_price, 0.0))
    actual_cost = max(0.0, safe_float(sold_actual_cost_usd, 0.0))
    if q_int <= 0 or exec_p <= 0.0:
        return {
            "proceeds_usd": 0.0,
            "actual_cost_usd": actual_cost,
            "gross_pnl_usd": 0.0,
            "fee_usd": 0.0,
            "net_pnl_usd": 0.0,
            "net_rate_pct": 0.0,
        }

    proceeds = round(float(q_int) * exec_p, 4)
    gross_pnl = round(proceeds - actual_cost, 4)
    fee_usd = round(
        ((actual_cost + proceeds) * 0.5) * (ROUND_TRIP_FEE_RATE_PCT / 100.0), 4
    )
    net_pnl = round(gross_pnl - fee_usd, 4)
    net_rate_pct = (
        round((net_pnl / actual_cost) * 100.0, 4) if actual_cost > 0.0 else 0.0
    )
    return {
        "proceeds_usd": proceeds,
        "actual_cost_usd": actual_cost,
        "gross_pnl_usd": gross_pnl,
        "fee_usd": fee_usd,
        "net_pnl_usd": net_pnl,
        "net_rate_pct": net_rate_pct,
    }


# ---------------------------------------------------------------------------
# [핵심 5] 포트폴리오 · 1~7층 골디락스 멀티 그리드 · 독립 골든포켓 · 2~7층 이동평균 · STEP2X_15PCT_C20 · GUARD30 통합 요약기 (Case 59 ~ 80)
# ---------------------------------------------------------------------------
def summarize_stratum_portfolio(
    state_dict: Dict[str, Any],
    live_price: float = 0.0,
) -> Dict[str, Any]:
    """
    🎯 1 ~ 🎯 5 & Case 59, 60, 67, 69, 71, 72, 73, 74, 76, 77, 78, 80:
    원장 상태(state_dict)와 현재가(live_price)를 받아:
    - 1층(활성 공격수) 및 상단 2층 ~ 6층 개별 완충층 · 통합 7층 본대(GRID_L2 ~ GRID_L7) 현황
    - 🌟 Case 80: 황금시간대 전액매수 모드(golden_allin_mode · 기본값 "NONE") 및 독립 골든포켓(golden_pocket) 보유 현황,
      +1.50% 목표가(golden_pocket_target_price), 수익률(golden_pocket_gain_pct), 황금시간 매매 통계 요약
    - 🎯 Case 78: 활성 1층 현재 보유 주수(l1_cur_qty), 1층 목표 정량(l1_target_quota_qty),
      미체결 잔량(l1_rem_quota_qty = max(0, l1_target_quota_qty - l1_cur_qty)) 산출
    - 상단 2층 ~ 7층 통합 이동평균 단가(upper_wma_price) 및 +1.00% 일괄 익절 목표가
    - 💉 Case 77 & Case 80: 온디맨드 예비시드 수혈 잔액(injected_reserve_usd)을 제외한 순수 코어 자산(core_equity_for_quota) 기반
      8% 정량 산출 및 30% 자투리 가드 최소 필요 현금(min_req_cash_guard30), 예비시드 한도(used/6회분) 요약을 반환한다.
    """
    st = state_dict if isinstance(state_dict, dict) else {}
    raw_buckets = buckets_from_dicts(st.get("buckets", []))
    buckets = enforce_true_breakeven_floor_on_buckets(raw_buckets)
    gp = pocket_from_dict(st.get("golden_pocket"))

    init_seed = max(
        100.0, safe_float(st.get("initial_seed_usd"), DEFAULT_INITIAL_SEED_USD)
    )
    cum_realized = round(
        safe_float(st.get("cumulative_realized_net_usd"), 0.0), 4
    )
    injected_reserve_usd = round(
        max(0.0, safe_float(st.get("injected_reserve_usd"), 0.0)), 4
    )
    used_reserve_portions_cnt = (
        0
        if injected_reserve_usd <= 0.0
        else max(
            1,
            min(
                MAX_RESERVE_PORTIONS,
                safe_int(st.get("used_reserve_portions_cnt"), 1),
            ),
        )
    )
    avail_reserve_portions = max(
        0, MAX_RESERVE_PORTIONS - used_reserve_portions_cnt
    )

    actual_invested_buckets = round(sum(b.actual_cost_usd for b in buckets), 4)
    book_invested_buckets = round(sum(b.book_invested_usd for b in buckets), 4)
    gp_qty = gp.qty if gp.is_active else 0
    gp_cost = round(gp.actual_cost_usd if gp.is_active else 0.0, 4)
    gp_price = round(gp.book_price if gp.is_active else 0.0, 4)

    actual_invested = round(actual_invested_buckets + gp_cost, 4)
    book_invested = round(book_invested_buckets + gp_cost, 4)

    # [Case 77 & Case 80 회계 항등식 확장]:
    expected_free_cash = round(
        max(
            0.0,
            (init_seed + cum_realized + injected_reserve_usd)
            - actual_invested,
        ),
        4,
    )
    free_cash = safe_float(st.get("free_cash_usd"), expected_free_cash)
    if abs(free_cash - expected_free_cash) > 0.05:
        free_cash = expected_free_cash

    held_shares = sum(b.qty for b in buckets)
    total_held_shares = held_shares + gp_qty
    held_lots = sum(max(1, b.lot_count) for b in buckets)
    held_tiers = len(buckets)
    lp = safe_float(live_price, 0.0)
    if lp <= 0.0:
        if buckets:
            lp = buckets[0].actual_avg_price
        elif gp.is_active:
            lp = gp.actual_avg_price

    actual_avg_p = (
        round(actual_invested / float(total_held_shares), 4)
        if total_held_shares > 0
        else 0.0
    )
    grid_actual_avg_p = (
        round(actual_invested_buckets / float(held_shares), 4)
        if held_shares > 0
        else 0.0
    )
    book_avg_p = (
        round(book_invested / float(total_held_shares), 4)
        if total_held_shares > 0
        else 0.0
    )

    threshold_mode = str(st.get("threshold_mode") or "WIDE_RUNWAY").upper()
    portion_mode = str(st.get("portion_mode") or "COMP_08PCT").upper()
    unlock_mode = str(
        st.get("unlock_mode") or DEFAULT_UNLOCK_MODE
    ).upper()
    golden_allin_mode = (
        str(st.get("golden_allin_mode") or DEFAULT_GOLDEN_ALLIN_MODE)
        .upper()
        .strip()
    )
    if golden_allin_mode not in GOLDEN_ALLIN_MODES:
        golden_allin_mode = DEFAULT_GOLDEN_ALLIN_MODE

    drop_buy_pct, rise_l1_pct, rise_l2_pct = get_golden8_prog_thresholds(
        held_lots=max(1, held_lots), threshold_mode=threshold_mode
    )

    gp_target_price = gp.target_sell_price(rise_pct=GOLDEN_POCKET_RISE_PCT)
    gp_gain_pct = (
        round(((lp - gp_price) / gp_price) * 100.0, 2)
        if (gp.is_active and lp > 0.0 and gp_price > 0.0)
        else 0.0
    )

    active_l1 = has_active_l1_bucket(buckets)
    is_l2_only = bool(len(buckets) > 0 and not active_l1)

    # [Case 78 : 활성 1층 현재 보유 주수, 목표 정량 및 미체결 잔량(l1_rem_quota_qty) 산출]
    raw_l1_target_q = max(0, safe_int(st.get("l1_target_quota_qty"), 0))
    pending_lot_tag = str(st.get("pending_lot_type") or "").upper().strip()
    if active_l1 and buckets:
        l1_cur_qty = buckets[0].qty
        l1_target_quota_qty = max(l1_cur_qty, raw_l1_target_q)
        l1_rem_quota_qty = max(0, l1_target_quota_qty - l1_cur_qty)
    else:
        l1_cur_qty = 0
        l1_target_quota_qty = (
            raw_l1_target_q
            if (
                bool(str(st.get("buy_order_id") or "").strip())
                and pending_lot_tag != "GOLDEN_POCKET"
            )
            else 0
        )
        l1_rem_quota_qty = 0

    wma_info = compute_upper_2_to_12_moving_avg(
        buckets, rise_upper_pct=rise_l2_pct
    )
    upper_tier_count = safe_int(wma_info.get("upper_tier_count"), 0)
    upper_qty = safe_int(wma_info.get("upper_qty"), 0)
    upper_lots = safe_int(wma_info.get("upper_lots"), 0)
    upper_wma_price = safe_float(wma_info.get("upper_wma_price"), 0.0)
    upper_wma_target_price = safe_float(
        wma_info.get("upper_wma_target_price"), 0.0
    )
    min_indiv_upper_price = safe_float(
        wma_info.get("min_indiv_upper_price"), 0.0
    )
    min_indiv_upper_target_price = safe_float(
        wma_info.get("min_indiv_upper_target_price"), 0.0
    )

    l1_target_price = 0.0
    l2_target_price = upper_wma_target_price
    l1_gain_pct = 0.0
    l2_gain_pct = 0.0
    min_indiv_upper_gain_pct = 0.0

    if active_l1 and buckets:
        b1 = buckets[0]
        l1_target_price = round(
            math.ceil(
                (b1.book_price * (1.0 + rise_l1_pct / 100.0) - 1e-9) * 100.0
            )
            / 100.0,
            2,
        )
        if lp > 0.0 and b1.book_price > 0.0:
            l1_gain_pct = round(
                ((lp - b1.book_price) / b1.book_price) * 100.0, 2
            )

    if upper_wma_price > 0.0 and lp > 0.0:
        l2_gain_pct = round(
            ((lp - upper_wma_price) / upper_wma_price) * 100.0, 2
        )
    if min_indiv_upper_price > 0.0 and lp > 0.0:
        min_indiv_upper_gain_pct = round(
            ((lp - min_indiv_upper_price) / min_indiv_upper_price) * 100.0, 2
        )

    anchor_p = safe_float(st.get("anchor_price"), 0.0)
    cycle_min_p = safe_float(st.get("cycle_min_buy_price"), 0.0)
    ratchet_p = safe_float(st.get("ratchet_anchor_price"), anchor_p)
    realized_equity_usd = round(max(0.0, init_seed + cum_realized), 4)

    # 🚨 Case 73: 1층 공석 시 상단 최하단 층(2층, min_indiv_upper_price)을 상한 가드로 전달!
    reentry_sig = evaluate_l2_only_hybrid_reentry_signal(
        live_price=lp,
        anchor_price=anchor_p,
        l2_book_price=(
            min_indiv_upper_price
            if min_indiv_upper_price > 0.0
            else upper_wma_price
        ),
        min_upper_tier_price=min_indiv_upper_price,
    )
    reentry_ref_anchor = safe_float(reentry_sig.get("ref_anchor"), anchor_p)
    reentry_pullback_price = safe_float(
        reentry_sig.get("pullback_target_price"), 0.0
    )
    reentry_breakout_price = safe_float(
        reentry_sig.get("breakout_target_price"), 0.0
    )
    chg_from_reentry_anchor_pct = safe_float(
        reentry_sig.get("chg_from_exit_pct"), 0.0
    )
    l2_ceiling_price = safe_float(
        reentry_sig.get("l2_ceiling_price"), min_indiv_upper_price
    )
    reentry_signal_type = str(
        reentry_sig.get("signal_type") or "HOLD_WAIT_GATE"
    )

    # 🚨 Case 60, Case 67, Case 72 & Case 76:
    if buckets:
        candidates = [
            p
            for p in (buckets[0].book_price, anchor_p, cycle_min_p)
            if p > 0.0
        ]
        active_buy_anchor = (
            min(candidates) if candidates else buckets[0].book_price
        )
    else:
        active_buy_anchor = (
            anchor_p if anchor_p > 0.0 else (lp if lp > 0.0 else 1.0)
        )

    trigger_buy_price = (
        round(active_buy_anchor * (1.0 + drop_buy_pct / 100.0), 2)
        if active_buy_anchor > 0.0
        else 0.0
    )

    # Case 76: 활성 1층 보유 중 STEP2X_15PCT_C20 스텝업 해금 자격 및 목표가 평가
    eff_step_drop = (
        0.0 if unlock_mode in ("STATIC", "NONE", "OFF") else STEP_UP_2X_DROP_PCT
    )
    step_up_eval = evaluate_step_up_2x_dip_signal(
        live_price=lp,
        buckets=buckets,
        anchor_price=anchor_p,
        cycle_min_buy_price=cycle_min_p,
        drop_buy_pct=drop_buy_pct,
        free_cash_usd=free_cash,
        realized_equity_usd=realized_equity_usd,
        step_up_drop_pct=eff_step_drop,
        min_cash_ratio=STEP_UP_2X_MIN_CASH_RATIO,
        min_rebound_mult=STEP_UP_2X_MIN_REBOUND_MULT,
        max_tiers_for_unlock=STEP_UP_2X_MAX_TIERS,
    )
    step_up_eligible = bool(step_up_eval.get("step_up_eligible", False))
    stepped_min_price = safe_float(step_up_eval.get("stepped_min_price"), 0.0)
    stepped_trigger_price = safe_float(
        step_up_eval.get("stepped_trigger_price"), 0.0
    )
    rebound_mult = safe_float(step_up_eval.get("rebound_mult"), 0.0)
    cash_ratio_pct = safe_float(step_up_eval.get("cash_ratio_pct"), 0.0)

    if is_l2_only:
        ref_buy_anchor = (
            reentry_ref_anchor
            if reentry_ref_anchor > 0.0
            else active_buy_anchor
        )
        chg_from_buy_anchor_pct = chg_from_reentry_anchor_pct
    else:
        ref_buy_anchor = active_buy_anchor
        chg_from_buy_anchor_pct = (
            round(((lp - active_buy_anchor) / active_buy_anchor) * 100.0, 2)
            if (lp > 0.0 and active_buy_anchor > 0.0)
            else 0.0
        )

    # [Case 77 & Case 80 : 온디맨드 예비시드 수혈금(injected_reserve_usd)을 제외한 순수 코어 자산 기준으로 8% 정량 예산 산출]:
    core_equity_for_quota = max(
        init_seed, (free_cash + actual_invested) - injected_reserve_usd
    )
    if len(buckets) == 0:
        ref_for_quota = (
            anchor_p if anchor_p > 0.0 else (lp if lp > 0.0 else 1.0)
        )
    elif is_l2_only:
        ref_for_quota = (
            reentry_ref_anchor
            if reentry_ref_anchor > 0.0
            else (lp if lp > 0.0 else active_buy_anchor)
        )
    elif bool(step_up_eval.get("is_step_up_unlock")) and stepped_min_price > 0.0:
        ref_for_quota = stepped_min_price
    else:
        ref_for_quota = active_buy_anchor

    anchor_quota_qty, next_portion_budget = compute_golden8_quota_qty(
        anchor_price=max(0.01, ref_for_quota),
        current_total_equity=core_equity_for_quota,
        initial_seed_usd=init_seed,
        portion_mode=portion_mode,
        exec_price=None,
    )
    eff_exec_for_cap = lp if lp > 0.0 else max(0.01, ref_for_quota)
    budget_cap_qty = max(
        1, int(math.floor((next_portion_budget + 1e-9) / eff_exec_for_cap))
    )
    next_target_qty = min(budget_cap_qty, anchor_quota_qty)

    # [Case 77]: 현재 상태에서의 30% 자투리 승격 방지 가드 최소 필요 현금(min_req_cash_guard30) 산출
    l1_cost_now = (
        buckets[0].actual_cost_usd if (active_l1 and buckets) else 0.0
    )
    guard30_eval = evaluate_guard30_and_reserve_injection(
        free_cash_usd=free_cash,
        broker_bp_usd=None,
        exec_price=eff_exec_for_cap,
        portion_budget=next_portion_budget,
        l1_actual_cost_usd=l1_cost_now,
        is_dip_promotion=bool(active_l1 and len(buckets) > 0),
        used_reserve_portions_cnt=used_reserve_portions_cnt,
        max_reserve_portions=MAX_RESERVE_PORTIONS,
    )
    min_req_cash_guard30 = safe_float(guard30_eval.get("min_req_cash"), 0.0)

    market_eval_usd = (
        round(float(total_held_shares) * lp, 4)
        if total_held_shares > 0 and lp > 0.0
        else 0.0
    )
    unrealized_pnl_usd = (
        round(market_eval_usd - actual_invested, 4)
        if total_held_shares > 0 and lp > 0.0
        else 0.0
    )
    unrealized_rate_pct = (
        round((unrealized_pnl_usd / actual_invested) * 100.0, 2)
        if actual_invested > 0.0
        else 0.0
    )

    realized_roi_pct = round((cum_realized / init_seed) * 100.0, 2)
    gross_mark_equity_usd = round(free_cash + market_eval_usd, 4)
    # 순수 자기자본 시가평가 총자산 (수혈받은 예비시드 원금 injected_reserve_usd 차감 기준)
    total_mark_equity_usd = round(
        max(0.0, gross_mark_equity_usd - injected_reserve_usd), 4
    )
    total_net_pnl_usd = round(cum_realized + unrealized_pnl_usd, 4)
    total_roi_pct = round((total_net_pnl_usd / init_seed) * 100.0, 2)

    reanchor_cnt = safe_int(st.get("reanchor_cnt"), 0)
    cum_reanchor_drop = round(
        safe_float(st.get("cumulative_reanchor_drop_usd"), 0.0), 4
    )
    indiv_grid_sell_cnt = safe_int(st.get("indiv_grid_sell_cnt"), 0)
    wma_grad_sell_cnt = safe_int(st.get("wma_grad_sell_cnt"), 0)

    # Case 74: 🛡️ 시드보호 패스는 당일 프리장 ~ 정규장(04:07 ~ 16:00 EST) 일일 주기 카운터(daily_seed_protect_pass_cnt)로 바인딩!
    daily_seed_protect_pass_cnt = safe_int(
        st.get("daily_seed_protect_pass_cnt"), 0
    )
    total_seed_protect_pass_cnt = safe_int(
        st.get("seed_protect_pass_cnt"), 0
    )
    seed_protect_pass_cnt = daily_seed_protect_pass_cnt

    extra_13plus_buy_events = safe_int(st.get("extra_13plus_buy_events"), 0)
    cond_unlock_buy_events = safe_int(st.get("cond_unlock_buy_events"), 0)
    daily_unlock_buy_events = safe_int(st.get("daily_unlock_buy_events"), 0)
    cum_leftover_saved = round(
        safe_float(st.get("cumulative_leftover_saved_usd"), 0.0), 4
    )

    # NEW [Case 80]: 황금시간대 전액매수 및 골든포켓 통계 바인딩
    golden_allin_buy_events = safe_int(st.get("golden_allin_buy_events"), 0)
    daily_golden_allin_buy_events = safe_int(
        st.get("daily_golden_allin_buy_events"), 0
    )
    golden_pocket_sell_cnt = safe_int(st.get("golden_pocket_sell_cnt"), 0)
    daily_golden_pocket_sell_cnt = safe_int(
        st.get("daily_golden_pocket_sell_cnt"), 0
    )
    golden_realized_net_usd = round(
        safe_float(st.get("golden_realized_net_usd"), 0.0), 4
    )
    daily_golden_realized_net_usd = round(
        safe_float(st.get("daily_golden_realized_net_usd"), 0.0), 4
    )
    last_golden_allin_date = str(st.get("last_golden_allin_date") or "").strip()

    total_reserve_injected_cnt = safe_int(
        st.get("total_reserve_injected_cnt"), 0
    )
    daily_reserve_injected_cnt = safe_int(
        st.get("daily_reserve_injected_cnt"), 0
    )
    cumulative_reserve_repaid_usd = round(
        safe_float(st.get("cumulative_reserve_repaid_usd"), 0.0), 4
    )
    dust_guard_blocked_cnt = safe_int(st.get("dust_guard_blocked_cnt"), 0)
    daily_dust_guard_blocked_cnt = safe_int(
        st.get("daily_dust_guard_blocked_cnt"), 0
    )
    waiting_reserve_deposit = bool(st.get("waiting_reserve_deposit", False))
    waiting_reserve_deposit_alert_sent = bool(
        st.get("waiting_reserve_deposit_alert_sent", False)
    )
    required_reserve_deposit_usd = round(
        max(0.0, safe_float(st.get("required_reserve_deposit_usd"), 0.0)), 2
    )

    return {
        "buckets": buckets,
        "golden_allin_mode": golden_allin_mode,
        "golden_allin_mode_label": get_golden_allin_mode_label(
            golden_allin_mode
        ),
        "golden_pocket": gp,
        "has_golden_pocket": gp.is_active,
        "golden_pocket_qty": gp_qty,
        "golden_pocket_price": gp_price,
        "golden_pocket_cost_usd": gp_cost,
        "golden_pocket_target_price": gp_target_price,
        "golden_pocket_gain_pct": gp_gain_pct,
        "last_golden_allin_date": last_golden_allin_date,
        "golden_allin_buy_events": golden_allin_buy_events,
        "daily_golden_allin_buy_events": daily_golden_allin_buy_events,
        "golden_pocket_sell_cnt": golden_pocket_sell_cnt,
        "daily_golden_pocket_sell_cnt": daily_golden_pocket_sell_cnt,
        "golden_realized_net_usd": golden_realized_net_usd,
        "daily_golden_realized_net_usd": daily_golden_realized_net_usd,
        "has_active_l1": active_l1,
        "l1_cur_qty": l1_cur_qty,
        "l1_target_quota_qty": l1_target_quota_qty,
        "l1_rem_quota_qty": l1_rem_quota_qty,
        "held_shares": held_shares,
        "total_held_shares": total_held_shares,
        "held_lots": held_lots,
        "held_tiers": held_tiers,
        "upper_tier_count": upper_tier_count,
        "upper_qty": upper_qty,
        "upper_lots": upper_lots,
        "upper_wma_price": upper_wma_price,
        "upper_wma_target_price": upper_wma_target_price,
        "min_indiv_upper_price": min_indiv_upper_price,
        "min_indiv_upper_target_price": min_indiv_upper_target_price,
        "min_indiv_upper_gain_pct": min_indiv_upper_gain_pct,
        "is_l2_only_anti_bloat": is_l2_only,
        "initial_seed_usd": init_seed,
        "free_cash_usd": free_cash,
        "actual_invested_buckets_usd": actual_invested_buckets,
        "actual_invested_usd": actual_invested,
        "book_invested_usd": book_invested,
        "actual_avg_price": actual_avg_p,
        "grid_actual_avg_price": grid_actual_avg_p,
        "book_avg_price": book_avg_p,
        "cycle_reanchor_credit_usd": 0.0,
        "market_eval_usd": market_eval_usd,
        "unrealized_pnl_usd": unrealized_pnl_usd,
        "unrealized_rate_pct": unrealized_rate_pct,
        "cumulative_realized_net_usd": cum_realized,
        "realized_equity_usd": realized_equity_usd,
        "realized_roi_pct": realized_roi_pct,
        "gross_mark_equity_usd": gross_mark_equity_usd,
        "total_mark_equity_usd": total_mark_equity_usd,
        "mark_equity_usd": total_mark_equity_usd,
        "total_net_pnl_usd": total_net_pnl_usd,
        "total_roi_pct": total_roi_pct,
        "mark_roi_pct": total_roi_pct,
        "drop_buy_pct": drop_buy_pct,
        "rise_sell_l1_pct": rise_l1_pct,
        "rise_sell_l2_pct": rise_l2_pct,
        "l1_target_price": l1_target_price,
        "l2_target_price": l2_target_price,
        "l1_gain_pct": l1_gain_pct,
        "l2_gain_pct": l2_gain_pct,
        "active_buy_anchor": round(active_buy_anchor, 4),
        "ref_buy_anchor": round(ref_buy_anchor, 4),
        "chg_from_buy_anchor_pct": chg_from_buy_anchor_pct,
        "cycle_min_buy_price": round(
            cycle_min_p if cycle_min_p > 0.0 else active_buy_anchor, 4
        ),
        "ratchet_anchor_price": round(ratchet_p, 4),
        "trigger_buy_price": trigger_buy_price,
        "unlock_mode": unlock_mode,
        "step_up_eligible": step_up_eligible,
        "stepped_min_price": stepped_min_price,
        "stepped_trigger_price": stepped_trigger_price,
        "rebound_mult": rebound_mult,
        "cash_ratio_pct": cash_ratio_pct,
        "cond_unlock_buy_events": cond_unlock_buy_events,
        "daily_unlock_buy_events": daily_unlock_buy_events,
        "reentry_ref_anchor": round(reentry_ref_anchor, 4),
        "reentry_pullback_price": reentry_pullback_price,
        "reentry_breakout_price": reentry_breakout_price,
        "chg_from_reentry_anchor_pct": chg_from_reentry_anchor_pct,
        "l2_ceiling_price": round(l2_ceiling_price, 4),
        "reentry_signal_type": reentry_signal_type,
        "next_target_qty": next_target_qty,
        "anchor_quota_qty": anchor_quota_qty,
        "budget_cap_qty": budget_cap_qty,
        "next_portion_budget": next_portion_budget,
        "min_req_cash_guard30": min_req_cash_guard30,
        "used_reserve_portions_cnt": used_reserve_portions_cnt,
        "avail_reserve_portions": avail_reserve_portions,
        "max_reserve_portions": MAX_RESERVE_PORTIONS,
        "injected_reserve_usd": injected_reserve_usd,
        "total_reserve_injected_cnt": total_reserve_injected_cnt,
        "daily_reserve_injected_cnt": daily_reserve_injected_cnt,
        "cumulative_reserve_repaid_usd": cumulative_reserve_repaid_usd,
        "dust_guard_blocked_cnt": dust_guard_blocked_cnt,
        "daily_dust_guard_blocked_cnt": daily_dust_guard_blocked_cnt,
        "waiting_reserve_deposit": waiting_reserve_deposit,
        "waiting_reserve_deposit_alert_sent": waiting_reserve_deposit_alert_sent,
        "required_reserve_deposit_usd": required_reserve_deposit_usd,
        "indiv_grid_sell_cnt": indiv_grid_sell_cnt,
        "wma_grad_sell_cnt": wma_grad_sell_cnt,
        "reanchor_cnt": reanchor_cnt,
        "cumulative_reanchor_drop_usd": cum_reanchor_drop,
        "seed_protect_pass_cnt": seed_protect_pass_cnt,
        "daily_seed_protect_pass_cnt": daily_seed_protect_pass_cnt,
        "total_seed_protect_pass_cnt": total_seed_protect_pass_cnt,
        "extra_13plus_buy_events": extra_13plus_buy_events,
        "cumulative_leftover_saved_usd": cum_leftover_saved,
    }


# ---------------------------------------------------------------------------
# [핵심 6] TDD 사전 무결성 자동 검증 슈트 (Case 25 ~ 80 전수 검증)
# ---------------------------------------------------------------------------
def run_quant_engine_tdd() -> bool:
    """
    기동 직전 8% 황금정량 산출, Case 67 min(1회분 예산 상한 주수, 기준가 고정 정량) 이중 캡핑,
    4단 와이드 활주로(-1.0% / -2.0% / -3.5% / -5.5%),
    1층 ~ 6층 개별 완충층 보존 및 8회차 최상단(6층+7층 ➔ 통합 7층 GRID_L7) 병합(Case 72),
    골든포켓(+1.50%) / 1층(+1.50%) / 2~7층 개별(+1.00%) / 2~7층 통합 이동평균(+1.00%) 4중 다중 익절 판정(Case 71, 72, 80),
    상단 그리드 단독 보유(1층 공석) 시 2층 단가 상한 역전 차단(HOLD_PREVENT_INVERSION · Case 73) 및
    눌림/돌파 독립 1층 재장전(Case 59, 73), 정적 기억저가 잠금 및 🔓 06_STEP2X_15PCT_C20 3중 안전문 스텝업 해금(Case 60, 72, 76),
    💉 05_RESV_6P_GUARD30 30% 자투리 승격 방지 가드 · 토스 계좌 여유자금 감지 자동 수혈 · 0주 졸업 자동 상환(Case 77),
    🎯 Case 78 지정가 부분 체결 후 미체결 잔량(TOPUP_1FL) 기존 1층 무승격 원자적 합산,
    🌟 Case 80 황금시간대(07:00 ~ 07:50 EST & RSI <= 19.0) 기본값 OFF("NONE") 및 POCKET_ALLIN / GRID_L1_ALLIN 판정 검증을 전수 수행한다.
    """
    assert DEFAULT_GOLDEN_ALLIN_MODE == "NONE", (
        f"TDD 실패(Case 80 기본값 OFF 위반): {DEFAULT_GOLDEN_ALLIN_MODE}"
    )

    # 1) 8% 황금정량 및 Case 67 min(budget_cap_qty, anchor_quota_qty) 캡핑 검증
    q_dip, bud_c67 = compute_golden8_quota_qty(
        82.39, 19155.74, 19000.0, "COMP_08PCT", exec_price=79.52
    )
    q_brk, _ = compute_golden8_quota_qty(
        82.39, 19155.74, 19000.0, "COMP_08PCT", exec_price=86.00
    )
    assert q_dip == 18 and q_brk == 17 and (q_brk * 86.00) <= bud_c67, (
        f"TDD 실패(Case 67): q_dip={q_dip}, q_brk={q_brk}"
    )

    # Case 67: 0주 상태에서 직전 anchor_price($85.00)가 존재하고 현재가($80.00)가 낮을 때 정량 일치 검증
    mock_zero_st = {
        "buckets": [],
        "initial_seed_usd": 10000.0,
        "anchor_price": 85.00,
        "cumulative_realized_net_usd": 0.0,
    }
    zero_sum = summarize_stratum_portfolio(mock_zero_st, live_price=80.00)
    q_zero_order, _ = compute_golden8_quota_qty(
        85.00, 10000.0, 10000.0, "COMP_08PCT", exec_price=80.00
    )
    assert (
        zero_sum["anchor_quota_qty"] == 9
        and zero_sum["budget_cap_qty"] == 10
        and zero_sum["next_target_qty"] == q_zero_order == 9
        and zero_sum["golden_allin_mode"] == "NONE"
    ), f"TDD 실패(Case 67/80 0주 정량/기본모드 일치): {zero_sum}"

    # 2) 4단 와이드 활주로 단차 검증
    d1, s1, s2 = get_golden8_prog_thresholds(1, "WIDE_RUNWAY")
    d5, _, _ = get_golden8_prog_thresholds(5, "WIDE_RUNWAY")
    d9, _, _ = get_golden8_prog_thresholds(9, "WIDE_RUNWAY")
    d11, _, _ = get_golden8_prog_thresholds(11, "WIDE_RUNWAY")
    assert (
        d1 == -1.00
        and d5 == -2.00
        and d9 == -3.50
        and d11 == -5.50
        and s1 == 1.50
        and s2 == 1.00
    ), "TDD 실패: 4단 와이드 단차 불일치"

    # 3) 🚨 Case 72: 1층 ~ 6층 개별 완충층 적재 및 8회차 유입 시 최상단(6층+7층 ➔ 통합 7층 GRID_L7) 병합 검증
    grid_q: List[StratumBucket] = []
    for step in range(8):
        p_step = round(100.0 - float(step), 2)
        tag_step = "REENTRY_1FL" if step == 0 else "DIP_1FL"
        grid_q = vrev_add_quota_lot_and_merge_2tier(
            grid_q, 10, p_step, round(10.0 * p_step, 4), tag_step
        )
        assert len(grid_q) == min(MAX_GRID_TIERS_7, step + 1), (
            f"TDD 실패(Case 72 그리드 층수): step={step}, len={len(grid_q)}"
        )

    assert (
        len(grid_q) == 7
        and has_active_l1_bucket(grid_q)
        and grid_q[0].book_price == 93.0
        and grid_q[-1].lot_type == "GRID_L7"
        and grid_q[-1].lot_count == 2
        and abs(grid_q[-1].book_price - 99.50) < 1e-4
    ), f"TDD 실패(Case 72): 8회차 시 최상단 통합 7층 병합 불일치 {grid_q[-1]}"

    # 4) 🚨 Case 71, Case 72 & Case 80: 4중 다중 익절 판정(골든포켓 +1.5% / 1층 +1.5% / 2~7층 개별 +1.0% / 2~7층 이동평균 +1.0%) 검증
    test_grid = [
        StratumBucket(10, 80.0, 800.0, 800.0, 1, "DIP_1FL"),
        StratumBucket(10, 81.0, 810.0, 810.0, 1, "GRID_L2"),
        StratumBucket(10, 85.0, 850.0, 850.0, 1, "GRID_L3"),
        StratumBucket(10, 90.0, 900.0, 900.0, 1, "GRID_L4"),
    ]
    res_part = evaluate_multi_grid_sell_targets(test_grid, live_price=81.90)
    assert (
        res_part["should_sell"]
        and res_part["sold_indices"] == [0, 1]
        and res_part["sell_qty"] == 20
        and res_part["hit_l1"]
        and res_part["hit_indiv_grid"]
    ), f"TDD 실패(Case 71/72 부분 다중익절): {res_part}"

    # Case 80: 독립 골든포켓 단독 익절(+1.50%) 및 그리드+골든포켓 동시 익절 검증
    mock_gp = GoldenAllInPocket(
        qty=50,
        book_price=70.00,
        book_invested_usd=3500.0,
        actual_cost_usd=3500.0,
        entry_ts=1000.0,
        order_date="2026-03-10",
    )
    res_gp_only = evaluate_multi_grid_sell_targets(
        test_grid, live_price=71.05, golden_pocket=mock_gp
    )
    assert (
        res_gp_only["should_sell"] is True
        and res_gp_only["hit_golden_pocket"] is True
        and res_gp_only["sell_pocket_qty"] == 50
        and res_gp_only["grid_sell_qty"] == 0
        and res_gp_only["sell_qty"] == 50
        and res_gp_only["reason_tag"] == "SELL_GOLDEN_POCKET"
    ), f"TDD 실패(Case 80 골든포켓 단독 익절): {res_gp_only}"

    rem_uppers = relabel_upper_grid_tiers(test_grid[2:])
    assert len(rem_uppers) == 2 and not has_active_l1_bucket(rem_uppers), (
        "TDD 실패(Case 71/72): 1층 익절 후 1층 공석(상단 그리드만 보유) 상태 판별 오류"
    )

    # 5) 🚨 Case 73: 1층 공석 상태에서 현재가 > 2층 단가($85.00)일 때 HOLD_PREVENT_INVERSION 단가 역전 차단 검증
    sig_inv = evaluate_l2_only_hybrid_reentry_signal(
        live_price=85.50,
        anchor_price=83.41,
        l2_book_price=85.00,
        min_upper_tier_price=85.00,
    )
    assert (
        sig_inv["should_buy"] is False
        and sig_inv["signal_type"] == "HOLD_PREVENT_INVERSION"
        and abs(sig_inv["l2_ceiling_price"] - 85.00) < 1e-4
    ), f"TDD 실패(Case 73 단가 역전 차단): {sig_inv}"

    sig_brk_ok = evaluate_l2_only_hybrid_reentry_signal(
        live_price=84.30,
        anchor_price=83.41,
        l2_book_price=85.00,
        min_upper_tier_price=85.00,
    )
    assert (
        sig_brk_ok["should_buy"] is True
        and sig_brk_ok["signal_type"] == "BREAKOUT_RELOAD"
    ), f"TDD 실패(Case 73 2층 이하 안전 돌파 승인): {sig_brk_ok}"

    sig_pull_ok = evaluate_l2_only_hybrid_reentry_signal(
        live_price=82.50,
        anchor_price=83.41,
        l2_book_price=85.00,
        min_upper_tier_price=85.00,
    )
    assert (
        sig_pull_ok["should_buy"] is True
        and sig_pull_ok["signal_type"] == "PULLBACK_RELOAD"
    ), f"TDD 실패(Case 73 눌림목 재장전 승인): {sig_pull_ok}"

    reloaded_grid = vrev_add_quota_lot_and_merge_2tier(
        rem_uppers, 10, 80.50, 805.0, "REENTRY_1FL"
    )
    assert (
        len(reloaded_grid) == 3
        and has_active_l1_bucket(reloaded_grid)
        and reloaded_grid[0].book_price == 80.50
        and reloaded_grid[1].book_price == 85.00
        and reloaded_grid[2].book_price == 90.00
    ), "TDD 실패(Case 59/72): 1층 공석 재장전 시 상단 그리드 비병합 배치 오류"

    res_grad = evaluate_multi_grid_sell_targets(reloaded_grid, live_price=88.50)
    assert (
        res_grad["should_sell"]
        and res_grad["sold_indices"] == [0, 1, 2]
        and res_grad["sell_qty"] == 30
        and res_grad["hit_wma_grad"]
    ), f"TDD 실패(Case 71/72 2~7층 이동평균 일괄졸업): {res_grad}"

    # 6) Case 60 & Case 72 정적 기억 최저가($80.00) 잠금 및 Case 74 당일 시드보호 패스 바인딩 검증
    mock_st = {
        "buckets": buckets_to_dicts(reloaded_grid),
        "initial_seed_usd": 10000.0,
        "anchor_price": 80.50,
        "cycle_min_buy_price": 80.00,
        "cumulative_realized_net_usd": 25.0,
        "seed_protect_pass_cnt": 120,
        "daily_seed_protect_pass_cnt": 7,
    }
    sum_info = summarize_stratum_portfolio(mock_st, live_price=81.00)
    assert abs(sum_info["active_buy_anchor"] - 80.00) < 1e-4, (
        "TDD 실패(Case 60/72): 정적 기억 최저가 잠금 풀림"
    )
    assert (
        sum_info["held_tiers"] == 3
        and sum_info["upper_tier_count"] == 2
        and abs(sum_info["upper_wma_price"] - 87.50) < 1e-4
        and abs(sum_info["l2_ceiling_price"] - 85.00) < 1e-4
        and sum_info["seed_protect_pass_cnt"] == 7
    ), "TDD 실패(Case 72/73/74): 상단 2~7층 이동평균 또는 당일 시드패스 요약 오류"

    # 7) [Case 76 : 🔓 06_STEP2X_15PCT_C20 3중 안전문 스텝업 저가 해금 검증]
    mock_2022_deadcat = [
        StratumBucket(75, 14.43, 1082.25, 1082.25, 1, "REENTRY_1FL"),
        StratumBucket(189, 47.82, 9037.98, 9037.98, 11, "GRID_L2"),
    ]
    res_deadcat = evaluate_step_up_2x_dip_signal(
        live_price=11.50,
        buckets=mock_2022_deadcat,
        anchor_price=14.43,
        cycle_min_buy_price=8.56,
        drop_buy_pct=-5.50,
        free_cash_usd=4500.0,
        realized_equity_usd=13913.0,
    )
    assert (
        res_deadcat["should_buy"] is False
        and res_deadcat["step_up_eligible"] is False
    ), f"TDD 실패(Case 76 2022 데드캣 오발동): {res_deadcat}"

    mock_2025_nov = [
        StratumBucket(41, 50.10, 2054.10, 2054.10, 1, "REENTRY_1FL"),
        StratumBucket(308, 60.64, 18677.12, 18677.12, 10, "GRID_L2"),
    ]
    res_step_ok = evaluate_step_up_2x_dip_signal(
        live_price=42.44,
        buckets=mock_2025_nov,
        anchor_price=50.10,
        cycle_min_buy_price=12.09,
        drop_buy_pct=-5.50,
        free_cash_usd=5699.55,
        realized_equity_usd=26431.99,
    )
    assert (
        res_step_ok["should_buy"] is True
        and res_step_ok["is_step_up_unlock"] is True
        and res_step_ok["trigger_tag"] == "UNLOCK_STEP2X_15P_C20"
        and abs(res_step_ok["quota_ref_price"] - 42.585) < 1e-4
        and abs(res_step_ok["next_cycle_min_price"] - 42.44) < 1e-4
    ), f"TDD 실패(Case 76 2025-11-05 스텝업 해금 미작동): {res_step_ok}"

    # 8) 단가 비교 층간 스마트 중간 편입 & 매도 층 원가 매칭 정산 검증
    mid_inserted = vrev_add_quota_lot_and_merge_2tier(
        reloaded_grid, 10, 84.50, 845.0, "MANUAL_SYNC_L1"
    )
    assert (
        len(mid_inserted) == 4
        and mid_inserted[0].book_price == 80.50
        and mid_inserted[1].book_price == 84.50
        and mid_inserted[1].lot_type == "GRID_L2"
        and mid_inserted[2].book_price == 85.00
        and mid_inserted[2].lot_type == "GRID_L3"
    ), f"TDD 실패(단가 비교 층간 편입): {mid_inserted}"

    match_res = match_and_remove_sold_buckets_7tier(
        mid_inserted, delta_remove_qty=10, sell_exec_price=82.50
    )
    assert (
        match_res["sold_qty"] == 10
        and abs(match_res["sold_actual_cost_usd"] - 805.0) < 1e-4
        and match_res["sold_l1_completely"] is True
        and len(match_res["rem_buckets"]) == 3
        and not has_active_l1_bucket(match_res["rem_buckets"])
        and match_res["pnl_info"]["net_pnl_usd"] > 0.0
    ), f"TDD 실패(수동 매도 층별 원가 매칭 정산): {match_res}"

    # 9) [Case 77 : 💉 05_RESV_6P_GUARD30 검증]
    g30_block = evaluate_guard30_and_reserve_injection(
        free_cash_usd=180.0,
        broker_bp_usd=180.0,
        exec_price=29.0,
        portion_budget=1440.0,
        l1_actual_cost_usd=1426.0,
        is_dip_promotion=True,
        used_reserve_portions_cnt=0,
    )
    assert (
        g30_block["action"] == "BLOCK_AND_ALERT_DEPOSIT"
        and g30_block["should_proceed"] is False
        and g30_block["is_dust_blocked"] is True
        and abs(g30_block["min_req_cash"] - 432.0) < 1e-4
        and abs(g30_block["recommended_deposit_usd"] - 1440.0) < 1e-4
    ), f"TDD 실패(Case 77 미입금 시 자투리 차단 오류): {g30_block}"

    g30_inj = evaluate_guard30_and_reserve_injection(
        free_cash_usd=180.0,
        broker_bp_usd=1680.0,
        exec_price=29.0,
        portion_budget=1440.0,
        l1_actual_cost_usd=1426.0,
        is_dip_promotion=True,
        used_reserve_portions_cnt=0,
    )
    assert (
        g30_inj["action"] == "INJECT_AND_PROCEED"
        and g30_inj["should_proceed"] is True
        and g30_inj["inject_portions"] == 1
        and abs(g30_inj["inject_usd"] - 1440.0) < 1e-4
        and g30_inj["rem_portions_after"] == 5
    ), f"TDD 실패(Case 77 입금 감지 자동 수혈 오류): {g30_inj}"

    repay_res = compute_reserve_repayment_on_zero(
        initial_seed_usd=10000.0,
        cumulative_realized_net_usd=11418.55,
        injected_reserve_usd=13242.27,
        used_reserve_portions_cnt=6,
    )
    assert (
        repay_res["did_repay"] is True
        and abs(repay_res["repaid_usd"] - 13242.27) < 1e-4
        and repay_res["rem_injected_reserve_usd"] == 0.0
        and repay_res["rem_used_reserve_portions_cnt"] == 0
        and repay_res["avail_reserve_portions"] == 6
        and abs(repay_res["free_cash_after_repay_usd"] - 21418.55) < 1e-4
    ), f"TDD 실패(Case 77 0주 졸업 예비시드 상환 오류): {repay_res}"

    # 10) [Case 78 : 지정가 부분 체결 후 잔량(TOPUP_1FL) 체결 시 무승격 단일 1층 합산 검증]
    partial_q = vrev_add_quota_lot_and_merge_2tier(
        [], 2, 90.71, round(2.0 * 90.71, 4), "REENTRY_1FL"
    )
    mock_part_st = {
        "buckets": buckets_to_dicts(partial_q),
        "initial_seed_usd": 19000.0,
        "anchor_price": 90.71,
        "cycle_min_buy_price": 90.71,
        "l1_target_quota_qty": 17,
    }
    part_sum = summarize_stratum_portfolio(mock_part_st, live_price=90.75)
    assert (
        part_sum["l1_cur_qty"] == 2
        and part_sum["l1_target_quota_qty"] == 17
        and part_sum["l1_rem_quota_qty"] == 15
    ), f"TDD 실패(Case 78 부분체결 잔량 요약 불일치): {part_sum}"

    completed_q = vrev_add_quota_lot_and_merge_2tier(
        partial_q, 15, 90.71, round(15.0 * 90.71, 4), "TOPUP_1FL"
    )
    assert (
        len(completed_q) == 1
        and completed_q[0].qty == 17
        and completed_q[0].lot_count == 1
        and abs(completed_q[0].book_price - 90.71) < 1e-4
        and abs(completed_q[0].actual_cost_usd - 1542.07) < 1e-4
    ), f"TDD 실패(Case 78 TOPUP_1FL 무승격 1층 합산 불일치): {completed_q}"

    # 11) NEW [Case 80 : 황금시간대(07:00 ~ 07:50 EST & RSI <= 19.0) 전액매수 판정 검증]
    g_off = evaluate_golden_allin_signal(
        hm=715,
        rsi_14=17.5,
        live_price=40.0,
        golden_allin_mode="NONE",
        today_str="2026-03-10",
    )
    assert g_off["should_buy"] is False and g_off["reason"] == "MODE_OFF", (
        f"TDD 실패(Case 80 OFF 모드 차단 오류): {g_off}"
    )

    g_pocket_ok = evaluate_golden_allin_signal(
        hm=725,
        rsi_14=18.4,
        live_price=40.0,
        golden_allin_mode="POCKET_ALLIN",
        today_str="2026-03-10",
        last_golden_allin_date="2026-03-09",
    )
    assert (
        g_pocket_ok["should_buy"] is True
        and g_pocket_ok["lot_type"] == "GOLDEN_POCKET"
    ), f"TDD 실패(Case 80 POCKET_ALLIN 승인 오류): {g_pocket_ok}"

    g_grid_ok = evaluate_golden_allin_signal(
        hm=745,
        rsi_14=19.0,
        live_price=40.0,
        golden_allin_mode="GRID_L1_ALLIN",
        today_str="2026-03-10",
        last_golden_allin_date="",
    )
    assert (
        g_grid_ok["should_buy"] is True
        and g_grid_ok["lot_type"] == "GOLDEN_L1"
    ), f"TDD 실패(Case 80 GRID_L1_ALLIN 승인 오류): {g_grid_ok}"

    allin_q, allin_spent = resolve_allin_affordable_buy_qty(
        price_t=40.0, free_cash_usd=8000.0
    )
    assert allin_q == 199 and abs(allin_spent - 7960.0) < 1e-4, (
        f"TDD 실패(Case 80 전액매수 주수 산출 오류): q={allin_q}, spent={allin_spent}"
    )

    logger.info(
        "✅ [QuantEngine TDD 사전 무결성 검증 통과] 챔피언 🌟 POCKET_ALLIN / 🔥 GRID_L1_ALLIN × 💉 05_RESV_6P_GUARD30 × 🔓 06_STEP2X_15PCT_C20 (기본값 OFF · Case 59~80) 검증 완료"
    )
    return True
