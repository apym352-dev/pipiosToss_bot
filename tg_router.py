# =====================================================================
# FILE: tg_router.py
# 목적: SOXS 단독 상태 제어 UI, 스케줄/명령어 라우팅 및 방어망 결속
# =====================================================================
# MODIFIED: SOXL UI 및 로직 100% 소각 (SOXS 100% 단일 종목 렌더링)
# MODIFIED: 04:00~09:29 '절대쉴드(04:01 덫 대기 유지)' 텍스트 렌더링 주입
# MODIFIED: 초과 Case 68 - 3단 동적 스위칭 (AUTO -> 수동 0.5% -> 수동 1.0%) 제어 UI 및 컷오프 표시망 증축

import os
import html
import asyncio
import time
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from quant_engine import AssassinLedger, MacroDataCache

router = Router()
api_client = None
ADMIN_CHAT_ID = None
wakeup_event = None

def inject_dependencies(client, admin_id, event):
    global api_client, ADMIN_CHAT_ID, wakeup_event
    api_client = client
    ADMIN_CHAT_ID = admin_id
    wakeup_event = event

class BudgetState(StatesGroup):
    waiting_for_budget = State()

def get_main_menu_text() -> str:
    now_est = datetime.now(ZoneInfo('America/New_York'))
    is_dst = now_est.dst() is not None and now_est.dst().total_seconds() != 0
    dst_status_text = "🌞서머타임 ON (EDT)" if is_dst else "❄️서머타임 OFF (EST)"
    
    return (
        f"🕒 <b>[ 운영 스케줄 ({dst_status_text}) ]</b>\n"
        "➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
        "🔹 17:00: 🧹 정산 스캔 및 시스템 대기\n"
        "🔹 04:00: 🌅 프리장 레이더 스캔 \n"
        "      (04:01 덫/즉각 타격 분기망 가동)\n"
        "🔹 09:30: 🔥 정규장 VWAP 스캔\n"
        "      (신규 진입 셧다운 및 덫 파기)\n"
        "🔹 15:59: 🛑 MOC 덤핑 (1.5초 주기)\n\n"
        "🛠 <b>[ 핵심 명령어 ]</b>\n"
        "▶️ /avwap : 🔫 트레이딩 레이더 관제탑\n"
        "▶️ /sync : 📜 통합 지시서 및 장부 동기화\n"
        "▶️ /settlement : ⚙️ 통합 전술 제어반\n\n"
        "⚠️ /reset : 🧹 단일 장부(SOXS) 초기화\n\n"
        "⚠️ /update : 🚀 시스템 자가 업데이트\n\n"
        "🌙 <b>오버나이트를 원할 경우 [통합 전술 제어반]에서 가동을 OFF 해주세요.</b>"
    )

@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    user = getattr(message, "from_user", None)
    if not user or getattr(user, "id", None) != ADMIN_CHAT_ID: 
        return
    print(f"💬 [TG 수신] /start 명령 하달 (User: {user.id})", flush=True)
    await state.clear()
    try:
        await message.answer(get_main_menu_text(), parse_mode="HTML")
    except Exception as e:
        print(f"🚨 [/start 응답 붕괴 방어] {e}", flush=True)

def parse_session_data(all_candles: list, session_start_est: datetime) -> dict:
    res = {
        "pre_h": 0.0, "pre_l": 0.0, "pre_amp": 0.0, "pre_vwap": 0.0, "pre_body": 0.0,
        "reg_h": 0.0, "reg_l": 0.0, "reg_amp": 0.0, "reg_vwap": 0.0, "reg_body": 0.0
    }
    if not all_candles: return res
    
    df = pd.DataFrame(all_candles)
    if df.empty: return res
    
    df['timestamp'] = pd.to_datetime(df['timestamp'], format='ISO8601', utc=True).dt.tz_convert(ZoneInfo('America/New_York'))
    df.set_index('timestamp', inplace=True)
    df.sort_index(ascending=True, inplace=True)
    
    for col in ['openPrice', 'highPrice', 'lowPrice', 'closePrice', 'volume']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
            
    df = df[df.index >= session_start_est]
    if df.empty: return res
    
    pre_df = df.between_time('04:00', '09:29')
    reg_df = df.between_time('09:30', '16:00')
    
    def calc_metrics(sub_df):
        if sub_df.empty: return 0.0, 0.0, 0.0, 0.0, 0.0
        h = float(sub_df['highPrice'].max())
        l = float(sub_df['lowPrice'].min())
        amp = ((h - l) / l * 100) if l > 0 else 0.0
        
        o = float(sub_df['openPrice'].iloc[0])
        c = float(sub_df['closePrice'].iloc[-1])
        body = ((c - o) / o * 100) if o > 0 else 0.0
        
        tp = (sub_df['highPrice'] + sub_df['lowPrice'] + sub_df['closePrice']) / 3.0
        pv = tp * sub_df['volume']
        vol = sub_df['volume'].sum()
        vwap = float(pv.sum() / vol) if vol > 0 else 0.0
        return h, l, float(amp), vwap, float(body)

    pre_h, pre_l, pre_amp, pre_vwap, pre_body = calc_metrics(pre_df)
    reg_h, reg_l, reg_amp, reg_vwap, reg_body = calc_metrics(reg_df)
    
    res.update({
        "pre_h": pre_h, "pre_l": pre_l, "pre_amp": pre_amp, "pre_vwap": pre_vwap, "pre_body": pre_body,
        "reg_h": reg_h, "reg_l": reg_l, "reg_amp": reg_amp, "reg_vwap": reg_vwap, "reg_body": reg_body
    })
    return res

async def build_avwap_radar() -> tuple[str, InlineKeyboardMarkup]:
    now_est = datetime.now(ZoneInfo('America/New_York'))
    
    t = now_est.hour * 100 + now_est.minute
    if 400 <= t <= 929:
        session_name_ui = "preMarket"
        market_header = "( <b>🌅 PRE_MARKET</b> )"
    elif 930 <= t <= 1559:
        session_name_ui = "regularMarket"
        market_header = "( <b>🔥 REG_MARKET</b> )"
    elif 1600 <= t <= 1659:
        session_name_ui = "afterMarket"
        market_header = "( <b>🛑 AFT_MARKET</b> )"
    else:
        session_name_ui = "dayMarket"
        market_header = "( <b>🌙 시스템 대기</b> )"

    try:
        is_open, _, sess_name, _ = await asyncio.wait_for(api_client.is_market_open(), timeout=3.0)
        if not is_open:
            session_name_ui = "dayMarket"
            if sess_name and "HOLIDAY" in sess_name:
                market_header = "( <b>🌙 주말/휴장일</b> )"
            else:
                market_header = "( <b>🌙 장외 대기</b> )"
    except Exception:
        pass

    nq_c, nq_h, nq_l = await MacroDataCache.get_cached_nq_data()
    
    nq_amp = ((nq_h - nq_l) / nq_l * 100.0) if nq_l > 0.0 else 0.0
    nq_current_amp = ((nq_c - nq_l) / nq_l * 100.0) if nq_l > 0.0 else 0.0
    
    lev_expected_amp = nq_amp * 5.0

    price_s = await api_client.get_current_price("SOXS")
    hold_s = await api_client.get_symbol_holdings_detail("SOXS")

    async def fetch_5ma_amp(symbol):
        avg_amp = 0.0
        yesterday_amp = 0.0
        yesterday_return = 0.0
        
        try:
            endpoint = f"/api/v1/candles?symbol={symbol}&interval=1d&count=6"
            data = await api_client._request("GET", endpoint, "MARKET_DATA_CHART", headers=api_client._get_headers())
            candles = data.get("result", {}).get("candles", [])
            
            if not candles:
                return 0.0, 0.0, 0.0
                
            c0_dt = pd.to_datetime(candles[0]['timestamp'], format='ISO8601', utc=True).tz_convert(ZoneInfo('America/New_York')).date()
            now_est_check = datetime.now(ZoneInfo('America/New_York'))
            today_dt = now_est_check.date()
            
            if c0_dt > today_dt:
                valid_candles = candles[1:6]
            elif c0_dt == today_dt:
                if 16 <= now_est_check.hour < 19:
                    valid_candles = candles[0:5]
                else:
                    valid_candles = candles[1:6]
            else:
                valid_candles = candles[0:5]
                
            amps = []
            
            for i, c in enumerate(valid_candles):
                h = float(c.get("highPrice", 0))
                l = float(c.get("lowPrice", 0))
                if l > 0: 
                    amp = (h - l) / l * 100
                    amps.append(amp)
                    if i == 0:
                        yesterday_amp = amp
            
            if len(valid_candles) >= 2:
                yest_cls_raw = valid_candles[0].get("closePrice")
                prev_cls_raw = valid_candles[1].get("closePrice")
                
                yest_cls = float(yest_cls_raw) if yest_cls_raw is not None else 0.0
                prev_cls = float(prev_cls_raw) if prev_cls_raw is not None else 0.0
                
                if prev_cls > 0.0:
                    yesterday_return = ((yest_cls - prev_cls) / prev_cls) * 100.0
                        
            if amps:
                avg_amp = sum(amps) / len(amps)
                
            return avg_amp, yesterday_amp, yesterday_return
        except Exception:
            return 0.0, 0.0, 0.0

    amp_l, yest_amp_l, yest_return_l = await fetch_5ma_amp("SOXL")
    amp_s, yest_amp_s, yest_return_s = await fetch_5ma_amp("SOXS")
    
    diff_return = abs(yest_return_l - yest_return_s)
    if diff_return <= 0.3:
        trend_msg = "▫️ ⚔️ <b>횡보/휩소장 (방향성 상실)</b> : 전일 실질 등락률 격차 미미 (극심한 공방)"
    elif yest_return_l > yest_return_s:
        trend_msg = "▫️ 🐂 <b>상승장 (SOXL 승리)</b> : 롱(SOXL) 전일 등락률 우위 (시장 강세)"
    else:
        trend_msg = "▫️ 🐻 <b>하락장 (SOXS 승리)</b> : 숏(SOXS) 전일 등락률 우위 (시장 약세)"

    async def fetch_session_stats(symbol):
        all_candles = []
        before = None
        
        if now_est.hour >= 4:
            session_start_est = now_est.replace(hour=4, minute=0, second=0, microsecond=0)
        else:
            session_start_est = (now_est - timedelta(days=1)).replace(hour=4, minute=0, second=0, microsecond=0)
        
        for _ in range(10):
            try:
                data = await api_client.get_1m_candles_pagination(symbol, count=200, before=before)
                candles = data.get("candles", [])
                all_candles.extend(candles)
                if not candles: break
                oldest_time = pd.to_datetime(candles[-1]['timestamp'], utc=True).tz_convert(ZoneInfo('America/New_York'))
                if oldest_time <= session_start_est: break
                before = data.get("nextBefore")
                if not before: break
            except Exception:
                break
        return await asyncio.to_thread(parse_session_data, all_candles, session_start_est)

    if session_name_ui == "dayMarket":
        sess_s = {"pre_h": 0.0, "pre_l": 0.0, "pre_amp": 0.0, "pre_vwap": 0.0, "pre_body": 0.0, "reg_h": 0.0, "reg_l": 0.0, "reg_amp": 0.0, "reg_vwap": 0.0, "reg_body": 0.0}
    else:
        sess_s = await fetch_session_stats("SOXS")

    pre_exp_l_s = sess_s['pre_h'] * (1 - amp_s / 100) if sess_s['pre_h'] > 0 else 0.0
    pre_exp_h_s = sess_s['pre_l'] * (1 + amp_s / 100) if sess_s['pre_l'] > 0 else 0.0
    reg_exp_l_s = sess_s['reg_h'] * (1 - amp_s / 100) if sess_s['reg_h'] > 0 else 0.0
    reg_exp_h_s = sess_s['reg_l'] * (1 + amp_s / 100) if sess_s['reg_l'] > 0 else 0.0

    def get_realtime_trend_single(body_short, amp_short):
        if amp_short <= 0.0:
            return "대기 (데이터 수집 중)"
        if abs(body_short) <= 0.3:
            return "⚔️ 횡보/휩소장 (세션 방향성 상실)"
        elif body_short < 0:
            return "🐂 상승장 (SOXS 하락 우위)"
        else:
            return "🐻 하락장 (SOXS 상승 우위)"

    pre_trend_msg = get_realtime_trend_single(sess_s['pre_body'], sess_s['pre_amp'])
    reg_trend_msg = get_realtime_trend_single(sess_s['reg_body'], sess_s['reg_amp'])

    state_s = await AssassinLedger.get_state("SOXS")
    budget_s, target_profit_rate_s, is_done_s, is_active_s, entry_s, entry_time_s, nq_entry_price_s, nq_entry_amp_s, profit_mode_s = state_s[1], state_s[2], state_s[4], state_s[5], state_s[8], state_s[9], state_s[10], state_s[11], state_s[12]

    def build_compact_status(symbol_short, is_active, budget, is_done, current_session, est_time, qty, entry_session, target_profit_rate, profit_mode, nq_amp_global, nq_entry_amp, avg_price):
        state_flag = "ON" if is_active else "OFF"
        
        expected_target = target_profit_rate
        if profit_mode == "AUTO":
            expected_target = 1.2 if nq_amp_global >= 0.63 else 0.5
            target_str = f"AUTO 예상 {expected_target}%"
        else:
            target_str = f"수동 {target_profit_rate}%"

        sl_str = ""
        if qty > 0 and nq_entry_amp > 0.0 and avg_price > 0.0:
            sl_pct = nq_entry_amp * 2.5
            sl_price = avg_price * (1.0 - sl_pct / 100.0)
            sl_str = f" | 컷오프 ${sl_price:.2f}(-{sl_pct:.2f}%)"

        if not is_active:
            state_text = "대기"
        elif qty > 0:
            state_text = f"보유(+{target_profit_rate}%{sl_str})"
        elif is_done:
            state_text = "타격완료"
        else:
            if current_session == "preMarket":
                if est_time.hour == 4 and est_time.minute == 0:
                    state_text = f"PRE대기 ({target_str})"
                else:
                    state_text = f"절대쉴드 ({target_str} 덫 대기)"
            elif current_session == "dayMarket":
                state_text = "시스템대기"
            else:
                state_text = "장외대기"

        emoji = "🐻"
        return f"{emoji} <b>{symbol_short}</b> <code>[{state_flag}]</code> {state_text} | <code>${budget:.0f}</code>"

    status_s = build_compact_status("SOXS", is_active_s, budget_s, is_done_s, session_name_ui, now_est, hold_s.get('qty', 0.0), entry_s, target_profit_rate_s, profit_mode_s, nq_amp, nq_entry_amp_s, hold_s.get('avg_price', 0.0))
    
    scan_time = now_est.strftime("%m-%d %H:%M:%S")

    text = f"""📡 <b>[aVWAP 레이더]</b> {market_header}
➖➖➖➖➖➖➖➖➖➖➖➖➖➖
🌐 <b>나스닥 100 선물 (NQ=F)</b>
▫️ 현재: <code>{nq_c:.2f}</code> | 고가: <code>{nq_h:.2f}</code> | 저가: <code>{nq_l:.2f}</code>
▫️ 총 진폭: <code>{nq_amp:.2f}%</code> | 저점 대비 반등: <code>{nq_current_amp:.2f}%</code>
▫️ 레버리지 기대 진폭 (x5.0): <code>{lev_expected_amp:.2f}%</code>
➖➖➖➖➖➖➖➖➖➖➖➖➖➖
📊 <b>현재가 & 5MA(어제 진폭)</b>
🐻 <b>SOXS</b> <code>${price_s:.2f}</code> | <code>{amp_s:.1f}%({yest_amp_s:.1f}%)</code>
{trend_msg}

🌅 <b>프리장</b> (04:00~09:29)
🐻 <b>SOXS</b> <code>[VWAP] ${sess_s['pre_vwap']:.2f}</code>
  ⤷ 팩트: <code>${sess_s['pre_l']:.2f}~${sess_s['pre_h']:.2f} ({sess_s['pre_amp']:.1f}%)</code>
  ⤷ 예상: <code>${pre_exp_l_s:.2f}~${pre_exp_h_s:.2f}</code>
▫️ <b>실시간:</b> <code>{pre_trend_msg}</code>

🔥 <b>정규장</b> (09:30~16:00)
🐻 <b>SOXS</b> <code>[VWAP] ${sess_s['reg_vwap']:.2f}</code>
  ⤷ 팩트: <code>${sess_s['reg_l']:.2f}~${sess_s['reg_h']:.2f} ({sess_s['reg_amp']:.1f}%)</code>
  ⤷ 예상: <code>${reg_exp_l_s:.2f}~${reg_exp_h_s:.2f}</code>
▫️ <b>실시간:</b> <code>{reg_trend_msg}</code>
➖➖➖➖➖➖➖➖➖➖➖➖➖➖
{status_s}

⏱️ 갱신: <code>{scan_time} EST</code>"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 레이더 갱신", callback_data="open_avwap")],
        [InlineKeyboardButton(text="🔙 메인 메뉴", callback_data="back_to_main")]
    ])
    return text, keyboard

async def build_sync_board() -> str:
    now_est = datetime.now(ZoneInfo('America/New_York'))
    is_dst = now_est.dst() is not None and now_est.dst().total_seconds() != 0
    dst_str = "🌞 서머타임" if is_dst else "❄️ 서머타임 OFF"
    
    t = now_est.hour * 100 + now_est.minute
    if 400 <= t <= 929:
        market_state = "🌅 프리장"
    elif 930 <= t <= 1559:
        market_state = "🔥 정규장"
    elif 1600 <= t <= 1659:
        market_state = "⛔ 장마감"
    else:
        market_state = "🌙 시스템 대기"

    try:
        is_open, _, sess_name, _ = await asyncio.wait_for(api_client.is_market_open(), timeout=3.0)
        if not is_open:
            if sess_name and "HOLIDAY" in sess_name:
                market_state = "🌙 주말/휴장일"
            else:
                market_state = "🌙 장외 대기"
    except Exception:
        pass

    bp = await api_client.get_usd_buying_power()
    
    exchange_rate = 1400.0
    try:
        ex_data = await api_client._request(
            "GET", 
            "/api/v1/exchange-rate?baseCurrency=USD&quoteCurrency=KRW", 
            "MARKET_INFO", 
            headers=api_client._get_headers()
        )
        exchange_rate = float(ex_data.get("result", {}).get("rate", 1400.0))
    except Exception:
        pass
    
    async def get_symbol_sync_data(symbol):
        state = await AssassinLedger.get_state(symbol)
        budget = state[1]
        target_profit_rate = state[2]
        entry_session = state[8]
        
        hold = await api_client.get_symbol_holdings_detail(symbol)
        qty = hold.get('qty', 0.0)
        avg_price = hold.get('avg_price', 0.0)
        profit_usd = hold.get('profit_usd', 0.0)
        profit_rate = hold.get('profit_rate', 0.0) * 100
        profit_krw = profit_usd * exchange_rate
        
        curr = await api_client.get_current_price(symbol)
        prev_close = curr
        
        if now_est.hour >= 4:
            session_start_est = now_est.replace(hour=4, minute=0, second=0, microsecond=0)
        else:
            session_start_est = (now_est - timedelta(days=1)).replace(hour=4, minute=0, second=0, microsecond=0)
        
        try:
            data_1d = await api_client._request("GET", f"/api/v1/candles?symbol={symbol}&interval=1d&count=5", "MARKET_DATA_CHART", headers=api_client._get_headers())
            candles_1d = data_1d.get("result", {}).get("candles", [])
            
            target_date = session_start_est.date()
            for c in candles_1d:
                c_dt = pd.to_datetime(c['timestamp'], format='ISO8601', utc=True).tz_convert(ZoneInfo('America/New_York')).date()
                if c_dt < target_date:
                    prev_close = float(c.get("closePrice", 0))
                    break
        except Exception:
            pass

        if market_state in ["🌙 시스템 대기", "🌙 주말/휴장일", "🌙 장외 대기"]:
            high = 0.0
            low = 0.0
            high_rate = 0.0
            low_rate = 0.0
        else:
            all_candles = []
            before = None
            for _ in range(10):
                try:
                    c_data = await api_client.get_1m_candles_pagination(symbol, count=200, before=before)
                    c_list = c_data.get("candles", [])
                    all_candles.extend(c_list)
                    if not c_list: break
                    oldest_time = pd.to_datetime(c_list[-1]['timestamp'], utc=True).tz_convert(ZoneInfo('America/New_York'))
                    if oldest_time <= session_start_est: break
                    before = c_data.get("nextBefore")
                    if not before: break
                except Exception:
                    break
                    
            high, low = 0.0, 0.0
            if all_candles:
                df = pd.DataFrame(all_candles)
                if not df.empty:
                    df['timestamp'] = pd.to_datetime(df['timestamp'], format='ISO8601', utc=True).dt.tz_convert(ZoneInfo('America/New_York'))
                    df.set_index('timestamp', inplace=True)
                    df = df[df.index >= session_start_est]
                    if not df.empty:
                        df['highPrice'] = pd.to_numeric(df['highPrice'], errors='coerce').fillna(0.0)
                        df['lowPrice'] = pd.to_numeric(df['lowPrice'], errors='coerce').fillna(0.0)
                        h_max = float(df['highPrice'].max())
                        l_min = float(df['lowPrice'].min())
                        if h_max > 0: high = h_max
                        if l_min > 0: low = l_min
                        
            if high == 0.0: high = curr
            if low == 0.0: low = curr

            high_rate = ((high - prev_close) / prev_close * 100) if prev_close > 0 else 0.0
            low_rate = ((low - prev_close) / prev_close * 100) if prev_close > 0 else 0.0
            
        return {
            "symbol": symbol,
            "budget": budget,
            "target_profit_rate": target_profit_rate,
            "entry_session": entry_session,
            "curr": curr,
            "avg_price": avg_price,
            "qty": qty,
            "high": high,
            "high_rate": high_rate,
            "low": low,
            "low_rate": low_rate,
            "profit_rate": profit_rate,
            "profit_usd": profit_usd,
            "profit_krw": profit_krw
        }

    soxs_data = await get_symbol_sync_data("SOXS")
    
    def format_symbol(d):
        profit_sign = "+" if d['profit_usd'] >= 0 else "-"
        flag_str = "⏳ 대기"
        if d['qty'] > 0:
            flag_str = f"🌅 [PRE 진입: +{d['target_profit_rate']}%]"
        
        return (
            f"⚖️ <b>[{d['symbol']}] 암살자(aVWAP) 지시서</b>\n"
            f"💵 총 시드: ${d['budget']:,.0f} | 🎯 {flag_str}\n"
            f"💰 현재 ${d['curr']:.2f} / 평단 ${d['avg_price']:.2f} ({int(d['qty'])}주)\n"
            f"📈 금일 고가: ${d['high']:.2f} ({d['high_rate']:+.2f}%)\n"
            f"📉 금일 저가: ${d['low']:.2f} ({d['low_rate']:+.2f}%)\n"
            f"🔺 수익: {d['profit_rate']:+.2f}% ({profit_sign}${abs(d['profit_usd']):,.2f} | {profit_sign}₩{int(abs(d['profit_krw'])):,})"
        )
        
    text = (
        f"📜 <b>[ 통합 지시서 ({market_state}) ]</b>\n"
        f"📅 {dst_str} ({now_est.strftime('%H:%M')})\n"
        f"💵 주문가능금액: ${bp:,.2f}\n"
        f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n\n"
        f"{format_symbol(soxs_data)}\n\n"
        f"▶️ /avwap : 🔫 트레이딩 레이더 관제탑"
    )
    return text

async def build_settlement_board() -> tuple[str, InlineKeyboardMarkup]:
    state_s = await AssassinLedger.get_state("SOXS")
    budget_s, target_profit_rate_s, is_active_s, profit_mode_s = state_s[1], state_s[2], state_s[5], state_s[12]
    state_s_str = "🟢 ON" if is_active_s else "🔴 OFF"

    if profit_mode_s == "AUTO":
        mode_display = "AUTO"
        next_mode_btn = "🎯 모드: AUTO ➡️ 수동 0.5%"
    elif profit_mode_s == "MANUAL_0.5":
        mode_display = "수동 0.5%"
        next_mode_btn = "🎯 모드: 수동 0.5% ➡️ 수동 1.2%"
    else:
        mode_display = "수동 1.2%"
        next_mode_btn = "🎯 모드: 수동 1.2% ➡️ AUTO"

    text = (
        "⚙️ <b>[전술 코어 제어반 (단독 락온)]</b>\n"
        "➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
        "🐻 <b>SOXS (SHORT 단독 가동)</b>\n"
        f"▫️ <b>상태:</b> <code>{state_s_str}</code>\n"
        f"▫️ <b>예산:</b> <code>${budget_s:,.2f}</code>\n"
        f"▫️ <b>익절:</b> <code>{mode_display}</code>"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔴 숏(SOXS) 정지" if is_active_s else "🟢 숏(SOXS) 가동", callback_data="toggle_set_act_SOXS")],
        [InlineKeyboardButton(text="💵 숏(SOXS) 시드 설정", callback_data="set_budget_SOXS")],
        [InlineKeyboardButton(text=next_mode_btn, callback_data="toggle_profit_rate_SOXS")],
        [InlineKeyboardButton(text="🔫 트레이딩 레이더", callback_data="open_avwap")],
        [InlineKeyboardButton(text="🔙 메인 메뉴", callback_data="back_to_main")]
    ])
    return text, keyboard

@router.message(Command("avwap"))
async def cmd_avwap(message: types.Message, state: FSMContext):
    user = getattr(message, "from_user", None)
    if not user or getattr(user, "id", None) != ADMIN_CHAT_ID:
        return
    print(f"💬 [TG 수신] /avwap 명령 하달 (User: {user.id})", flush=True)
    await state.clear()
    try:
        msg = await message.answer("📡 <b>레이더 스캔 및 데이터 동기화 중...</b>", parse_mode="HTML")
        text, keyboard = await build_avwap_radar()
        await msg.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        await message.answer(f"🚨 <b>관제탑 렌더링 실패:</b> {html.escape(str(e))}", parse_mode="HTML")

@router.callback_query(F.data == "open_avwap")
async def process_open_avwap(callback_query: types.CallbackQuery, state: FSMContext):
    user = getattr(callback_query, "from_user", None)
    if not user or getattr(user, "id", None) != ADMIN_CHAT_ID:
        return
    print(f"💬 [TG 콜백 수신] open_avwap (User: {user.id})", flush=True)
    await state.clear()
    try:
        text, keyboard = await build_avwap_radar()
        await callback_query.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        if "message is not modified" not in str(e).lower():
            await callback_query.message.answer(f"🚨 <b>관제탑 갱신 실패:</b> {html.escape(str(e))}", parse_mode="HTML")
    finally:
        try:
            await callback_query.answer("레이더 갱신 완료")
        except Exception:
            pass

@router.message(Command("sync"))
async def cmd_sync(message: types.Message, state: FSMContext):
    user = getattr(message, "from_user", None)
    if not user or getattr(user, "id", None) != ADMIN_CHAT_ID:
        return
    print(f"💬 [TG 수신] /sync 명령 하달 (User: {user.id})", flush=True)
    await state.clear()
    try:
        msg = await message.answer("📡 <b>통합 지시서 데이터 스캔 중...</b>", parse_mode="HTML")
        text = await build_sync_board()
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 새로고침", callback_data="open_sync")],
            [InlineKeyboardButton(text="🔙 메인 메뉴", callback_data="back_to_main")]
        ])
        await msg.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        await message.answer(f"🚨 <b>통합 지시서 동기화 실패:</b> {html.escape(str(e))}", parse_mode="HTML")

@router.callback_query(F.data == "open_sync")
async def process_open_sync(callback_query: types.CallbackQuery, state: FSMContext):
    user = getattr(callback_query, "from_user", None)
    if not user or getattr(user, "id", None) != ADMIN_CHAT_ID:
        return
    print(f"💬 [TG 콜백 수신] open_sync (User: {user.id})", flush=True)
    await state.clear()
    try:
        text = await build_sync_board()
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 새로고침", callback_data="open_sync")],
            [InlineKeyboardButton(text="🔙 메인 메뉴", callback_data="back_to_main")]
        ])
        await callback_query.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        if "message is not modified" not in str(e).lower():
            await callback_query.message.answer(f"🚨 <b>갱신 실패:</b> {html.escape(str(e))}", parse_mode="HTML")
    finally:
        try:
            await callback_query.answer("동기화 완료")
        except Exception:
            pass

@router.message(Command("settlement"))
async def cmd_settlement(message: types.Message, state: FSMContext):
    user = getattr(message, "from_user", None)
    if not user or getattr(user, "id", None) != ADMIN_CHAT_ID:
        return
    print(f"💬 [TG 수신] /settlement 명령 하달 (User: {user.id})", flush=True)
    await state.clear()
    text, keyboard = await build_settlement_board()
    try:
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        pass

@router.callback_query(F.data == "open_settlement")
async def process_open_settlement(callback_query: types.CallbackQuery, state: FSMContext):
    user = getattr(callback_query, "from_user", None)
    if not user or getattr(user, "id", None) != ADMIN_CHAT_ID:
        return
    print(f"💬 [TG 콜백 수신] open_settlement (User: {user.id})", flush=True)
    await state.clear()
    try:
        text, keyboard = await build_settlement_board()
        await callback_query.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        pass

@router.callback_query(F.data.startswith("toggle_set_act_"))
async def process_toggle_set_act(callback_query: types.CallbackQuery, state: FSMContext):
    user = getattr(callback_query, "from_user", None)
    if not user or getattr(user, "id", None) != ADMIN_CHAT_ID:
        return
    symbol = callback_query.data.split("_")[3].upper()
    print(f"💬 [TG 콜백 수신] toggle_set_act_{symbol} (User: {user.id})", flush=True)
    state_data = await AssassinLedger.get_state(symbol)
    await AssassinLedger.save_state(symbol, is_active=not state_data[5])
    text, keyboard = await build_settlement_board()
    try:
        await callback_query.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        pass

@router.callback_query(F.data.startswith("toggle_profit_rate_"))
async def process_toggle_profit_rate(callback_query: types.CallbackQuery, state: FSMContext):
    user = getattr(callback_query, "from_user", None)
    if not user or getattr(user, "id", None) != ADMIN_CHAT_ID:
        return
    symbol = callback_query.data.split("_")[3].upper()
    print(f"💬 [TG 콜백 수신] toggle_profit_rate_{symbol} (User: {user.id})", flush=True)
    state_data = await AssassinLedger.get_state(symbol)
    profit_mode = state_data[12]
    
    if profit_mode == "AUTO":
        new_mode = "MANUAL_0.5"
        new_rate = 0.5
    elif profit_mode == "MANUAL_0.5":
        new_mode = "MANUAL_1.2"
        new_rate = 1.2
    else:
        new_mode = "AUTO"
        new_rate = 0.5
        
    await AssassinLedger.save_state(symbol, target_profit_rate=new_rate, profit_mode=new_mode)
    text, keyboard = await build_settlement_board()
    try:
        await callback_query.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        await callback_query.answer(f"✅ 익절 모드가 {new_mode}로 변경되었습니다.", show_alert=True)
    except Exception:
        pass

@router.callback_query(F.data.startswith("set_budget_"))
async def process_set_budget(callback_query: types.CallbackQuery, state: FSMContext):
    user = getattr(callback_query, "from_user", None)
    if not user or getattr(user, "id", None) != ADMIN_CHAT_ID:
        return
    symbol = callback_query.data.split("_")[2].upper()
    print(f"💬 [TG 콜백 수신] set_budget_{symbol} (User: {user.id})", flush=True)
    await state.set_state(BudgetState.waiting_for_budget)
    await state.update_data(symbol=symbol)
    text = f"⌨️ <b>{html.escape(symbol)} 예산 입력 (USD)</b>\n\n▫️ 투입할 달러 예산을 숫자로 전송하십시오."
    try:
        await callback_query.message.edit_text(text, parse_mode="HTML")
    except Exception:
        pass

@router.message(BudgetState.waiting_for_budget)
async def process_budget_input(message: types.Message, state: FSMContext):
    user = getattr(message, "from_user", None)
    if not user or getattr(user, "id", None) != ADMIN_CHAT_ID:
        return
        
    user_data = await state.get_data()
    symbol = user_data.get("symbol")
    if not symbol:
        return
        
    print(f"💬 [TG 상태 수신] {symbol} 예산 입력 접수: {message.text.strip()} (User: {user.id})", flush=True)
    try:
        budget = float(message.text.strip())
        await AssassinLedger.save_state(symbol, budget=budget)
        await state.clear()
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 제어반으로", callback_data="open_settlement")]])
        await message.answer(f"✅ <b>{html.escape(symbol)} 예산 ${budget:,.2f} 락온 완료.</b>", reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        await message.answer("🚨 유효한 숫자를 입력하세요.", parse_mode="HTML")

@router.message(Command("reset"))
async def cmd_reset(message: types.Message, state: FSMContext):
    user = getattr(message, "from_user", None)
    if not user or getattr(user, "id", None) != ADMIN_CHAT_ID:
        return
    print(f"💬 [TG 수신] /reset 명령 하달 (User: {user.id})", flush=True)
    await state.clear()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ 단독(SOXS) 장부 초기화", callback_data="execute_single_reset")],
        [InlineKeyboardButton(text="🔙 취소", callback_data="back_to_main")]
    ])
    text = (
        "⚠️ <b>[SOXS 장부 초기화]</b>\n\n"
        "경고: SOXS 단독 로컬 장부(평단가, 목표가, 주문 ID, NQ 기록, 세션 락)를 100% 영구 소각하고 0점으로 원자적 초기화를 수행합니다.\n"
        "진행하시겠습니까?"
    )
    try:
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        pass

@router.callback_query(F.data == "execute_single_reset")
async def process_execute_single_reset(callback_query: types.CallbackQuery, state: FSMContext):
    user = getattr(callback_query, "from_user", None)
    if not user or getattr(user, "id", None) != ADMIN_CHAT_ID:
        return
    print(f"💬 [TG 콜백 수신] execute_single_reset (User: {user.id})", flush=True)
    await state.clear()
    try:
        await AssassinLedger.save_state("SOXS", price=0.0, target_sell_price=0.0, buy_order_id="", sell_order_id="", is_session_done=False, entry_session="", entry_time=0.0, nq_entry_price=0.0, nq_entry_amp=0.0)
        
        await callback_query.answer("✅ SOXS 장부 영구 소각 완료", show_alert=True)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 메인 메뉴", callback_data="back_to_main")]
        ])
        await callback_query.message.edit_text("✅ <b>[SOXS 장부 영구 소각 완료]</b>\n▫️ SOXS 숏 전용 장부가 0점으로 초기화되었습니다.", reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        if "message is not modified" not in str(e).lower():
            try:
                await callback_query.message.answer(f"🚨 <b>초기화 실패:</b> {html.escape(str(e))}", parse_mode="HTML")
            except Exception:
                pass

@router.message(Command("update"))
async def cmd_update(message: types.Message, state: FSMContext):
    user = getattr(message, "from_user", None)
    if not user or getattr(user, "id", None) != ADMIN_CHAT_ID:
        return
    print(f"💬 [TG 수신] /update 명령 하달 (User: {user.id})", flush=True)
    await state.clear()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 구글 클라우드 서버 탑재", callback_data="execute_update")],
        [InlineKeyboardButton(text="🔙 취소", callback_data="back_to_main")]
    ])
    text = (
        "⚠️ <b>[시스템 자가 업데이트]</b>\n\n"
        "경고: 깃허브 게시판(main)에 탑재되어 있는 파이썬 코드를 다운로드 받아 구글 클라우드 서버에 강제 탑재(동기화)하고 시스템을 하드 킬(os._exit)합니다.\n"
        "진행하시겠습니까?"
    )
    try:
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        pass

@router.callback_query(F.data == "execute_update")
async def process_execute_update(callback_query: types.CallbackQuery, state: FSMContext):
    user = getattr(callback_query, "from_user", None)
    if not user or getattr(user, "id", None) != ADMIN_CHAT_ID:
        return
    print(f"💬 [TG 콜백 수신] execute_update (User: {user.id})", flush=True)
    await state.clear()
    try:
        await callback_query.message.edit_text("🔄 <b>GitHub 파이썬 코드를 다운로드 및 구글 클라우드 서버 탑재 검증 중...</b>", parse_mode="HTML")

        def _run_git_update():
            import subprocess
            import py_compile
            
            def run_cmd(cmd):
                proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                try:
                    out, err = proc.communicate(timeout=20)
                    return proc.returncode, out.strip(), err.strip()
                except subprocess.TimeoutExpired:
                    proc.kill()
                    return -1, "", "Subprocess Timeout Expired"
            
            code, current_hash, err = run_cmd("git rev-parse HEAD")
            if code != 0:
                return False, f"해시 백업 실패: {err}"
            
            code, fetch_out, fetch_err = run_cmd("git fetch origin main")
            if code != 0:
                return False, f"Fetch 실패:\n{fetch_err}"
                
            code, local_hash, _ = run_cmd("git rev-parse HEAD")
            code, remote_hash, _ = run_cmd("git rev-parse origin/main")
            
            if local_hash == remote_hash:
                return True, "Already up to date."
            
            code, reset_out, reset_err = run_cmd("git reset --hard origin/main")
            if code != 0:
                run_cmd(f"git reset --hard {current_hash}")
                return False, f"Hard Reset 붕괴 (원상 복구됨):\n{reset_err}"
                
            try:
                py_compile.compile('main.py', doraise=True)
                py_compile.compile('tg_router.py', doraise=True)
                py_compile.compile('quant_engine.py', doraise=True)
                py_compile.compile('toss_api.py', doraise=True)
                py_compile.compile('candle_recorder.py', doraise=True)
            except Exception as e:
                run_cmd(f"git reset --hard {current_hash}")
                return False, f"문법 에러 감지. 롤백 완료:\n{str(e)}"
                
            return True, f"업데이트 성공:\n{reset_out}"

        success, msg = await asyncio.to_thread(_run_git_update)
        
        if success:
            if "Already up to date." in msg:
                await callback_query.message.edit_text("✅ <b>서버 탑재 완료</b>\n▫️ 구글 클라우드 서버가 이미 최신 버전입니다.", parse_mode="HTML")
            else:
                await callback_query.message.edit_text(f"🚀 <b>탑재 성공. 구글 클라우드 코어 재기동(os._exit) 격발.</b>\n<pre>{html.escape(msg)}</pre>", parse_mode="HTML")
                await asyncio.sleep(1.0)
                os._exit(0)
        else:
            await callback_query.message.edit_text(f"🚨 <b>업데이트 실패 (롤백됨)</b>\n<pre>{html.escape(msg)}</pre>", parse_mode="HTML")

    except Exception as e:
        await callback_query.message.edit_text(f"🚨 <b>서버 탑재 붕괴 방어:</b> {html.escape(str(e))}", parse_mode="HTML")

@router.callback_query(F.data == "back_to_main")
async def process_back_to_main(callback_query: types.CallbackQuery, state: FSMContext):
    user = getattr(callback_query, "from_user", None)
    if not user or getattr(user, "id", None) != ADMIN_CHAT_ID:
        return
    print(f"💬 [TG 콜백 수신] back_to_main (User: {user.id})", flush=True)
    await state.clear()
    try:
        await callback_query.answer()
        await callback_query.message.edit_text(get_main_menu_text(), reply_markup=None, parse_mode="HTML")
    except Exception:
        pass
