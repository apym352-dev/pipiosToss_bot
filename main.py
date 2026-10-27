# -*- coding: utf-8 -*-
"""
# MODIFIED: main.py
인피니트 스노우볼 (Infinite Snowball) v3.0 — 순수 롱(🐂 SOXL 단독) 매수 04:07 ~ 16:00 EST 제한 &
익절 매도 24시간 전 세션(프리마켓 + 정규장 + 애프터마켓 + 데이마켓) 확장 오버나이트 7층 골디락스 멀티 그리드 지층관리 스나이퍼
메인 오케스트레이터 · TossApiClient 폴리필(close 포함) · 내장형 사용자 중심 초슬림 텔레그램 롱폴링/관제탑 컨트롤러 통합 코어 모듈 (Step 06 / 06)
- 최종 확정 진화 챔피언 (💉 05_RESV_6P_GUARD30 × 🔓 06_STEP2X_15PCT_C20 / 🔥 03_7G_PURE_10_01 진화형 · Case 70 ~ Case 79) 100% 결속:
  1) 8%(12.5분할) 황금비율 정액 기반 정량제 & 온디맨드 예비시드 수혈금(injected_reserve_usd)을 제외한 순수 코어 총자산(core_equity) 기반 정량 산출 &
     min(1회분 예산 상한 주수, 기준가 고정 정량) 이중 캡핑(Case 67, Case 77) & 자투리 절약금(부분 체결 시 비례 정산 Case 78) · 세후 실현수익금 실시간 시드 풀 복리 산입 (COMP_08PCT 고정)
  2) 04:07 ~ 16:00 EST 매수 시간창(is_active_buy_window) 내 0주 상태 60초 타임쉴드 확인 후 실시간 현재가 조회 및 현재가 지정가(LIMIT) 실물 1층(REENTRY_1FL) 산입
  2-B) 🎯 [Case 78] 활성 1층 지정가 부분 체결(buckets[0].qty < l1_target_quota_qty) 시 04:07 ~ 16:00 EST 구간에서 매수 후 60.0초 타임쉴드 경과 시점부터
       매 1.5초 실시간 모니터에서 현재가 <= 1층 단가(buckets[0].book_price) 재도래 시 미체결 잔량(TOPUP_1FL) 지정가 60초 재대기 및 기존 1층 무승격 원자적 합산!
  3) 상단 2층 ~ 7층(GRID_L2 ~ GRID_L7) 보유 중 1층 공석 시 04:07 ~ 16:00 EST 구간에서 10분 게이트를 기다리지 않고 매 60.0초(1분) 타임쉴드 주기마다
     실시간 현재가를 조회하되 현재가 <= 2층 단가(buckets[0].book_price) 상한 가드(HOLD_PREVENT_INVERSION · Case 73) 하에서
     눌림목(-1.00%) OR 상승돌파(+1.00%) 하이브리드 독립 실물 1층(REENTRY_1FL) 재장전 (상단 지층 비병합 · Case 67 이중 캡핑!)
  4) 활성 1층 보유 중 정적 기억 사이클 최저 매수가(cycle_min_buy_price) 기본 잠금 기반 10분 고정 4단 와이드 활주로 시드보호 매수 게이트
     (WIDE_RUNWAY : 1~4회 -1.0% / 5~8회 -2.0% / 9~10회 -3.5% / 11회+ -5.5% 신저가 도달 시 또는
      STEP2X_15PCT_C20 3중 안전문[2층 이하 & 가용현금 20.0%+ & 저점대비 2.0배+ 반등] 통과 후 활성 1층 대비 -15.0% 도달 시에만
      현재가 지정가 추매 및 2~6층 개별 승격 · 8회차 이상 최상단 6층+7층을 통합 7층 본대[GRID_L7]로 가중평균 합병 · Case 72, Case 76)
  5) 💉 [Case 77 : 05_RESV_6P_GUARD30] 30% 자투리 1주 승격 방지 가드(GUARD30) · 시드고갈 시 단 1회 입금 요청 알림 영구 래치(waiting_reserve_deposit_alert_sent) ·
     토스 실계좌 여유자금(1회분 이상) 입금 자동 감지 기반 최대 +6회분 온디맨드 예비시드 자동 수혈 및 0주 졸업 시 원금 자동 상환!
  6) ⚡ [Case 65, Case 70, Case 71, Case 72 & Case 79] 매수 직후 최초 60.0초 타임쉴드 유지 & 이후 보유 중 프리마켓·정규장·애프터마켓(16:00 ~ 19:59 EST)·데이마켓(20:00 ~ 03:59 EST)
     24시간 전 세션(is_active_sell_window)에서 매 1.5초 실시간 3중 다중 익절 스나이퍼 매도 모니터 가동!
     (오버나이트 중에도 ① 1층 +1.50% 이상 개별 익절 / ② 2~6층 개별 및 통합 7층 +1.00% 이상 개별 익절 /
      ③ 2~7층 통합 이동평균 단가 대비 +1.00% 이상 일괄 졸업 도래 즉시 현재가 지정가 매도 발주 · 데이마켓 시세 미제공 및 종목 거래 제한 시 알림 폭탄 100% 묵음!)
  7) 🚨 [Case 66 미결 매수/매도 선행 정산] 루프 진입 시 reconcile 호출 전에 sync_pending_buy_order_plugin / sync_pending_sell_order_plugin 을
     최우선 실행하여, 거래소 즉시 체결 시에도 텔레그램 체결 알림 · 자투리 절약금/실현익 누적 · 60초 타임쉴드 각인이 100% 실행되도록 보장!
  8) 📡 [Case 11, Case 15, Case 16, Case 62, Case 64, Case 74, Case 76, Case 77, Case 78 & Case 79 문단 하단 2중 중복 인라인 메뉴 전면 제거 · /reset 차단 및 /reset_profit 전용 대체 ·
     04:00 EST 및 17:00 EST 당일 시드보호 패스·스텝업 해금·예비수혈 카운터 0회 리셋(단 1회 입금 알림 래치 보존) 보장]
  9) 🚨 [Case 68, Case 69, Case 71 ~ Case 79 폴더 위치(base_dir) 기반 멀티 봇 자동 식별 격리 & 3중 원장 금고 & 순수 원가 100% 보존]
- 제1헌법 ~ 제6헌법 및 Case 01 ~ 79 전수 락온
"""

from __future__ import annotations

import asyncio
import html
import inspect
import json
import logging
import math
import os
import re
import signal
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd

import defense_plugin
import plugin_updater
import quant_engine
import quant_indicators_plugin
import sniper_exit_plugin
import sniper_plugin
import tg_ui_plugin
import toss_api
from defense_plugin import (
    execute_0400_premarket_stabilization_plugin,
    execute_1600_daily_closing_settlement_plugin,
    execute_daily_1700_gc_and_backup_plugin,
    reconcile_stratum_with_broker_holdings_plugin,
)
from plugin_updater import (
    purge_deprecated_legacy_files,
    verify_all_modules_compile,
)
from quant_engine import (
    MAX_RESERVE_PORTIONS,
    buckets_from_dicts,
    run_quant_engine_tdd,
    summarize_stratum_portfolio,
)
from quant_indicators_plugin import (
    evaluate_buy_gate_bucket_status,
    get_market_session_label,
    is_active_buy_window,
    is_active_sell_window,
    is_active_trading_window,
    is_extended_sell_only_window,
    refresh_metrics_with_live_tick,
)
from sniper_exit_plugin import (
    execute_1m_sniper_sell_and_reanchor_plugin,
    is_within_post_buy_time_shield,
    is_within_post_sell_time_shield,
    is_within_sell_monitor_time_shield,
    sync_pending_sell_order_plugin,
    update_exit_snapshot_on_hold,
)
from sniper_plugin import (
    execute_seed_protected_buy_gate_plugin,
    is_within_reentry_monitor_time_shield,
    is_within_reserve_deposit_check_shield,
    mark_reserve_deposit_check_shield,
    sync_pending_buy_order_plugin,
)
from toss_api import (
    DEFAULT_INITIAL_SEED_USD,
    EST_TZ,
    LOCKED_BUY_INTERVAL_MIN,
    TARGET_SYMBOL,
    TossApiClient,
    get_bot_base_dir,
    get_folder_slug,
    resolve_folder_isolated_ledger_paths,
    safe_float,
    safe_int,
)

# ---------------------------------------------------------------------------
# 로깅 포맷 설정 (EST/KST 병기 지원 및 저소음 고신뢰 로그)
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("toss_sniper.main")

# 메인 루프 주기 상수 (평시 1.5초 실시간 타점 감시 / 미체결 주문 체결 확인 부스터 0.4초)
NORMAL_LOOP_INTERVAL_SEC: float = 1.50
FAST_SHIELD_LOOP_INTERVAL_SEC: float = 0.40
KRW_PER_USD_DEFAULT: float = 1380.0

# Case 68: [💵 기준 시드머니($) 설정] 버튼 클릭 후 일반 숫자 입력을 허용하는 유효 시간(초)
SEED_INPUT_PROMPT_TIMEOUT_SEC: float = 300.0

# URL("https://...") 오매칭을 100% 차단하는 엄격한 텔레그램 봇 토큰 정규식
_TG_TOKEN_STRICT_RE = re.compile(r"\b(\d{8,12}:[A-Za-z0-9_-]{25,60})\b")


# ---------------------------------------------------------------------------
# [핵심 1] Case 13 & Case 62 : 적응형 비동기 플러그인 호출기 및 동적 심볼 리졸버
# ---------------------------------------------------------------------------
async def _call_plugin_adaptive(
    func: Callable[..., Any],
    **kwargs: Any,
) -> Any:
    """
    🚨 Case 13:
    플러그인 함수의 시그니처(인자 목록 및 **kwargs 수용 여부)를 동적으로 검사하여
    허용된 인자만 안전하게 주입하고 동기/비동기 함수를 모두 실행한다.
    """
    sig = inspect.signature(func)
    accepts_var_kw = any(
        p.kind == inspect.Parameter.VAR_KEYWORD
        for p in sig.parameters.values()
    )
    if accepts_var_kw:
        filtered_kwargs = kwargs
    else:
        filtered_kwargs = {
            k: v for k, v in kwargs.items() if k in sig.parameters
        }

    res = func(**filtered_kwargs)
    if inspect.isawaitable(res):
        return await res
    return res


def _resolve_module_attr(
    modules: Iterable[Any],
    candidate_names: Tuple[str, ...],
    predicate: Optional[Callable[[Any], bool]] = None,
) -> Any:
    """
    주어진 모듈 목록에서 후보 심볼명을 순차 탐색하거나 조건(predicate)에 부합하는 객체를 반환한다.
    """
    for mod in modules:
        for name in candidate_names:
            obj = getattr(mod, name, None)
            if obj is not None:
                return obj
    if predicate is not None:
        for mod in modules:
            for attr_name in dir(mod):
                if attr_name.startswith("_"):
                    continue
                obj = getattr(mod, attr_name, None)
                try:
                    if predicate(obj):
                        return obj
                except Exception:
                    pass
    return None


# ---------------------------------------------------------------------------
# [핵심 1-B] TossApiClient 런타임 메서드 호환성 폴리필 어댑터 (close 포함 AttributeError 원천 소각)
# ---------------------------------------------------------------------------
def _empty_soxl_holding_entry() -> Dict[str, Any]:
    return {
        "symbol": TARGET_SYMBOL,
        "qty": 0,
        "quantity": 0,
        "avg_price": 0.0,
        "averagePurchasePrice": 0.0,
        "last_price": 0.0,
        "lastPrice": 0.0,
        "purchase_amount": 0.0,
        "eval_amount": 0.0,
        "profit_loss": 0.0,
        "profit_rate": 0.0,
    }


def _normalize_single_holding_item(
    item: Dict[str, Any], symbol: str = TARGET_SYMBOL
) -> Dict[str, Any]:
    sym = str(item.get("symbol") or symbol or TARGET_SYMBOL).upper().strip()
    qty = max(
        0,
        safe_int(
            item.get("qty")
            if item.get("qty") is not None
            else item.get("quantity"),
            0,
        ),
    )
    avg_p = round(
        max(
            0.0,
            safe_float(
                item.get("avg_price")
                if item.get("avg_price") is not None
                else item.get("averagePurchasePrice"),
                0.0,
            ),
        ),
        4,
    )
    last_p = round(
        max(
            0.0,
            safe_float(
                item.get("last_price")
                if item.get("last_price") is not None
                else item.get("lastPrice"),
                avg_p,
            ),
        ),
        4,
    )

    mv_obj = (
        item.get("marketValue")
        if isinstance(item.get("marketValue"), dict)
        else {}
    )
    pl_obj = (
        item.get("profitLoss")
        if isinstance(item.get("profitLoss"), dict)
        else {}
    )

    pur_amt = safe_float(
        item.get("purchase_amount")
        if item.get("purchase_amount") is not None
        else mv_obj.get("purchaseAmount"),
        round(float(qty) * avg_p, 4),
    )
    eval_amt = safe_float(
        item.get("eval_amount")
        if item.get("eval_amount") is not None
        else mv_obj.get("amount"),
        round(float(qty) * last_p, 4),
    )
    pnl_amt = safe_float(
        item.get("profit_loss")
        if item.get("profit_loss") is not None
        else (
            pl_obj.get("amountAfterCost")
            if pl_obj.get("amountAfterCost") is not None
            else pl_obj.get("amount")
        ),
        round(eval_amt - pur_amt, 4),
    )
    raw_rate = safe_float(
        item.get("profit_rate")
        if item.get("profit_rate") is not None
        else (
            pl_obj.get("rateAfterCost")
            if pl_obj.get("rateAfterCost") is not None
            else pl_obj.get("rate")
        ),
        0.0,
    )
    if pur_amt > 0.0 and abs(raw_rate) < 2.0 and abs(pnl_amt / pur_amt) > 0.005:
        profit_rate = round((pnl_amt / pur_amt) * 100.0, 2)
    else:
        profit_rate = round(raw_rate, 2)

    return {
        "symbol": sym,
        "qty": qty,
        "quantity": qty,
        "avg_price": avg_p,
        "averagePurchasePrice": avg_p,
        "last_price": last_p,
        "lastPrice": last_p,
        "purchase_amount": round(pur_amt, 4),
        "eval_amount": round(eval_amt, 4),
        "profit_loss": round(pnl_amt, 4),
        "profit_rate": profit_rate,
    }


def _normalize_holdings_payload(
    raw_res: Any,
) -> Tuple[Dict[str, Dict[str, Any]], bool]:
    if raw_res is None:
        return {}, False

    if isinstance(raw_res, tuple) and len(raw_res) == 2:
        first, second = raw_res
        if isinstance(first, bool) and isinstance(second, dict):
            norm_map, _ = _normalize_holdings_payload(second)
            return norm_map, first
        if isinstance(first, dict):
            norm_map, _ = _normalize_holdings_payload(first)
            return norm_map, bool(second)

    out_map: Dict[str, Dict[str, Any]] = {
        TARGET_SYMBOL: _empty_soxl_holding_entry()
    }

    if isinstance(raw_res, dict):
        if TARGET_SYMBOL in raw_res and isinstance(
            raw_res[TARGET_SYMBOL], dict
        ):
            out_map[TARGET_SYMBOL] = _normalize_single_holding_item(
                raw_res[TARGET_SYMBOL], TARGET_SYMBOL
            )
            return out_map, True

        if (
            str(raw_res.get("symbol") or "").upper().strip() == TARGET_SYMBOL
            and ("quantity" in raw_res or "qty" in raw_res)
        ):
            out_map[TARGET_SYMBOL] = _normalize_single_holding_item(
                raw_res, TARGET_SYMBOL
            )
            return out_map, True

        res_obj = (
            raw_res.get("result")
            if isinstance(raw_res.get("result"), dict)
            else raw_res
        )
        items = res_obj.get("items") if isinstance(res_obj, dict) else None
        if isinstance(items, list):
            for it in items:
                if isinstance(it, dict):
                    sym = str(it.get("symbol") or "").upper().strip()
                    if sym == TARGET_SYMBOL:
                        out_map[TARGET_SYMBOL] = _normalize_single_holding_item(
                            it, TARGET_SYMBOL
                        )
            return out_map, True

        if len(raw_res) == 0:
            return out_map, True

    if isinstance(raw_res, list):
        for it in raw_res:
            if isinstance(it, dict):
                sym = str(it.get("symbol") or "").upper().strip()
                if sym == TARGET_SYMBOL:
                    out_map[TARGET_SYMBOL] = _normalize_single_holding_item(
                        it, TARGET_SYMBOL
                    )
        return out_map, True

    return out_map, True


async def _invoke_raw_toss_api(
    api: Any,
    method: str,
    path: str,
    params: Optional[Dict[str, Any]] = None,
    json_data: Optional[Dict[str, Any]] = None,
    require_account: bool = False,
) -> Any:
    for req_name in (
        "_request",
        "request",
        "_api_request",
        "_call_api",
        "_fetch_json",
    ):
        req_fn = getattr(api, req_name, None)
        if callable(req_fn):
            sig = inspect.signature(req_fn)
            kw: Dict[str, Any] = {}
            accepts_var_kw = any(
                p.kind == inspect.Parameter.VAR_KEYWORD
                for p in sig.parameters.values()
            )
            for p_name in sig.parameters:
                if p_name in ("method", "http_method"):
                    kw[p_name] = method
                elif p_name in ("path", "endpoint", "url", "uri"):
                    kw[p_name] = path
                elif p_name in ("params", "query", "query_params"):
                    kw[p_name] = params
                elif p_name in ("json_data", "json", "body", "data", "payload"):
                    kw[p_name] = json_data
                elif p_name in (
                    "require_account",
                    "use_account",
                    "account_required",
                    "with_account",
                    "need_account",
                ):
                    kw[p_name] = require_account
                elif p_name in ("rate_group", "group"):
                    kw[p_name] = (
                        "MARKET_DATA_CHART"
                        if "candles" in path
                        else ("ASSET" if "holdings" in path else "MARKET_DATA")
                    )
            if accepts_var_kw:
                if "params" not in kw and params is not None:
                    kw["params"] = params
                if "json_data" not in kw and json_data is not None:
                    kw["json_data"] = json_data
            try:
                res = req_fn(**kw)
                if inspect.isawaitable(res):
                    return await res
                return res
            except TypeError:
                res = req_fn(method, path, params=params)
                if inspect.isawaitable(res):
                    return await res
                return res
    return None


def _extract_candles_list(
    raw_res: Any,
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    if isinstance(raw_res, list):
        return [c for c in raw_res if isinstance(c, dict)], None
    if isinstance(raw_res, dict):
        res_obj = (
            raw_res.get("result")
            if isinstance(raw_res.get("result"), dict)
            else raw_res
        )
        if isinstance(res_obj, dict):
            c_list = res_obj.get("candles")
            next_b = res_obj.get("nextBefore")
            if isinstance(c_list, list):
                return (
                    [c for c in c_list if isinstance(c, dict)],
                    str(next_b) if next_b else None,
                )
    return [], None


def _install_toss_api_compatibility_patches() -> None:
    """
    서버의 TossApiClient 에 get_holdings_map_with_status, get_candles_1m, get_candles_1d, close 등의
    메서드가 없을 경우 자동으로 폴리필을 장착하여 런타임 및 종료 시점의 AttributeError 를 0건으로 차단한다.
    """
    if not hasattr(TossApiClient, "get_holdings_map_with_status"):

        async def _poly_get_holdings_map_with_status(
            self: Any, symbol: str = TARGET_SYMBOL
        ) -> Tuple[Dict[str, Dict[str, Any]], bool]:
            for cand_name in (
                "get_holdings_map",
                "get_holdings",
                "fetch_holdings_map",
                "fetch_holdings",
                "get_account_holdings",
                "get_broker_holdings",
                "get_positions",
            ):
                fn = getattr(self, cand_name, None)
                if callable(fn):
                    try:
                        res = await _call_plugin_adaptive(fn, symbol=symbol)
                        return _normalize_holdings_payload(res)
                    except Exception as exc:
                        logger.warning(
                            "TossApiClient.%s 호출 예외: %s", cand_name, exc
                        )
                        return {}, False

            try:
                raw = await _invoke_raw_toss_api(
                    self,
                    method="GET",
                    path="/api/v1/holdings",
                    params={"symbol": symbol},
                    require_account=True,
                )
                return _normalize_holdings_payload(raw)
            except Exception as exc:
                logger.warning("GET /api/v1/holdings 폴백 호출 예외: %s", exc)
                return {}, False

        setattr(
            TossApiClient,
            "get_holdings_map_with_status",
            _poly_get_holdings_map_with_status,
        )

    if not hasattr(TossApiClient, "get_candles_1m"):

        async def _poly_get_candles_1m(
            self: Any,
            symbol: str = TARGET_SYMBOL,
            total_count: int = 300,
            count: Optional[int] = None,
            **kwargs: Any,
        ) -> List[Dict[str, Any]]:
            req_total = max(1, safe_int(count or total_count, 200))
            for cand_name in (
                "get_candles_paginated",
                "fetch_candles_1m",
                "get_minute_candles",
                "get_1m_candles",
                "get_candles",
                "fetch_candles",
                "get_chart_candles",
            ):
                fn = getattr(self, cand_name, None)
                if callable(fn):
                    try:
                        res = await _call_plugin_adaptive(
                            fn,
                            symbol=symbol,
                            interval="1m",
                            count=min(200, req_total),
                            total_count=req_total,
                            adjusted=True,
                        )
                        c_list, _ = _extract_candles_list(res)
                        if c_list:
                            return c_list
                    except Exception:
                        pass

            collected: List[Dict[str, Any]] = []
            before_cursor: Optional[str] = None
            pages = 2 if req_total > 200 else 1
            for _ in range(pages):
                rem = max(1, min(200, req_total - len(collected)))
                q_params: Dict[str, Any] = {
                    "symbol": symbol,
                    "interval": "1m",
                    "count": rem,
                    "adjusted": "true",
                }
                if before_cursor:
                    q_params["before"] = before_cursor
                raw = await _invoke_raw_toss_api(
                    self,
                    method="GET",
                    path="/api/v1/candles",
                    params=q_params,
                    require_account=False,
                )
                page_candles, next_b = _extract_candles_list(raw)
                if not page_candles:
                    break
                collected.extend(page_candles)
                if not next_b or len(collected) >= req_total:
                    break
                before_cursor = next_b
            return collected

        setattr(TossApiClient, "get_candles_1m", _poly_get_candles_1m)

    if not hasattr(TossApiClient, "get_candles_1d"):

        async def _poly_get_candles_1d(
            self: Any,
            symbol: str = TARGET_SYMBOL,
            count: int = 10,
            **kwargs: Any,
        ) -> List[Dict[str, Any]]:
            req_cnt = max(1, min(200, safe_int(count, 10)))
            for cand_name in (
                "fetch_candles_1d",
                "get_daily_candles",
                "get_1d_candles",
                "get_candles",
                "fetch_candles",
                "get_chart_candles",
            ):
                fn = getattr(self, cand_name, None)
                if callable(fn):
                    try:
                        res = await _call_plugin_adaptive(
                            fn,
                            symbol=symbol,
                            interval="1d",
                            count=req_cnt,
                            total_count=req_cnt,
                            adjusted=True,
                        )
                        c_list, _ = _extract_candles_list(res)
                        if c_list:
                            return c_list
                    except Exception:
                        pass

            raw = await _invoke_raw_toss_api(
                self,
                method="GET",
                path="/api/v1/candles",
                params={
                    "symbol": symbol,
                    "interval": "1d",
                    "count": req_cnt,
                    "adjusted": "true",
                },
                require_account=False,
            )
            c_list, _ = _extract_candles_list(raw)
            return c_list

        setattr(TossApiClient, "get_candles_1d", _poly_get_candles_1d)

    if not hasattr(TossApiClient, "get_open_orders"):

        async def _poly_get_open_orders(
            self: Any, symbol: str = TARGET_SYMBOL
        ) -> List[Dict[str, Any]]:
            for cand_name in (
                "fetch_open_orders",
                "get_orders",
                "list_open_orders",
            ):
                fn = getattr(self, cand_name, None)
                if callable(fn):
                    try:
                        res = await _call_plugin_adaptive(
                            fn, status="OPEN", symbol=symbol
                        )
                        if isinstance(res, list):
                            return res
                        if isinstance(res, dict):
                            r_obj = (
                                res.get("result")
                                if isinstance(res.get("result"), dict)
                                else res
                            )
                            if isinstance(r_obj, dict) and isinstance(
                                r_obj.get("orders"), list
                            ):
                                return r_obj["orders"]
                    except Exception:
                        pass
            raw = await _invoke_raw_toss_api(
                self,
                method="GET",
                path="/api/v1/orders",
                params={"status": "OPEN", "symbol": symbol},
                require_account=True,
            )
            if isinstance(raw, dict):
                r_obj = (
                    raw.get("result")
                    if isinstance(raw.get("result"), dict)
                    else raw
                )
                if isinstance(r_obj, dict) and isinstance(
                    r_obj.get("orders"), list
                ):
                    return r_obj["orders"]
            return []

        setattr(TossApiClient, "get_open_orders", _poly_get_open_orders)

    if not hasattr(TossApiClient, "cancel_all_open_orders"):

        async def _poly_cancel_all_open_orders(
            self: Any, symbol: str = TARGET_SYMBOL
        ) -> int:
            orders = await self.get_open_orders(symbol=symbol)
            cnt = 0
            for o in orders:
                if isinstance(o, dict):
                    oid = str(o.get("orderId") or "").strip()
                    if oid and hasattr(self, "cancel_order"):
                        try:
                            await self.cancel_order(oid)
                            cnt += 1
                        except Exception:
                            pass
            return cnt

        setattr(
            TossApiClient,
            "cancel_all_open_orders",
            _poly_cancel_all_open_orders,
        )

    if not hasattr(TossApiClient, "find_latest_open_order_id"):

        async def _poly_find_latest_open_order_id(
            self: Any, symbol: str = TARGET_SYMBOL, side: Optional[str] = None
        ) -> str:
            orders = await self.get_open_orders(symbol=symbol)
            target_side = str(side or "").upper().strip()
            for o in orders:
                if isinstance(o, dict):
                    o_side = str(o.get("side") or "").upper().strip()
                    if not target_side or o_side == target_side:
                        oid = str(o.get("orderId") or "").strip()
                        if oid:
                            return oid
            return ""

        setattr(
            TossApiClient,
            "find_latest_open_order_id",
            _poly_find_latest_open_order_id,
        )

    if not hasattr(TossApiClient, "get_buying_power_usd"):

        async def _poly_get_buying_power_usd(
            self: Any, safety_buffer_pct: float = 0.2
        ) -> float:
            for cand_name in (
                "get_buying_power",
                "fetch_buying_power_usd",
                "fetch_buying_power",
            ):
                fn = getattr(self, cand_name, None)
                if callable(fn):
                    try:
                        res = await _call_plugin_adaptive(
                            fn,
                            currency="USD",
                            safety_buffer_pct=safety_buffer_pct,
                        )
                        if isinstance(res, (int, float)):
                            return max(0.0, float(res))
                        if isinstance(res, dict):
                            r_obj = (
                                res.get("result")
                                if isinstance(res.get("result"), dict)
                                else res
                            )
                            return max(
                                0.0,
                                safe_float(r_obj.get("cashBuyingPower"), 0.0),
                            )
                    except Exception:
                        pass
            try:
                raw = await _invoke_raw_toss_api(
                    self,
                    method="GET",
                    path="/api/v1/buying-power",
                    params={"currency": "USD"},
                    require_account=True,
                )
                if isinstance(raw, dict):
                    r_obj = (
                        raw.get("result")
                        if isinstance(raw.get("result"), dict)
                        else raw
                    )
                    raw_bp = max(
                        0.0, safe_float(r_obj.get("cashBuyingPower"), 0.0)
                    )
                    mult = max(
                        0.90,
                        min(
                            1.0,
                            1.0 - safe_float(safety_buffer_pct, 0.0) / 100.0,
                        ),
                    )
                    return round(raw_bp * mult, 4)
            except Exception:
                pass
            return 0.0

        setattr(
            TossApiClient, "get_buying_power_usd", _poly_get_buying_power_usd
        )

    if not hasattr(TossApiClient, "get_usd_krw_rate"):

        async def _poly_get_usd_krw_rate(self: Any) -> float:
            for cand_name in (
                "get_exchange_rate",
                "fetch_usd_krw_rate",
                "fetch_exchange_rate",
            ):
                fn = getattr(self, cand_name, None)
                if callable(fn):
                    try:
                        res = await _call_plugin_adaptive(
                            fn, baseCurrency="USD", quoteCurrency="KRW"
                        )
                        if isinstance(res, (int, float)) and float(res) > 0.0:
                            return float(res)
                        if isinstance(res, dict):
                            r_obj = (
                                res.get("result")
                                if isinstance(res.get("result"), dict)
                                else res
                            )
                            rate_v = safe_float(r_obj.get("rate"), 0.0)
                            if rate_v > 0.0:
                                return rate_v
                    except Exception:
                        pass
            try:
                raw = await _invoke_raw_toss_api(
                    self,
                    method="GET",
                    path="/api/v1/exchange-rate",
                    params={"baseCurrency": "USD", "quoteCurrency": "KRW"},
                    require_account=False,
                )
                if isinstance(raw, dict):
                    r_obj = (
                        raw.get("result")
                        if isinstance(raw.get("result"), dict)
                        else raw
                    )
                    rate_v = safe_float(r_obj.get("rate"), 0.0)
                    if rate_v > 0.0:
                        return rate_v
            except Exception:
                pass
            return KRW_PER_USD_DEFAULT

        setattr(TossApiClient, "get_usd_krw_rate", _poly_get_usd_krw_rate)

    if not hasattr(TossApiClient, "close"):

        async def _poly_close(self: Any) -> None:
            for sess_attr in ("_session", "session", "_client", "client"):
                s_obj = getattr(self, sess_attr, None)
                if s_obj is not None and hasattr(s_obj, "close"):
                    try:
                        c_res = s_obj.close()
                        if inspect.isawaitable(c_res):
                            await c_res
                    except Exception:
                        pass
            return None

        setattr(TossApiClient, "close", _poly_close)


_install_toss_api_compatibility_patches()


def _instantiate_stratum_ledger(
    filepath: str, base_dir: Optional[str] = None
) -> Any:
    """
    🚨 Case 68:
    폴더 위치(base_dir)와 원장 경로(filepath)를 주입하여 폴더별 3중 안전 원장을 초기화한다.
    """
    ledger_cls = _resolve_module_attr(
        modules=(toss_api, quant_engine),
        candidate_names=(
            "SoxlStratumLedger",
            "StratumLedger",
            "AssassinLedger",
            "TossStratumLedger",
            "SoxlLedger",
        ),
        predicate=lambda c: (
            inspect.isclass(c)
            and hasattr(c, "get_state")
            and hasattr(c, "update_state")
        ),
    )
    if ledger_cls is None:
        raise RuntimeError(
            "원장 클래스(get_state/update_state 보유)를 찾을 수 없습니다."
        )

    try:
        sig = inspect.signature(ledger_cls.__init__)
        kw: Dict[str, Any] = {}
        if "filepath" in sig.parameters:
            kw["filepath"] = filepath
        if "base_dir" in sig.parameters and base_dir:
            kw["base_dir"] = base_dir
        if kw:
            return ledger_cls(**kw)
        if len(sig.parameters) >= 2:
            return ledger_cls(filepath)
        return ledger_cls()
    except Exception:
        return ledger_cls(filepath)


def _check_weekend_nyse_closed_dynamic(now_est: datetime) -> bool:
    """
    # MODIFIED [Case 01 & Case 79]:
    금요일 애프터마켓(16:00 ~ 19:59 EST) 익절 매도 개방을 위해 금요일 휴장 진입 시각을 20:00 EST 로 동기화한다.
    """
    fn = _resolve_module_attr(
        modules=(quant_indicators_plugin, toss_api),
        candidate_names=(
            "is_weekend_nyse_closed",
            "is_weekend_closed",
            "is_nyse_weekend_closed",
        ),
    )
    if callable(fn):
        try:
            return bool(fn(now_est))
        except Exception:
            pass

    dt = now_est.astimezone(EST_TZ)
    wd = dt.weekday()
    hm = dt.hour * 100 + dt.minute
    if wd == 4 and hm >= 2000:
        return True
    if wd == 5:
        return True
    if wd == 6 and hm < 1800:
        return True
    return False


# ---------------------------------------------------------------------------
# [핵심 1-C] 자체 벡터화 1분봉/일봉 지표 산출 폴백 (VWAP · 5MA · HA양봉/음봉)
# ---------------------------------------------------------------------------
def _compute_vectorized_metrics_fallback(
    candles_1m: List[Dict[str, Any]],
    live_price: float,
    now_est: datetime,
    candles_1d: List[Dict[str, Any]],
) -> Dict[str, Any]:
    dt_now = now_est.astimezone(EST_TZ)
    today_str = dt_now.strftime("%Y-%m-%d")
    lp = safe_float(live_price, 0.0)

    out: Dict[str, Any] = {
        "symbol": TARGET_SYMBOL,
        "live_price": round(lp, 4),
        "ma5_amp_pct": 6.50,
        "rsi_14": 50.0,
        "ha_bull": True,
        "ha_badge": "🕯️HA양봉",
        "premarket_vwap": 0.0,
        "premarket_high": 0.0,
        "premarket_low": 0.0,
        "premarket_amp_pct": 0.0,
        "premarket_est_low": 0.0,
        "premarket_est_high": 0.0,
        "regular_vwap": 0.0,
        "regular_high": 0.0,
        "regular_low": 0.0,
        "regular_amp_pct": 0.0,
        "regular_est_low": 0.0,
        "regular_est_high": 0.0,
    }

    if isinstance(candles_1d, list) and len(candles_1d) >= 2:
        try:
            df_d = pd.DataFrame(candles_1d)
            if "highPrice" in df_d.columns and "lowPrice" in df_d.columns:
                hs = pd.to_numeric(df_d["highPrice"], errors="coerce")
                ls = pd.to_numeric(df_d["lowPrice"], errors="coerce")
                valid = (hs > 0) & (ls > 0) & (hs >= ls)
                hv = (
                    hs[valid].to_numpy(dtype=float)[-6:-1]
                    if valid.sum() > 5
                    else hs[valid].to_numpy(dtype=float)[-5:]
                )
                lv = (
                    ls[valid].to_numpy(dtype=float)[-6:-1]
                    if valid.sum() > 5
                    else ls[valid].to_numpy(dtype=float)[-5:]
                )
                if len(lv) >= 1:
                    out["ma5_amp_pct"] = round(
                        float(
                            np.mean(((hv - lv) / np.maximum(0.01, lv)) * 100.0)
                        ),
                        2,
                    )
        except Exception:
            pass

    if not isinstance(candles_1m, list) or not candles_1m:
        return refresh_metrics_with_live_tick(out, lp, now_est=dt_now)

    try:
        df = pd.DataFrame(candles_1m)
        if df.empty or "timestamp" not in df.columns:
            return refresh_metrics_with_live_tick(out, lp, now_est=dt_now)

        ts_utc = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
        df = df.loc[ts_utc.notna()].copy()
        df["dt_est"] = ts_utc[ts_utc.notna()].dt.tz_convert(EST_TZ)
        df.sort_values("dt_est", ascending=True, inplace=True)
        df.drop_duplicates(subset=["dt_est"], keep="last", inplace=True)

        df["O"] = pd.to_numeric(
            df.get("openPrice", df.get("open")), errors="coerce"
        )
        df["H"] = pd.to_numeric(
            df.get("highPrice", df.get("high")), errors="coerce"
        )
        df["L"] = pd.to_numeric(
            df.get("lowPrice", df.get("low")), errors="coerce"
        )
        df["C"] = pd.to_numeric(
            df.get("closePrice", df.get("close")), errors="coerce"
        )
        df["V"] = pd.to_numeric(
            df.get("volume", 0.0), errors="coerce"
        ).fillna(0.0)
        df.dropna(subset=["O", "H", "L", "C"], inplace=True)
        if df.empty:
            return refresh_metrics_with_live_tick(out, lp, now_est=dt_now)

        if lp <= 0.0:
            lp = float(df["C"].iloc[-1])
            out["live_price"] = round(lp, 4)

        opens = df["O"].to_numpy(dtype=float)
        highs = df["H"].to_numpy(dtype=float)
        lows = df["L"].to_numpy(dtype=float)
        closes = df["C"].to_numpy(dtype=float)
        if lp > 0.0 and len(closes) > 0:
            closes[-1] = lp
            highs[-1] = max(highs[-1], lp)
            lows[-1] = min(lows[-1], lp)

        ha_c = (opens + highs + lows + closes) * 0.25
        shifted = np.empty(len(ha_c), dtype=float)
        shifted[0] = (opens[0] + closes[0]) * 0.5
        if len(ha_c) > 1:
            shifted[1:] = ha_c[:-1]
        ha_o = (
            pd.Series(shifted)
            .ewm(alpha=0.5, adjust=False)
            .mean()
            .to_numpy(dtype=float)
        )
        is_bull = bool(ha_c[-1] >= ha_o[-1])
        out["ha_bull"] = is_bull
        out["ha_badge"] = "🕯️HA양봉" if is_bull else "🌑HA음봉"
        out["prev_ha_open"] = round(
            float(ha_o[-2] if len(ha_o) >= 2 else ha_o[-1]), 4
        )
        out["prev_ha_close"] = round(
            float(ha_c[-2] if len(ha_c) >= 2 else ha_c[-1]), 4
        )
        out["cur_bar_open"] = round(float(opens[-1]), 4)
        out["cur_bar_high"] = round(float(highs[-1]), 4)
        out["cur_bar_low"] = round(float(lows[-1]), 4)

        df["Date"] = df["dt_est"].dt.strftime("%Y-%m-%d")
        df["hm"] = df["dt_est"].dt.hour * 100 + df["dt_est"].dt.minute
        t_date = (
            today_str
            if (df["Date"] == today_str).any()
            else str(df["Date"].iloc[-1])
        )
        df_t = df[df["Date"] == t_date]

        amp_ratio = max(0.01, float(out["ma5_amp_pct"]) / 100.0)
        for prefix, sub in (
            ("premarket", df_t[(df_t["hm"] >= 400) & (df_t["hm"] <= 929)]),
            ("regular", df_t[(df_t["hm"] >= 930) & (df_t["hm"] <= 1600)]),
        ):
            if not sub.empty:
                h_a = sub["H"].to_numpy(dtype=float)
                l_a = sub["L"].to_numpy(dtype=float)
                c_a = sub["C"].to_numpy(dtype=float)
                v_a = np.maximum(0.0, sub["V"].to_numpy(dtype=float))
                tp = (h_a + l_a + c_a) / 3.0
                tv = float(np.sum(v_a))
                vwap_v = (
                    float(np.sum(tp * v_a) / tv)
                    if tv > 0
                    else float(np.mean(tp))
                )
                sh = float(np.max(h_a))
                sl = float(np.min(l_a))
                out[f"{prefix}_vwap"] = round(vwap_v, 4)
                out[f"{prefix}_high"] = round(sh, 4)
                out[f"{prefix}_low"] = round(sl, 4)
                out[f"{prefix}_amp_pct"] = round(
                    ((sh - sl) / sl) * 100.0 if sl > 0 else 0.0, 2
                )
                out[f"{prefix}_est_high"] = round(
                    max(sh, sl * (1.0 + amp_ratio)), 2
                )
                out[f"{prefix}_est_low"] = round(
                    min(sl, sh / (1.0 + amp_ratio)), 2
                )
    except Exception:
        pass

    return refresh_metrics_with_live_tick(out, lp, now_est=dt_now)


async def _compute_candle_metrics_dynamic(
    context: Any,
    candles_1m: List[Dict[str, Any]],
    live_price: float,
    now_est: datetime,
    candles_1d: List[Dict[str, Any]],
) -> Dict[str, Any]:
    excluded = {
        "evaluate_buy_gate_bucket_status",
        "is_active_trading_window",
        "is_active_buy_window",
        "is_active_sell_window",
        "is_extended_sell_only_window",
        "refresh_metrics_with_live_tick",
        "is_weekend_nyse_closed",
        "is_weekend_closed",
    }
    fn = _resolve_module_attr(
        modules=(quant_indicators_plugin, quant_engine),
        candidate_names=(
            "compute_soxl_quant_metrics_1m",
            "compute_quant_metrics_1m",
            "calculate_soxl_quant_metrics_1m",
            "compute_candle_metrics_1m",
            "build_soxl_candle_metrics",
            "calculate_vwap_metrics_1m",
        ),
        predicate=lambda f: (
            inspect.isfunction(f)
            and getattr(f, "__module__", "")
            == quant_indicators_plugin.__name__
            and f.__name__ not in excluded
            and not f.__name__.startswith("_")
        ),
    )
    if callable(fn):
        try:
            res = await _call_plugin_adaptive(
                fn,
                context=context,
                api=context.api,
                symbol=TARGET_SYMBOL,
                candles=candles_1m,
                candles_1m=candles_1m,
                minute_candles=candles_1m,
                daily_candles=candles_1d,
                candles_1d=candles_1d,
                day_candles=candles_1d,
                live_price=live_price,
                current_price=live_price,
                price=live_price,
                now_est=now_est,
                dt_now=now_est,
            )
            if isinstance(res, dict) and (
                safe_float(res.get("premarket_vwap"), 0.0) > 0.0
                or safe_float(res.get("regular_vwap"), 0.0) > 0.0
            ):
                return refresh_metrics_with_live_tick(
                    res, live_price, now_est=now_est
                )
        except Exception:
            pass

    return _compute_vectorized_metrics_fallback(
        candles_1m=candles_1m,
        live_price=live_price,
        now_est=now_est,
        candles_1d=candles_1d,
    )


# ---------------------------------------------------------------------------
# [핵심 1-D] 폴더 위치(base_dir) 전용 텔레그램 토큰·채팅방 ID 자동 탐색기 (Case 68)
# ---------------------------------------------------------------------------
def _extract_valid_tg_token(text: str) -> str:
    if not text or "://" in text:
        return ""
    m = _TG_TOKEN_STRICT_RE.search(str(text).strip())
    return m.group(1) if m else ""


def _discover_telegram_credentials(
    base_dir: str, api_obj: Any = None
) -> Tuple[str, str]:
    """
    🚨 Case 68:
    1) "/home/pipiosToss" 고정 경로 하드코딩을 100% 영구 제거하고, 오직 현재 봇이 위치한
       물리적 폴더(target_dir = get_bot_base_dir(base_dir))의 .env 와 설정 파일만 참조한다.
    2) TOKEN_URL("https://...") 등 URL 상수가 봇 토큰으로 오매칭되는 버그를 100% 차단하고
       오직 _TG_TOKEN_STRICT_RE(\\d{8,12}:[A-Za-z0-9_-]{25,60}) 에 일치하는 토큰만 추출한다.
    """
    target_dir = get_bot_base_dir(base_dir)
    candidate_dirs = [target_dir]
    for d in candidate_dirs:
        if not d or not os.path.isdir(d):
            continue
        env_fp = os.path.join(d, ".env")
        if os.path.isfile(env_fp):
            try:
                with open(env_fp, "r", encoding="utf-8", errors="ignore") as f:
                    for raw_line in f:
                        line = raw_line.strip()
                        if not line or line.startswith("#") or "=" not in line:
                            continue
                        if line.startswith("export "):
                            line = line[len("export ") :].strip()
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip("'").strip('"')
                        if k and v and k not in os.environ:
                            os.environ[k] = v
            except Exception:
                pass

    token_keys = (
        "TELEGRAM_BOT_TOKEN",
        "TG_BOT_TOKEN",
        "BOT_TOKEN",
        "TELEGRAM_TOKEN",
        "TG_TOKEN",
    )
    chat_keys = (
        "TELEGRAM_CHAT_ID",
        "TG_CHAT_ID",
        "CHAT_ID",
        "TELEGRAM_ADMIN_ID",
        "ADMIN_CHAT_ID",
        "ALLOWED_CHAT_ID",
    )

    bot_token = ""
    chat_id = ""

    # 1) 환경변수 우선 탐색
    for k in token_keys:
        cand = _extract_valid_tg_token(str(os.environ.get(k) or ""))
        if cand:
            bot_token = cand
            break

    if not bot_token:
        for _, v in os.environ.items():
            cand = _extract_valid_tg_token(str(v or ""))
            if cand:
                bot_token = cand
                break

    for k in chat_keys:
        v = str(os.environ.get(k) or "").strip()
        if v.lstrip("-").isdigit() and len(v.lstrip("-")) >= 5:
            chat_id = v
            break

    # 2) api_obj 인스턴스 및 tg_ui_plugin / toss_api 모듈 전역 변수 탐색
    scan_targets: List[Any] = [tg_ui_plugin, toss_api]
    if api_obj is not None:
        scan_targets.insert(0, api_obj)

    for target in scan_targets:
        try:
            obj_dict = vars(target)
        except Exception:
            continue
        for attr_name, attr_val in obj_dict.items():
            if isinstance(attr_val, (str, int)):
                s_val = str(attr_val).strip()
                u_name = attr_name.upper()
                if not bot_token:
                    cand = _extract_valid_tg_token(s_val)
                    if cand:
                        bot_token = cand
                if not chat_id and (
                    "CHAT_ID" in u_name or "ADMIN_ID" in u_name
                ):
                    if (
                        s_val.lstrip("-").isdigit()
                        and len(s_val.lstrip("-")) >= 5
                    ):
                        chat_id = s_val

    # 3) 현재 폴더(target_dir) 내 설정 파일(.env / .json / .py) 텍스트 정규식 스캔 폴백
    if not bot_token or not chat_id:
        chat_re = re.compile(
            r"(?:CHAT_ID|chat_id)\s*[:=]\s*['\"]?(-?\d{6,15})['\"]?"
        )
        for d in candidate_dirs:
            if not d or not os.path.isdir(d):
                continue
            for fn in (
                ".env",
                "config.json",
                "secrets.json",
                "toss_api.py",
                "tg_ui_plugin.py",
            ):
                fp = os.path.join(d, fn)
                if not os.path.isfile(fp):
                    continue
                try:
                    with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    if not bot_token:
                        m_tok = _TG_TOKEN_STRICT_RE.search(content)
                        if m_tok:
                            bot_token = m_tok.group(1)
                    if not chat_id:
                        m_cid = chat_re.search(content)
                        if m_cid:
                            chat_id = m_cid.group(1)
                except Exception:
                    pass

    return bot_token, chat_id


def _escape_html(val: Any) -> str:
    return html.escape(str(val if val is not None else ""), quote=False)


def _get_dst_badge(now_est: Optional[datetime] = None) -> str:
    dt = now_est.astimezone(EST_TZ) if now_est else datetime.now(EST_TZ)
    tz_name = dt.tzname() or "EST"
    if "EDT" in tz_name.upper():
        return "☀️서머타임 ON (EDT)"
    return "❄️서머타임 OFF (EST)"


def _resolve_display_seed(st: Dict[str, Any]) -> float:
    """
    🚨 Case 68:
    initial_seed_usd 가 0.0 또는 비정상 초기값일 때 $100.0 으로 잘못 표시되지 않도록 방어한다.
    """
    raw_s = safe_float((st or {}).get("initial_seed_usd"), 0.0)
    explicit_100 = bool((st or {}).get("seed_explicitly_set_100", False))
    if raw_s > 100.0:
        return round(raw_s, 4)
    if abs(raw_s - 100.0) < 1e-6 and explicit_100:
        return 100.0
    return DEFAULT_INITIAL_SEED_USD


def _resolve_folder_identity_badge(
    context: Optional[Any], st: Optional[Dict[str, Any]] = None
) -> Tuple[str, str]:
    """
    Case 68:
    현재 봇이 가동 중인 폴더 식별자(folder_slug)와 고유 원장 파일명을 반환한다.
    """
    slug = ""
    primary_name = ""
    if context is not None and hasattr(context, "ledger"):
        slug = str(getattr(context.ledger, "folder_slug", "") or "").strip()
        p_fp = str(
            getattr(context.ledger, "primary_filepath", "") or ""
        ).strip()
        if p_fp:
            primary_name = os.path.basename(p_fp)

    if not slug and isinstance(st, dict):
        slug = str(st.get("folder_slug") or "").strip()

    if not slug:
        base_d = (
            getattr(context, "base_dir", None) if context is not None else None
        )
        slug = get_folder_slug(base_d)

    if not primary_name:
        primary_name = f"soxl_stratum_ledger_{slug}.json"

    return slug, primary_name


def _format_case67_quota_badge(summary: Dict[str, Any]) -> str:
    """
    Case 67:
    기준가 고정 정량(anchor_quota_qty)과 현재가 기준 1회분 예산 상한 주수(budget_cap_qty)의
    min(budget_cap_qty, anchor_quota_qty) 캡핑 상태를 직관적인 문자열로 반환한다.
    """
    next_qty = safe_int(summary.get("next_target_qty"), 1)
    anc_qty = safe_int(summary.get("anchor_quota_qty"), next_qty)
    cap_qty = safe_int(summary.get("budget_cap_qty"), next_qty)
    if next_qty < anc_qty:
        return f"<b>{next_qty}주</b> (🛡️min(1회분 {cap_qty}주, 고정 {anc_qty}주) 예산초과 차단)"
    return f"<b>{next_qty}주</b> (min(1회분, 고정 {anc_qty}주) 대기)"


def _format_multi_grid_stratum_lines(
    summary: Dict[str, Any],
    live_price: float,
    is_ext_sell_only: bool = False,
) -> List[str]:
    """
    # MODIFIED [Case 71, Case 72, Case 73, Case 78 & Case 79]:
    1층(활성 공격수 · 부분체결 시 미체결 잔량 및 1.5s 감시 표시 / 또는 60초 주기 공석 감시 & 2층 단가 상한) 및
    상단 2층 ~ 6층 개별 완충층 · 통합 7층 본대와 2~7층 통합 이동평균 목표가를 모바일 화면에 최적화된 형태로 전수 렌더링한다.
    - 애프터마켓/데이마켓(is_ext_sell_only == True)에서는 매수는 잠겨 있고 익절 매도만 1.5s 실시간 감시 중임을 표시한다.
    """
    held_sh = safe_int(summary.get("held_shares"), 0)
    buckets = summary.get("buckets", [])
    if held_sh <= 0 or not buckets:
        if is_ext_sell_only:
            return [
                "⚪ <b>[보유 지층 없음 · 0주]</b> 🔒장외 매수잠금 · 04:07 EST 프리장 개시 후 첫 1층(REENTRY_1FL) 진입 대기"
            ]
        return [
            "⚪ <b>[보유 지층 없음 · 0주]</b> 60초 타임쉴드 확인 후 현재가 지정가 1층(REENTRY_1FL) 즉시 산입 대기"
        ]

    lines: List[str] = []
    active_l1 = bool(summary.get("has_active_l1", True))
    rise_u_pct = safe_float(summary.get("rise_sell_l2_pct"), 1.00)

    if active_l1:
        b1 = buckets[0]
        l1_t = safe_float(summary.get("l1_target_price"), 0.0)
        l1_g = safe_float(summary.get("l1_gain_pct"), 0.0)
        g1_sign = "+" if l1_g >= 0.0 else ""
        # [Case 78]: 1층 부분 체결 미체결 잔량(l1_rem_quota_qty > 0) 존재 시 목표 정량 및 1.5s 잔량 감시 표출
        l1_rem_q = safe_int(summary.get("l1_rem_quota_qty"), 0)
        l1_target_q = safe_int(summary.get("l1_target_quota_qty"), b1.qty)
        if l1_rem_q > 0 and l1_target_q > b1.qty:
            topup_mode_str = (
                "04:07 EST 잔량대기"
                if is_ext_sell_only
                else f"${b1.book_price:.2f} 이하 1.5s감시"
            )
            l1_qty_label = (
                f"공격수 {b1.qty}주/목표{l1_target_q}주 · "
                f"🎯잔량 {l1_rem_q}주({topup_mode_str})"
            )
        else:
            l1_qty_label = f"공격수 {b1.qty}주"

        lines.append(
            f"⚡ <b>[1층: {l1_qty_label}]</b> 단가 <b>${b1.book_price:.2f}</b> · "
            f"익절 <b>${l1_t:.2f}</b>(+1.5%) [{g1_sign}{l1_g:.2f}%]"
        )
        upper_buckets = buckets[1:]
    else:
        l2_cap = safe_float(
            summary.get("l2_ceiling_price"),
            safe_float(summary.get("min_indiv_upper_price"), 0.0),
        )
        cap_note = f" · 2층상한 ${l2_cap:.2f} 이하" if l2_cap > 0.0 else ""
        if is_ext_sell_only:
            lines.append(
                f"⚡ <b>[1층: 공석 · 🔒장외 매수잠금(04:07 EST 이후 재장전{cap_note})]</b>"
            )
        else:
            lines.append(
                f"⚡ <b>[1층: 공석 · 60초(1분) 주기 눌림(-1.0%)/돌파(+1.0%) 감시{cap_note}]</b>"
            )
        upper_buckets = buckets[:]

    if upper_buckets:
        u_cnt = len(upper_buckets)
        u_qty = safe_int(
            summary.get("upper_qty"), sum(b.qty for b in upper_buckets)
        )
        u_lots = safe_int(
            summary.get("upper_lots"), sum(b.lot_count for b in upper_buckets)
        )
        u_wma_p = safe_float(summary.get("upper_wma_price"), 0.0)
        u_wma_t = safe_float(summary.get("upper_wma_target_price"), 0.0)
        u_gain = safe_float(summary.get("l2_gain_pct"), 0.0)
        ug_sign = "+" if u_gain >= 0.0 else ""
        tier_range_label = "2층" if u_cnt == 1 else f"2~{u_cnt + 1}층"
        lines.append(
            f"📦 <b>[{tier_range_label} 통합이평: {u_cnt}개층 {u_qty}주({u_lots}회차)]</b> "
            f"이평 <b>${u_wma_p:.2f}</b> · 일괄졸업 <b>${u_wma_t:.2f}</b>(+1.0%) [{ug_sign}{u_gain:.2f}%]"
        )

        # 7-Layer 에서는 상단 그리드가 최대 6개(2층 ~ 7층)이므로 전 층을 중략 없이 개별 표출
        for idx_u, bu in enumerate(upper_buckets):
            t_no = idx_u + 2
            bu_t = (
                math.ceil(
                    (bu.book_price * (1.0 + rise_u_pct / 100.0) - 1e-9)
                    * 100.0
                )
                / 100.0
            )
            bu_g = (
                ((live_price - bu.book_price) / bu.book_price) * 100.0
                if (live_price > 0.0 and bu.book_price > 0.0)
                else 0.0
            )
            bg_s = "+" if bu_g >= 0.0 else ""
            if t_no >= 7 and bu.lot_count > 1:
                tier_tag = f"통합{t_no}층"
                lot_note = f"({bu.lot_count}회합병)"
            else:
                tier_tag = f"{t_no}층"
                lot_note = f"({bu.lot_count}회)" if bu.lot_count > 1 else ""
            lines.append(
                f"  ▫️ <b>{tier_tag}</b>: {bu.qty}주{lot_note} @ ${bu.book_price:.2f} "
                f"➔ 개별익절 <b>${bu_t:.2f}</b>(+1.0%) [{bg_s}{bu_g:.2f}%]"
            )

    return lines


def _build_main_reply_keyboard() -> Dict[str, Any]:
    return {
        "keyboard": [
            [
                {"text": "🔫 스나이퍼 레이더"},
                {"text": "📜 지층 지시서"},
                {"text": "⬅️ 메인 메뉴"},
            ],
            [
                {"text": "⚙️ 전술 제어반"},
                {"text": "🔄 잔고 동기화"},
                {"text": "🚀 시스템 업데이트"},
            ],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
    }


def _build_radar_inline_keyboard() -> Optional[Dict[str, Any]]:
    """
    # 하단 고정 메뉴(_build_main_reply_keyboard)와 2중으로 중복 출력되던
    문단 아래 인라인 네비게이션 버튼을 전면 비활성화(None 반환)한다.
    """
    return None


def _build_settlement_inline_keyboard(is_active: bool) -> Dict[str, Any]:
    """
    # [Case 64 엄수 & 하단 중복 메뉴 제거]:
    전술 제어반(/settlement)에는 하단 고정 메뉴와 중복되는 [스나이퍼 레이더 / 지층 지시서] 버튼을 제거하고,
    오직 [작동 ON/OFF] 와 [시드머니 설정] 2가지 핵심 조작 버튼만 둔다.
    """
    power_label = (
        "🔴 스나이퍼 작동 OFF 로 전환"
        if is_active
        else "🟢 스나이퍼 작동 ON 으로 전환"
    )
    return {
        "inline_keyboard": [
            [
                {"text": power_label, "callback_data": "toggle_bot_active"},
            ],
            [
                {
                    "text": "💵 기준 시드머니($) 설정",
                    "callback_data": "prompt_seed_input",
                },
            ],
        ]
    }


class _AdaptiveTelegramBridge:
    """
    외부 tg_ui_plugin 의 폴링 루프 구조에 구애받지 않고
    자체 내장 getUpdates 롱폴링 + /start, /avwap, /sync, /settlement, /reset_profit, /update +
    인라인 버튼 콜백 + 시드 숫자 입력을 100% 직접 수행하는 완결형 텔레그램 컨트롤러 (Case 62 ~ 79).
    """

    def __init__(self, context: Any) -> None:
        self.context: Any = context
        self.bot_token, self.chat_id = _discover_telegram_credentials(
            context.base_dir, getattr(context, "api", None)
        )
        self._boot_epoch: float = time.time()
        self._last_update_id: int = 0
        try:
            st_init = self.context.ledger.get_state(TARGET_SYMBOL)
            self._last_update_id = max(
                0, safe_int(st_init.get("last_tg_update_id"), 0)
            )
        except Exception:
            self._last_update_id = 0
        self._awaiting_seed_input_chats: Dict[str, float] = {}

    def _api_url(self, method: str) -> str:
        return f"https://api.telegram.org/bot{self.bot_token}/{method}"

    def _post_tg_sync(
        self,
        method: str,
        payload: Dict[str, Any],
        timeout_sec: float = 15.0,
    ) -> Dict[str, Any]:
        if not self.bot_token:
            return {"ok": False, "description": "missing-bot-token"}
        url = self._api_url(method)
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            url=url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                return json.loads(raw) if raw else {"ok": True}
        except urllib.error.HTTPError as he:
            try:
                err_raw = he.read().decode("utf-8", errors="replace")
                return json.loads(err_raw)
            except Exception:
                return {"ok": False, "error_code": he.code}
        except Exception as exc:
            return {"ok": False, "description": str(exc)}

    async def _call_tg(
        self,
        method: str,
        payload: Dict[str, Any],
        timeout_sec: float = 15.0,
    ) -> Dict[str, Any]:
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(
                    self._post_tg_sync, method, payload, timeout_sec
                ),
                timeout=timeout_sec + 3.0,
            )
        except Exception as exc:
            logger.debug("텔레그램 API(%s) 호출 예외: %s", method, exc)
            return {"ok": False, "description": str(exc)}

    async def _ack_telegram_offset(self, target_update_id: int) -> None:
        uid = max(self._last_update_id, safe_int(target_update_id, 0))
        if uid <= 0:
            return
        self._last_update_id = uid
        try:
            await self.context.ledger.update_state(
                TARGET_SYMBOL, last_tg_update_id=uid
            )
        except Exception:
            pass
        try:
            await self._call_tg(
                "getUpdates",
                {"offset": uid + 1, "limit": 1, "timeout": 0},
                timeout_sec=5.0,
            )
        except Exception:
            pass

    async def _flush_stale_updates_on_startup(self) -> None:
        try:
            res = await self._call_tg(
                "getUpdates",
                {"offset": -1, "timeout": 0},
                timeout_sec=6.0,
            )
            if not (isinstance(res, dict) and bool(res.get("ok"))):
                return
            updates = res.get("result")
            if not isinstance(updates, list) or not updates:
                return

            max_stale_uid = 0
            for upd in updates:
                if isinstance(upd, dict):
                    uid = safe_int(upd.get("update_id"), 0)
                    if uid > max_stale_uid:
                        max_stale_uid = uid

            if max_stale_uid > 0:
                await self._ack_telegram_offset(max_stale_uid)
                logger.info(
                    "🧹 [텔레그램 부팅 전 적체 큐 전량 소각 완료] last_update_id=%d",
                    max_stale_uid,
                )
        except Exception as exc:
            logger.debug("부팅 시 텔레그램 큐 플러시 스킵: %s", exc)

    async def send_message(
        self,
        text: str,
        chat_id: Optional[str] = None,
        reply_markup: Optional[Dict[str, Any]] = None,
        parse_mode: str = "HTML",
    ) -> bool:
        target_chat = str(chat_id or self.chat_id or "").strip()
        if self.bot_token and target_chat:
            payload: Dict[str, Any] = {
                "chat_id": target_chat,
                "text": text,
                "parse_mode": parse_mode,
                "disable_web_page_preview": True,
            }
            if reply_markup is not None:
                payload["reply_markup"] = reply_markup
            res = await self._call_tg("sendMessage", payload, timeout_sec=10.0)
            if not bool(res.get("ok")):
                payload.pop("parse_mode", None)
                res = await self._call_tg(
                    "sendMessage", payload, timeout_sec=10.0
                )
            if bool(res.get("ok")):
                return True

        fn = _resolve_module_attr(
            modules=(tg_ui_plugin,),
            candidate_names=(
                "send_telegram_message",
                "send_slim_alert",
                "send_telegram_alert",
            ),
        )
        if callable(fn):
            res_f = await _call_plugin_adaptive(
                fn,
                context=self.context,
                title=text,
                body="",
                text=text,
                message=text,
                reply_markup=reply_markup,
            )
            return bool(res_f)
        return False

    async def edit_or_send_message(
        self,
        chat_id: str,
        message_id: Optional[int],
        text: str,
        reply_markup: Optional[Dict[str, Any]] = None,
    ) -> bool:
        if self.bot_token and chat_id and message_id and message_id > 0:
            payload: Dict[str, Any] = {
                "chat_id": str(chat_id),
                "message_id": int(message_id),
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            }
            if reply_markup is not None:
                payload["reply_markup"] = reply_markup
            res = await self._call_tg(
                "editMessageText", payload, timeout_sec=10.0
            )
            if bool(res.get("ok")) or "message is not modified" in str(
                res.get("description") or ""
            ):
                return True
        return await self.send_message(
            text=text, chat_id=chat_id, reply_markup=reply_markup
        )

    async def send_slim_alert(
        self,
        title: str,
        body: str = "",
        reply_markup: Optional[Dict[str, Any]] = None,
    ) -> bool:
        safe_title = _escape_html(title)
        safe_body = _escape_html(body)
        msg = (
            f"<b>{safe_title}</b>\n🔸 {safe_body}"
            if safe_body
            else f"<b>{safe_title}</b>"
        )
        if self.bot_token and self.chat_id:
            return await self.send_message(
                text=msg, chat_id=self.chat_id, reply_markup=reply_markup
            )

        fn = _resolve_module_attr(
            modules=(tg_ui_plugin,),
            candidate_names=(
                "send_slim_alert",
                "send_telegram_slim_alert",
                "send_telegram_alert",
                "send_telegram_message",
            ),
        )
        if callable(fn):
            res = await _call_plugin_adaptive(
                fn,
                context=self.context,
                title=title,
                body=body,
                text=msg,
                message=msg,
            )
            return bool(res)
        return False

    async def send_startup_alive_banner(self) -> None:
        """
        # 기동 완료 후 "✅ 서버가 정상 작동 중입니다." 단일 라인 생존 신호 타전 (Case 16)
        """
        text = "<b>✅ 서버가 정상 작동 중입니다.</b>"
        sent = await self.send_message(
            text=text, reply_markup=_build_main_reply_keyboard()
        )
        if not sent:
            await self.send_slim_alert(
                title="✅ 서버가 정상 작동 중입니다.",
                body="",
            )

    # -----------------------------------------------------------------------
    # 4대 관제 보드 메시지 빌더 (/start · /avwap · /sync · /settlement)
    # -----------------------------------------------------------------------
    def _build_start_schedule_message(
        self, st: Dict[str, Any], now_est: datetime
    ) -> str:
        """
        # MODIFIED [Case 02 & Case 79]:
        - /reset 을 메뉴에서 완전 삭제하고 그 자리에 /reset_profit 만 배치
        - 애프터마켓(16:00 ~ 19:59 EST) 및 데이마켓(20:00 ~ 03:59 EST) 익절 매도 확장(매수 잠금) 스케줄 명시
        """
        dst_str = _get_dst_badge(now_est)
        lines = [
            f"🐂 <b>[ 스나이퍼 ({_escape_html(dst_str)}) ]</b>",
            "──────────────",
            "🔹 04:00 ~ 04:06: 🌅 휩소 안정화",
            "🔹 04:07 ~ 09:29: 🔫 프리장 (매수·익절)",
            "🔹 09:30 ~ 16:00: 🔥 정규장 (매수·익절)",
            "🔹 16:00 ~ 19:59: 🌇 애프터장 (익절감시·매수잠금)",
            "🔹 20:00 ~ 03:59: 🌃 데이장 (익절감시·매수잠금)",
            "──────────────",
            "📡 /avwap : 실시간 스나이퍼 레이더",
            "📜 /sync : 지층 지시서",
            "⚙️ /settlement : 전술 제어반",
            "       (작동 ON/OFF · 시드머니 설정)",
            "",
            "🧹 /reset_profit : 실현수익 0점 초기화",
            "",
            "🚀 /update : 최신 코드 업데이트",
        ]
        return "\n".join(lines)

    def _build_avwap_radar_message(
        self,
        st: Dict[str, Any],
        metrics: Dict[str, Any],
        live_price: float,
        now_est: datetime,
    ) -> str:
        """
        # MODIFIED [Case 65, Case 70, Case 71, Case 72, Case 73, Case 74, Case 76, Case 77, Case 78 & Case 79]:
        📡 /avwap 사용자 중심 초슬림 레이더 메시지 생성:
        - 상단 배지를 ⚡1.5s 실시간타점 (미체결 체결 감시 중일 때는 ⚡0.4s 체결감시)으로 표출한다.
        - 애프터마켓/데이마켓(is_ext_sell_only == True)에서는 상단에 `🌇/🌃 장외 ⚡1.5s 익절감시 가동 중 (🔒매수잠금)` 배너를 표출한다.
        - 매수 직후 최초 60.0초 타임쉴드(in_b) 가동 중일 때만 잔여 초를 표출하고,
          경과 후에는 보유 중 불필요한 60초 매도 대기 문구 없이 상시 1.5초 실시간 익절 감시 상태를 표출한다.
        - 🎯 [Case 78]: 1층이 부분 체결되어 미체결 잔량(l1_rem_quota_qty > 0)이 대기 중일 때는
          매수 후 60초 타임쉴드 해제 즉시 `🎯 [1층 미체결 잔량 K주(목표 M주) ⚡1.5초 감시 중]` 배너를 표출한다.
        """
        dt_now = now_est.astimezone(EST_TZ)
        hm_now = dt_now.hour * 100 + dt_now.minute
        is_ext_sell_only = is_extended_sell_only_window(hm_now, now_est=dt_now)

        met = refresh_metrics_with_live_tick(
            metrics, live_price, now_est=dt_now
        )
        lp = safe_float(
            live_price,
            safe_float(
                met.get("live_price"), safe_float(st.get("anchor_price"), 0.0)
            ),
        )
        summary = summarize_stratum_portfolio(st, live_price=lp)
        is_active = bool(st.get("is_active", True))
        active_badge = "🟢 ON" if is_active else "🔴 OFF"
        fast_badge = (
            "⚡0.4s 체결감시"
            if getattr(self.context, "fast_shield_mode", False)
            else (
                "🌃장외 ⚡1.5s 익절감시"
                if is_ext_sell_only
                else "⚡1.5s 실시간타점"
            )
        )

        held_sh = safe_int(summary.get("held_shares"), 0)
        held_lots = safe_int(summary.get("held_lots"), 0)
        held_tiers = safe_int(summary.get("held_tiers"), 0)
        is_l2_only = bool(summary.get("is_l2_only_anti_bloat"))
        l1_rem_q = safe_int(summary.get("l1_rem_quota_qty"), 0)
        l1_target_q = safe_int(summary.get("l1_target_quota_qty"), 0)
        buckets_list = summary.get("buckets", [])
        l1_book_p = buckets_list[0].book_price if buckets_list else lp

        # 🛡️ Case 65, Case 70, Case 73, Case 77, Case 78 & Case 79: 매수 직후 60초 / 1층 공석 60초 / 매도 후 60초 / 입금 대기 60초 / 장외 익절 상태 확인
        in_b, rem_b = is_within_post_buy_time_shield(
            self.context, st, TARGET_SYMBOL
        )
        in_s, rem_s = is_within_post_sell_time_shield(
            self.context, st, TARGET_SYMBOL
        )
        in_re, rem_re = is_within_reentry_monitor_time_shield(
            self.context, st, TARGET_SYMBOL
        )
        waiting_dep = bool(summary.get("waiting_reserve_deposit", False))
        req_dep_usd = safe_float(
            summary.get("required_reserve_deposit_usd"), 0.0
        )
        used_res_cnt = safe_int(summary.get("used_reserve_portions_cnt"), 0)
        avail_res_cnt = safe_int(
            summary.get("avail_reserve_portions"), MAX_RESERVE_PORTIONS
        )
        max_res_cnt = safe_int(
            summary.get("max_reserve_portions"), MAX_RESERVE_PORTIONS
        )
        inj_res_usd = safe_float(summary.get("injected_reserve_usd"), 0.0)
        min_req_g30 = safe_float(summary.get("min_req_cash_guard30"), 0.0)

        shield_line = ""
        if in_b:
            topup_wait_note = (
                f" &amp; 1층 잔량 {l1_rem_q}주(${l1_book_p:.2f} 이하)"
                if l1_rem_q > 0
                else ""
            )
            shield_line = (
                f"🛡️ <b>[매수 직후 60초 타임쉴드 가동 중]</b> 잔여 <b>{rem_b:.1f}초</b> 후 "
                f"⚡1.5초 실시간 3중 다중익절{topup_wait_note} 감시 개시"
            )
        elif waiting_dep:
            _, rem_dep_s = is_within_reserve_deposit_check_shield(
                self.context, st, TARGET_SYMBOL
            )
            wait_s_note = (
                f" · 차기검문 {rem_dep_s:.0f}초" if rem_dep_s > 0.0 else ""
            )
            shield_line = (
                f"🚨 <b>[💉 시드고갈 입금 대기 중 · 60초 자동감시{wait_s_note}]</b> "
                f"권장입금 <b>${req_dep_usd:,.2f}</b> (잔여한도 {avail_res_cnt}/{max_res_cnt}회분 · 1회알림 발송완료)"
            )
        elif is_ext_sell_only:
            sess_lbl = get_market_session_label(dt_now)
            shield_line = (
                f"🌃 <b>[{_escape_html(sess_lbl)}]</b> "
                "보유 지층 목표가 도달 시 지정가 즉시 익절 · 신규/추가 매수는 04:07 EST 까지 잠금"
            )
        elif is_l2_only and in_re:
            shield_line = (
                f"🛡️ <b>[60초 1층 공석 재장전 타임쉴드 가동 중]</b> 잔여 <b>{rem_re:.1f}초</b> 후 "
                "1층 재장전(2층 단가 이하 눌림/돌파) 검문 · 상단 익절 ⚡1.5초 상시감시 중"
            )
        elif in_s:
            shield_line = (
                f"🛡️ <b>[매도 후 60초 타임쉴드 가동 중]</b> 잔여 <b>{rem_s:.1f}초</b> 후 "
                "현재가 조회 &amp; 매수 감시 개시"
            )
        elif l1_rem_q > 0 and not is_l2_only:
            shield_line = (
                f"🎯 <b>[1층 미체결 잔량 {l1_rem_q}주(목표 {l1_target_q}주) ⚡1.5초 감시 중]</b> "
                f"<b>${l1_book_p:.2f}</b> 이하 재도래 즉시 잔량 60초 지정가 발주"
            )

        stratum_lines = _format_multi_grid_stratum_lines(
            summary, lp, is_ext_sell_only=is_ext_sell_only
        )

        _, _, _, gate_info = evaluate_buy_gate_bucket_status(
            now_est=dt_now,
            buy_interval_min=LOCKED_BUY_INTERVAL_MIN,
            last_evaluated_bucket_id=safe_int(
                st.get("last_evaluated_buy_bucket_id"), -1
            ),
            last_evaluated_date=str(st.get("last_evaluated_date") or ""),
        )
        next_gate_str = str(gate_info.get("next_gate_hm_str") or "04:07 EST")
        next_bud = safe_float(summary.get("next_portion_budget"), 800.0)
        quota_badge_str = _format_case67_quota_badge(summary)
        ref_anchor = safe_float(summary.get("ref_buy_anchor"), lp)
        chg_anchor = safe_float(summary.get("chg_from_buy_anchor_pct"), 0.0)
        c_sign = "+" if chg_anchor >= 0.0 else ""

        # [🎯 4 분기 1 & Case 65, Case 73, Case 76, Case 77, Case 78, Case 79]: 0주 상태 / 1층 공석 / 활성 1층 보유 3대 매수 모니터 상태 분리 표출
        if held_sh <= 0:
            if is_ext_sell_only:
                z_wait_label = "🔒장외 매수잠금 · 04:07 EST 해제"
            elif in_s:
                z_wait_label = f"60초 타임쉴드 잔여 {rem_s:.1f}초"
            else:
                z_wait_label = "04:07~16:00 EST 실시간 진입 대기"
            gate_header_line = (
                f"🛡️ <b>[0주 첫 1층 진입 모니터 · 60초 타임쉴드]</b> ({z_wait_label})"
            )
            gate_cond_line = (
                f"▫️ 직전기준 ${ref_anchor:.2f} · 04:07~16:00 EST 구간 내 실시간 현재가(<b>${lp:.2f}</b>) 지정가 첫 1층(REENTRY_1FL) 산입"
            )
        elif is_l2_only:
            pull_p = safe_float(summary.get("reentry_pullback_price"), 0.0)
            brk_p = safe_float(summary.get("reentry_breakout_price"), 0.0)
            locked_min_p = safe_float(summary.get("cycle_min_buy_price"), 0.0)
            l2_cap_p = safe_float(
                summary.get("l2_ceiling_price"),
                safe_float(summary.get("min_indiv_upper_price"), 0.0),
            )
            if is_ext_sell_only:
                re_wait_label = "🔒장외 매수잠금 · 04:07 EST 재개"
            elif in_re:
                re_wait_label = f"60초 주기 · 잔여 {rem_re:.1f}초"
            else:
                re_wait_label = "60초 주기 실시간 감시"
            gate_header_line = (
                f"🛡️ <b>[60초 주기 1층 공석 재장전 모니터 · 2층 역전차단]</b> ({re_wait_label})"
            )
            if l2_cap_p > 0.0 and lp > (l2_cap_p + 1e-6):
                cap_status_str = (
                    f" · 🚫<b>역전차단(현재가&gt;2층 ${l2_cap_p:.2f})</b>"
                )
            elif l2_cap_p > 0.0:
                cap_status_str = f" · 2층상한 <b>${l2_cap_p:.2f}</b> 이하"
            else:
                cap_status_str = ""
            gate_cond_line = (
                f"▫️ 직전익절 ${ref_anchor:.2f} 대비 {c_sign}{chg_anchor:.2f}% "
                f"(눌림목 <b>${pull_p:.2f}</b> 이하 OR 돌파 <b>${brk_p:.2f}</b> 이상{cap_status_str} · 기억저가 ${locked_min_p:.2f} 잠금)"
            )
        else:
            drop_req = safe_float(summary.get("drop_buy_pct"), -1.0)
            trig_p = safe_float(summary.get("trigger_buy_price"), 0.0)
            step_eligible = bool(summary.get("step_up_eligible", False))
            step_trig_p = safe_float(summary.get("stepped_trigger_price"), 0.0)
            reb_mult = safe_float(summary.get("rebound_mult"), 1.0)
            gate_header_line = (
                f"🛡️ <b>[10분 고정 와이드 &amp; 스텝업 시드보호 게이트]</b> (차기검문: {_escape_html(next_gate_str)})"
            )
            step_note = (
                f" · 🔓<b>스텝업해금(-15%): ${step_trig_p:.2f} 이하</b>[반등 {reb_mult:.2f}x]"
                if (step_eligible and step_trig_p > 0.0)
                else ""
            )
            topup_cond_note = (
                f" · 🎯<b>1층잔량 {l1_rem_q}주(${l1_book_p:.2f} 이하 1.5s대기)</b>"
                if l1_rem_q > 0
                else ""
            )
            gate_cond_line = (
                f"▫️ 정적기억저가 ${ref_anchor:.2f} 대비 현재 {c_sign}{chg_anchor:.2f}% "
                f"(와이드단차 {drop_req:.2f}% · 신저가 <b>${trig_p:.2f}</b> 이하{step_note}{topup_cond_note})"
            )

        pass_cnt = safe_int(summary.get("seed_protect_pass_cnt"), 0)
        dust_blk_cnt = safe_int(summary.get("daily_dust_guard_blocked_cnt"), 0)
        extra_13 = safe_int(summary.get("extra_13plus_buy_events"), 0)
        unlock_cnt = safe_int(summary.get("cond_unlock_buy_events"), 0)
        saved_u = safe_float(summary.get("cumulative_leftover_saved_usd"), 0.0)
        cum_net = safe_float(summary.get("cumulative_realized_net_usd"), 0.0)
        free_cash = safe_float(summary.get("free_cash_usd"), 0.0)
        mark_eq = safe_float(summary.get("mark_equity_usd"), 0.0)
        mark_roi = safe_float(summary.get("mark_roi_pct"), 0.0)
        n_sign = "+" if cum_net >= 0.0 else "-"
        m_sign = "+" if mark_roi >= 0.0 else ""

        dust_note = (
            f" (30%자투리차단 {dust_blk_cnt}회)" if dust_blk_cnt > 0 else ""
        )
        res_status_line = (
            f"💉 예비시드 탄창: 사용 <b>{used_res_cnt}/{max_res_cnt}회분</b> "
            f"(수혈잔액 ${inj_res_usd:,.2f} · 0주졸업 자동상환)"
        )

        lines = [
            f"📡 <b>[레이더]</b> ({active_badge} · {fast_badge})",
            f"🐂 <b>SOXL</b> [{active_badge}] 현재가 <b>${lp:.2f}</b>",
        ]
        if shield_line:
            lines.append(shield_line)

        lines.extend(
            [
                "──────────────",
                f"🏛️ <b>[1~6층 개별 &amp; 통합 7층 본대 · 2~7층 통합이평]</b> (총 {held_sh}주 · {held_tiers}개층 · {held_lots}회차)",
                *stratum_lines,
                "──────────────",
                gate_header_line,
                gate_cond_line,
                f"▫️ 차기 8% 정량: 예산 ${next_bud:,.2f}(30%가드 ${min_req_g30:,.2f}) ➔ {quota_badge_str}",
                "──────────────",
                f"🛡️ 시드보호 패스: {pass_cnt:,}회{dust_note}",
                f"🔥 13회차+ 확장매수: {extra_13}회 · 🔓 스텝업해금: {unlock_cnt}회",
                res_status_line,
                f"💰 자투리절약 누적: +${saved_u:,.2f} · 세후실현익: {n_sign}${abs(cum_net):,.2f}",
                f"💵 가용현금: <b>${free_cash:,.2f}</b> · 총자산: <b>${mark_eq:,.2f}</b> ({m_sign}{mark_roi:.2f}%)",
                f"🕒 갱신: {dt_now.strftime('%m-%d %H:%M:%S EST')}",
            ]
        )
        return "\n".join(lines)

    def _build_sync_instruction_message(
        self,
        st: Dict[str, Any],
        holdings: Dict[str, Dict[str, Any]],
        live_price: float,
        broker_bp_usd: float,
        fx_rate: float,
        now_est: datetime,
    ) -> str:
        """
        # 📜 /sync 사용자 중심 초슬림 지층 지시서 메시지 생성 (7칸 공백 들여쓰기 및 Case 77 예비시드 / Case 78 잔량 상태 적용)
        """
        h_info = (holdings or {}).get(TARGET_SYMBOL, {})
        lp = safe_float(
            live_price,
            safe_float(
                h_info.get("last_price"),
                safe_float(st.get("anchor_price"), 0.0),
            ),
        )
        summary = summarize_stratum_portfolio(st, live_price=lp)

        init_seed = safe_float(summary.get("initial_seed_usd"), 10000.0)
        free_cash = safe_float(summary.get("free_cash_usd"), 0.0)
        actual_inv = safe_float(summary.get("actual_invested_usd"), 0.0)

        held_sh = safe_int(summary.get("held_shares"), 0)
        held_tiers = safe_int(summary.get("held_tiers"), 0)
        held_lots = safe_int(summary.get("held_lots"), 0)
        l1_rem_q = safe_int(summary.get("l1_rem_quota_qty"), 0)
        l1_target_q = safe_int(summary.get("l1_target_quota_qty"), 0)
        actual_avg = safe_float(summary.get("actual_avg_price"), 0.0)
        upper_wma = safe_float(summary.get("upper_wma_price"), 0.0)
        locked_min_p = safe_float(summary.get("cycle_min_buy_price"), 0.0)

        used_res_cnt = safe_int(summary.get("used_reserve_portions_cnt"), 0)
        max_res_cnt = safe_int(
            summary.get("max_reserve_portions"), MAX_RESERVE_PORTIONS
        )
        inj_res_usd = safe_float(summary.get("injected_reserve_usd"), 0.0)
        cum_repaid_usd = safe_float(
            summary.get("cumulative_reserve_repaid_usd"), 0.0
        )
        unalloc_dep_usd = max(0.0, safe_float(broker_bp_usd, 0.0) - free_cash)
        rem_note = (
            f" · 🎯1층잔량 {l1_rem_q}/{l1_target_q}주 대기"
            if l1_rem_q > 0
            else ""
        )

        lines = [
            "📜 <b>[스나이퍼 지시서]</b>",
            f"💵 설정 기준시드: <b>${init_seed:,.2f}</b>",
            f"🏦 스나이퍼 가용현금: <b>${free_cash:,.2f}</b>",
            f"       토스 실주문가능: ${broker_bp_usd:,.2f} (입금여력 +${unalloc_dep_usd:,.2f})",
            f"💉 예비시드 탄창: 사용 <b>{used_res_cnt}/{max_res_cnt}회분</b> (수혈잔액 ${inj_res_usd:,.2f} · 누적상환 ${cum_repaid_usd:,.2f})",
            f"📦 보유 그리드 합계: <b>{held_sh}주</b> ({held_tiers}개층 · {held_lots}회차 · 순수매수원금 ${actual_inv:,.2f}{rem_note})",
            f"📐 전체 순수평단: <b>${actual_avg:.2f}</b> · 2~7층 통합이평: <b>${upper_wma:.2f}</b> (기억저가 ${locked_min_p:.2f})",
            "──────────────",
            f"🕒 동기화 시각: {now_est.strftime('%Y-%m-%d %H:%M:%S EST')}",
        ]
        return "\n".join(lines)

    def _build_settlement_control_message(
        self, st: Dict[str, Any], live_price: float, now_est: datetime
    ) -> str:
        """
        # ⚙️ /settlement 사용자 중심 초슬림 전술 제어반 메시지 생성 (0️⃣ ~ 4️⃣ 넘버링 및 10000 예시 적용)
        """
        lp = safe_float(live_price, safe_float(st.get("anchor_price"), 100.0))
        summary = summarize_stratum_portfolio(st, live_price=lp)

        is_active = bool(st.get("is_active", True))
        power_str = "🟢 가동 중 (ON)" if is_active else "🔴 일시정지 (OFF)"
        init_seed = safe_float(summary.get("initial_seed_usd"), 10000.0)
        free_cash = safe_float(summary.get("free_cash_usd"), 0.0)
        real_eq = safe_float(summary.get("realized_equity_usd"), init_seed)
        next_bud = safe_float(
            summary.get("next_portion_budget"), init_seed * 0.08
        )
        quota_badge_str = _format_case67_quota_badge(summary)
        held_sh = safe_int(summary.get("held_shares"), 0)
        held_tiers = safe_int(summary.get("held_tiers"), 0)
        held_lots = safe_int(summary.get("held_lots"), 0)
        l1_rem_q = safe_int(summary.get("l1_rem_quota_qty"), 0)
        l1_target_q = safe_int(summary.get("l1_target_quota_qty"), 0)
        used_res_cnt = safe_int(summary.get("used_reserve_portions_cnt"), 0)
        avail_res_cnt = safe_int(
            summary.get("avail_reserve_portions"), MAX_RESERVE_PORTIONS
        )
        max_res_cnt = safe_int(
            summary.get("max_reserve_portions"), MAX_RESERVE_PORTIONS
        )
        inj_res_usd = safe_float(summary.get("injected_reserve_usd"), 0.0)
        rem_note = (
            f" · 🎯1층잔량 {l1_rem_q}/{l1_target_q}주 대기"
            if l1_rem_q > 0
            else ""
        )

        lines = [
            "⚙️ <b>[전술 제어반]</b>",
            f"0️⃣ 마스터 전원: <b>{power_str}</b>",
            f"1️⃣ 기준 시드머니: <b>${init_seed:,.2f}</b> (실현기준 총자산 ${real_eq:,.2f})",
            f"2️⃣ 차기 1회(8%) 정량: 예산 <b>${next_bud:,.2f}</b> ➔ {quota_badge_str} (가용현금 ${free_cash:,.2f})",
            f"3️⃣ 현재 보유 지층: <b>{held_sh}주</b> ({held_tiers}개층 · {held_lots}회차{rem_note})",
            f"4️⃣ 예비시드 탄창: 사용 <b>{used_res_cnt}/{max_res_cnt}회분</b> (수혈잔액 ${inj_res_usd:,.2f} · 잔여한도 {avail_res_cnt}회분)",
            "──────────────",
            "💡 시드머니를 변경하시려면 아래 <b>[💵 기준 시드머니($) 설정]</b> 버튼을 누른 뒤 숫자(예: <code>10000</code>)를 입력하거나, <code>/seed 10000</code> 명령어를 입력하세요.",
            f"🕒 기준 시각: {now_est.strftime('%m-%d %H:%M:%S EST')}",
        ]
        return "\n".join(lines)

    # -----------------------------------------------------------------------
    # 실시간 시세/잔고 갱신 및 명령어/콜백 핸들러 (문단 하단 중복 인라인 버튼 제거)
    # -----------------------------------------------------------------------
    async def _refresh_live_price_and_metrics(
        self,
    ) -> Tuple[float, Dict[str, Any]]:
        now_est = datetime.now(EST_TZ)
        live_p = safe_float(
            self.context.latest_prices.get(TARGET_SYMBOL), 0.0
        )
        try:
            p_map = await self.context.api.get_current_prices_batch(
                (TARGET_SYMBOL,)
            )
            fetched_p = safe_float(p_map.get(TARGET_SYMBOL), 0.0)
            if fetched_p > 0.0:
                live_p = fetched_p
                self.context.latest_prices[TARGET_SYMBOL] = live_p
        except Exception:
            pass

        base_met = self.context.candle_metrics_cache.get(TARGET_SYMBOL, {})
        met = refresh_metrics_with_live_tick(
            base_met, live_p, now_est=now_est
        )
        self.context.candle_metrics_cache[TARGET_SYMBOL] = met
        if live_p <= 0.0:
            live_p = safe_float(met.get("live_price"), 0.0)
        return live_p, met

    async def _render_and_send_avwap(
        self, chat_id: str, edit_msg_id: Optional[int] = None
    ) -> None:
        """
        # 하단 고정 메뉴와 중복되는 문단 아래 인라인 버튼 부착 제거(reply_markup=None)
        """
        live_p, met = await self._refresh_live_price_and_metrics()
        st = self.context.ledger.get_state(TARGET_SYMBOL)
        msg = self._build_avwap_radar_message(
            st=st,
            metrics=met,
            live_price=live_p,
            now_est=datetime.now(EST_TZ),
        )
        await self.edit_or_send_message(
            chat_id=chat_id,
            message_id=edit_msg_id,
            text=msg,
            reply_markup=None,
        )

    async def _render_and_send_sync(
        self, chat_id: str, edit_msg_id: Optional[int] = None
    ) -> None:
        """
        # 하단 고정 메뉴와 중복되는 문단 아래 인라인 버튼 부착 제거(reply_markup=None)
        # [Case 77]: 사용자가 입금 후 /sync 를 누르면 60초 입금 대기 타임쉴드를 즉시 해제하고
        # wakeup_event.set() 을 호출하여 다음 루프에서 즉시 온디맨드 수혈 및 매수가 집행되도록 연동!
        """
        now_est = datetime.now(EST_TZ)
        live_p, _ = await self._refresh_live_price_and_metrics()
        holdings_map, fetch_ok = (
            await self.context.api.get_holdings_map_with_status()
        )
        if fetch_ok and isinstance(holdings_map, dict):
            self.context.latest_holdings = holdings_map
            self.context.holdings_fetch_ok = True
            await _call_plugin_adaptive(
                reconcile_stratum_with_broker_holdings_plugin,
                context=self.context,
                holdings=holdings_map,
                prices={TARGET_SYMBOL: live_p},
                now_est=now_est,
                force_sync=False,
            )
        else:
            holdings_map = self.context.latest_holdings

        bp_usd = await self.context.api.get_buying_power_usd(
            safety_buffer_pct=0.0
        )
        fx_rate = await self.context.api.get_usd_krw_rate()
        st = self.context.ledger.get_state(TARGET_SYMBOL)

        if bool(st.get("waiting_reserve_deposit", False)):
            mark_reserve_deposit_check_shield(
                self.context, TARGET_SYMBOL, clear_shield=True
            )
            st = await self.context.ledger.update_state(
                TARGET_SYMBOL, last_reserve_check_ts=0.0
            )
            self.context.wakeup_event.set()

        msg = self._build_sync_instruction_message(
            st=st,
            holdings=holdings_map,
            live_price=live_p,
            broker_bp_usd=bp_usd,
            fx_rate=fx_rate,
            now_est=now_est,
        )
        await self.edit_or_send_message(
            chat_id=chat_id,
            message_id=edit_msg_id,
            text=msg,
            reply_markup=None,
        )

    async def _render_and_send_settlement(
        self, chat_id: str, edit_msg_id: Optional[int] = None
    ) -> None:
        live_p, _ = await self._refresh_live_price_and_metrics()
        st = self.context.ledger.get_state(TARGET_SYMBOL)
        msg = self._build_settlement_control_message(
            st=st, live_price=live_p, now_est=datetime.now(EST_TZ)
        )
        await self.edit_or_send_message(
            chat_id=chat_id,
            message_id=edit_msg_id,
            text=msg,
            reply_markup=_build_settlement_inline_keyboard(
                bool(st.get("is_active", True))
            ),
        )

    async def _apply_new_seed_value(
        self, chat_id: str, raw_num_str: str
    ) -> None:
        cleaned = (
            str(raw_num_str)
            .replace(",", "")
            .replace("$", "")
            .replace("불", "")
            .replace("달러", "")
            .strip()
        )
        try:
            val = float(cleaned)
        except Exception:
            return
        if val < 100.0 or val > 10000000.0:
            await self.send_message(
                chat_id=chat_id,
                text="⚠️ 시드머니는 <b>$100 ~ $10,000,000</b> 사이의 숫자로 입력해 주세요. (예: <code>10000</code>)",
            )
            return

        mark_reserve_deposit_check_shield(
            self.context, TARGET_SYMBOL, clear_shield=True
        )
        updated_st = await self.context.ledger.update_state(
            TARGET_SYMBOL,
            initial_seed_usd=round(val, 4),
            seed_explicitly_set_100=bool(abs(val - 100.0) < 1e-6),
            waiting_reserve_deposit=False,
            waiting_reserve_deposit_alert_sent=False,
            required_reserve_deposit_usd=0.0,
            last_reserve_check_ts=0.0,
        )
        self.context.wakeup_event.set()
        live_p, _ = await self._refresh_live_price_and_metrics()
        summary = summarize_stratum_portfolio(updated_st, live_price=live_p)
        quota_badge_str = _format_case67_quota_badge(summary)
        await self.send_message(
            chat_id=chat_id,
            text=(
                "✅ <b>[기준 시드머니 설정 완료]</b>\n"
                f"🔸 새 기준 시드머니: <b>${val:,.2f}</b>\n"
                f"🔸 가용 현금시드: <b>${safe_float(summary.get('free_cash_usd'), 0.0):,.2f}</b>\n"
                f"🔸 차기 1회(8%) 예산: <b>${safe_float(summary.get('next_portion_budget'), 0.0):,.2f}</b> "
                f"➔ {quota_badge_str}"
            ),
            reply_markup=_build_settlement_inline_keyboard(
                bool(updated_st.get("is_active", True))
            ),
        )

    async def _reset_realized_profit_only(self, chat_id: str) -> None:
        """
        # [Case 02, Case 74, Case 76 & Case 77]:
        보유 중인 주식 지층(buckets · 1~7층 개별 단가 · 정적 기억저가 cycle_min_buy_price)과
        설정된 기준 시드머니(initial_seed_usd)는 100% 보존하고, 오직 누적/당일 세후 실현수익금 및
        자투리 절약금·스텝업 해금 횟수(cond_unlock_buy_events)·예비시드 통계·입금 알림 래치만 0점으로 초기화하여
        설정된 기준 시드머니의 8% 정량 투입으로 복귀시킨다.
        """
        mark_reserve_deposit_check_shield(
            self.context, TARGET_SYMBOL, clear_shield=True
        )
        st_cur = self.context.ledger.get_state(TARGET_SYMBOL)
        has_buckets = bool(st_cur.get("buckets"))
        reset_kw: Dict[str, Any] = {
            "cumulative_realized_gross_usd": 0.0,
            "cumulative_realized_fee_usd": 0.0,
            "cumulative_realized_net_usd": 0.0,
            "daily_realized_net_usd": 0.0,
            "cumulative_leftover_saved_usd": 0.0,
            "daily_leftover_saved_usd": 0.0,
            "seed_protect_pass_cnt": 0,
            "daily_seed_protect_pass_cnt": 0,
            "cond_unlock_buy_events": 0,
            "daily_unlock_buy_events": 0,
            "total_reserve_injected_cnt": 0,
            "daily_reserve_injected_cnt": 0,
            "cumulative_reserve_repaid_usd": 0.0,
            "dust_guard_blocked_cnt": 0,
            "daily_dust_guard_blocked_cnt": 0,
            "waiting_reserve_deposit": False,
            "waiting_reserve_deposit_alert_sent": False,
            "required_reserve_deposit_usd": 0.0,
            "last_reserve_check_ts": 0.0,
            "extra_13plus_buy_events": 0,
            "total_buy_events": 0,
            "daily_buy_events": 0,
            "total_sell_events": 0,
            "total_sold_shares": 0,
            "win_sell_events": 0,
            "daily_sell_events": 0,
            "indiv_grid_sell_cnt": 0,
            "daily_indiv_grid_sell_cnt": 0,
            "wma_grad_sell_cnt": 0,
            "daily_wma_grad_sell_cnt": 0,
            "reanchor_cnt": 0,
            "daily_reanchor_cnt": 0,
            "cumulative_reanchor_drop_usd": 0.0,
        }
        if not has_buckets:
            reset_kw["used_reserve_portions_cnt"] = 0
            reset_kw["injected_reserve_usd"] = 0.0

        st_reset = await self.context.ledger.update_state(
            TARGET_SYMBOL, **reset_kw
        )
        snap_fn = getattr(
            self.context.ledger, "create_daily_backup_snapshot", None
        )
        if callable(snap_fn):
            try:
                await snap_fn()
            except Exception:
                pass

        self.context.wakeup_event.set()
        live_p, _ = await self._refresh_live_price_and_metrics()
        summary = summarize_stratum_portfolio(st_reset, live_price=live_p)
        init_seed = safe_float(summary.get("initial_seed_usd"), 10000.0)
        free_cash = safe_float(summary.get("free_cash_usd"), 0.0)
        next_bud = safe_float(
            summary.get("next_portion_budget"), init_seed * 0.08
        )
        quota_badge_str = _format_case67_quota_badge(summary)
        held_sh = safe_int(summary.get("held_shares"), 0)
        held_tiers = safe_int(summary.get("held_tiers"), 0)
        held_lots = safe_int(summary.get("held_lots"), 0)

        await self.send_message(
            chat_id=chat_id,
            text=(
                "🧹 <b>[실현수익 0점 초기화 완료]</b>\n"
                "🔸 누적 세후실현익: <b>$0.00</b> (자투리절약 <b>$0.00</b> · 🔓스텝업해금 <b>0회</b>)\n"
                f"🔸 복귀 기준시드: <b>${init_seed:,.2f}</b> (가용현금 <b>${free_cash:,.2f}</b>)\n"
                f"🔸 차기 1회(8%) 정량: 예산 <b>${next_bud:,.2f}</b> ➔ {quota_badge_str}\n"
                f"🔸 보유 지층 보존: <b>{held_sh}주</b> ({held_tiers}개층 · {held_lots}회차 유지)"
            ),
        )

    async def _execute_manual_update_command(self, chat_id: str) -> None:
        """
        # 사용자 중심 초슬림 시스템 업데이트 개시 및 검증 통과 메시지 타전
        """
        await self._ack_telegram_offset(self._last_update_id)
        await self.send_message(
            chat_id=chat_id,
            text=(
                "⏳ <b>[시스템 업데이트 개시]</b>\n"
                "🔸 GitHub 최신 코드 동기화 및 9대 코어 모듈 프리플라이트 검증 중..."
            ),
        )
        fn_upd = getattr(
            plugin_updater, "execute_git_pull_and_preflight", None
        )
        changed = False
        if callable(fn_upd):
            upd_res = await _call_plugin_adaptive(
                fn_upd, base_dir=self.context.base_dir
            )
            if isinstance(upd_res, tuple):
                ok = bool(upd_res[0]) if len(upd_res) >= 1 else False
                if len(upd_res) >= 3 and isinstance(upd_res[2], bool):
                    changed = bool(upd_res[2])
                str_parts = [
                    str(x).strip()
                    for x in upd_res[1:]
                    if isinstance(x, str) and str(x).strip()
                ]
                msg = (
                    " · ".join(str_parts)
                    if str_parts
                    else "✅ 9대 코어 모듈 인메모리 컴파일 및 AST 심볼 정합성 100% 통과 · 원장 보존"
                )
            else:
                ok = bool(upd_res)
                msg = "✅ 9대 코어 모듈 인메모리 컴파일 및 AST 심볼 정합성 100% 통과 · 원장 보존"
        else:
            ok, msg = verify_all_modules_compile(self.context.base_dir)

        await self._ack_telegram_offset(self._last_update_id)

        if not ok:
            await self.send_message(
                chat_id=chat_id,
                text=f"⚠️ <b>[업데이트 중단 · 기존 원장 안전 보존]</b>\n{_escape_html(msg)}",
            )
            return

        if not changed:
            await self.send_message(
                chat_id=chat_id,
                text=(
                    "✅ <b>[최신 버전 검증 완료 · 무중단 가동 유지]</b>\n"
                    "🔸 원격 변경사항이 없으므로 재기동 없이 현재 스나이퍼 엔진과 원장을 계속 유지합니다."
                ),
            )
            return

        await self.send_message(
            chat_id=chat_id,
            text=(
                "🚀 <b>[신규 업데이트 검증 통과]</b>\n"
                "🔸 원장 데이터 100% 보존 상태로 잠시 후 스나이퍼 데몬을 재기동합니다..."
            ),
        )
        await asyncio.sleep(0.5)
        os._exit(0)

    async def _handle_command_or_text(
        self, chat_id: str, raw_text: str
    ) -> None:
        text = str(raw_text or "").strip()
        if not text:
            return

        if not self.chat_id and chat_id:
            self.chat_id = str(chat_id)

        clean_num_check = (
            text.replace(",", "").replace("$", "").replace(".", "").strip()
        )
        if clean_num_check.isdigit():
            prompt_ts = safe_float(
                self._awaiting_seed_input_chats.get(chat_id), 0.0
            )
            if (
                prompt_ts > 0.0
                and (time.monotonic() - prompt_ts)
                <= SEED_INPUT_PROMPT_TIMEOUT_SEC
            ):
                self._awaiting_seed_input_chats.pop(chat_id, None)
                await self._apply_new_seed_value(chat_id, text)
            else:
                self._awaiting_seed_input_chats.pop(chat_id, None)
                await self.send_message(
                    chat_id=chat_id,
                    text=(
                        "🔒 <b>[시드머니 오입력 방지 잠금 안내]</b>\n"
                        "🔸 평시 숫자 오입력으로 인해 시드머니가 변조되는 것을 막기 위해 잠금 상태입니다.\n"
                        "🔸 시드를 변경하시려면 <b>⚙️ 전술 제어반(/settlement)</b> 에서 <b>[💵 기준 시드머니($) 설정]</b> 버튼을 먼저 누르거나, "
                        f"<code>/seed {_escape_html(clean_num_check)}</code> 명령어로 입력해 주세요."
                    ),
                )
            return

        first_token = text.split()[0].lower()
        if "@" in first_token:
            first_token = first_token.split("@", 1)[0]

        if first_token in ("/start", "/menu", "/help") or text == "⬅️ 메인 메뉴":
            st = self.context.ledger.get_state(TARGET_SYMBOL)
            msg = self._build_start_schedule_message(
                st, now_est=datetime.now(EST_TZ)
            )
            await self.send_message(
                chat_id=chat_id,
                text=msg,
                reply_markup=_build_main_reply_keyboard(),
            )
            return

        if (
            first_token in ("/avwap", "/status", "/radar")
            or text == "🔫 스나이퍼 레이더"
        ):
            await self._render_and_send_avwap(chat_id=chat_id)
            return

        if first_token == "/sync" or text in (
            "📜 지층 지시서",
            "🔄 잔고 동기화",
        ):
            await self._render_and_send_sync(chat_id=chat_id)
            return

        if (
            first_token in ("/settlement", "/config")
            or text == "⚙️ 전술 제어반"
        ):
            await self._render_and_send_settlement(chat_id=chat_id)
            return

        if first_token == "/seed":
            parts = text.split(maxsplit=1)
            if len(parts) >= 2:
                self._awaiting_seed_input_chats.pop(chat_id, None)
                await self._apply_new_seed_value(chat_id, parts[1])
            else:
                self._awaiting_seed_input_chats[chat_id] = time.monotonic()
                await self._render_and_send_settlement(chat_id=chat_id)
            return

        # 오직 /reset_profit 만 허용하여 보유 지층(buckets)은 100% 보존하고 실현수익만 0점 초기화!
        if first_token == "/reset_profit":
            await self._reset_realized_profit_only(chat_id=chat_id)
            return

        # 사용자가 실수로 /reset 또는 /reset_seed 를 입력하더라도 보유 지층을 절대 초기화하지 못하도록 원천 차단!
        if first_token in ("/reset", "/reset_seed"):
            await self.send_message(
                chat_id=chat_id,
                text=(
                    "🔒 <b>[지층 리셋 영구 차단 안내]</b>\n"
                    "🔸 보유 중인 주식 지층 보호를 위해 지층 초기화 기능은 비활성화되었습니다.\n"
                    "🔸 보유 주식을 유지한 채 실현수익만 초기화하여 설정된 기준 시드로 복귀하시려면 <code>/reset_profit</code> 명령어를 입력해 주세요."
                ),
            )
            return

        if first_token == "/update" or text == "🚀 시스템 업데이트":
            await self._execute_manual_update_command(chat_id=chat_id)
            return

    async def _handle_callback_query(self, cb: Dict[str, Any]) -> None:
        cb_id = str(cb.get("id") or "").strip()
        data = str(cb.get("data") or "").strip()
        msg_obj = (
            cb.get("message") if isinstance(cb.get("message"), dict) else {}
        )
        chat_obj = (
            msg_obj.get("chat") if isinstance(msg_obj.get("chat"), dict) else {}
        )
        chat_id = str(chat_obj.get("id") or self.chat_id or "").strip()
        msg_id = safe_int(msg_obj.get("message_id"), 0)

        if cb_id:
            await self._call_tg(
                "answerCallbackQuery",
                {"callback_query_id": cb_id},
                timeout_sec=5.0,
            )

        if not chat_id:
            return

        if data == "cmd_avwap":
            await self._render_and_send_avwap(
                chat_id=chat_id, edit_msg_id=msg_id
            )
        elif data == "cmd_sync":
            await self._render_and_send_sync(
                chat_id=chat_id, edit_msg_id=msg_id
            )
        elif data == "cmd_settlement":
            await self._render_and_send_settlement(
                chat_id=chat_id, edit_msg_id=msg_id
            )
        elif data == "cmd_start":
            st = self.context.ledger.get_state(TARGET_SYMBOL)
            msg = self._build_start_schedule_message(
                st, now_est=datetime.now(EST_TZ)
            )
            await self.edit_or_send_message(
                chat_id=chat_id,
                message_id=msg_id,
                text=msg,
                reply_markup=None,
            )
        elif data == "toggle_bot_active":
            st_cur = self.context.ledger.get_state(TARGET_SYMBOL)
            next_act = not bool(st_cur.get("is_active", True))
            await self.context.ledger.update_state(
                TARGET_SYMBOL, is_active=next_act
            )
            if next_act:
                fn_relock = getattr(
                    defense_plugin, "relock_stratum_on_bot_resume", None
                )
                if callable(fn_relock):
                    await _call_plugin_adaptive(
                        fn_relock,
                        context=self.context,
                        now_est=datetime.now(EST_TZ),
                    )
                else:
                    await _call_plugin_adaptive(
                        reconcile_stratum_with_broker_holdings_plugin,
                        context=self.context,
                        holdings=self.context.latest_holdings,
                        prices=self.context.latest_prices,
                        now_est=datetime.now(EST_TZ),
                        force_sync=True,
                    )
            self.context.wakeup_event.set()
            await self._render_and_send_settlement(
                chat_id=chat_id, edit_msg_id=msg_id
            )
        elif data == "prompt_seed_input":
            self._awaiting_seed_input_chats[chat_id] = time.monotonic()
            await self.send_message(
                chat_id=chat_id,
                text=(
                    "💵 <b>[기준 시드머니($) 입력 안내]</b>\n"
                    "🔸 지금부터 <b>5분 이내</b>에 운용할 기준 달러 시드머니 금액을 숫자만 채팅창에 입력해 주세요.\n"
                    "🔸 예시: <code>10000</code> 또는 <code>19000</code>"
                ),
            )
        elif data == "reset_profit_only":
            await self._reset_realized_profit_only(chat_id=chat_id)

    async def run_polling_loop(self) -> None:
        if not _extract_valid_tg_token(self.bot_token):
            self.bot_token, discovered_cid = _discover_telegram_credentials(
                self.context.base_dir, getattr(self.context, "api", None)
            )
            if not self.chat_id and discovered_cid:
                self.chat_id = discovered_cid

        if not _extract_valid_tg_token(self.bot_token):
            logger.error(
                "🚨 유효한 텔레그램 봇 토큰(숫자:영숫자)을 찾을 수 없습니다! 현재 폴더(%s)의 .env 내 TELEGRAM_BOT_TOKEN 을 확인하세요.",
                self.context.base_dir,
            )
            while not self.context.shutdown_event.is_set():
                await asyncio.sleep(10.0)
            return

        await self._call_tg(
            "deleteWebhook", {"drop_pending_updates": False}, timeout_sec=8.0
        )
        await self._flush_stale_updates_on_startup()
        logger.info(
            "📡 [텔레그램 관제탑 폴링 루프 가동 완료] (폴더=%s · chat_id=%s)",
            getattr(self.context, "folder_slug", "default"),
            self.chat_id or "auto-detect",
        )

        while not self.context.shutdown_event.is_set():
            try:
                payload: Dict[str, Any] = {
                    "offset": self._last_update_id + 1,
                    "timeout": 15,
                    "allowed_updates": ["message", "callback_query"],
                }
                res = await self._call_tg(
                    "getUpdates", payload, timeout_sec=20.0
                )
                if isinstance(res, dict) and bool(res.get("ok")):
                    updates = res.get("result")
                    if isinstance(updates, list):
                        for upd in updates:
                            if not isinstance(upd, dict):
                                continue
                            uid = safe_int(upd.get("update_id"), 0)
                            if uid > self._last_update_id:
                                self._last_update_id = uid
                                try:
                                    await self.context.ledger.update_state(
                                        TARGET_SYMBOL, last_tg_update_id=uid
                                    )
                                except Exception:
                                    pass

                            if isinstance(upd.get("callback_query"), dict):
                                await self._handle_callback_query(
                                    upd["callback_query"]
                                )
                            elif isinstance(upd.get("message"), dict):
                                m_obj = upd["message"]
                                c_obj = (
                                    m_obj.get("chat")
                                    if isinstance(m_obj.get("chat"), dict)
                                    else {}
                                )
                                cid = str(
                                    c_obj.get("id") or self.chat_id or ""
                                ).strip()
                                if self.chat_id and cid and cid != self.chat_id:
                                    continue
                                txt = str(m_obj.get("text") or "").strip()
                                msg_date = safe_float(m_obj.get("date"), 0.0)
                                if (
                                    msg_date > 0.0
                                    and msg_date < (self._boot_epoch - 1.0)
                                    and (
                                        txt.lower().startswith("/update")
                                        or txt == "🚀 시스템 업데이트"
                                    )
                                ):
                                    await self._ack_telegram_offset(uid)
                                    continue
                                if txt:
                                    await self._handle_command_or_text(
                                        chat_id=cid, raw_text=txt
                                    )
                else:
                    await asyncio.sleep(1.5)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.debug("텔레그램 폴링 루프 일시 예외: %s", exc)
                await asyncio.sleep(2.0)


async def _run_auto_update_loop_dynamic(
    context: Any, interval_sec: float = 3600.0
) -> None:
    fn = _resolve_module_attr(
        modules=(plugin_updater,),
        candidate_names=(
            "run_auto_update_loop",
            "auto_update_loop",
            "start_auto_update_loop",
            "background_auto_update_loop",
        ),
        predicate=lambda f: (
            inspect.iscoroutinefunction(f) and "loop" in f.__name__.lower()
        ),
    )
    if callable(fn):
        await _call_plugin_adaptive(
            fn, context=context, interval_sec=interval_sec
        )
        return

    while not context.shutdown_event.is_set():
        try:
            await asyncio.wait_for(
                context.shutdown_event.wait(), timeout=interval_sec
            )
        except asyncio.TimeoutError:
            pass


# ---------------------------------------------------------------------------
# [핵심 2] 스나이퍼 애플리케이션 전역 컨텍스트 (SniperAppContext — Case 68 폴더별 3중 원장 결속)
# ---------------------------------------------------------------------------
class SniperAppContext:
    """
    9대 코어 모듈이 공유하는 단일 런타임 상태 컨텍스트 (Case 68 폴더 위치 기반 격리 적용).
    """

    def __init__(self, base_dir: Optional[str] = None) -> None:
        _install_toss_api_compatibility_patches()
        self.base_dir: str = get_bot_base_dir(base_dir)
        (
            self.primary_ledger_path,
            self.ledger_path,
            self.backup_ledger_path,
            self.folder_slug,
        ) = resolve_folder_isolated_ledger_paths(base_dir=self.base_dir)

        self.api: TossApiClient = TossApiClient(base_dir=self.base_dir)
        self.ledger: Any = _instantiate_stratum_ledger(
            filepath=self.ledger_path, base_dir=self.base_dir
        )

        self.in_memory_ordering_lock: asyncio.Lock = asyncio.Lock()
        self.dual_strike_mutex: asyncio.Lock = asyncio.Lock()
        self.wakeup_event: asyncio.Event = asyncio.Event()
        self.shutdown_event: asyncio.Event = asyncio.Event()

        self.latest_prices: Dict[str, float] = {TARGET_SYMBOL: 0.0}
        self.latest_holdings: Dict[str, Dict[str, Any]] = {
            TARGET_SYMBOL: _empty_soxl_holding_entry()
        }
        self.holdings_fetch_ok: bool = False
        self.candle_metrics_cache: Dict[str, Dict[str, Any]] = {}
        self.exit_snapshot_cache: Dict[str, Dict[str, Any]] = {}
        self.indexing_grace_cache: Dict[str, Dict[str, Any]] = {}

        self._strike_hold_alert_ts: Dict[str, float] = {}
        self.last_0400_sync_date: str = ""
        self.fast_shield_mode: bool = False

        self.tg: _AdaptiveTelegramBridge = _AdaptiveTelegramBridge(
            context=self
        )

    async def send_slim_alert(self, title: str, body: str = "") -> bool:
        return await self.tg.send_slim_alert(title=title, body=body)

    async def send_strike_hold_alert_once(
        self,
        symbol: str,
        reason_key: str,
        message: str,
        cooldown_sec: float = 1800.0,
    ) -> None:
        # Case 79: 데이마켓/애프터마켓 시세 결측이나 거래 제한 관련 사유는 절대 알림을 보내지 않고 100% 묵음 처리
        r_lower = str(reason_key or "").lower()
        if any(
            k in r_lower
            for k in (
                "daymarket",
                "extended",
                "restrict",
                "no_price",
                "no_live_price",
                "hours_closed",
            )
        ):
            return
        key = f"{symbol}:{reason_key}"
        now_m = time.monotonic()
        last_m = self._strike_hold_alert_ts.get(key, 0.0)
        if (now_m - last_m) < cooldown_sec:
            return
        self._strike_hold_alert_ts[key] = now_m
        await self.send_slim_alert(
            title=f"⚠️ [{symbol} 7층 골디락스 스나이퍼 안내]",
            body=message,
        )


# ---------------------------------------------------------------------------
# [핵심 3] 백그라운드 태스크 1 : 1분봉 시계열 및 10분 게이트 지표 레이더 (candle_radar_loop)
# ---------------------------------------------------------------------------
async def candle_radar_loop(context: SniperAppContext) -> None:
    """
    # MODIFIED [Case 79]:
    데이마켓/애프터마켓에서 브로커가 캔들 데이터를 제공하지 않거나 일시 오류가 발생하더라도
    경고 로그나 알림 스팸 없이 조용히 디버그 로깅으로 묵음 처리한다.
    """
    while not context.shutdown_event.is_set():
        now_est = datetime.now(EST_TZ)
        hm = now_est.hour * 100 + now_est.minute
        in_market = bool(
            (400 <= hm <= 1605)
            and not _check_weekend_nyse_closed_dynamic(now_est)
        )
        sleep_sec = 5.0 if in_market else 20.0

        try:
            candles_1m = await context.api.get_candles_1m(
                symbol=TARGET_SYMBOL, total_count=300
            )
            candles_1d = await context.api.get_candles_1d(
                symbol=TARGET_SYMBOL, count=10
            )
            live_p = safe_float(
                context.latest_prices.get(TARGET_SYMBOL),
                safe_float(
                    context.latest_holdings.get(TARGET_SYMBOL, {}).get(
                        "last_price"
                    ),
                    0.0,
                ),
            )
            metrics = await _compute_candle_metrics_dynamic(
                context=context,
                candles_1m=candles_1m,
                live_price=live_p,
                now_est=now_est,
                candles_1d=candles_1d,
            )
            context.candle_metrics_cache[TARGET_SYMBOL] = metrics
            if (
                live_p <= 0.0
                and safe_float(metrics.get("live_price"), 0.0) > 0.0
            ):
                context.latest_prices[TARGET_SYMBOL] = safe_float(
                    metrics.get("live_price"), 0.0
                )
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.debug("SOXL 캔들 레이더 루프 폴백(묵음): %s", exc)

        try:
            await asyncio.wait_for(
                context.shutdown_event.wait(), timeout=sleep_sec
            )
        except asyncio.TimeoutError:
            pass


# ---------------------------------------------------------------------------
# [핵심 4] 백그라운드 태스크 2 : 매수(04:07 ~ 16:00 EST) & 익절 매도(24시간 전 세션) 메인 지층 스나이퍼 루프 (main_sniper_loop)
# ---------------------------------------------------------------------------
def _evaluate_fast_shield_mode(
    context: SniperAppContext,
    now_est: datetime,
    live_p: float,
) -> bool:
    """
    # MODIFIED [Case 70 & Case 79]:
    - 평시 보유 중 매도 모니터 및 1층 미체결 잔량(TOPUP_1FL) 모니터는 매 1.5초(NORMAL_LOOP_INTERVAL_SEC)마다 실시간 타점 감시를 수행한다.
    - 0.4초 고속 루프(FAST_SHIELD_LOOP_INTERVAL_SEC)는 프리·정규·애프터·데이마켓 전 구간(is_active_sell_window)에서
      미체결 주문(buy_order_id / sell_order_id) 체결 확인 시점 및 04:07 ~ 16:00 EST 의 10분 매수 게이트 정각 오픈 경계에서 작동한다.
    """
    hm = now_est.hour * 100 + now_est.minute
    if not is_active_sell_window(hm, now_est=now_est):
        return False

    st = context.ledger.get_state(TARGET_SYMBOL)
    if not bool(st.get("is_active", True)):
        return False

    if str(st.get("buy_order_id") or "").strip() or str(
        st.get("sell_order_id") or ""
    ).strip():
        return True

    if is_active_buy_window(hm, now_est=now_est):
        is_gate_open, _, _, b_info = evaluate_buy_gate_bucket_status(
            now_est=now_est,
            buy_interval_min=LOCKED_BUY_INTERVAL_MIN,
            last_evaluated_bucket_id=safe_int(
                st.get("last_evaluated_buy_bucket_id"), -1
            ),
            last_evaluated_date=str(st.get("last_evaluated_date") or ""),
        )
        if is_gate_open and bool(b_info.get("is_exact_boundary_min")):
            return True

    return False


async def main_sniper_loop(context: SniperAppContext) -> None:
    """
    # MODIFIED [Case 66, Case 70 ~ Case 79]:
    - 04:00 ~ 04:06 EST : 프리장 개장 초기 호가 안정화 및 직전 데이마켓 미결 주문 선행 정산 후 잔류 미체결 취소
    - 04:07 ~ 16:00 EST : 프리장 + 정규장 (매수 게이트 + ⚡1.5초 실시간 익절 매도 모니터 동시 가동)
    - 16:00 ~ 19:59 EST : 애프터마켓 (16:00 일일 결산 보고 단 1회 실행 직후 루프 중단 없이 ⚡1.5초 실시간 익절 매도 모니터 연속 가동 · 매수 잠금)
    - 20:00 ~ 03:59 EST : 데이마켓 (⚡1.5초 실시간 익절 매도 모니터 상시 가동 · 매수 잠금 · 브로커 시세 미제공/거래 제한 시 100% 묵음 대기)
    """
    while not context.shutdown_event.is_set():
        now_est = datetime.now(EST_TZ)
        hm = now_est.hour * 100 + now_est.minute

        try:
            if _check_weekend_nyse_closed_dynamic(now_est):
                context.fast_shield_mode = False
                try:
                    await asyncio.wait_for(
                        context.shutdown_event.wait(), timeout=15.0
                    )
                except asyncio.TimeoutError:
                    pass
                continue

            is_ext_sell_only = is_extended_sell_only_window(
                hm, now_est=now_est
            )

            price_map = await context.api.get_current_prices_batch(
                (TARGET_SYMBOL,)
            )
            fresh_tick_p = safe_float(price_map.get(TARGET_SYMBOL), 0.0)
            live_p = fresh_tick_p
            if live_p > 0.0:
                context.latest_prices[TARGET_SYMBOL] = live_p

            holdings_map, fetch_ok = (
                await context.api.get_holdings_map_with_status()
            )
            context.holdings_fetch_ok = fetch_ok
            if fetch_ok and isinstance(holdings_map, dict):
                context.latest_holdings = holdings_map
                # Case 79: 프리장/정규장에서만 holdings.last_price 폴백을 허용하고,
                # 데이마켓/애프터마켓(is_ext_sell_only)에서 시세 API 가 0.0 을 반환한 날에는
                # 정적 종가(last_price)로 매도 모니터가 오발주하지 않도록 fresh_tick_p 만 신뢰한다.
                if live_p <= 0.0 and not is_ext_sell_only:
                    live_p = safe_float(
                        holdings_map.get(TARGET_SYMBOL, {}).get("last_price"),
                        0.0,
                    )
                    if live_p > 0.0:
                        context.latest_prices[TARGET_SYMBOL] = live_p

            if (
                live_p > 0.0
                and TARGET_SYMBOL in context.candle_metrics_cache
                and isinstance(
                    context.candle_metrics_cache[TARGET_SYMBOL], dict
                )
            ):
                context.candle_metrics_cache[TARGET_SYMBOL] = (
                    refresh_metrics_with_live_tick(
                        context.candle_metrics_cache[TARGET_SYMBOL],
                        live_p,
                        now_est=now_est,
                    )
                )

            prices = dict(context.latest_prices)
            # Case 79: 애프터/데이마켓에서는 실제로 방금 조회된 실시간 시세(fresh_tick_p)만 매도 모니터에 전달!
            prices_for_sell = (
                {TARGET_SYMBOL: fresh_tick_p}
                if is_ext_sell_only
                else prices
            )
            holdings = dict(context.latest_holdings)

            if 400 <= hm <= 406:
                prev_0400_date = str(
                    getattr(context, "last_0400_sync_date", "") or ""
                )
                today_0400_str = now_est.strftime("%Y-%m-%d")
                await _call_plugin_adaptive(
                    execute_0400_premarket_stabilization_plugin,
                    context=context,
                    holdings=holdings,
                    prices=prices,
                    now_est=now_est,
                )
                # 🚨 Case 74, Case 76 & Case 77: 00:00 EST 에 logical_date 가 먼저 롤오버되었더라도
                # 04:00 EST 오프닝 시점에 일일 카운터는 0회로 확실히 리셋하되, 단 1회 입금 알림 래치는 보존!
                if prev_0400_date != today_0400_str:
                    await context.ledger.update_state(
                        TARGET_SYMBOL,
                        daily_seed_protect_pass_cnt=0,
                        daily_unlock_buy_events=0,
                        daily_reserve_injected_cnt=0,
                        daily_dust_guard_blocked_cnt=0,
                        pending_step_up_min_price=0.0,
                        last_evaluated_buy_bucket_id=-1,
                        last_evaluated_date=today_0400_str,
                        last_reentry_eval_ts=0.0,
                        last_reserve_check_ts=0.0,
                    )

            elif is_active_sell_window(hm, now_est=now_est):
                # 🌙 [Step 3-A · Case 79] 16:00 ~ 16:59 EST 정규장 마감 진입 시 일일 결산 보고를 단 1회 실행하되,
                # 루프를 건너뛰지 않고 즉시 아래 애프터마켓 실시간 익절 매도 감시로 직결!
                if 1600 <= hm <= 1659:
                    st_chk = context.ledger.get_state(TARGET_SYMBOL)
                    today_close_str = now_est.strftime("%Y-%m-%d")
                    if (
                        str(st_chk.get("last_closing_report_date") or "")
                        != today_close_str
                    ):
                        await _call_plugin_adaptive(
                            execute_1600_daily_closing_settlement_plugin,
                            context=context,
                            holdings=holdings,
                            prices=prices,
                            now_est=now_est,
                        )

                # 🚨 [Step 3-0 · Case 66] 미결 매수/매도 주문 최우선 선행 정산
                st_pre = context.ledger.get_state(TARGET_SYMBOL)
                if str(st_pre.get("buy_order_id") or "").strip():
                    await _call_plugin_adaptive(
                        sync_pending_buy_order_plugin,
                        context=context,
                        holdings=holdings,
                        prices=prices,
                        now_est=now_est,
                    )
                if str(st_pre.get("sell_order_id") or "").strip():
                    await _call_plugin_adaptive(
                        sync_pending_sell_order_plugin,
                        context=context,
                        holdings=holdings,
                        prices=prices,
                        now_est=now_est,
                    )

                # [Step 3-1] 로컬 7층 그리드 원장 ↔ 토스 실보유 잔고 무결성 화해 (24시간 전 세션 작동)
                await _call_plugin_adaptive(
                    reconcile_stratum_with_broker_holdings_plugin,
                    context=context,
                    holdings=holdings,
                    prices=prices,
                    now_est=now_est,
                )

                # ⚡ [Step 3-2 · Case 70, 71, 72, 79] 프리·정규·애프터·데이마켓 24시간 전 세션 매 1.5초 실시간 3중 다중 익절 매도 모니터
                sell_res = await _call_plugin_adaptive(
                    execute_1m_sniper_sell_and_reanchor_plugin,
                    context=context,
                    holdings=holdings,
                    prices=prices_for_sell,
                    now_est=now_est,
                )
                did_sell = bool(
                    isinstance(sell_res, dict)
                    and sell_res.get("did_sell_or_ratchet")
                )

                # 🔵 [Step 3-3 · Case 44, 78, 79] 매수 게이트/모니터는 오직 04:07 ~ 16:00 EST (is_active_buy_window) 구간에서만 가동!
                if not did_sell and is_active_buy_window(hm, now_est=now_est):
                    await _call_plugin_adaptive(
                        execute_seed_protected_buy_gate_plugin,
                        context=context,
                        holdings=holdings,
                        prices=prices,
                        now_est=now_est,
                    )

            else:
                st_idle = context.ledger.get_state(TARGET_SYMBOL)
                if str(st_idle.get("sell_order_id") or "").strip():
                    await _call_plugin_adaptive(
                        sync_pending_sell_order_plugin,
                        context=context,
                        holdings=holdings,
                        prices=prices,
                        now_est=now_est,
                    )
                if str(st_idle.get("buy_order_id") or "").strip():
                    await _call_plugin_adaptive(
                        sync_pending_buy_order_plugin,
                        context=context,
                        holdings=holdings,
                        prices=prices,
                        now_est=now_est,
                    )

            context.fast_shield_mode = _evaluate_fast_shield_mode(
                context=context,
                now_est=now_est,
                live_p=safe_float(
                    context.latest_prices.get(TARGET_SYMBOL), 0.0
                ),
            )

        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.error("메인 7층 그리드 스나이퍼 루프 예외: %s", exc, exc_info=True)

        loop_wait = (
            FAST_SHIELD_LOOP_INTERVAL_SEC
            if context.fast_shield_mode
            else NORMAL_LOOP_INTERVAL_SEC
        )
        context.wakeup_event.clear()
        try:
            await asyncio.wait_for(
                context.wakeup_event.wait(), timeout=loop_wait
            )
        except asyncio.TimeoutError:
            pass


# ---------------------------------------------------------------------------
# [핵심 5] 백그라운드 태스크 3 : 17:00 EST 일일 GC · 날짜별 금고 백업 및 롤오버 루프 (Case 74, Case 76, Case 77, Case 79)
# ---------------------------------------------------------------------------
async def daily_gc_and_rollover_loop(context: SniperAppContext) -> None:
    last_gc_date = ""
    while not context.shutdown_event.is_set():
        now_est = datetime.now(EST_TZ)
        today_str = now_est.strftime("%Y-%m-%d")
        hm = now_est.hour * 100 + now_est.minute

        try:
            if hasattr(context.ledger, "rollover_daily_counters_if_needed"):
                await _call_plugin_adaptive(
                    context.ledger.rollover_daily_counters_if_needed,
                    logical_date=today_str,
                    today_str=today_str,
                )
            if hm >= 1700 and last_gc_date != today_str:
                last_gc_date = today_str
                await execute_daily_1700_gc_and_backup_plugin(
                    context=context, now_est=now_est
                )
                # 🚨 Case 74, Case 76, Case 77 & Case 79: 17:00 EST 일일 마감 롤오버 시 일일 매수/패스 카운터는 0회로 리셋하되
                # 단 1회 입금 요청 알림 영구 래치(waiting_reserve_deposit_alert_sent) 및 애프터장 미결 매도 주문은 보존!
                await context.ledger.update_state(
                    TARGET_SYMBOL,
                    daily_seed_protect_pass_cnt=0,
                    daily_unlock_buy_events=0,
                    daily_reserve_injected_cnt=0,
                    daily_dust_guard_blocked_cnt=0,
                    pending_step_up_min_price=0.0,
                    last_evaluated_buy_bucket_id=-1,
                    last_reentry_eval_ts=0.0,
                )
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.warning("일일 GC/롤오버 루프 예외: %s", exc)

        try:
            await asyncio.wait_for(
                context.shutdown_event.wait(), timeout=30.0
            )
        except asyncio.TimeoutError:
            pass


# ---------------------------------------------------------------------------
# [핵심 6] 시스템 부트스트랩 · 프리플라이트 TDD · Case 11 시그널 0.1초 고속 종료 가드
# ---------------------------------------------------------------------------
async def _run_init_step_with_cancel_guard(
    context: SniperAppContext,
    coro: Awaitable[Any],
    timeout_sec: float = 8.0,
) -> Any:
    """
    Case 11 [부팅 중 SIGTERM 0.1초 고속 종료 가드]:
    부팅 초기화 네트워크 I/O 도중 SIGTERM / SIGINT 시그널이 유입되면
    블로킹 대기 없이 0.1초 이내에 즉시 코루틴을 취소하고 탈출하여
    systemd 의 'State stop-sigterm timed out. Killing.' 현상을 100% 원천 차단한다.
    """
    if context.shutdown_event.is_set():
        try:
            coro.close()  # type: ignore[attr-defined]
        except Exception:
            pass
        return None

    work_task = asyncio.create_task(coro)
    stop_task = asyncio.create_task(context.shutdown_event.wait())
    try:
        done, _ = await asyncio.wait(
            {work_task, stop_task},
            timeout=timeout_sec,
            return_when=asyncio.FIRST_COMPLETED,
        )
        if stop_task in done or context.shutdown_event.is_set():
            work_task.cancel()
            return None
        if work_task in done:
            return work_task.result()
        work_task.cancel()
        return None
    finally:
        if not stop_task.done():
            stop_task.cancel()
        if not work_task.done():
            work_task.cancel()


async def async_main() -> None:
    base_dir = get_bot_base_dir()

    purged = purge_deprecated_legacy_files(base_dir)
    if purged:
        logger.info("🧹 [구버전 폐기 파일 청소 완료] 삭제 목록: %s", purged)

    ok_compile, err_msg = verify_all_modules_compile(base_dir)
    if not ok_compile:
        logger.critical(
            "🚨 [프리플라이트 컴파일/심볼 검증 실패] 기동 중단: %s", err_msg
        )
        sys.exit(1)

    run_quant_engine_tdd()
    logger.info(
        "✅ [QuantEngine TDD 사전 무결성 검증 통과] 챔피언 💉 05_RESV_6P_GUARD30 × 🔓 06_STEP2X_15PCT_C20 (1~6층 개별 + 통합 7층 본대 · 30%% 자투리 가드 & +6회분 자동 수혈/상환 · Case 78 TOPUP_1FL 잔량 합산 · Case 79 애프터/데이장 익절 확장 & 묵음 방어 Case 59~79) 검증 완료"
    )

    context = SniperAppContext(base_dir=base_dir)

    loop = asyncio.get_running_loop()

    def _on_signal() -> None:
        logger.info(
            "🛑 종료 시그널(SIGTERM/SIGINT) 수신 -> 고속 안전 종료 개시..."
        )
        context.shutdown_event.set()
        context.wakeup_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _on_signal)
        except NotImplementedError:
            pass

    if context.shutdown_event.is_set():
        logger.info("✅ [SOXL 7층 골디락스 스나이퍼 안전 종료 완료]")
        return

    try:
        acc_seq = await _run_init_step_with_cancel_guard(
            context, context.api.ensure_account_seq(), timeout_sec=8.0
        )
        if acc_seq is not None:
            logger.info(
                "🏛️ [제2헌법 AccountSeq 락온 완료 · 폴더=%s] accountSeq=%d",
                context.folder_slug,
                acc_seq,
            )
    except Exception as exc:
        logger.warning(
            "⚠️ 초기 AccountSeq 조회 지연 (루프 내 자동 재시도): %s", exc
        )

    if context.shutdown_event.is_set():
        logger.info("✅ [SOXL 7층 골디락스 스나이퍼 안전 종료 완료]")
        return

    try:
        price_map = await _run_init_step_with_cancel_guard(
            context,
            context.api.get_current_prices_batch((TARGET_SYMBOL,)),
            timeout_sec=6.0,
        )
        if (
            isinstance(price_map, dict)
            and safe_float(price_map.get(TARGET_SYMBOL), 0.0) > 0.0
        ):
            context.latest_prices[TARGET_SYMBOL] = safe_float(
                price_map.get(TARGET_SYMBOL), 0.0
            )
        h_res = await _run_init_step_with_cancel_guard(
            context,
            context.api.get_holdings_map_with_status(),
            timeout_sec=6.0,
        )
        if isinstance(h_res, tuple) and len(h_res) == 2:
            holdings_map, fetch_ok = h_res
            context.holdings_fetch_ok = bool(fetch_ok)
            if fetch_ok and isinstance(holdings_map, dict):
                context.latest_holdings = holdings_map
                await _run_init_step_with_cancel_guard(
                    context,
                    reconcile_stratum_with_broker_holdings_plugin(
                        context=context,
                        holdings=holdings_map,
                        prices=context.latest_prices,
                        now_est=datetime.now(EST_TZ),
                        force_sync=True,
                    ),
                    timeout_sec=6.0,
                )
    except Exception as exc:
        logger.warning("초기 잔고/시세 동기화 폴백: %s", exc)

    if context.shutdown_event.is_set():
        logger.info("✅ [SOXL 7층 골디락스 스나이퍼 안전 종료 완료]")
        return

    await _run_init_step_with_cancel_guard(
        context, context.tg._flush_stale_updates_on_startup(), timeout_sec=6.0
    )
    if not context.shutdown_event.is_set():
        await _run_init_step_with_cancel_guard(
            context, context.tg.send_startup_alive_banner(), timeout_sec=6.0
        )

    if context.shutdown_event.is_set():
        logger.info("✅ [SOXL 7층 골디락스 스나이퍼 안전 종료 완료]")
        return

    tasks = [
        asyncio.create_task(candle_radar_loop(context), name="candle_radar"),
        asyncio.create_task(main_sniper_loop(context), name="main_sniper"),
        asyncio.create_task(
            context.tg.run_polling_loop(), name="telegram_polling"
        ),
        asyncio.create_task(
            daily_gc_and_rollover_loop(context), name="daily_gc"
        ),
        asyncio.create_task(
            _run_auto_update_loop_dynamic(context, interval_sec=3600.0),
            name="auto_updater",
        ),
    ]

    logger.info(
        "🚀 [SOXL 7층 골디락스 멀티그리드 스나이퍼 가동 완료 · 폴더=%s] 매수 04:07~16:00 EST & 익절 매도 24시간(프리·정규·애프터·데이장) 전 구간 확장 · 데이장 시세미제공/거래제한 100%% 묵음 방어(Case 65~79)",
        context.folder_slug,
    )

    try:
        await context.shutdown_event.wait()
    finally:
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        close_fn = getattr(context.api, "close", None)
        if callable(close_fn):
            try:
                c_res = close_fn()
                if inspect.isawaitable(c_res):
                    await c_res
            except Exception:
                pass
        logger.info("✅ [SOXL 7층 골디락스 스나이퍼 안전 종료 완료]")


if __name__ == "__main__":
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        pass
