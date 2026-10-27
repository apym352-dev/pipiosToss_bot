# -*- coding: utf-8 -*-
"""
# MODIFIED: sniper_exit_plugin.py
순수 롱(SOXL) 전용 '매수 체결 후 최초 60초 강제 타임쉴드(POST_BUY_TO_SELL_SHIELD_SEC = 60.0) &
매수 후 60초 경과 시점부터 프리마켓·정규장·애프터마켓(16:00 ~ 19:59 EST)·데이마켓(20:00 ~ 03:59 EST) 24시간 전 세션에서
보유 중 60초 블라인드 대기 락 없이 매 1.5초 실시간 4중 다중 익절 타점 스나이퍼 매도 모니터(Case 70, Case 71, Case 72, Case 79, Case 80) ·
1.5초 실시간 감시 중 4중 다중 익절 조건(① 독립 골든포켓 +1.50% 이상 / ② 1층 +1.50% 이상 / ③ 2~6층 개별 완충층 및 통합 7층 +1.00% 이상 /
④ 2~7층 통합 이동평균 +1.00% 이상) 도래 즉시 실시간 현재가 재확인 후 그 현재가 지정가(LIMIT) 매도 발주(장중 및 오버나이트 윗꼬리 익절 기회 상실 원천 차단!) ·
데이마켓/애프터마켓 브로커 시세 미제공 또는 특정 종목 집중 거래 제한(ATS 제한 · 422 order-hours-closed · stock-restricted 등) 발생 시
텔레그램 알림 메시지 폭탄 없이 100% 조용히 묵음(Silent) 스킵 및 60초 인메모리 쿨다운 방어(Case 79) ·
매수 1호가(Bid 1) 참조 및 하향 추격 정정 100% 영구 소각(Case 65) ·
리앵커링 원가 차감 영구 폐기 및 순수 실물 원가(book_price == actual_avg_price) 100% 보존(Case 69, Case 71, Case 72, Case 80) ·
독립 골든포켓(golden_pocket) 단독 익절 시 기존 1~7층 그리드의 단가·기억저가·목표정량 100% 비오염 보존 및 원리금 복리 환원(Case 80) ·
1층 익절 후 상단 2~7층 잔존 시 1층 공석(GRID_L2 ~ GRID_L7) 보존 · l1_target_quota_qty = 0 자동 클리어(Case 78) 및 싸이클 최저가(cycle_min_buy_price) 잠금 유지(Case 59, Case 60, Case 71, Case 72, Case 73) ·
익절 매도로 가용현금 회복 시 시드고갈 입금 대기 및 단 1회 알림 래치(waiting_reserve_deposit_alert_sent) 자동 해제 &
0주 전량 졸업 시 온디맨드 예비시드 원금 자동 상환 및 6/6회분 한도 원상 복구(compute_reserve_repayment_on_zero · Case 77) ·
매도 체결(부분 익절 · 골든포켓 익절 및 0주 전량 졸업) 즉시 기정산 주문 ID(last_settled_order_ids) 등록 및
60초 매도타임쉴드(last_sell_fill_ts / last_cycle_end_ts) & 1층 공석 재장전 타임쉴드 클리어(last_reentry_eval_ts = 0.0) &
15초 잔고 인덱싱 그레이스 쉴드(last_auto_fill_ts) 동시 각인' 코어 플러그인 (Step 07 / 10)
- 제1헌법 ~ 제6헌법 및 Case 01 ~ 80 완벽 준수
"""

from __future__ import annotations

import asyncio
import logging
import math
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from quant_engine import (
    GOLDEN_POCKET_RISE_PCT,
    GoldenAllInPocket,
    MAX_GRID_TIERS_7,
    MAX_GRID_TIERS_12,
    MAX_RESERVE_PORTIONS,
    REANCHOR_NET_BUFFER_MULT,
    StratumBucket,
    buckets_from_dicts,
    buckets_to_dicts,
    calc_sell_realized_pnl,
    compute_reserve_repayment_on_zero,
    compute_upper_2_to_7_moving_avg,
    compute_upper_2_to_12_moving_avg,
    evaluate_multi_grid_sell_targets,
    get_golden8_prog_thresholds,
    has_active_golden_pocket,
    has_active_l1_bucket,
    pocket_from_dict,
    pocket_to_dict,
    relabel_upper_grid_tiers,
    vrev_reanchor_single_tier_quota,
)
from quant_indicators_plugin import (
    is_active_buy_window,
    is_active_sell_window,
    is_active_trading_window,
    is_extended_sell_only_window,
    refresh_metrics_with_live_tick,
)
from toss_api import (
    DEFAULT_INITIAL_SEED_USD,
    EST_TZ,
    TARGET_SYMBOL,
    _NonRetryableApiError,
    generate_client_order_id,
    safe_float,
    safe_int,
)

logger = logging.getLogger("toss_sniper.sniper_exit_plugin")

# Case 65 & Case 70: 매수 직후 최초 60.0초 타임쉴드 · 매도(및 0주 종료) 후 60.0초 타임쉴드 상수
# (SELL_MONITOR_TIME_SHIELD_SEC 는 AST 하위호환을 위해 유지하되 보유 중 블라인드 락은 0.0초로 해제)
POST_BUY_TO_SELL_SHIELD_SEC: float = 60.0
SELL_MONITOR_TIME_SHIELD_SEC: float = 0.0
POST_SELL_TO_BUY_SHIELD_SEC: float = 60.0

# 순수 현재가 지정가 매도 주문 발주 후 미체결 최대 대기 시간(초) — 하향 정정 없이 60초 미체결 시 안전 취소
SELL_ORDER_MAX_WAIT_SEC: float = 60.0

# [Case 79]: 데이마켓/애프터마켓 종목 집중 거래 제한 또는 세션 공백(422 order-hours-closed / stock-restricted 등) 시
# 알림 메시지 폭탄 없이 조용히 대기하는 인메모리 묵음 쿨다운 시간(초)
EXTENDED_SELL_RESTRICTION_COOLDOWN_SEC: float = 60.0


# ---------------------------------------------------------------------------
# 내부 헬퍼 : 실시간 SOXL 현재가 조회 · 장외 거래제한 묵음 쿨다운 · 매수/매도 후 60초 타임쉴드 판별
# ---------------------------------------------------------------------------
def mark_extended_sell_restriction_cooldown(
    context: Any,
    symbol: str = TARGET_SYMBOL,
    cooldown_sec: float = EXTENDED_SELL_RESTRICTION_COOLDOWN_SEC,
    reason: str = "EXTENDED_RESTRICTED",
) -> None:
    """
    # [Case 79 : 데이마켓·애프터마켓 거래 제한/세션 공백 시 100% 묵음(Silent) 인메모리 쿨다운 각인]:
    데이마켓 등에서 브로커가 특정 종목 거래를 제한하거나 세션 전환 공백으로 주문을 거부했을 때,
    텔레그램 알림을 발송하지 않고 조용히 cooldown_sec(기본 60초) 동안 재발주 시도를 보류한다.
    """
    sym = str(symbol or TARGET_SYMBOL).upper().strip()
    c_sec = max(0.0, safe_float(cooldown_sec, 60.0))
    until_mono = (time.monotonic() + c_sec) if c_sec > 0.0 else 0.0
    snap_map = getattr(context, "exit_snapshot_cache", None)
    if isinstance(snap_map, dict):
        entry = snap_map.get(sym) if isinstance(snap_map.get(sym), dict) else {}
        entry["ext_sell_restrict_until_mono"] = until_mono
        entry["ext_sell_restrict_reason"] = str(reason or "EXTENDED_RESTRICTED")
        snap_map[sym] = entry


def is_within_extended_sell_restriction_cooldown(
    context: Any,
    symbol: str = TARGET_SYMBOL,
) -> Tuple[bool, float]:
    """
    # [Case 79 : 데이마켓·애프터마켓 거래 제한 묵음 쿨다운 작동 여부 판별]:
    인메모리 묵음 쿨다운이 작동 중이면 (True, 잔여 초)를 반환한다.
    """
    sym = str(symbol or TARGET_SYMBOL).upper().strip()
    snap_map = getattr(context, "exit_snapshot_cache", None)
    if isinstance(snap_map, dict):
        entry = snap_map.get(sym)
        if isinstance(entry, dict):
            until_m = safe_float(entry.get("ext_sell_restrict_until_mono"), 0.0)
            rem = until_m - time.monotonic()
            if rem > 0.0:
                return True, round(rem, 1)
    return False, 0.0


def _get_live_soxl_price(
    context: Any,
    prices: Dict[str, float],
    holdings: Dict[str, Dict[str, Any]],
    now_est: datetime,
    allow_stale_fallback: bool = True,
) -> float:
    """
    # [Case 79]:
    - 프리장/정규장(allow_stale_fallback=True)에서는 prices -> 캔들 캐시 -> 보유 잔고 last_price 순으로 폴백한다.
    - 데이마켓/애프터마켓(allow_stale_fallback=False)에서는 브로커가 시세를 제공하지 않는 날
      정적 종가(holdings.last_price)나 과거 캔들 종가로 오발주하는 일을 막기 위해
      오직 실시간 시세 API(prices)에서 조회된 가격만 인정한다.
    """
    lp = safe_float((prices or {}).get(TARGET_SYMBOL), 0.0)
    if lp > 0.0:
        return lp
    if not allow_stale_fallback:
        return 0.0

    raw_cache = getattr(context, "candle_metrics_cache", {})
    base_met = (
        raw_cache.get(TARGET_SYMBOL) if isinstance(raw_cache, dict) else None
    )
    if isinstance(base_met, dict):
        met = refresh_metrics_with_live_tick(base_met, 0.0, now_est=now_est)
        lp = safe_float(met.get("live_price"), 0.0)
        if lp > 0.0:
            return lp
    h_info = (holdings or {}).get(TARGET_SYMBOL, {})
    return safe_float(h_info.get("last_price"), 0.0)


async def _fetch_fresh_current_soxl_price(
    context: Any,
    fallback_price: float = 0.0,
) -> float:
    """
    🚨 Case 65, Case 70 & Case 79:
    1.5초 실시간 매도 모니터에서 익절 타점 도달이 감지된 직후(또는 가격 폴백 필요 시)
    토스 Open API(/api/v1/prices)를 직접 호출하여 가장 최신의 실시간 현재가를 확인한다.
    (데이마켓 시세 미제공 시에도 예외/알림 없이 조용히 fallback_price 를 반환한다.)
    """
    try:
        fresh_map = await context.api.get_current_prices_batch((TARGET_SYMBOL,))
        fresh_p = safe_float((fresh_map or {}).get(TARGET_SYMBOL), 0.0)
        if fresh_p > 0.0:
            if isinstance(getattr(context, "latest_prices", None), dict):
                context.latest_prices[TARGET_SYMBOL] = fresh_p
            if isinstance(getattr(context, "candle_metrics_cache", None), dict):
                base_met = context.candle_metrics_cache.get(TARGET_SYMBOL)
                if isinstance(base_met, dict):
                    context.candle_metrics_cache[TARGET_SYMBOL] = (
                        refresh_metrics_with_live_tick(base_met, fresh_p)
                    )
            return fresh_p
    except Exception as exc:
        logger.debug("실시간 현재가 재조회 폴백 사용(묵음): %s", exc)
    return safe_float(fallback_price, 0.0)


def _resolve_safe_l2_book_price(
    bucket: StratumBucket,
    st: Optional[Dict[str, Any]] = None,
) -> float:
    """
    🚨 [Case 69, Case 71 & Case 72 진성 손익분기점(순수 매수 원가) 하한선 가드]:
    최종 확정 챔피언에서는 인위적 리앵커링 차감을 수행하지 않으므로,
    모든 그리드 지층의 기준 단가는 언제나 순수 실물 매수 평단가(actual_avg_price) 이상으로 강제된다.
    """
    if bucket.qty <= 0:
        return max(0.01, bucket.book_price)
    return round(max(0.01, bucket.actual_avg_price, bucket.book_price), 4)


def is_within_post_buy_time_shield(
    context: Any,
    st: Optional[Dict[str, Any]] = None,
    symbol: str = TARGET_SYMBOL,
) -> Tuple[bool, float]:
    """
    🚨 Case 65 [매수 체결 직후 최초 60.0초 강제 타임쉴드]:
    매수가 체결된 시점(last_buy_fill_mono 단조 시계 및 원장 last_buy_fill_ts / entry_ts)으로부터
    60.0초가 경과하기 전에는 True 와 남은 초(remain_sec)를 반환하여 일체의 매도(및 중복 매수) 시도를 차단한다.
    """
    sym = str(symbol or TARGET_SYMBOL).upper().strip()
    now_mono = time.monotonic()

    guard_map = getattr(context, "indexing_grace_cache", None)
    if isinstance(guard_map, dict):
        info = guard_map.get(sym)
        if isinstance(info, dict):
            last_buy_mono = safe_float(info.get("last_buy_fill_mono"), 0.0)
            if (
                last_buy_mono <= 0.0
                and str(info.get("lot_type") or "") != "SELL_FILL"
            ):
                last_buy_mono = safe_float(info.get("last_auto_fill_ts"), 0.0)
            if last_buy_mono > 0.0:
                elapsed_mono = now_mono - last_buy_mono
                if 0.0 <= elapsed_mono < POST_BUY_TO_SELL_SHIELD_SEC:
                    return True, round(
                        POST_BUY_TO_SELL_SHIELD_SEC - elapsed_mono, 1
                    )

    state_obj = (
        st
        if isinstance(st, dict)
        else (
            context.ledger.get_state(sym)
            if hasattr(context, "ledger")
            else {}
        )
    )
    last_buy_epoch = max(
        safe_float(state_obj.get("last_buy_fill_ts"), 0.0),
        safe_float(state_obj.get("entry_ts"), 0.0),
    )
    if last_buy_epoch > 0.0:
        elapsed_epoch = time.time() - last_buy_epoch
        if 0.0 <= elapsed_epoch < POST_BUY_TO_SELL_SHIELD_SEC:
            return True, round(POST_BUY_TO_SELL_SHIELD_SEC - elapsed_epoch, 1)

    return False, 0.0


def mark_sell_monitor_60s_cycle_shield(
    context: Any,
    symbol: str = TARGET_SYMBOL,
    eval_price: float = 0.0,
    clear_shield: bool = False,
) -> float:
    """
    # [Case 70 & Case 75 : 보유 중 60초 블라인드 매도 대기 락 영구 해제 및 AST 심볼 호환 유지]:
    보유 중 목표가 미달 시 60초간 눈을 감아 장중 윗꼬리(Upper-Wick) 익절 기회를 놓치던
    블라인드 쿨다운을 전면 해제하여, 항상 0.0(쿨다운 없음)으로 상태를 정리하고 반환한다.
    """
    sym = str(symbol or TARGET_SYMBOL).upper().strip()

    snap_map = getattr(context, "exit_snapshot_cache", None)
    if isinstance(snap_map, dict):
        entry = snap_map.get(sym) if isinstance(snap_map.get(sym), dict) else {}
        entry["last_sell_gate_eval_mono"] = 0.0
        entry["last_sell_gate_eval_ts"] = 0.0
        if eval_price > 0.0:
            entry["last_sell_gate_eval_price"] = round(
                safe_float(eval_price, 0.0), 4
            )
        snap_map[sym] = entry

    guard_map = getattr(context, "indexing_grace_cache", None)
    if isinstance(guard_map, dict):
        g_entry = (
            guard_map.get(sym) if isinstance(guard_map.get(sym), dict) else {}
        )
        g_entry["last_sell_gate_eval_mono"] = 0.0
        g_entry["last_sell_gate_eval_ts"] = 0.0
        guard_map[sym] = g_entry

    return 0.0


def is_within_sell_monitor_time_shield(
    context: Any,
    st: Optional[Dict[str, Any]] = None,
    symbol: str = TARGET_SYMBOL,
) -> Tuple[bool, float]:
    """
    # [Case 70 : 매수 직후 최초 60.0초 타임쉴드만 검문 & 이후 보유 중 1.5초 상시 실시간 감시 허용]:
    매수 체결 직후 최초 60.0초 호가 안정화 타임쉴드(is_within_post_buy_time_shield)만 확인하며,
    매수 후 60.0초가 경과한 뒤에는 언제나 (False, 0.0)을 반환하여 매 1.5초 실시간 타점 감시가 즉시 작동하도록 보장한다.
    """
    return is_within_post_buy_time_shield(context, st, symbol)


def mark_post_sell_time_shield(
    context: Any,
    symbol: str = TARGET_SYMBOL,
    fill_price: float = 0.0,
    sold_qty: int = 0,
    is_cycle_end: bool = False,
) -> None:
    """
    🚨 Case 61, Case 65, Case 69, Case 70, Case 73, Case 77 & Case 80:
    매도 체결 및 0주 싸이클 종료 후 60.0초 매수 타임쉴드 & 1층 공석/입금대기 타임쉴드 클리어 & 15.0초 잔고 인덱싱 그레이스 쉴드 동시 각인.
    """
    sym = str(symbol or TARGET_SYMBOL).upper().strip()
    now_mono = time.monotonic()
    now_epoch = time.time()

    snap_map = getattr(context, "exit_snapshot_cache", None)
    if isinstance(snap_map, dict):
        entry = snap_map.get(sym) if isinstance(snap_map.get(sym), dict) else {}
        entry["last_sell_fill_mono"] = now_mono
        entry["last_sell_fill_ts"] = now_epoch
        entry["last_reentry_eval_mono"] = 0.0
        entry["last_reentry_eval_ts"] = 0.0
        entry["last_reserve_check_mono"] = 0.0
        entry["last_reserve_check_ts"] = 0.0
        entry["last_sell_gate_eval_mono"] = 0.0
        entry["last_sell_gate_eval_ts"] = 0.0
        entry["ext_sell_restrict_until_mono"] = 0.0
        if is_cycle_end:
            entry["last_cycle_end_mono"] = now_mono
            entry["last_cycle_end_ts"] = now_epoch
        entry["last_sell_price"] = safe_float(fill_price, 0.0)
        entry["last_sold_qty"] = safe_int(sold_qty, 0)
        snap_map[sym] = entry

    guard_map = getattr(context, "indexing_grace_cache", None)
    if isinstance(guard_map, dict):
        g_entry = (
            guard_map.get(sym) if isinstance(guard_map.get(sym), dict) else {}
        )
        prev_lot_type = str(g_entry.get("lot_type") or "")
        if (
            prev_lot_type != "SELL_FILL"
            and safe_float(g_entry.get("last_auto_fill_ts"), 0.0) > 0.0
        ):
            g_entry["last_buy_fill_mono"] = safe_float(
                g_entry.get("last_auto_fill_ts"), 0.0
            )
        g_entry["last_auto_fill_ts"] = now_mono
        g_entry["last_sell_fill_mono"] = now_mono
        g_entry["last_sell_fill_ts"] = now_epoch
        g_entry["last_reentry_eval_mono"] = 0.0
        g_entry["last_reentry_eval_ts"] = 0.0
        g_entry["last_reserve_check_mono"] = 0.0
        g_entry["last_reserve_check_ts"] = 0.0
        g_entry["last_sell_gate_eval_mono"] = 0.0
        g_entry["last_sell_gate_eval_ts"] = 0.0
        if is_cycle_end:
            g_entry["last_cycle_end_mono"] = now_mono
            g_entry["last_cycle_end_ts"] = now_epoch
        g_entry["lot_type"] = "SELL_FILL"
        g_entry["fill_price"] = safe_float(fill_price, 0.0)
        g_entry["filled_qty"] = safe_int(sold_qty, 0)
        guard_map[sym] = g_entry


def is_within_post_sell_time_shield(
    context: Any,
    st: Optional[Dict[str, Any]] = None,
    symbol: str = TARGET_SYMBOL,
) -> Tuple[bool, float]:
    """
    🚨 Case 65 [매도 체결 및 0주 싸이클 종료 후 60.0초 강제 타임쉴드 판별]:
    직전 매도 체결 시각(last_sell_fill_mono / last_sell_fill_ts) 또는
    0주 싸이클 종료 시각(last_cycle_end_mono / last_cycle_end_ts)으로부터
    60.0초(POST_SELL_TO_BUY_SHIELD_SEC)가 경과하기 전에는 True 와 남은 초(remain_sec)를 반환한다.
    """
    sym = str(symbol or TARGET_SYMBOL).upper().strip()
    now_mono = time.monotonic()

    snap_map = getattr(context, "exit_snapshot_cache", None)
    if isinstance(snap_map, dict):
        entry = snap_map.get(sym)
        if isinstance(entry, dict):
            last_sell_mono = max(
                safe_float(entry.get("last_sell_fill_mono"), 0.0),
                safe_float(entry.get("last_cycle_end_mono"), 0.0),
            )
            if last_sell_mono > 0.0:
                elapsed_mono = now_mono - last_sell_mono
                if 0.0 <= elapsed_mono < POST_SELL_TO_BUY_SHIELD_SEC:
                    return True, round(
                        POST_SELL_TO_BUY_SHIELD_SEC - elapsed_mono, 1
                    )

    guard_map = getattr(context, "indexing_grace_cache", None)
    if isinstance(guard_map, dict):
        g_entry = guard_map.get(sym)
        if isinstance(g_entry, dict):
            g_sell_mono = max(
                safe_float(g_entry.get("last_sell_fill_mono"), 0.0),
                safe_float(g_entry.get("last_cycle_end_mono"), 0.0),
            )
            if g_sell_mono > 0.0:
                elapsed_g = now_mono - g_sell_mono
                if 0.0 <= elapsed_g < POST_SELL_TO_BUY_SHIELD_SEC:
                    return True, round(
                        POST_SELL_TO_BUY_SHIELD_SEC - elapsed_g, 1
                    )

    state_obj = (
        st
        if isinstance(st, dict)
        else (
            context.ledger.get_state(sym)
            if hasattr(context, "ledger")
            else {}
        )
    )
    last_sell_epoch = max(
        safe_float(state_obj.get("last_sell_fill_ts"), 0.0),
        safe_float(state_obj.get("last_cycle_end_ts"), 0.0),
    )
    if last_sell_epoch > 0.0:
        elapsed_epoch = time.time() - last_sell_epoch
        if 0.0 <= elapsed_epoch < POST_SELL_TO_BUY_SHIELD_SEC:
            return True, round(POST_SELL_TO_BUY_SHIELD_SEC - elapsed_epoch, 1)

    return False, 0.0


def update_exit_snapshot_on_hold(
    context: Any,
    symbol: str = TARGET_SYMBOL,
    holdings_qty: int = 0,
    avg_price: float = 0.0,
    live_price: float = 0.0,
) -> Dict[str, Any]:
    """
    Case 19 & Case 70: 보유 중 exit_snapshot_cache["SOXL"] 에 실보유 수량과 평단가,
    현재가를 백업하되 기존의 타임쉴드 시각을 안전하게 보존한다.
    """
    sym = str(symbol or TARGET_SYMBOL).upper().strip()
    snap_map: Dict[str, Dict[str, Any]] = getattr(
        context, "exit_snapshot_cache", {}
    )
    prev = snap_map.get(sym) if isinstance(snap_map.get(sym), dict) else {}

    lp = safe_float(live_price, 0.0)
    ap = safe_float(avg_price, safe_float(prev.get("last_avg_price"), 0.0))
    qty = max(
        0, safe_int(holdings_qty, safe_int(prev.get("last_holdings_qty"), 0))
    )

    updated = dict(prev)
    updated.update(
        {
            "symbol": sym,
            "last_holdings_qty": qty,
            "last_avg_price": ap,
            "last_live_price": (
                lp if lp > 0.0 else safe_float(prev.get("last_live_price"), ap)
            ),
            "last_sweep_price": safe_float(prev.get("last_sweep_price"), 0.0),
            "last_sweep_reason": str(prev.get("last_sweep_reason") or ""),
            "updated_ts": time.time(),
        }
    )
    if isinstance(snap_map, dict):
        snap_map[sym] = updated
    return updated


# ---------------------------------------------------------------------------
# [핵심 1] Case 24, Case 65, Case 70, Case 71, Case 72, Case 79 & Case 80 : 순수 현재가 지정가(LIMIT) 다중 그리드/골든포켓 스나이퍼 매도 발주
# ---------------------------------------------------------------------------
async def execute_bulletproof_sell_sweep(
    context: Any,
    symbol: str = TARGET_SYMBOL,
    holdings_qty: int = 1,
    sweep_price: float = 0.0,
    min_floor_price: float = 0.0,
    reason_tag: str = "SELL_L1_ONLY",
    pending_sell_indices: Optional[Sequence[int]] = None,
    pending_sell_pocket_qty: int = 0,
) -> Dict[str, Any]:
    """
    🚨 Case 24, Case 65, Case 70, Case 71, Case 72, Case 79 & Case 80:
    1.5초 실시간 4중 다중 익절 스나이퍼 매도 발사 시:
    - 오직 목표 익절 지정가(min_floor_price) 이상인 '그 시점의 실시간 현재가 지정가(sweep_price)'로만 LIMIT 매도 주문을 발주한다!
    - 매도 대상 그리드 인덱스 리스트(pending_sell_indices)와 독립 골든포켓 매도 수량(pending_sell_pocket_qty)을
      원장에 기록하여 체결 시 정확히 해당 물량만 정산한다.
    - 🛡️ [Case 79 묵음 방어]: 데이마켓/애프터마켓에서 미국 현지 종목 집중 거래 제한(stock-restricted),
      세션 공백(order-hours-closed), 매도가능수량 0(장외 주문 제한) 등이 발생할 경우
      텔레그램 에러 알림을 절대 발송하지 않고 조용히 60초 인메모리 쿨다운(mark_extended_sell_restriction_cooldown) 처리한다!
    """
    sym = str(symbol or TARGET_SYMBOL).upper().strip()
    target_sell_qty = max(1, safe_int(holdings_qty, 1))
    floor_p = max(
        0.01,
        math.ceil((safe_float(min_floor_price, 0.0) - 1e-9) * 100.0) / 100.0,
    )
    raw_sp = max(
        0.01,
        math.floor((safe_float(sweep_price, 0.0) + 1e-9) * 100.0) / 100.0,
    )
    sp = max(floor_p, raw_sp)
    clean_indices = sorted(
        {
            safe_int(x, -1)
            for x in (pending_sell_indices or [])
            if safe_int(x, -1) >= 0
        }
    )
    clean_pocket_q = max(0, safe_int(pending_sell_pocket_qty, 0))

    now_est = datetime.now(EST_TZ)
    hm_now = now_est.hour * 100 + now_est.minute
    is_ext_session = is_extended_sell_only_window(hm_now, now_est=now_est)

    snap_map: Dict[str, Dict[str, Any]] = getattr(
        context, "exit_snapshot_cache", {}
    )
    if isinstance(snap_map, dict):
        snap_entry = (
            snap_map.get(sym) if isinstance(snap_map.get(sym), dict) else {}
        )
        snap_entry["last_sweep_price"] = sp
        snap_entry["last_sweep_reason"] = str(reason_tag or "SELL_L1_ONLY")
        snap_entry["last_holdings_qty"] = target_sell_qty
        snap_map[sym] = snap_entry

    async with context.in_memory_ordering_lock:
        st = context.ledger.get_state(sym)
        sell_oid = str(st.get("sell_order_id") or "").strip()

        if sell_oid:
            return {
                "status": "SELL_ORDER_ALREADY_ACTIVE",
                "symbol": sym,
                "orderId": sell_oid,
                "sweep_price": safe_float(st.get("target_sell_price"), sp),
                "qty": target_sell_qty,
                "reason": reason_tag,
            }

        latest_open = await context.api.find_latest_open_order_id(
            sym, side="SELL"
        )
        if latest_open:
            try:
                await context.api.cancel_order(latest_open)
            except Exception:
                pass

        sellable_q = 0
        deadline = time.monotonic() + (1.0 if is_ext_session else 2.0)
        while time.monotonic() < deadline:
            sellable_q = await context.api.get_sellable_quantity(sym)
            if sellable_q >= target_sell_qty or sellable_q > 0:
                break
            await asyncio.sleep(0.20)

        # Case 79: 데이마켓/애프터마켓에서 종목 거래 제한 등으로 매도가능수량이 0으로 잠겨 있으면 조용히 60초 묵음 쿨다운
        if is_ext_session and sellable_q <= 0:
            mark_extended_sell_restriction_cooldown(
                context,
                symbol=sym,
                cooldown_sec=EXTENDED_SELL_RESTRICTION_COOLDOWN_SEC,
                reason="EXTENDED_SELLABLE_ZERO",
            )
            logger.debug(
                "🔇 [%s] 장외(데이/애프터) 매도가능수량 0 또는 거래제한 감지 -> 알림 없이 60초 묵음 대기",
                sym,
            )
            return {
                "status": "SILENT_EXTENDED_SELL_RESTRICTED",
                "symbol": sym,
                "reason": "EXTENDED_SELLABLE_ZERO",
            }

        final_qty = (
            min(target_sell_qty, sellable_q)
            if sellable_q > 0
            else target_sell_qty
        )
        eff_pocket_q = min(clean_pocket_q, final_qty)
        cid = generate_client_order_id(prefix="S1M")
        try:
            ord_res = await context.api.create_order(
                symbol=sym,
                side="SELL",
                quantity=final_qty,
                price=sp,
                order_type="LIMIT",
                time_in_force="DAY",
                client_order_id=cid,
                enforce_daymarket_block=False,
            )
            new_oid = str(ord_res.get("orderId") or "").strip()
            await context.ledger.update_state(
                sym,
                sell_order_id=new_oid,
                client_order_id=cid,
                ordered_qty=final_qty,
                target_sell_price=sp,
                pending_sell_mode=str(reason_tag or "SELL_L1_ONLY"),
                pending_sell_indices=clean_indices,
                pending_sell_pocket_qty=eff_pocket_q,
                last_modify_mono=time.monotonic(),
                last_sell_gate_eval_ts=0.0,
            )
            context.wakeup_event.set()
            logger.info(
                "🔥 [%s] 1.5초 실시간 타점 4중 다중익절 스나이퍼 매도 발사(%s · indices=%s · pocket=%d주) 완료: %d주 @ 지정가 $%.2f (목표하한 $%.2f · orderId=%s)",
                sym,
                reason_tag,
                clean_indices,
                eff_pocket_q,
                final_qty,
                sp,
                floor_p,
                new_oid,
            )
            return {
                "status": "NEW_SELL_SWEEP_OK",
                "symbol": sym,
                "orderId": new_oid,
                "sweep_price": sp,
                "qty": final_qty,
                "reason": reason_tag,
                "sold_indices": clean_indices,
                "sell_pocket_qty": eff_pocket_q,
            }
        except _NonRetryableApiError as api_err:
            err_code_l = str(getattr(api_err, "error_code", "") or "").lower()
            is_restrict_or_closed = any(
                k in err_code_l
                for k in (
                    "order-hours-closed",
                    "stock-restricted",
                    "market-closed",
                    "order-type-not-allowed",
                    "market-not-supported",
                    "maintenance",
                    "internal-error",
                )
            )
            if is_ext_session or is_restrict_or_closed:
                mark_extended_sell_restriction_cooldown(
                    context,
                    symbol=sym,
                    cooldown_sec=EXTENDED_SELL_RESTRICTION_COOLDOWN_SEC,
                    reason=err_code_l or "EXTENDED_API_RESTRICTED",
                )
                logger.debug(
                    "🔇 [%s] 장외/종목제한 매도 보류(묵음 쿨다운 60초): %s",
                    sym,
                    api_err,
                )
                return {
                    "status": "SILENT_EXTENDED_SELL_RESTRICTED",
                    "symbol": sym,
                    "error_code": err_code_l,
                }
            logger.error(
                "🚨 [%s] 스나이퍼 매도 발사(%s) 실패: %s",
                sym,
                reason_tag,
                api_err,
            )
            return {
                "status": "SWEEP_FAILED",
                "symbol": sym,
                "error": str(api_err),
            }
        except Exception as exc:
            if is_ext_session:
                mark_extended_sell_restriction_cooldown(
                    context,
                    symbol=sym,
                    cooldown_sec=EXTENDED_SELL_RESTRICTION_COOLDOWN_SEC,
                    reason="EXTENDED_EXCEPTION",
                )
                logger.debug(
                    "🔇 [%s] 장외 매도 통신 예외(묵음 쿨다운 60초): %s",
                    sym,
                    exc,
                )
                return {
                    "status": "SILENT_EXTENDED_SELL_RESTRICTED",
                    "symbol": sym,
                    "error": str(exc),
                }
            logger.error(
                "🚨 [%s] 스나이퍼 매도 발사(%s) 실패: %s",
                sym,
                reason_tag,
                exc,
            )
            return {"status": "SWEEP_FAILED", "symbol": sym, "error": str(exc)}


# ---------------------------------------------------------------------------
# [핵심 2] 실물 매도 FILLED 정산 · 골든포켓/그리드 분리 정산(Case 80) · 세후 순익 복리 산입 · 0주 졸업 시 예비시드 자동 상환
# ---------------------------------------------------------------------------
async def _commit_filled_sell_and_reanchor_ledger(
    context: Any,
    filled_qty: int,
    avg_fill_price: float,
    sell_mode: str,
    settled_order_id: str = "",
) -> Dict[str, Any]:
    """
    🎯 1 ~ 🎯 4 & Case 19, 59, 60, 61, 65, 69, 70, 71, 72, 73, 77, 78, 79, 80:
    7층 골디락스 멀티 그리드 및 독립 골든포켓 스나이퍼 매도 주문이 체결(FILLED)되었을 때:
    1) pending_sell_pocket_qty (독립 골든포켓) 및 pending_sell_indices (1~7층 그리드)에 해당하는
       순수 매수 원금과 실제 매도 체결가(avg_fill_price)로 왕복 수수료(0.14%) 차감 후 세후 실현 순수익금을 산출한다.
    2) 🚨 [Case 80 골든포켓 단독 익절 시 7층 그리드 100% 비오염 보존]:
       - 만약 골든포켓만 단독 익절(sold_pocket_q > 0 and sold_grid_q == 0)되고 기존 그리드(rem_buckets)가 남아 있으면,
         그리드의 anchor_price, cycle_min_buy_price, l1_target_quota_qty 를 변경하지 않고 그대로 보존한다!
       - 골든포켓에서 발생한 세후 실현순익은 golden_realized_net_usd, daily_golden_realized_net_usd 및
         golden_pocket_sell_cnt, daily_golden_pocket_sell_cnt 에도 별도 누적 기록한다.
    3) 🚨 [Case 77 & Case 80 : 0주 전량 졸업(len(rem_buckets) == 0 and not rem_gp.is_active) 시 예비시드 자동 상환]
    """
    st = context.ledger.get_state(TARGET_SYMBOL)
    buckets = buckets_from_dicts(st.get("buckets", []))
    gp = pocket_from_dict(st.get("golden_pocket"))
    fill_p = round(max(0.01, safe_float(avg_fill_price, 0.01)), 4)
    q_filled = max(1, safe_int(filled_qty, 1))
    mode = str(
        sell_mode or st.get("pending_sell_mode") or "SELL_L1_ONLY"
    ).upper()
    eff_oid = str(settled_order_id or st.get("sell_order_id") or "").strip()

    settled_oids: List[str] = list(st.get("last_settled_order_ids") or [])
    if eff_oid and eff_oid not in settled_oids:
        settled_oids.append(eff_oid)
    settled_oids = settled_oids[-50:]

    if not buckets and not gp.is_active:
        now_empty_epoch = time.time()
        mark_post_sell_time_shield(
            context=context,
            symbol=TARGET_SYMBOL,
            fill_price=fill_p,
            sold_qty=q_filled,
            is_cycle_end=True,
        )
        await context.ledger.update_state(
            TARGET_SYMBOL,
            l1_target_quota_qty=0,
            last_sell_fill_ts=now_empty_epoch,
            last_cycle_end_ts=now_empty_epoch,
            last_sell_gate_eval_ts=0.0,
            last_reentry_eval_ts=0.0,
            waiting_reserve_deposit=False,
            waiting_reserve_deposit_alert_sent=False,
            required_reserve_deposit_usd=0.0,
            last_reserve_check_ts=0.0,
            sell_order_id="",
            ordered_qty=0,
            target_sell_price=0.0,
            pending_sell_mode="",
            pending_sell_indices=[],
            pending_sell_pocket_qty=0,
            last_settled_order_ids=settled_oids,
        )
        return {"status": "NO_BUCKETS_TO_SETTLE"}

    rem_fill_to_alloc = q_filled
    raw_pending_pocket_q = max(0, safe_int(st.get("pending_sell_pocket_qty"), 0))
    if raw_pending_pocket_q <= 0 and gp.is_active and mode in (
        "SELL_GOLDEN_POCKET",
        "SELL_POCKET_AND_GRID",
    ):
        raw_pending_pocket_q = gp.qty

    # 1) 독립 골든포켓(golden_pocket) 매도 수량 우선 배분 및 잔여 포켓 산출 (Case 80)
    sold_pocket_q = 0
    sold_pocket_cost = 0.0
    rem_gp = pocket_from_dict(gp.to_dict())

    if rem_gp.is_active and raw_pending_pocket_q > 0 and rem_fill_to_alloc > 0:
        alloc_p_q = min(rem_gp.qty, raw_pending_pocket_q, rem_fill_to_alloc)
        if alloc_p_q >= rem_gp.qty:
            sold_pocket_q = rem_gp.qty
            sold_pocket_cost = round(rem_gp.actual_cost_usd, 4)
            rem_gp = GoldenAllInPocket()
        else:
            sold_pocket_q = alloc_p_q
            unit_gp_p = rem_gp.actual_avg_price
            sold_pocket_cost = round(float(sold_pocket_q) * unit_gp_p, 4)
            keep_gp_q = rem_gp.qty - sold_pocket_q
            keep_gp_cost = round(
                max(
                    0.01 * float(keep_gp_q),
                    rem_gp.actual_cost_usd - sold_pocket_cost,
                ),
                4,
            )
            rem_gp = GoldenAllInPocket(
                qty=keep_gp_q,
                book_price=round(keep_gp_cost / float(keep_gp_q), 4),
                book_invested_usd=keep_gp_cost,
                actual_cost_usd=keep_gp_cost,
                entry_ts=rem_gp.entry_ts,
                order_date=rem_gp.order_date,
            )
        rem_fill_to_alloc -= sold_pocket_q

    # 2) 1층 ~ 7층 그리드(buckets) 매도 수량 배분 및 잔여 지층 산출
    was_active_l1 = has_active_l1_bucket(buckets)
    raw_p_indices = st.get("pending_sell_indices")
    target_indices: List[int] = []
    if isinstance(raw_p_indices, list) and raw_p_indices:
        target_indices = sorted(
            {
                safe_int(idx, -1)
                for idx in raw_p_indices
                if 0 <= safe_int(idx, -1) < len(buckets)
            }
        )

    if not target_indices and rem_fill_to_alloc > 0 and buckets:
        if mode in ("SELL_ALL_GRAD", "SELL_L2_GRAD") or len(buckets) == 1:
            target_indices = list(range(len(buckets)))
        elif mode == "SELL_WMA_UPPER" and len(buckets) >= 2:
            start_i = 1 if was_active_l1 else 0
            target_indices = list(range(start_i, len(buckets)))
        elif mode != "SELL_GOLDEN_POCKET":
            target_indices = [0]

    target_set: Set[int] = set(target_indices)
    sold_l1_flag = bool(
        was_active_l1 and (0 in target_set) and rem_fill_to_alloc > 0
    )

    sold_buckets: List[StratumBucket] = []
    rem_buckets: List[StratumBucket] = []

    for idx, b in enumerate(buckets):
        if idx not in target_set or rem_fill_to_alloc <= 0:
            rem_buckets.append(b)
            continue

        if rem_fill_to_alloc >= b.qty:
            sold_buckets.append(b)
            rem_fill_to_alloc -= b.qty
        else:
            part_q = rem_fill_to_alloc
            rem_fill_to_alloc = 0
            ratio = min(1.0, float(part_q) / float(b.qty))
            sold_cost_part = round(b.actual_cost_usd * ratio, 4)
            rem_q = b.qty - part_q
            rem_cost_part = round(
                max(0.01 * float(rem_q), b.actual_cost_usd - sold_cost_part), 4
            )
            sold_buckets.append(
                StratumBucket(
                    qty=part_q,
                    book_price=b.book_price,
                    book_invested_usd=sold_cost_part,
                    actual_cost_usd=sold_cost_part,
                    lot_count=1,
                    lot_type=b.lot_type,
                )
            )
            rem_buckets.append(
                StratumBucket(
                    qty=rem_q,
                    book_price=b.book_price,
                    book_invested_usd=rem_cost_part,
                    actual_cost_usd=rem_cost_part,
                    lot_count=max(1, b.lot_count),
                    lot_type=b.lot_type,
                )
            )
            if idx == 0 and was_active_l1:
                sold_l1_flag = False

    sold_grid_q = sum(b.qty for b in sold_buckets)
    sold_grid_cost = round(sum(b.actual_cost_usd for b in sold_buckets), 4)

    # 🚨 Case 71 & Case 72: 남은 그리드 지층 라벨 정규화 (1층이 팔렸으면 남은 층들은 GRID_L2 ~ GRID_L7 로 1층 공석 유지!)
    if rem_buckets:
        if was_active_l1 and not sold_l1_flag:
            active_b1 = rem_buckets[0]
            re_uppers = relabel_upper_grid_tiers(
                rem_buckets[1:], max_tiers=MAX_GRID_TIERS_7
            )
            rem_buckets = [active_b1] + re_uppers
        else:
            rem_buckets = relabel_upper_grid_tiers(
                rem_buckets, max_tiers=MAX_GRID_TIERS_7
            )

    # [Case 78 & Case 80]: 1층 익절 또는 그리드 0주 시 l1_target_quota_qty = 0 클리어 (골든포켓 단독 익절 시에는 기존 값 보존)
    rem_has_active_l1 = has_active_l1_bucket(rem_buckets)
    if not rem_buckets or not rem_has_active_l1 or sold_l1_flag:
        next_l1_target_q = 0
    else:
        prev_target_q = max(0, safe_int(st.get("l1_target_quota_qty"), 0))
        next_l1_target_q = max(rem_buckets[0].qty, prev_target_q)

    sold_q = sold_grid_q + sold_pocket_q
    sold_actual_cost = round(sold_grid_cost + sold_pocket_cost, 4)
    pnl_info = calc_sell_realized_pnl(
        sold_qty=sold_q,
        sell_exec_price=fill_p,
        sold_actual_cost_usd=sold_actual_cost,
    )
    gross_pnl = pnl_info["gross_pnl_usd"]
    fee_usd = pnl_info["fee_usd"]
    net_pnl = pnl_info["net_pnl_usd"]
    net_rate = pnl_info["net_rate_pct"]

    pocket_net_pnl = 0.0
    if sold_pocket_q > 0:
        p_pnl_info = calc_sell_realized_pnl(
            sold_qty=sold_pocket_q,
            sell_exec_price=fill_p,
            sold_actual_cost_usd=sold_pocket_cost,
        )
        pocket_net_pnl = p_pnl_info["net_pnl_usd"]

    is_grid_empty = bool(len(rem_buckets) == 0)
    is_graduated_zero = bool(is_grid_empty and not rem_gp.is_active)
    is_pocket_only_sell = bool(sold_pocket_q > 0 and sold_grid_q == 0)

    # 🚨 Case 60 & Case 80: 골든포켓만 단독 익절되고 그리드가 남아 있으면 anchor_price 및 cycle_min_buy_price 를 원형 그대로 보존!
    old_anchor_p = safe_float(st.get("anchor_price"), fill_p)
    old_cycle_min_p = safe_float(st.get("cycle_min_buy_price"), 0.0)
    if is_pocket_only_sell and not is_grid_empty:
        next_anchor_p = old_anchor_p if old_anchor_p > 0.0 else fill_p
        next_cycle_min_p = round(old_cycle_min_p, 4)
    else:
        next_anchor_p = fill_p
        next_cycle_min_p = (
            round(old_cycle_min_p, 4) if not is_grid_empty else 0.0
        )

    tot_sell_ev = safe_int(st.get("total_sell_events"), 0) + 1
    tot_sold_sh = safe_int(st.get("total_sold_shares"), 0) + sold_q
    win_ev = safe_int(st.get("win_sell_events"), 0) + (
        1 if net_pnl > 0.0 else 0
    )
    day_sell_ev = safe_int(st.get("daily_sell_events"), 0) + 1

    indiv_inc = (
        1 if mode in ("SELL_GRID_INDIV", "SELL_L1_AND_GRID") else 0
    )
    wma_inc = (
        1
        if (
            mode == "SELL_WMA_UPPER"
            or (mode == "SELL_ALL_GRAD" and len(buckets) > 1)
        )
        else 0
    )
    gp_sell_inc = 1 if sold_pocket_q > 0 else 0

    indiv_cnt = safe_int(st.get("indiv_grid_sell_cnt"), 0) + indiv_inc
    day_indiv_cnt = (
        safe_int(st.get("daily_indiv_grid_sell_cnt"), 0) + indiv_inc
    )
    wma_cnt = safe_int(st.get("wma_grad_sell_cnt"), 0) + wma_inc
    day_wma_cnt = safe_int(st.get("daily_wma_grad_sell_cnt"), 0) + wma_inc
    gp_sell_cnt = safe_int(st.get("golden_pocket_sell_cnt"), 0) + gp_sell_inc
    day_gp_sell_cnt = (
        safe_int(st.get("daily_golden_pocket_sell_cnt"), 0) + gp_sell_inc
    )
    gp_net_cum = round(
        safe_float(st.get("golden_realized_net_usd"), 0.0) + pocket_net_pnl, 4
    )
    gp_net_day = round(
        safe_float(st.get("daily_golden_realized_net_usd"), 0.0)
        + pocket_net_pnl,
        4,
    )

    cum_gross = round(
        safe_float(st.get("cumulative_realized_gross_usd"), 0.0) + gross_pnl, 4
    )
    cum_fee = round(
        safe_float(st.get("cumulative_realized_fee_usd"), 0.0) + fee_usd, 4
    )
    cum_net = round(
        safe_float(st.get("cumulative_realized_net_usd"), 0.0) + net_pnl, 4
    )
    day_net = round(
        safe_float(st.get("daily_realized_net_usd"), 0.0) + net_pnl, 4
    )

    # [Case 77 : 0주 전량 졸업 시 온디맨드 예비시드 원금 자동 상환 및 6/6회분 한도 원상 복구]:
    init_seed = max(
        100.0, safe_float(st.get("initial_seed_usd"), DEFAULT_INITIAL_SEED_USD)
    )
    cur_inj_res_usd = max(
        0.0, safe_float(st.get("injected_reserve_usd"), 0.0)
    )
    cur_used_res_cnt = max(
        0, safe_int(st.get("used_reserve_portions_cnt"), 0)
    )
    cum_repaid_usd = max(
        0.0, safe_float(st.get("cumulative_reserve_repaid_usd"), 0.0)
    )
    repaid_this_time = 0.0
    next_inj_res_usd = cur_inj_res_usd
    next_used_res_cnt = cur_used_res_cnt

    if is_graduated_zero and cur_inj_res_usd > 0.0:
        repay_info = compute_reserve_repayment_on_zero(
            initial_seed_usd=init_seed,
            cumulative_realized_net_usd=cum_net,
            injected_reserve_usd=cur_inj_res_usd,
            used_reserve_portions_cnt=cur_used_res_cnt,
            max_reserve_portions=MAX_RESERVE_PORTIONS,
        )
        if bool(repay_info.get("did_repay")):
            repaid_this_time = round(
                safe_float(repay_info.get("repaid_usd"), 0.0), 4
            )
            next_inj_res_usd = round(
                safe_float(repay_info.get("rem_injected_reserve_usd"), 0.0), 4
            )
            next_used_res_cnt = max(
                0,
                safe_int(
                    repay_info.get("rem_used_reserve_portions_cnt"), 0
                ),
            )
            cum_repaid_usd = round(cum_repaid_usd + repaid_this_time, 4)
            logger.info(
                "🎓 [Case 77 0주 졸업 온디맨드 예비시드 자동 상환 완료] 상환액=$%.2f · 잔여수혈잔액=$%.2f · 예비한도 복구=%d/%d회분",
                repaid_this_time,
                next_inj_res_usd,
                MAX_RESERVE_PORTIONS - next_used_res_cnt,
                MAX_RESERVE_PORTIONS,
            )

    now_sell_epoch = time.time()
    mark_post_sell_time_shield(
        context=context,
        symbol=TARGET_SYMBOL,
        fill_price=fill_p,
        sold_qty=sold_q,
        is_cycle_end=is_graduated_zero,
    )

    update_kwargs: Dict[str, Any] = {
        "buckets": buckets_to_dicts(rem_buckets),
        "golden_pocket": rem_gp.to_dict(),
        "anchor_price": next_anchor_p,
        "cycle_min_buy_price": next_cycle_min_p,
        "ratchet_anchor_price": next_anchor_p,
        "cycle_reanchor_credit_usd": 0.0,
        "l1_target_quota_qty": next_l1_target_q,
        "used_reserve_portions_cnt": next_used_res_cnt,
        "injected_reserve_usd": next_inj_res_usd,
        "cumulative_reserve_repaid_usd": cum_repaid_usd,
        # Case 77: 익절 매도로 현금이 회수되었으므로 시드고갈 입금 대기 및 단 1회 알림 래치 즉시 해제
        "waiting_reserve_deposit": False,
        "waiting_reserve_deposit_alert_sent": False,
        "required_reserve_deposit_usd": 0.0,
        "last_reserve_check_ts": 0.0,
        "last_sell_fill_ts": now_sell_epoch,
        "last_sell_gate_eval_ts": 0.0,
        "last_reentry_eval_ts": 0.0,
        "sell_order_id": "",
        "ordered_qty": 0,
        "target_sell_price": 0.0,
        "pending_sell_mode": "",
        "pending_sell_indices": [],
        "pending_sell_pocket_qty": 0,
        "last_settled_order_ids": settled_oids,
        "total_sell_events": tot_sell_ev,
        "total_sold_shares": tot_sold_sh,
        "win_sell_events": win_ev,
        "daily_sell_events": day_sell_ev,
        "indiv_grid_sell_cnt": indiv_cnt,
        "daily_indiv_grid_sell_cnt": day_indiv_cnt,
        "wma_grad_sell_cnt": wma_cnt,
        "daily_wma_grad_sell_cnt": day_wma_cnt,
        "golden_pocket_sell_cnt": gp_sell_cnt,
        "daily_golden_pocket_sell_cnt": day_gp_sell_cnt,
        "golden_realized_net_usd": gp_net_cum,
        "daily_golden_realized_net_usd": gp_net_day,
        "cumulative_realized_gross_usd": cum_gross,
        "cumulative_realized_fee_usd": cum_fee,
        "cumulative_realized_net_usd": cum_net,
        "daily_realized_net_usd": day_net,
    }
    if is_graduated_zero:
        update_kwargs["last_cycle_end_ts"] = now_sell_epoch

    updated_st = await context.ledger.update_state(
        TARGET_SYMBOL, **update_kwargs
    )

    context.wakeup_event.set()
    free_cash_now = safe_float(updated_st.get("free_cash_usd"), 0.0)

    now_est_dt = datetime.now(EST_TZ)
    hm_now = now_est_dt.hour * 100 + now_est_dt.minute
    is_ext_sell = is_extended_sell_only_window(hm_now, now_est=now_est_dt)

    if hasattr(context, "send_slim_alert"):
        sign = "+" if net_pnl >= 0.0 else "-"
        r_sign = "+" if net_rate >= 0.0 else ""
        sess_tag = " · 🌃장외익절" if is_ext_sell else ""
        if is_pocket_only_sell:
            grid_sh = sum(b.qty for b in rem_buckets)
            title_msg = (
                f"🌟 [SOXL 독립 골든포켓 +1.5% 익절 체결{sess_tag}] "
                f"{sold_q}주 @ ${fill_p:.2f} ({r_sign}{net_rate:.2f}%)"
            )
            body_msg = (
                f"세후순익 {sign}${abs(net_pnl):,.2f} 시드 복리산입 및 원리금 금고 환원 완료! · "
                f"기존 7층그리드({len(rem_buckets)}개층·{grid_sh}주 · 기억저가 ${next_cycle_min_p:.2f}) 무결성 유지 · "
                f"가용현금 ${free_cash_now:,.2f}"
            )
        else:
            if is_graduated_zero:
                repay_note = ""
                if repaid_this_time > 0.0:
                    avail_p = max(0, MAX_RESERVE_PORTIONS - next_used_res_cnt)
                    repay_note = (
                        f" · 💉예비시드 원금 ${repaid_this_time:,.2f} 자동상환 완료"
                        f"(예비한도 {avail_p}/{MAX_RESERVE_PORTIONS}회분 복구!)"
                    )
                next_entry_guide = (
                    "🔒장외 매수잠금 · 04:07 EST 프리장 개시 후 첫 1층 진입 대기!"
                    if is_ext_sell
                    else "🛡️60초 타임쉴드 경과 후 현재가 조회 및 첫 1층 진입!"
                )
                note_str = (
                    f"🎓 전 지층 흑자 졸업 완료(0주 싸이클 종료{repay_note} "
                    f"➔ {next_entry_guide})"
                )
            elif is_grid_empty and rem_gp.is_active:
                note_str = (
                    f"🌟 그리드 전량 졸업 완료 · 잔여 골든포켓 {rem_gp.qty}주(@${rem_gp.book_price:.2f}) 익절 감시 지속"
                )
            else:
                wma_info = compute_upper_2_to_7_moving_avg(rem_buckets)
                u_cnt = safe_int(
                    wma_info.get("upper_tier_count"), len(rem_buckets)
                )
                u_qty = safe_int(
                    wma_info.get("upper_qty"), sum(b.qty for b in rem_buckets)
                )
                u_wma_p = safe_float(wma_info.get("upper_wma_price"), 0.0)
                u_wma_t = safe_float(
                    wma_info.get("upper_wma_target_price"), 0.0
                )
                if not rem_has_active_l1:
                    l2_cap_p = safe_float(
                        wma_info.get("min_indiv_upper_price"),
                        rem_buckets[0].book_price,
                    )
                    reload_guide = (
                        f"🔒장외 매수잠금(04:07 EST 이후 2층상한 ${l2_cap_p:.2f} 이하 1층재장전 · 기억저가 ${next_cycle_min_p:.2f} 잠금)"
                        if is_ext_sell
                        else f"🛡️60초 타임쉴드 후 1분 주기 1층재장전(2층상한 ${l2_cap_p:.2f} 이하 · 기억저가 ${next_cycle_min_p:.2f} 잠금)"
                    )
                    note_str = (
                        f"📦 잔여 2~{u_cnt + 1}층({u_cnt}개층·{u_qty}주) 순수이평 ${u_wma_p:.2f}(목표 ${u_wma_t:.2f}) 1.5초 실시간 익절감시 "
                        f"· {reload_guide}"
                    )
                else:
                    note_str = (
                        f"📦 잔여 1층+상단({len(rem_buckets)}개층) 순수이평 ${u_wma_p:.2f}(목표 ${u_wma_t:.2f}) 1.5초 실시간 익절감시 "
                        f"· 10분게이트 대기(기억저가 ${next_cycle_min_p:.2f} 잠금)"
                    )
            title_msg = (
                f"🔴 [SOXL 현재가 지정가 익절 체결 ({mode}{sess_tag})] "
                f"{sold_q}주 @ ${fill_p:.2f} ({r_sign}{net_rate:.2f}%)"
            )
            body_msg = (
                f"세후순익 {sign}${abs(net_pnl):,.2f} 시드 복리산입! · "
                f"{note_str} · 가용현금 ${free_cash_now:,.2f}"
            )
        await context.send_slim_alert(title=title_msg, body=body_msg)

    return {
        "status": "SELL_FILLED_AND_SETTLED",
        "did_sell_or_ratchet": True,
        "sold_qty": sold_q,
        "sold_pocket_qty": sold_pocket_q,
        "fill_price": fill_p,
        "net_pnl_usd": net_pnl,
        "repaid_reserve_usd": repaid_this_time,
        "reanchor_drop_usd": 0.0,
        "remaining_tiers": len(rem_buckets),
        "remaining_pocket_qty": rem_gp.qty,
        "free_cash_usd": free_cash_now,
    }


async def sync_pending_sell_order_plugin(
    context: Any,
    holdings: Dict[str, Dict[str, Any]],
    prices: Dict[str, float],
    now_est: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    🚨 Case 19, Case 24, Case 65, Case 70, Case 71, Case 72, Case 79 & Case 80:
    장부에 대기 중인 미체결 매도 주문(sell_order_id)이 존재할 때:
    1) GET /api/v1/orders/{orderId} 로 FILLED 여부를 조회하여 체결 완료 시
       즉시 _commit_filled_sell_and_reanchor_ledger() 로 복리 정산 및 60초 타임쉴드/15초 그레이스 쉴드 각인을 수행한다.
    2) 데이마켓/애프터마켓에서 브로커가 주문을 REJECTED(거래 제한 등) 처리하고 체결 수량이 0주인 경우,
       알림 메시지 폭탄 없이 조용히 60초 인메모리 묵음 쿨다운을 각인하고 주문 ID를 정리한다(Case 79).
    3) 현재가 지정가로 발주된 매도 주문이 60.0초(SELL_ORDER_MAX_WAIT_SEC) 동안 체결되지 않으면,
       가격을 낮추지 않고 미체결 주문을 안전하게 취소(cancel_order)한 뒤
       1.5초 실시간 타점 감시 상태로 즉시 복귀한다.
    """
    st = context.ledger.get_state(TARGET_SYMBOL)
    sell_oid = str(st.get("sell_order_id") or "").strip()
    if not sell_oid:
        return {"status": "NO_PENDING_SELL", "did_sell_or_ratchet": False}

    ordered_qty = max(1, safe_int(st.get("ordered_qty"), 1))
    target_p = safe_float(st.get("target_sell_price"), 0.0)
    sell_mode = str(st.get("pending_sell_mode") or "SELL_L1_ONLY")

    detail = await context.api.get_order_detail(sell_oid)
    if isinstance(detail, dict):
        ord_status = str(detail.get("status") or "").upper().strip()
        exec_obj = (
            detail.get("execution")
            if isinstance(detail.get("execution"), dict)
            else {}
        )
        filled_q = safe_int(exec_obj.get("filledQuantity"), 0)
        avg_fill_p = safe_float(exec_obj.get("averageFilledPrice"), 0.0)

        # Case 19: 오직 FILLED 체결 데이터의 averageFilledPrice 와 filledQuantity 만 반영!
        if ord_status == "FILLED" or (
            filled_q > 0 and ord_status in ("CANCELED", "REPLACED", "REJECTED")
        ):
            eff_q = filled_q if filled_q > 0 else ordered_qty
            eff_p = avg_fill_p if avg_fill_p > 0.0 else target_p
            return await _commit_filled_sell_and_reanchor_ledger(
                context=context,
                filled_qty=eff_q,
                avg_fill_price=eff_p,
                sell_mode=sell_mode,
                settled_order_id=sell_oid,
            )

        if ord_status in ("CANCELED", "REJECTED") and filled_q == 0:
            if ord_status == "REJECTED":
                mark_extended_sell_restriction_cooldown(
                    context,
                    symbol=TARGET_SYMBOL,
                    cooldown_sec=EXTENDED_SELL_RESTRICTION_COOLDOWN_SEC,
                    reason="SELL_ORDER_REJECTED",
                )
            await context.ledger.update_state(
                TARGET_SYMBOL,
                sell_order_id="",
                ordered_qty=0,
                target_sell_price=0.0,
                pending_sell_mode="",
                pending_sell_indices=[],
                pending_sell_pocket_qty=0,
                last_sell_gate_eval_ts=0.0,
            )
            return {
                "status": f"SELL_ORDER_{ord_status}_CLEARED",
                "did_sell_or_ratchet": False,
            }

    last_mod = safe_float(st.get("last_modify_mono"), 0.0)
    if (
        last_mod > 0.0
        and (time.monotonic() - last_mod) >= SELL_ORDER_MAX_WAIT_SEC
    ):
        try:
            await context.api.cancel_order(sell_oid)
        except Exception:
            pass

        final_detail = await context.api.get_order_detail(sell_oid)
        if isinstance(final_detail, dict):
            f_status = str(final_detail.get("status") or "").upper().strip()
            f_exec = (
                final_detail.get("execution")
                if isinstance(final_detail.get("execution"), dict)
                else {}
            )
            f_qty = safe_int(f_exec.get("filledQuantity"), 0)
            f_avg = safe_float(f_exec.get("averageFilledPrice"), 0.0)
            if f_status == "FILLED" or f_qty > 0:
                return await _commit_filled_sell_and_reanchor_ledger(
                    context=context,
                    filled_qty=(f_qty if f_qty > 0 else ordered_qty),
                    avg_fill_price=(f_avg if f_avg > 0.0 else target_p),
                    sell_mode=sell_mode,
                    settled_order_id=sell_oid,
                )

        await context.ledger.update_state(
            TARGET_SYMBOL,
            sell_order_id="",
            ordered_qty=0,
            target_sell_price=0.0,
            pending_sell_mode="",
            pending_sell_indices=[],
            pending_sell_pocket_qty=0,
            last_sell_gate_eval_ts=0.0,
        )
        logger.info(
            "⏳ [SOXL 지정가 매도 60초 미체결 안전 취소] 지정가 $%.2f 유지 종료 ➔ ⚡1.5초 실시간 타점 감시 복귀",
            target_p,
        )
        return {
            "status": "SELL_ORDER_UNFILLED_CANCELED_SAFE",
            "did_sell_or_ratchet": False,
        }

    return {
        "status": "SELL_ORDER_PENDING",
        "did_sell_or_ratchet": True,
        "orderId": sell_oid,
    }


# ---------------------------------------------------------------------------
# [핵심 3] 24시간 전 세션(프리·정규·애프터·데이마켓) 매수 후 최초 60초 타임쉴드 & 이후 보유 중 매 1.5초 실시간 4중 다중 익절 매도 모니터 (Case 69 ~ 80)
# ---------------------------------------------------------------------------
async def execute_1m_sniper_sell_and_reanchor_plugin(
    context: Any,
    holdings: Dict[str, Dict[str, Any]],
    prices: Dict[str, float],
    now_est: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    # [🎯 2 Step 2 & Case 24, 44, 46 ~ 80]:
    프리마켓(04:07 ~ 09:29 EST) · 정규장(09:30 ~ 16:00 EST) · 애프터마켓(16:00 ~ 19:59 EST) · 데이마켓(20:00 ~ 03:59 EST)
    전 구간(is_active_sell_window)에서 작동하는 '매수 후 최초 60.0초 타임쉴드 + 이후 보유 중 매 1.5초 실시간 타점' 4중 다중 익절 스나이퍼 매도(오팔) 모니터:
    1) 대기 중인 미체결 매도 주문(sell_order_id)이 있으면 먼저 체결 확인을 수행한다.
    2) 🛡️ [Case 79 장외 거래 제한 묵음 쿨다운 검문]
    3) 🛡️ [Case 65 매수 후 최초 60.0초 강제 타임쉴드 검문]
    4) ⚡ [Case 70, Case 71, Case 72, Case 79 & Case 80 : 매수 후 60.0초 경과 시점부터 매 1.5초 실시간 4중 다중 익절 판정]:
       - ① 독립 골든포켓(golden_pocket) 단가 대비 +1.50% 이상 도래
       - ② 활성 1층(buckets[0]) 단가 대비 +1.50% 이상 도래
       - ③ 상단 2층 ~ 6층 개별 완충층 및 통합 7층 본대 단가 대비 +1.00% 이상 도래
       - ④ 상단 2층 ~ 7층 통합 이동평균 단가(wma_2_to_7) 대비 +1.00% 이상 도래
       중 하나라도 충족되면 즉시 최신 현재가를 재확인한 뒤 목표 익절 하한가 이상인 그 실시간 현재가 지정가(LIMIT)로 매도 주문을 발주한다!
    """
    dt_now = now_est.astimezone(EST_TZ) if now_est else datetime.now(EST_TZ)
    hm = dt_now.hour * 100 + dt_now.minute

    st = context.ledger.get_state(TARGET_SYMBOL)

    # 1) 미체결 매도 주문이 있으면 먼저 체결 확인 수행
    if str(st.get("sell_order_id") or "").strip():
        return await sync_pending_sell_order_plugin(
            context=context,
            holdings=holdings,
            prices=prices,
            now_est=dt_now,
        )

    # [Case 79]: 매도 모니터를 애프터마켓 및 데이마켓까지 전 구간 개방 (04:00~04:06 오프닝 안정화 및 주말 휴장만 제외)
    if not is_active_sell_window(hm, now_est=dt_now):
        return {
            "status": "OUTSIDE_TRADING_WINDOW",
            "did_sell_or_ratchet": False,
        }

    if not bool(st.get("is_active", True)):
        return {"status": "BOT_INACTIVE", "did_sell_or_ratchet": False}

    if str(st.get("buy_order_id") or "").strip():
        return {
            "status": "BUY_ORDER_IN_PROGRESS",
            "did_sell_or_ratchet": False,
        }

    buckets = buckets_from_dicts(st.get("buckets", []))
    gp = pocket_from_dict(st.get("golden_pocket"))
    if not buckets and not gp.is_active:
        return {"status": "NO_BUCKETS_HELD", "did_sell_or_ratchet": False}

    # [Case 79]: 장외(데이마켓·애프터마켓) 종목 거래 제한 묵음 쿨다운 확인
    in_ext_cd, rem_ext_cd = is_within_extended_sell_restriction_cooldown(
        context, TARGET_SYMBOL
    )
    if in_ext_cd:
        return {
            "status": "SILENT_HOLD_EXTENDED_RESTRICT_COOLDOWN",
            "did_sell_or_ratchet": False,
            "remain_cooldown_sec": rem_ext_cd,
        }

    # 🛡️ 2) [Case 65 & Case 70] 매수 체결 직후 최초 60.0초 호가 안정화 타임쉴드 강제 검문!
    in_buy_shield, remain_buy_sec = is_within_post_buy_time_shield(
        context, st, TARGET_SYMBOL
    )
    if in_buy_shield:
        return {
            "status": "HOLD_POST_BUY_60S_TIME_SHIELD",
            "did_sell_or_ratchet": False,
            "remain_shield_sec": remain_buy_sec,
        }

    # ⚡ 3) [Case 70, Case 71, Case 72 & Case 79] 실시간 현재가 확인 (데이마켓 시세 미제공 시 100% 묵음 스킵!)
    is_ext_sell_only = is_extended_sell_only_window(hm, now_est=dt_now)
    live_p = _get_live_soxl_price(
        context,
        prices,
        holdings,
        dt_now,
        allow_stale_fallback=(not is_ext_sell_only),
    )
    if live_p <= 0.0 and not is_ext_sell_only:
        live_p = await _fetch_fresh_current_soxl_price(
            context, fallback_price=0.0
        )
    if live_p <= 0.0:
        return {
            "status": (
                "SILENT_EXTENDED_NO_LIVE_PRICE"
                if is_ext_sell_only
                else "NO_LIVE_PRICE"
            ),
            "did_sell_or_ratchet": False,
        }

    h_info = (holdings or {}).get(TARGET_SYMBOL, {})
    ledger_total_qty = sum(b.qty for b in buckets) + (
        gp.qty if gp.is_active else 0
    )
    h_qty = safe_int(h_info.get("qty"), ledger_total_qty)
    default_avg_p = (
        buckets[0].actual_avg_price
        if buckets
        else (gp.actual_avg_price if gp.is_active else live_p)
    )
    avg_p = safe_float(h_info.get("avg_price"), default_avg_p)
    update_exit_snapshot_on_hold(
        context, TARGET_SYMBOL, h_qty, avg_p, live_p
    )

    held_lots = max(1, sum(b.lot_count for b in buckets))
    threshold_mode = str(st.get("threshold_mode") or "WIDE_RUNWAY").upper()
    _, rise_sell_l1_pct, rise_sell_upper_pct = get_golden8_prog_thresholds(
        held_lots=held_lots, threshold_mode=threshold_mode
    )

    # 🎯 4) [Case 70 ~ 72, Case 79 & Case 80] 골든포켓(+1.50%) · 1층(+1.50%) · 2~6층 개별 및 통합 7층(+1.00%) · 2~7층 통합 이동평균(+1.00%) 실시간 판정!
    sell_eval = evaluate_multi_grid_sell_targets(
        buckets=buckets,
        live_price=live_p,
        rise_l1_pct=rise_sell_l1_pct,
        rise_upper_pct=rise_sell_upper_pct,
        golden_pocket=gp,
        rise_pocket_pct=GOLDEN_POCKET_RISE_PCT,
    )

    if bool(sell_eval.get("should_sell")):
        # 익절 조건 도래 즉시 최신 실시간 현재가를 1회 재확인하여 추가 슈팅분까지 반영
        fresh_live_p = await _fetch_fresh_current_soxl_price(
            context,
            fallback_price=(0.0 if is_ext_sell_only else live_p),
        )
        if is_ext_sell_only and fresh_live_p <= 0.0:
            return {
                "status": "SILENT_EXTENDED_NO_FRESH_LIVE_PRICE",
                "did_sell_or_ratchet": False,
            }

        eff_live_p = max(live_p, fresh_live_p)
        fresh_eval = evaluate_multi_grid_sell_targets(
            buckets=buckets,
            live_price=eff_live_p,
            rise_l1_pct=rise_sell_l1_pct,
            rise_upper_pct=rise_sell_upper_pct,
            golden_pocket=gp,
            rise_pocket_pct=GOLDEN_POCKET_RISE_PCT,
        )
        if bool(fresh_eval.get("should_sell")):
            sell_eval = fresh_eval

        sold_indices = list(sell_eval.get("sold_indices") or [])
        sell_pocket_qty = max(0, safe_int(sell_eval.get("sell_pocket_qty"), 0))
        sell_qty = max(1, safe_int(sell_eval.get("sell_qty"), 1))
        min_floor_p = max(
            0.01, safe_float(sell_eval.get("min_floor_price"), eff_live_p)
        )
        reason_tag = str(sell_eval.get("reason_tag") or "SELL_L1_ONLY")
        order_limit_p = max(
            min_floor_p,
            math.floor((eff_live_p + 1e-9) * 100.0) / 100.0,
        )

        sweep_res = await execute_bulletproof_sell_sweep(
            context=context,
            symbol=TARGET_SYMBOL,
            holdings_qty=sell_qty,
            sweep_price=order_limit_p,
            min_floor_price=min_floor_p,
            reason_tag=reason_tag,
            pending_sell_indices=sold_indices,
            pending_sell_pocket_qty=sell_pocket_qty,
        )
        did_order = str(sweep_res.get("status") or "") in (
            "NEW_SELL_SWEEP_OK",
            "SELL_ORDER_ALREADY_ACTIVE",
        )
        return {
            "status": (
                "SNIPER_MULTI_GRID_SELL_ORDERED"
                if did_order
                else str(sweep_res.get("status") or "SILENT_EXTENDED_HOLD")
            ),
            "did_sell_or_ratchet": did_order,
            "sell_mode": reason_tag,
            "sold_indices": sold_indices,
            "sell_pocket_qty": sell_pocket_qty,
            "qty": sell_qty,
            "sweep_price": order_limit_p,
            "result": sweep_res,
        }

    # ⚡ 5) [Case 70 & Case 75] 목표 미달 시 60초 블라인드 락이나 디스크 쓰기 없이 즉시 반환 -> 1.5초 후 재감시!
    ref_b0_p = (
        buckets[0].book_price
        if buckets
        else (gp.book_price if gp.is_active else live_p)
    )
    chg_now_pct = (
        ((live_p - ref_b0_p) / ref_b0_p) * 100.0 if ref_b0_p > 0.0 else 0.0
    )
    return {
        "status": "MONITORING_1_5S_REALTIME_SNIPER_SELL",
        "did_sell_or_ratchet": False,
        "chg_from_first_tier_pct": round(chg_now_pct, 2),
        "target_l1_pct": rise_sell_l1_pct,
    }


# 하위 호환 별칭 (타 모듈에서 호출 시 안전 직결)
manage_mechanical_profit_trap_plugin = execute_1m_sniper_sell_and_reanchor_plugin
reconcile_zero_holdings_exit_plugin = sync_pending_sell_order_plugin
