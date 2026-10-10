# =====================================================================
# FILE: quant_engine.py
# 목적: SOXS 단일 장부 격리 및 세션별 aVWAP 연산 엔진 (I/O 통제 결속)
# =====================================================================
# MODIFIED: 초과 Case 44 - 오버나이트 로직 전면 소각 및 수동 통제 위임
# MODIFIED: 3단 하향망 로직 전면 소각 (1.0% 고정 락온) 및 관련 플래그 증발
# MODIFIED: 취약점 1 방어 - NQ=F 매크로 데이터 60초 TTL 인메모리 캐시 중앙 통제소(MacroDataCache) 신설
# MODIFIED: 취약점 1 완벽 방어 - 통신 실패 및 결측치 발생 시에도 타임스탬프 원자적 갱신으로 60초 TTL 쿨다운 강제 (IP 밴 차단 락온)
# MODIFIED: 치명적 취약점 방어 - NQ=F 세션 시프트 직후 데이터 프레임 증발 시 발생하는 IndexError 원천 소각 (df.empty 검증망 주입)
# MODIFIED: NQ=F 1d 자정 롤오버 왜곡 방어 - 45분 갭 필터링 경계값 원자적 하드 락온 (>= 45분)
# NEW: 초과 Case 67 방어 - NQ=F 진입가(nq_entry_price) 및 진입 진폭(nq_entry_amp) 동적 최대 손실 덤핑을 위한 장부 필드 원자적 증축

import os
import json
import time
import pandas as pd
import yfinance as yf
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo
from toss_api import GlobalThrottle

class MacroDataCache:
    """
    NQ=F 60초 TTL 인메모리 캐싱 파이프라인 중앙화.
    main.py와 tg_router.py의 중복 API 호출을 방지하고 IP 밴 및 통신 병목을 원천 봉쇄합니다.
    """
    _nq_cache_data = (0.0, 0.0, 0.0, 0.0) # (current, high, low, timestamp)
    _nq_cache_lock = asyncio.Lock()

    @classmethod
    async def get_cached_nq_data(cls):
        async with cls._nq_cache_lock:
            now = time.time()
            if now - cls._nq_cache_data[3] > 60.0:
                def _fetch():
                    tkr = yf.Ticker("NQ=F")
                    df = tkr.history(period="5d", interval="1m")
                    if df.empty: return 0.0, 0.0, 0.0
                    df.index = pd.to_datetime(df.index, utc=True).tz_convert(ZoneInfo('America/New_York'))
                    time_diffs = df.index.to_series().diff()
                    gaps = time_diffs[time_diffs >= pd.Timedelta(minutes=45)]
                    if not gaps.empty:
                        last_gap_time = gaps.index[-1]
                        df = df[df.index >= last_gap_time]
                        
                    if df.empty: return 0.0, 0.0, 0.0
                    
                    return float(df['Close'].iloc[-1]), float(df['High'].max()), float(df['Low'].min())
                try:
                    c, h, l = await asyncio.wait_for(asyncio.to_thread(_fetch), timeout=5.0)
                    if l > 0.0:
                        cls._nq_cache_data = (c, h, l, now)
                    else:
                        cls._nq_cache_data = (cls._nq_cache_data[0], cls._nq_cache_data[1], cls._nq_cache_data[2], now)
                except Exception as e:
                    cls._nq_cache_data = (cls._nq_cache_data[0], cls._nq_cache_data[1], cls._nq_cache_data[2], now)
                    print(f"🚨 [NQ=F 캐시 갱신 방어] {e}", flush=True)
            return cls._nq_cache_data[0], cls._nq_cache_data[1], cls._nq_cache_data[2]

class AssassinLedger:
    @classmethod
    def _get_file_path(cls, symbol: str) -> str:
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), f"AssassinLedger_{symbol}.json")

    @classmethod
    async def get_state(cls, symbol: str) -> tuple[float, float, str, bool, bool, float, str, str, float, float, float]:
        filepath = cls._get_file_path(symbol)
        async with GlobalThrottle.get_file_lock(filepath):
            def _read():
                if not os.path.exists(filepath):
                    return 0.0, 100.0, "", False, True, 0.0, "", "", 0.0, 0.0, 0.0
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        return (
                            float(data.get("last_buy_price", 0.0)),
                            float(data.get("budget", 100.0)),
                            str(data.get("last_session_id", "")),
                            bool(data.get("is_session_done", False)),
                            bool(data.get("is_active", True)),
                            float(data.get("target_sell_price", 0.0)),
                            str(data.get("sell_order_id", "")),
                            str(data.get("entry_session", "")),
                            float(data.get("entry_time", 0.0)),
                            float(data.get("nq_entry_price", 0.0)),
                            float(data.get("nq_entry_amp", 0.0))
                        )
                except Exception:
                    return 0.0, 100.0, "", False, True, 0.0, "", "", 0.0, 0.0, 0.0
            return await asyncio.to_thread(_read)

    @classmethod
    async def get_buy_order_id(cls, symbol: str) -> str:
        filepath = cls._get_file_path(symbol)
        async with GlobalThrottle.get_file_lock(filepath):
            def _read():
                if not os.path.exists(filepath):
                    return ""
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        return str(json.load(f).get("buy_order_id", ""))
                except Exception:
                    return ""
            return await asyncio.to_thread(_read)

    @classmethod
    async def save_state(cls, symbol: str, price: float = None, budget: float = None, 
                         last_session_id: str = None, is_session_done: bool = None, 
                         is_active: bool = None, target_sell_price: float = None, 
                         buy_order_id: str = None, sell_order_id: str = None, 
                         entry_session: str = None, entry_time: float = None,
                         nq_entry_price: float = None, nq_entry_amp: float = None):
        filepath = cls._get_file_path(symbol)
        async with GlobalThrottle.get_file_lock(filepath):
            def _write():
                data = {}
                if os.path.exists(filepath):
                    try:
                        with open(filepath, "r", encoding="utf-8") as f:
                            data = json.load(f)
                    except Exception:
                        pass
                
                if price is not None: data["last_buy_price"] = price
                if budget is not None: data["budget"] = budget
                if last_session_id is not None: data["last_session_id"] = last_session_id
                if is_session_done is not None: data["is_session_done"] = is_session_done
                if is_active is not None: data["is_active"] = is_active
                if target_sell_price is not None: data["target_sell_price"] = target_sell_price
                if buy_order_id is not None: data["buy_order_id"] = buy_order_id
                if sell_order_id is not None: data["sell_order_id"] = sell_order_id
                if entry_session is not None: data["entry_session"] = entry_session
                if entry_time is not None: data["entry_time"] = entry_time
                if nq_entry_price is not None: data["nq_entry_price"] = nq_entry_price
                if nq_entry_amp is not None: data["nq_entry_amp"] = nq_entry_amp
                
                # 낡은 조건주문 ID 및 세션 모드 데드코드 원자적 파기
                for obsolete_key in ["pre_first_flag", "force_downgrade", "force_downgrade_0_6", "is_stage_3", "cond_order_id", "session_mode"]:
                    data.pop(obsolete_key, None)
                
                tmp_path = filepath + ".tmp"
                with open(tmp_path, "w", encoding="utf-8") as f:
                    json.dump(data, f)
                os.replace(tmp_path, filepath) 
            await asyncio.to_thread(_write)

class AVWAPEngine:
    @staticmethod
    def calculate_vwap(candles_json: list, session_start_est: datetime) -> float:
        if not candles_json:
            return 0.0
            
        df = pd.DataFrame(candles_json)
        if df.empty: return 0.0
        
        df['timestamp'] = pd.to_datetime(df['timestamp'], format='ISO8601', utc=True)
        df['timestamp'] = df['timestamp'].dt.tz_convert(ZoneInfo('America/New_York'))
        df.set_index('timestamp', inplace=True)
        df.sort_index(ascending=True, inplace=True)
        
        for col in ['highPrice', 'lowPrice', 'closePrice', 'volume']:
            if col not in df.columns:
                df[col] = 0.0
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
            
        session_df = df[df.index >= session_start_est]
        if session_df.empty:
            return 0.0
            
        typical_price = (session_df['highPrice'] + session_df['lowPrice'] + session_df['closePrice']) / 3.0
        pv = typical_price * session_df['volume']
        
        cumulative_pv = pv.sum()
        cumulative_vol = session_df['volume'].sum()
        
        if cumulative_vol <= 0:
            return 0.0
            
        return float(cumulative_pv / cumulative_vol)
