# -*- coding: utf-8 -*-
"""
# MODIFIED: quant_indicators_plugin.py
인피니트 스노우볼 (Infinite Snowball) v3.0 — 순수 롱(SOXL) 매수 04:07 ~ 16:00 EST 제한 &
익절 매도 24시간 전 세션(프리마켓 + 정규장 + 애프터마켓 + 데이마켓) 확장 오버나이트 지층관리 스나이퍼
시계열 100% 벡터화 지표 엔진 및 10분 고정 매수 게이트 버킷 산출 코어 모듈 (Step 02 / 06)
- 제4헌법 & Case 01 & Case 79:
  1) 모든 시계열 및 세션 경계 연산은 미국 동부 시간(EST_TZ = ZoneInfo('America/New_York')) 단일 소스 락온
  2) 매수 허용 시간창(is_active_buy_window : 평일 04:07 ~ 16:00 EST)과
     익절 매도 허용 시간창(is_active_sell_window : 04:00 ~ 04:06 EST 오프닝 안정화 및 주말 휴장 외
     프리마켓 · 정규장 · 애프터마켓[16:00 ~ 19:59 EST] · 데이마켓[20:00 ~ 03:59 EST] 전 구간) 엄격 분리!
  3) 금요일 애프터마켓(16:00 ~ 19:59 EST) 익절 매도를 허용하기 위해 주말 휴장 구간을
     금요일 20:00 EST ~ 일요일 17:59 EST 로 제어 (일요일 18:00 EST 이후 월요일 데이마켓 정상 개방)
- Case 36 & Case 64: 04:07 ~ 16:00 EST 구간 10분 고정 매수 게이트(LOCKED_BUY_INTERVAL_MIN = 10) 버킷 산출 및
  동일 버킷 내 중복 평가 원천 차단(evaluate_buy_gate_bucket_status)
- 벡터화 강제: Pandas DataFrame / NumPy 배열 연산 시 for 루프를 100% 배제하고 벡터화 수식으로만
  프리장(04:00 ~ 09:29 EST) / 정규장(09:30 ~ 16:00 EST) 누적 VWAP, 고/저가 진폭, 5일 이동평균(5MA) 진폭 기반
  예상 변동 밴드, 실시간 하이킨 아시(Heikin-Ashi) 양/음봉 배지 및 Wilder's RSI(14)를 고속 산출한다.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from toss_api import (
    EST_TZ,
    LOCKED_BUY_INTERVAL_MIN,
    TARGET_SYMBOL,
    safe_float,
    safe_int,
)

logger = logging.getLogger("toss_sniper.quant_indicators_plugin")

# 04:07 EST 기준 분(minute of day = 4 * 60 + 7 = 247) 및 16:00 EST 마감 분(16 * 60 = 960) 0칸 표준 정렬
GATE_START_MIN_OF_DAY: int = 4 * 60 + 7   # 247 (04:07 EST)
GATE_END_MIN_OF_DAY: int = 16 * 60        # 960 (16:00 EST)
REGULAR_START_MIN_OF_DAY: int = 9 * 60 + 30  # 570 (09:30 EST)


# ---------------------------------------------------------------------------
# [핵심 1] 매수 시간창(04:07 ~ 16:00 EST) vs 익절 매도 시간창(24시간 전 세션) 및 주말 휴장 판별기 (Case 01 & Case 79)
# ---------------------------------------------------------------------------
def is_weekend_nyse_closed(now_est: Optional[datetime] = None) -> bool:
    """
    # MODIFIED [Case 01 & Case 79]:
    미국 동부 시간(EST/EDT) 기준 주말 휴장 판정:
    - 금요일 애프터마켓(16:00 ~ 19:59 EST) 익절 매도 주문을 허용하기 위해 금요일(wd == 4)은 20:00 EST 부터 휴장으로 판정한다.
    - 토요일(wd == 5) 전 구간 및 일요일(wd == 6) 17:59 EST 까지를 주말 휴장으로 판정하며,
      일요일 18:00 EST 이후(한국 시간 월요일 오전 데이마켓)는 익절 매도 감시를 위해 정상 개장(False)으로 판정한다.
    """
    dt = now_est.astimezone(EST_TZ) if now_est else datetime.now(EST_TZ)
    wd = dt.weekday()  # 월=0, 화=1, ..., 금=4, 토=5, 일=6
    hm = dt.hour * 100 + dt.minute

    if wd == 4 and hm >= 2000:
        return True
    if wd == 5:
        return True
    if wd == 6 and hm < 1800:
        return True
    return False


def is_active_buy_window(
    hm: int, now_est: Optional[datetime] = None
) -> bool:
    """
    # NEW [🎯 2 & Case 01, Case 79 : 매수 전용 시간창 (평일 04:07 ~ 16:00 EST 엄격 제한)]:
    - 모든 매수(0주 첫 진입 REENTRY_1FL · 1층 미체결 잔량 TOPUP_1FL · 1층 공석 60초 주기 재장전 · 10분 와이드/스텝업 추매 DIP_1FL)는
      오직 평일(월~금) 프리장 개시(04:07 EST)부터 정규장 마감(16:00 EST)까지만 허용한다.
    - 애프터마켓(16:01 ~ 19:59 EST) 및 데이마켓(20:00 ~ 03:59 EST, 일요일 저녁 포함)에서는 매수를 100% 차단(False)한다.
    """
    if now_est is not None:
        dt = now_est.astimezone(EST_TZ)
        if is_weekend_nyse_closed(dt) or dt.weekday() >= 5:
            return False
    hm_int = safe_int(hm, 0)
    return 407 <= hm_int <= 1600


def is_active_trading_window(
    hm: int, now_est: Optional[datetime] = None
) -> bool:
    """
    하위 호환 심볼 유지: 기존 매수 게이트 및 10분 버킷 산출기에서 호출하는 함수로
    is_active_buy_window(04:07 ~ 16:00 EST)와 동일하게 작동한다.
    """
    return is_active_buy_window(hm, now_est=now_est)


def is_active_sell_window(
    hm: int, now_est: Optional[datetime] = None
) -> bool:
    """
    # NEW [🎯 2 & Case 79 : 익절 매도 전용 확장 시간창 (프리마켓 + 정규장 + 애프터마켓 + 데이마켓 전 구간 개방)]:
    - 오버나이트를 하면서도 목표 익절가(1층 +1.50% / 2~7층 개별 및 이동평균 +1.00%)에 도달하면
      애프터마켓(16:00 ~ 19:59 EST)과 데이마켓(20:00 ~ 03:59 EST)에서도 즉시 지정가 익절 매도가 나가도록 개방한다.
    - 오직 04:00 ~ 04:06 EST 프리장 오프닝 안정화 구간(7분)과 주말 휴장(금 20:00 ~ 일 17:59 EST)에만 매도 모니터를 멈춘다.
    """
    if now_est is not None:
        dt = now_est.astimezone(EST_TZ)
        if is_weekend_nyse_closed(dt):
            return False
    hm_int = safe_int(hm, 0)
    if 400 <= hm_int <= 406:
        return False
    return True


def is_extended_sell_only_window(
    hm: int, now_est: Optional[datetime] = None
) -> bool:
    """
    # NEW [Case 79 : 장외 익절 매도 전용 구간(애프터마켓 · 데이마켓) 여부 판별기]:
    현재 시각이 익절 매도는 열려 있으나(is_active_sell_window == True)
    신규/추가 매수는 잠겨 있는(is_active_buy_window == False) 애프터마켓 또는 데이마켓 구간인지 판별한다.
    """
    return bool(
        is_active_sell_window(hm, now_est=now_est)
        and not is_active_buy_window(hm, now_est=now_est)
    )


def get_market_session_label(now_est: Optional[datetime] = None) -> str:
    """
    # MODIFIED [Case 79]:
    현재 EST 시각에 따른 세션 상태 라벨(애프터장 · 데이장 익절감시 및 매수잠금 상태 명시)을 반환한다.
    """
    dt = now_est.astimezone(EST_TZ) if now_est else datetime.now(EST_TZ)
    if is_weekend_nyse_closed(dt):
        return "🛑 주말휴장"
    hm = dt.hour * 100 + dt.minute
    if 400 <= hm <= 406:
        return "🌅 프리장 오프닝 안정화(04:00~04:06)"
    if 407 <= hm <= 929 and dt.weekday() < 5:
        return "🔫 프리장 스나이퍼 가동(04:07~09:29)"
    if 930 <= hm <= 1600 and dt.weekday() < 5:
        return "🔥 정규장 스나이퍼 가동(09:30~16:00)"
    if 1601 <= hm <= 1959 and dt.weekday() < 5:
        return "🌇 애프터장 익절감시(16:00~19:59·매수잠금)"
    return "🌃 데이장 익절감시(20:00~03:59·매수잠금)"


# ---------------------------------------------------------------------------
# [핵심 2] 04:07 ~ 16:00 EST 10분 고정 매수 게이트 버킷 산출기 (Case 01, 36, 64, 79)
# ---------------------------------------------------------------------------
def evaluate_buy_gate_bucket_status(
    now_est: Optional[datetime] = None,
    buy_interval_min: int = LOCKED_BUY_INTERVAL_MIN,
    last_evaluated_bucket_id: int = -1,
    last_evaluated_date: str = "",
) -> Tuple[bool, int, str, Dict[str, Any]]:
    """
    🚨 Case 01, Case 36, Case 64 & Case 79:
    04:07 EST 기점 10분 고정 매수 게이트(04:07, 04:17, 04:27, ..., 15:57 및 16:00 마감봉)의
    현재 버킷 ID(cur_bucket_id)와 게이트 오픈 여부(is_gate_open), 차기 검문 시각(next_gate_hm_str)을 산출한다.
    - 애프터마켓(16:01 ~ 19:59 EST) 및 데이마켓(20:00 ~ 03:59 EST)에서는 is_active_buy_window == False 이므로
      언제나 is_gate_open = False 를 반환하여 장외 매수를 100% 원천 차단한다.
    - 동일 거래일(today_str) 내 동일 버킷(cur_bucket_id <= last_evaluated_bucket_id)에서는
      is_gate_open = False 를 반환하여 중복 매수를 100% 원천 차단한다.
    """
    dt = now_est.astimezone(EST_TZ) if now_est else datetime.now(EST_TZ)
    today_str = dt.strftime("%Y-%m-%d")
    hm = dt.hour * 100 + dt.minute
    cur_min_of_day = dt.hour * 60 + dt.minute

    interval = LOCKED_BUY_INTERVAL_MIN  # 10분 하드 고정 (Case 64)

    if not is_active_buy_window(hm, now_est=dt) or is_weekend_nyse_closed(dt):
        return (
            False,
            -1,
            today_str,
            {
                "is_active_window": False,
                "is_sell_window_open": is_active_sell_window(hm, now_est=dt),
                "mins_from_0407": -1,
                "bucket_10m": -1,
                "is_exact_boundary_min": False,
                "next_gate_hm_str": "04:07 EST (매수잠금·익절감시)",
                "session_label": get_market_session_label(dt),
            },
        )

    mins_from_0407 = max(0, cur_min_of_day - GATE_START_MIN_OF_DAY)
    if hm == 1600:
        cur_bucket_id = 72
        is_exact_boundary = True
        next_gate_str = "익일 04:07 EST"
    else:
        cur_bucket_id = int(mins_from_0407 // interval)
        is_exact_boundary = bool((mins_from_0407 % interval) == 0)
        next_bucket_min_of_day = (
            GATE_START_MIN_OF_DAY + (cur_bucket_id + 1) * interval
        )
        if next_bucket_min_of_day >= GATE_END_MIN_OF_DAY:
            next_gate_str = "16:00 EST"
        else:
            nh = next_bucket_min_of_day // 60
            nm = next_bucket_min_of_day % 60
            next_gate_str = f"{nh:02d}:{nm:02d} EST"

    prev_date = str(last_evaluated_date or "").strip()
    prev_bucket = safe_int(last_evaluated_bucket_id, -1)

    if prev_date != today_str:
        is_gate_open = True
    else:
        is_gate_open = bool(cur_bucket_id > prev_bucket)

    info: Dict[str, Any] = {
        "is_active_window": True,
        "is_sell_window_open": True,
        "mins_from_0407": mins_from_0407,
        "bucket_10m": cur_bucket_id,
        "is_exact_boundary_min": is_exact_boundary,
        "next_gate_hm_str": next_gate_str,
        "session_label": get_market_session_label(dt),
    }
    return is_gate_open, cur_bucket_id, today_str, info


# ---------------------------------------------------------------------------
# [핵심 3] 100% 벡터화 시계열 지표 산출 엔진 (compute_soxl_quant_metrics_1m)
# ---------------------------------------------------------------------------
def _compute_5ma_intraday_amp_pct_vectorized(
    daily_candles: Optional[List[Dict[str, Any]]],
    df_1m: Optional[pd.DataFrame] = None,
) -> float:
    """
    최근 5영업일 일봉(또는 1분봉 일별 집계)의 일중 진폭 ((High - Low) / Low * 100.0) 평균을
    100% 벡터화 연산으로 산출한다.
    """
    if isinstance(daily_candles, list) and len(daily_candles) >= 2:
        try:
            df_d = pd.DataFrame(daily_candles)
            if "highPrice" in df_d.columns and "lowPrice" in df_d.columns:
                h_s = pd.to_numeric(df_d["highPrice"], errors="coerce")
                l_s = pd.to_numeric(df_d["lowPrice"], errors="coerce")
                valid = (h_s > 0.0) & (l_s > 0.0) & (h_s >= l_s)
                h_v = h_s[valid].to_numpy(dtype=float)
                l_v = l_s[valid].to_numpy(dtype=float)
                if len(l_v) >= 2:
                    if len(l_v) > 5:
                        h_sub = h_v[-6:-1]
                        l_sub = l_v[-6:-1]
                    else:
                        h_sub = h_v[-5:]
                        l_sub = l_v[-5:]
                    amps = ((h_sub - l_sub) / np.maximum(0.01, l_sub)) * 100.0
                    mean_amp = float(np.mean(amps))
                    if not math.isnan(mean_amp) and mean_amp > 0.0:
                        return round(mean_amp, 2)
        except Exception:
            pass

    if df_1m is not None and not df_1m.empty and "Date" in df_1m.columns:
        try:
            grp = df_1m.groupby("Date", sort=True).agg(
                day_h=("H", "max"), day_l=("L", "min")
            )
            valid_g = grp[(grp["day_l"] > 0.0) & (grp["day_h"] >= grp["day_l"])]
            if not valid_g.empty:
                amps = (
                    (
                        valid_g["day_h"].to_numpy(dtype=float)
                        - valid_g["day_l"].to_numpy(dtype=float)
                    )
                    / np.maximum(0.01, valid_g["day_l"].to_numpy(dtype=float))
                ) * 100.0
                mean_amp = float(np.mean(amps[-5:]))
                if not math.isnan(mean_amp) and mean_amp > 0.0:
                    return round(mean_amp, 2)
        except Exception:
            pass

    return 6.50


def _compute_vectorized_heikin_ashi_and_rsi(
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
) -> Dict[str, Any]:
    """
    100% 벡터화(Wilder's EWM & Heikin-Ashi EWM) 연산으로 직전 봉 기저 및 현재 HA 양/음봉 상태와 RSI(14)를 산출한다.
    """
    n = len(closes)
    if n == 0:
        return {
            "rsi_14": 50.0,
            "ha_open": 0.0,
            "ha_close": 0.0,
            "prev_ha_open": 0.0,
            "prev_ha_close": 0.0,
            "cur_bar_open": 0.0,
            "cur_bar_high": 0.0,
            "cur_bar_low": 0.0,
            "ha_bull": True,
            "ha_badge": "🕯️HA양봉",
        }

    ha_close_arr = (opens + highs + lows + closes) * 0.25
    ha_seed = (opens[0] + closes[0]) * 0.5
    shifted_hc = np.empty(n, dtype=float)
    shifted_hc[0] = ha_seed
    if n > 1:
        shifted_hc[1:] = ha_close_arr[:-1]
    ha_open_series = (
        pd.Series(shifted_hc)
        .ewm(alpha=0.5, adjust=False)
        .mean()
        .to_numpy(dtype=float)
    )

    cur_ha_open = float(ha_open_series[-1])
    cur_ha_close = float(ha_close_arr[-1])
    prev_ha_open = float(ha_open_series[-2]) if n >= 2 else cur_ha_open
    prev_ha_close = float(ha_close_arr[-2]) if n >= 2 else cur_ha_close
    is_bull = bool(cur_ha_close >= cur_ha_open)

    # Wilder's RSI(14) 벡터화 연산 (8칸 표준 들여쓰기 고정)
    rsi_val = 50.0
    if n >= 3:
        s_close = pd.Series(closes)
        delta = s_close.diff()
        gain = delta.clip(lower=0.0)
        loss = (-delta).clip(lower=0.0)
        avg_gain = gain.ewm(
            alpha=1.0 / 14.0, min_periods=1, adjust=False
        ).mean()
        avg_loss = loss.ewm(
            alpha=1.0 / 14.0, min_periods=1, adjust=False
        ).mean()
        last_g = float(avg_gain.iloc[-1])
        last_l = float(avg_loss.iloc[-1])
        if last_l <= 1e-12:
            rsi_val = 100.0 if last_g > 0.0 else 50.0
        else:
            rs = last_g / last_l
            rsi_val = 100.0 - (100.0 / (1.0 + rs))

    return {
        "rsi_14": round(rsi_val, 2),
        "ha_open": round(cur_ha_open, 4),
        "ha_close": round(cur_ha_close, 4),
        "prev_ha_open": round(prev_ha_open, 4),
        "prev_ha_close": round(prev_ha_close, 4),
        "cur_bar_open": round(float(opens[-1]), 4),
        "cur_bar_high": round(float(highs[-1]), 4),
        "cur_bar_low": round(float(lows[-1]), 4),
        "ha_bull": is_bull,
        "ha_badge": "🕯️HA양봉" if is_bull else "🌑HA음봉",
    }


def _calc_session_vwap_and_bands(
    df_sess: pd.DataFrame,
    ma5_amp_pct: float,
) -> Dict[str, float]:
    """
    주어진 세션(프리장 또는 정규장) DataFrame 에 대해 누적 VWAP, 고가, 저가, 진폭(%),
    5MA 진폭 기반 예상 저가/고가 밴드를 100% 벡터화 연산으로 산출한다.
    """
    if df_sess is None or df_sess.empty:
        return {
            "vwap": 0.0,
            "high": 0.0,
            "low": 0.0,
            "amp_pct": 0.0,
            "est_low": 0.0,
            "est_high": 0.0,
        }

    h_arr = df_sess["H"].to_numpy(dtype=float)
    l_arr = df_sess["L"].to_numpy(dtype=float)
    c_arr = df_sess["C"].to_numpy(dtype=float)
    v_arr = np.maximum(0.0, df_sess["V"].to_numpy(dtype=float))

    tp_arr = (h_arr + l_arr + c_arr) / 3.0
    tot_vol = float(np.sum(v_arr))
    if tot_vol > 0.0:
        vwap_val = float(np.sum(tp_arr * v_arr) / tot_vol)
    else:
        vwap_val = float(np.mean(tp_arr))

    sess_h = float(np.max(h_arr))
    sess_l = float(np.min(l_arr))
    amp_pct = (
        ((sess_h - sess_l) / sess_l) * 100.0 if sess_l > 0.0 else 0.0
    )

    amp_ratio = max(0.01, float(ma5_amp_pct) / 100.0)
    est_high = sess_l * (1.0 + amp_ratio) if sess_l > 0.0 else 0.0
    est_low = sess_h / (1.0 + amp_ratio) if sess_h > 0.0 else 0.0

    return {
        "vwap": round(vwap_val, 4),
        "high": round(sess_h, 4),
        "low": round(sess_l, 4),
        "amp_pct": round(amp_pct, 2),
        "est_low": round(min(est_low, sess_l), 2),
        "est_high": round(max(est_high, sess_h), 2),
    }


def compute_soxl_quant_metrics_1m(
    candles: List[Dict[str, Any]],
    live_price: float = 0.0,
    now_est: Optional[datetime] = None,
    daily_candles: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    🎯 2 & Case 01, 15, 79:
    토스 Open API 1분봉(candles) 및 일봉(daily_candles)을 입력받아:
    1) 당일 프리장(04:00 ~ 09:29 EST) VWAP · 고/저가 진폭 · 예상 변동 밴드
    2) 당일 정규장(09:30 ~ 16:00 EST) VWAP · 고/저가 진폭 · 예상 변동 밴드
    3) 최근 5영업일 평균 진폭(5MA) 및 실시간 하이킨 아시 추세 배지(🕯️HA양봉 / 🌑HA음봉)
    4) 04:07 ~ 16:00 EST 10분 고정 매수 게이트 버킷 정보
    를 100% 벡터화 연산으로 산출하여 반환한다.
    (Case 79: 데이마켓/애프터마켓에서 브로커가 시세·캔들을 제공하지 않는 경우에도 경고 로그나 알림 없이 조용히 묵음 반환)
    """
    dt_now = now_est.astimezone(EST_TZ) if now_est else datetime.now(EST_TZ)
    _, cur_bucket_id, today_str, gate_info = evaluate_buy_gate_bucket_status(
        now_est=dt_now, buy_interval_min=LOCKED_BUY_INTERVAL_MIN
    )
    lp = safe_float(live_price, 0.0)

    default_out: Dict[str, Any] = {
        "symbol": TARGET_SYMBOL,
        "live_price": round(lp, 4),
        "ma5_amp_pct": 6.50,
        "rsi_14": 50.0,
        "ha_open": round(lp, 4),
        "ha_close": round(lp, 4),
        "prev_ha_open": round(lp, 4),
        "prev_ha_close": round(lp, 4),
        "cur_bar_open": round(lp, 4),
        "cur_bar_high": round(lp, 4),
        "cur_bar_low": round(lp, 4),
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
        "day_vwap": 0.0,
        "day_high": 0.0,
        "day_low": 0.0,
        "day_amp_pct": 0.0,
        "bucket_10m": cur_bucket_id,
        "next_gate_hm_str": gate_info.get("next_gate_hm_str", "04:07 EST"),
        "session_label": gate_info.get("session_label", ""),
        "updated_est": dt_now.strftime("%m-%d %H:%M:%S EST"),
    }

    if not isinstance(candles, list) or not candles:
        default_out["ma5_amp_pct"] = _compute_5ma_intraday_amp_pct_vectorized(
            daily_candles, None
        )
        return default_out

    try:
        df = pd.DataFrame(candles)
        if df.empty or "timestamp" not in df.columns:
            return default_out

        ts_utc = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
        valid_ts = ts_utc.notna()
        df = df.loc[valid_ts].copy()
        if df.empty:
            return default_out

        df["dt_est"] = ts_utc[valid_ts].dt.tz_convert(EST_TZ)
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
        df = df[
            (df["O"] > 0.0)
            & (df["H"] > 0.0)
            & (df["L"] > 0.0)
            & (df["C"] > 0.0)
        ].copy()
        if df.empty:
            return default_out

        df["Date"] = df["dt_est"].dt.strftime("%Y-%m-%d")
        df["hm"] = df["dt_est"].dt.hour * 100 + df["dt_est"].dt.minute

        last_candle_close = float(df["C"].iloc[-1])
        if lp <= 0.0:
            lp = last_candle_close

        ma5_amp = _compute_5ma_intraday_amp_pct_vectorized(daily_candles, df)

        opens = df["O"].to_numpy(dtype=float)
        highs = df["H"].to_numpy(dtype=float)
        lows = df["L"].to_numpy(dtype=float)
        closes = df["C"].to_numpy(dtype=float)
        if lp > 0.0 and len(closes) > 0:
            closes[-1] = lp
            highs[-1] = max(highs[-1], lp)
            lows[-1] = min(lows[-1], lp)

        ha_rsi_info = _compute_vectorized_heikin_ashi_and_rsi(
            opens, highs, lows, closes
        )

        target_date = (
            today_str
            if (df["Date"] == today_str).any()
            else str(df["Date"].iloc[-1])
        )
        df_today = df[df["Date"] == target_date]

        df_pre = df_today[(df_today["hm"] >= 400) & (df_today["hm"] <= 929)]
        df_reg = df_today[(df_today["hm"] >= 930) & (df_today["hm"] <= 1600)]

        pre_stats = _calc_session_vwap_and_bands(df_pre, ma5_amp)
        reg_stats = _calc_session_vwap_and_bands(df_reg, ma5_amp)
        all_stats = _calc_session_vwap_and_bands(df_today, ma5_amp)

        active_vwap = (
            reg_stats["vwap"]
            if reg_stats["vwap"] > 0.0
            else (
                pre_stats["vwap"]
                if pre_stats["vwap"] > 0.0
                else all_stats["vwap"]
            )
        )

        out = dict(default_out)
        out.update(ha_rsi_info)
        out.update(
            {
                "live_price": round(lp, 4),
                "ma5_amp_pct": ma5_amp,
                "premarket_vwap": pre_stats["vwap"],
                "premarket_high": pre_stats["high"],
                "premarket_low": pre_stats["low"],
                "premarket_amp_pct": pre_stats["amp_pct"],
                "premarket_est_low": pre_stats["est_low"],
                "premarket_est_high": pre_stats["est_high"],
                "regular_vwap": reg_stats["vwap"],
                "regular_high": reg_stats["high"],
                "regular_low": reg_stats["low"],
                "regular_amp_pct": reg_stats["amp_pct"],
                "regular_est_low": reg_stats["est_low"],
                "regular_est_high": reg_stats["est_high"],
                "day_vwap": active_vwap,
                "day_high": all_stats["high"],
                "day_low": all_stats["low"],
                "day_amp_pct": all_stats["amp_pct"],
            }
        )
        return refresh_metrics_with_live_tick(out, lp, now_est=dt_now)
    except Exception as exc:
        # Case 79: 데이마켓 등 장외 시간대 캔들 결측 시에도 소음 없이 조용히 디버그 로깅
        logger.debug("compute_soxl_quant_metrics_1m 연산 폴백(묵음): %s", exc)
        return default_out


# ---------------------------------------------------------------------------
# [핵심 4] 실시간 틱(live_price) O(1) 무부하 합성기 (refresh_metrics_with_live_tick)
# ---------------------------------------------------------------------------
def refresh_metrics_with_live_tick(
    base_metrics: Optional[Dict[str, Any]],
    live_price: float,
    now_est: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    캔들 레이더 스캔 주기(5.0초) 사이사이에 유입되는 실시간 현재가(live_price)를
    O(1) 상수 시간으로 기존 지표 딕셔너리에 합성하여 실시간 고/저가 진폭, 예상 밴드,
    하이킨 아시 양/음봉 배지 및 10분 게이트 시각을 최신 상태로 유지한다.
    """
    dt_now = now_est.astimezone(EST_TZ) if now_est else datetime.now(EST_TZ)
    hm = dt_now.hour * 100 + dt_now.minute
    _, cur_bucket_id, _, gate_info = evaluate_buy_gate_bucket_status(
        now_est=dt_now, buy_interval_min=LOCKED_BUY_INTERVAL_MIN
    )

    met = dict(base_metrics) if isinstance(base_metrics, dict) else {}
    lp = safe_float(live_price, 0.0)
    if lp <= 0.0:
        lp = safe_float(met.get("live_price"), 0.0)
    else:
        met["live_price"] = round(lp, 4)

    ma5_amp = max(1.0, safe_float(met.get("ma5_amp_pct"), 6.50))
    amp_ratio = ma5_amp / 100.0

    # 1) 실시간 틱 기반 Heikin-Ashi 양/음봉 O(1) 합성
    if lp > 0.0:
        prev_ho = safe_float(met.get("prev_ha_open"), lp)
        prev_hc = safe_float(met.get("prev_ha_close"), lp)
        cur_o = safe_float(met.get("cur_bar_open"), lp)
        cur_h = max(safe_float(met.get("cur_bar_high"), lp), lp)
        cur_l = min(
            safe_float(met.get("cur_bar_low"), lp)
            if safe_float(met.get("cur_bar_low"), 0.0) > 0.0
            else lp,
            lp,
        )
        live_ha_open = (prev_ho + prev_hc) * 0.5
        live_ha_close = (cur_o + cur_h + cur_l + lp) * 0.25
        is_bull = bool(live_ha_close >= live_ha_open)
        met["cur_bar_high"] = round(cur_h, 4)
        met["cur_bar_low"] = round(cur_l, 4)
        met["ha_open"] = round(live_ha_open, 4)
        met["ha_close"] = round(live_ha_close, 4)
        met["ha_bull"] = is_bull
        met["ha_badge"] = "🕯️HA양봉" if is_bull else "🌑HA음봉"

    # 2) 현재 세션(프리장 04:00 ~ 09:29 / 정규장 09:30 ~ 16:00) 고/저가 및 예상 밴드 실시간 갱신
    if lp > 0.0 and 400 <= hm <= 929:
        ph = max(safe_float(met.get("premarket_high"), 0.0), lp)
        pl_prev = safe_float(met.get("premarket_low"), 0.0)
        pl = min(pl_prev, lp) if pl_prev > 0.0 else lp
        p_amp = ((ph - pl) / pl) * 100.0 if pl > 0.0 else 0.0
        met["premarket_high"] = round(ph, 4)
        met["premarket_low"] = round(pl, 4)
        met["premarket_amp_pct"] = round(p_amp, 2)
        met["premarket_est_high"] = round(max(ph, pl * (1.0 + amp_ratio)), 2)
        met["premarket_est_low"] = round(min(pl, ph / (1.0 + amp_ratio)), 2)
        if safe_float(met.get("premarket_vwap"), 0.0) <= 0.0:
            met["premarket_vwap"] = round(lp, 4)
    elif lp > 0.0 and 930 <= hm <= 1600:
        rh = max(safe_float(met.get("regular_high"), 0.0), lp)
        rl_prev = safe_float(met.get("regular_low"), 0.0)
        rl = min(rl_prev, lp) if rl_prev > 0.0 else lp
        r_amp = ((rh - rl) / rl) * 100.0 if rl > 0.0 else 0.0
        met["regular_high"] = round(rh, 4)
        met["regular_low"] = round(rl, 4)
        met["regular_amp_pct"] = round(r_amp, 2)
        met["regular_est_high"] = round(max(rh, rl * (1.0 + amp_ratio)), 2)
        met["regular_est_low"] = round(min(rl, rh / (1.0 + amp_ratio)), 2)
        if safe_float(met.get("regular_vwap"), 0.0) <= 0.0:
            met["regular_vwap"] = round(lp, 4)

    met["bucket_10m"] = cur_bucket_id
    met["next_gate_hm_str"] = gate_info.get("next_gate_hm_str", "04:07 EST")
    met["session_label"] = gate_info.get("session_label", "")
    met["updated_est"] = dt_now.strftime("%m-%d %H:%M:%S EST")
    return met


# 하위 호환 별칭 (타 모듈 임포트 호환 100% 보장)
compute_quant_metrics_1m = compute_soxl_quant_metrics_1m
calculate_soxl_quant_metrics_1m = compute_soxl_quant_metrics_1m
is_weekend_closed = is_weekend_nyse_closed
