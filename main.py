# =====================================================================
# FILE: main.py
# 목적: SOXS 단독 암살자 엔진 가동 (04:01 분기망 덫 영구 유지 + 제로오버나잇)
# =====================================================================
# MODIFIED: 초과 Case 67 방어 - NQ=F 동적 덤핑 방향성 락온 (abs 소각, 상승장 전용 단방향 쉴드 결속)
# NEW: 04:00~04:01 틱 다수결 분기망 및 휩소 바이패스(Whipsaw Bypass) 절대 락온
# MODIFIED: 타임아웃 킬러 소각 - 발사된 모든 매수 주문(현재가 지정가/VWAP 덫)은 09:29까지 휩소 노출 체결 강제 (무한 대기)

import sys
import os
import math
import time
import asyncio
import html
import logging
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from dotenv import load_dotenv

from toss_api import TossApiClient
from quant_engine import AssassinLedger, AVWAPEngine, MacroDataCache
from tg_router import router, inject_dependencies
from candle_recorder import record_candles_loop

logging.getLogger("aiogram").setLevel(logging.CRITICAL)
logging.getLogger("aiohttp").setLevel(logging.CRITICAL)

env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
load_dotenv(dotenv_path=env_path)

TOSS_CLIENT_ID = os.getenv("TOSS_CLIENT_ID")
TOSS_CLIENT_SECRET = os.getenv("TOSS_CLIENT_SECRET")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
_telegram_chat_id_str = os.getenv("TELEGRAM_CHAT_ID")

if not all([TOSS_CLIENT_ID, TOSS_CLIENT_SECRET, TELEGRAM_BOT_TOKEN, _telegram_chat_id_str]):
    print("🚨 치명적 에러: 필수 환경변수 누락.", flush=True)
    sys.exit(1)

ADMIN_CHAT_ID = int(_telegram_chat_id_str)
wakeup_event = asyncio.Event()

HOLIDAY_TRANSLATIONS = {
    "New Year's Day": "신정 (New Year's Day)",
    "Martin Luther King Jr. Day": "마틴 루터 킹 주니어 탄생일 (MLK Day)",
    "Washington's Birthday": "대통령의 날 (Presidents' Day)",
    "Good Friday": "성금요일 (Good Friday)",
    "Memorial Day": "메모리얼 데이 (Memorial Day)",
    "Juneteenth National Independence Day": "노예해방기념일 (Juneteenth)",
    "Independence Day": "독립기념일 (Independence Day)",
    "Labor Day": "노동절 (Labor Day)",
    "Thanksgiving Day": "추수감사절 (Thanksgiving Day)",
    "Christmas": "크리스마스 (Christmas Day)",
    "Christmas Day": "크리스마스 (Christmas Day)",
    "주말 (Weekend)": "주말 (Weekend)"
}

in_memory_ordering_lock = {"SOXS": False}
shared_holdings = {"SOXS": 0}

idempotency_keys = {
    "SOXS": {"BUY": None, "TRAP": None, "MOC": None, "M_DUMP": None}
}

holiday_notify_lock = asyncio.Lock()
last_holiday_notified_date = ""

async def fetch_full_session_candles(client: TossApiClient, symbol: str, session_start_est: datetime) -> list:
    all_candles = []
    before = None
    
    for _ in range(6): 
        try:
            candles_page = await client.get_1m_candles_pagination(symbol, count=200, before=before)
            candles = candles_page.get("candles", [])
            all_candles.extend(candles)
            
            if not candles: break
            oldest_time = pd.to_datetime(candles[-1]['timestamp'], utc=True).tz_convert(ZoneInfo('America/New_York'))
            if oldest_time <= session_start_est: break
            
            before = candles_page.get("nextBefore")
            if not before: break
        except Exception:
            break
            
    return all_candles

def _run_git_update_sync() -> tuple[bool, str]:
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

async def auto_update_loop(bot: Bot, chat_id: int):
    while True:
        try:
            now_est = datetime.now(ZoneInfo('America/New_York'))
            
            if 4 <= now_est.hour < 17:
                await asyncio.sleep(3600.0)
                continue
                
            success, msg = await asyncio.to_thread(_run_git_update_sync)
            
            if success:
                if "Already up to date." not in msg:
                    await bot.send_message(
                        chat_id=chat_id,
                        text=f"🚀 <b>[무인 자동 업데이트 성공]</b>\n▫️ 최신 코드가 백그라운드에서 감지되어 구글 클라우드 서버에 안전하게 탑재되었습니다.\n▫️ 파이썬 컴파일 검증 완료. 코어 재기동(os._exit) 격발.\n<pre>{html.escape(msg)}</pre>",
                        parse_mode="HTML"
                    )
                    await asyncio.sleep(1.0)
                    os._exit(0)
            else:
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"🚨 <b>[무인 자동 업데이트 실패 및 롤백]</b>\n<pre>{html.escape(msg)}</pre>",
                    parse_mode="HTML"
                )
                
        except Exception as e:
            print(f"🚨 [무인 업데이트망 붕괴 방어] {e}", flush=True)
            
        await asyncio.sleep(3600.0)

async def assassin_loop(client: TossApiClient, bot: Bot, chat_id: int, symbol: str):
    global last_holiday_notified_date
    last_moc_tick = 0.0
    moc_dump_active = False
    last_heartbeat_hour = -1
    last_logged_session = ""
    prev_is_active = None 
    last_gc_date = ""
    
    last_error_msg = ""
    last_trap_error_msg = ""
    
    pre_ticks_up = 0
    pre_ticks_down = 0
    whipsaw_bypass_active = False

    async def notify_tg(text: str):
        try:
            await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
        except Exception as e:
            print(f"🚨 [텔레그램 전송 붕괴 방어] {e}", flush=True)

    while True:
        try:
            await asyncio.wait_for(wakeup_event.wait(), timeout=1.5)
            wakeup_event.clear()
        except asyncio.TimeoutError:
            pass
        
        try:
            now_est = datetime.now(ZoneInfo('America/New_York'))
            est_time_int = now_est.hour * 100 + now_est.minute
            today_str = now_est.strftime("%Y-%m-%d")

            try:
                holdings_detail = await client.get_symbol_holdings_detail(symbol)
                holdings_qty = int(math.floor(holdings_detail['qty']))
                shared_holdings[symbol] = holdings_qty
                
                if last_error_msg != "":
                    await notify_tg(f"✅ <b>[aVWAP {symbol}] 토스증권 API 통신망 복구 완료</b>\n▫️ 서버 응답 정상화. 레이더 감시 및 전술 연산을 즉시 재개합니다.")
                    print(f"✅ [통신 복구 {symbol}] 억제 해 해제 및 정상화 타전 완료.", flush=True)
                    last_error_msg = ""
            except Exception as e:
                err_str = str(e)
                if err_str != last_error_msg:
                    await notify_tg(f"🚨 <b>[aVWAP {symbol}] 통신 붕괴 (유령 잔고 방어)</b>\n▫️ 사유: {html.escape(err_str)}")
                    last_error_msg = err_str
                else:
                    print(f"🔇 [알람 무한 침묵 {symbol}] 동일 통신 에러 타전 영구 억제 중: {err_str}", flush=True)
                await asyncio.sleep(5)
                continue

            (last_buy_price, budget, target_profit_rate, last_session_id, is_session_done, is_active, 
             target_sell_price, sell_order_id, entry_session, entry_time,
             nq_entry_price, nq_entry_amp) = await AssassinLedger.get_state(symbol)
            
            buy_order_id = await AssassinLedger.get_buy_order_id(symbol)

            if prev_is_active is None:
                prev_is_active = is_active
            just_turned_off = (prev_is_active is True and is_active is False)
            prev_is_active = is_active

            if 17 <= now_est.hour < 19 and last_gc_date != today_str:
                last_gc_date = today_str
                in_memory_ordering_lock[symbol] = False
                idempotency_keys[symbol] = {"BUY": None, "TRAP": None, "MOC": None, "M_DUMP": None}
                last_moc_tick = 0.0
                moc_dump_active = False
                pre_ticks_up = 0
                pre_ticks_down = 0
                whipsaw_bypass_active = False
                if holdings_qty == 0:
                    await AssassinLedger.save_state(symbol, buy_order_id="", sell_order_id="", entry_session="", entry_time=0.0, nq_entry_price=0.0, nq_entry_amp=0.0)
                print(f"🧹 [GC {symbol}] 17:00~18:59 EST 윈도우 진입. 락 해제 및 자정 초기화 확증 완료.", flush=True)
                await asyncio.sleep(60)
                continue
            
            try:
                is_open, _, sess_name, _ = await asyncio.wait_for(client.is_market_open(), timeout=10.0)
            except Exception:
                is_open = True
                sess_name = "UNKNOWN"

            if not is_open and (sess_name and (sess_name.startswith("HOLIDAY") or sess_name in ["CLOSED", "UNKNOWN"])):
                if sess_name.startswith("HOLIDAY"):
                    raw_reason = sess_name.split("|")[1] if "|" in sess_name else "미국 주식시장 정규 휴장"
                    translated_reason = HOLIDAY_TRANSLATIONS.get(raw_reason, raw_reason)
                    reason = html.escape(translated_reason)
                    
                    if last_holiday_notified_date != today_str:
                        if 400 <= est_time_int <= 405:
                            async with holiday_notify_lock:
                                if last_holiday_notified_date != today_str:
                                    last_holiday_notified_date = today_str
                                    await notify_tg(f"🛑 <b>[시스템 대기] 미국 주식시장 휴무 안내</b>\n▫️ 사유: {reason}\n▫️ 조치: 금일 전술 가동 전면 차단 및 레이더망 휴식")
                                    print(f"🛑 [휴장 감지] {today_str} {reason} - 시스템 대기.", flush=True)
                await asyncio.sleep(60.0)
                continue

            if 400 <= est_time_int < 930:
                hardcoded_session = "preMarket"
                base_h, base_m = 4, 0
                base_date = now_est
            elif 930 <= est_time_int < 1600:
                hardcoded_session = "regularMarket"
                base_h, base_m = 9, 30
                base_date = now_est
            elif 1600 <= est_time_int <= 1859:
                hardcoded_session = "afterMarket"
                base_h, base_m = 16, 0
                base_date = now_est
            else:
                hardcoded_session = "dayMarket"
                base_h, base_m = 19, 0
                base_date = now_est if now_est.hour >= 19 else now_est - timedelta(days=1)
                
            session_baseline_est = base_date.replace(hour=base_h, minute=base_m, second=0, microsecond=0)
            current_session_id = f"{session_baseline_est.strftime('%Y%m%d_%H%M')}_{hardcoded_session}"

            if hardcoded_session != last_logged_session:
                if last_logged_session:
                    print(f"🔄 [세션 전이 {symbol}] {last_logged_session} ➡️ {hardcoded_session} 진입 완료.", flush=True)
                last_logged_session = hardcoded_session

            if now_est.hour != last_heartbeat_hour:
                print(f"💓 [맥박 {symbol}] 논 시계: {now_est.strftime('%Y-%m-%d %H:%M:%S')} EST | 세션: {hardcoded_session} | 활성: {is_active} | 잔고: {holdings_qty}주", flush=True)
                last_heartbeat_hour = now_est.hour

            nq_c_global, nq_h_global, nq_l_global = await MacroDataCache.get_cached_nq_data()
            nq_amp_global = ((nq_h_global - nq_l_global) / nq_l_global * 100.0) if nq_l_global > 0.0 else 0.0

            dynamic_threshold = nq_entry_amp * 0.5 if nq_entry_amp > 0.0 else 0.0
            
            nq_diff_pct = ((nq_c_global - nq_entry_price) / nq_entry_price * 100.0) if nq_entry_price > 0.0 else 0.0

            is_macro_breach = (nq_amp_global >= 2.0)
            is_dynamic_breach = (nq_entry_price > 0.0 and dynamic_threshold > 0.0 and nq_c_global > 0.0 and nq_diff_pct >= dynamic_threshold)

            is_reg_moc = ((now_est.hour == 15 and now_est.minute == 59) or (now_est.hour == 16 and 0 <= now_est.minute <= 1))

            if is_reg_moc and is_active:
                if not in_memory_ordering_lock[symbol]:
                    current_time = time.time()
                    if current_time - last_moc_tick >= 1.5:
                        in_memory_ordering_lock[symbol] = True
                        try:
                            if sell_order_id:
                                try:
                                    await client.cancel_order(sell_order_id)
                                except Exception as e:
                                    print(f"🚨 [MOC 매도 주문 취소 방어] {e}", flush=True)
                                finally:
                                    await AssassinLedger.save_state(symbol, sell_order_id="", target_sell_price=0.0)
                                    sell_order_id = ""
                                    target_sell_price = 0.0

                            open_orders = await client.get_orders(status="OPEN", symbol=symbol)
                            cancel_issued = False
                            if open_orders:
                                for order in open_orders:
                                    try:
                                        await client.cancel_order(order["orderId"])
                                        cancel_issued = True
                                    except Exception as e:
                                        print(f"🚨 [MOC 미체결 취소 방어] {e}", flush=True)
                            
                            if cancel_issued:
                                await asyncio.sleep(0.5)
                                idempotency_keys[symbol]["MOC"] = None
                                
                            holdings_detail_moc = await client.get_symbol_holdings_detail(symbol)
                            dump_qty = int(math.floor(holdings_detail_moc['qty']))
                            
                            if dump_qty > 0:
                                orderbook = await client.get_orderbook(symbol)
                                bids = orderbook.get("bids", [])
                                current_price = await client.get_current_price(symbol)
                                
                                bid_1_price = float(bids[0]["price"]) if bids and float(bids[0]["price"]) > 0.0 else current_price
                                
                                if bid_1_price > 0.0:
                                    idem = idempotency_keys[symbol]["MOC"]
                                    if not idem:
                                        idem = {"key": f"MOC_{symbol}_{now_est.strftime('%H%M%S')}"[:36], "qty": dump_qty, "price": bid_1_price}
                                        idempotency_keys[symbol]["MOC"] = idem
                                    else:
                                        dump_qty = idem["qty"]
                                        bid_1_price = idem["price"]
                                        
                                    client_id = idem["key"]
                                    
                                    try:
                                        await asyncio.wait_for(
                                            client.create_order(
                                                symbol=symbol, side="SELL", order_type="LIMIT",
                                                quantity=dump_qty, price=f"{bid_1_price:.2f}",
                                                client_order_id=client_id
                                            ),
                                            timeout=2.0
                                        )
                                        
                                        print(f"🔴 [매도 덤핑 스윕 {symbol}] 1.5초 주기 타격! 수량: {dump_qty}주 | 단가: ${bid_1_price:.2f}", flush=True)
                                        await AssassinLedger.save_state(symbol, is_session_done=True)
                                        
                                        if not moc_dump_active:
                                            moc_dump_active = True
                                            await notify_tg(f"🔴 <b>[aVWAP {symbol}] 15:59~16:01 제로오버나이트 덤핑망 결속</b>\n▫️ 1.5초 간격 체결 추적 및 매수 1호가 지속 폭격 개시")
                                            
                                        idempotency_keys[symbol]["MOC"] = None
                                    except asyncio.TimeoutError:
                                        print(f"🚨 [MOC 타임아웃 방어 {symbol}] API 응답 2초 초과. 병목 회피 및 락 해제.", flush=True)
                            else:
                                await AssassinLedger.save_state(symbol, is_session_done=True) 
                        except Exception as e:
                            err_str = str(e)
                            print(f"🚨 [MOC 방어] {err_str}", flush=True)
                            if any(code in err_str for code in ["400", "422", "404", "409"]):
                                idempotency_keys[symbol]["MOC"] = None
                        finally:
                            last_moc_tick = time.time()
                            in_memory_ordering_lock[symbol] = False
                continue
            else:
                moc_dump_active = False

            if is_macro_breach and is_active and not in_memory_ordering_lock[symbol]:
                if not is_session_done:
                    in_memory_ordering_lock[symbol] = True
                    try:
                        open_orders_macro = await client.get_orders(status="OPEN", symbol=symbol)
                        for order in open_orders_macro:
                            if order.get("side") == "BUY":
                                try:
                                    await client.cancel_order(order["orderId"])
                                except Exception as e:
                                    print(f"🚨 [매크로 매수 취소 방어] {e}", flush=True)
                        await AssassinLedger.save_state(symbol, is_session_done=True)
                        print(f"🛑 [매크로 진입 차단 {symbol}] NQ=F 진폭 {nq_amp_global:.2f}% 도달. 당일 신규 미체결 매수 원자적 파기 및 소각.", flush=True)
                    except Exception as e:
                        print(f"🚨 [매크로 매수 파기 방어 {symbol}] {e}", flush=True)
                    finally:
                        in_memory_ordering_lock[symbol] = False

            if (is_macro_breach or is_dynamic_breach) and is_active and not in_memory_ordering_lock[symbol]:
                if holdings_qty > 0:
                    current_price = await client.get_current_price(symbol)
                    avg_price_dump = float(holdings_detail.get('avg_price', 0.0))
                    if avg_price_dump <= 0.0: 
                        avg_price_dump = last_buy_price
                    
                    if avg_price_dump > 0.0 and current_price < avg_price_dump:
                        in_memory_ordering_lock[symbol] = True
                        try:
                            if sell_order_id:
                                try:
                                    await client.cancel_order(sell_order_id)
                                except Exception as e:
                                    print(f"🚨 [매크로 지정가 매도 덫 취소 방어] {e}", flush=True)
                                finally:
                                    await AssassinLedger.save_state(symbol, sell_order_id="", target_sell_price=0.0)
                                    sell_order_id = ""
                                    target_sell_price = 0.0
                                    await asyncio.sleep(0.5)
                            
                            open_orders = await client.get_orders(status="OPEN", symbol=symbol)
                            cancel_issued = False
                            if open_orders:
                                for order in open_orders:
                                    if order.get("side") == "SELL":
                                        try:
                                            await client.cancel_order(order["orderId"])
                                            cancel_issued = True
                                        except Exception as e:
                                            print(f"🚨 [매크로 추가 매도 취소 방어] {e}", flush=True)
                            
                            if cancel_issued:
                                await asyncio.sleep(0.5)
                                idempotency_keys[symbol]["M_DUMP"] = None
                                
                            holdings_detail_mdump = await client.get_symbol_holdings_detail(symbol)
                            dump_qty = int(math.floor(holdings_detail_mdump['qty']))
                            
                            if dump_qty > 0:
                                orderbook = await client.get_orderbook(symbol)
                                bids = orderbook.get("bids", [])
                                bid_1_price = float(bids[0]["price"]) if bids and float(bids[0]["price"]) > 0.0 else current_price
                                
                                if bid_1_price > 0.0:
                                    idem = idempotency_keys[symbol]["M_DUMP"]
                                    is_new_dump = (idem is None)
                                    if not idem:
                                        idem = {"key": f"MDUMP_{symbol}_{now_est.strftime('%H%M%S')}"[:36], "qty": dump_qty, "price": bid_1_price}
                                        idempotency_keys[symbol]["M_DUMP"] = idem
                                    else:
                                        dump_qty = idem["qty"]
                                        bid_1_price = idem["price"]
                                        
                                    client_id = idem["key"]
                                        
                                    await asyncio.wait_for(
                                        client.create_order(
                                            symbol=symbol, side="SELL", order_type="LIMIT",
                                            quantity=dump_qty, price=f"{bid_1_price:.2f}",
                                            client_order_id=client_id
                                        ),
                                        timeout=2.0
                                    )
                                    await AssassinLedger.save_state(symbol, is_session_done=True)
                                    
                                    if is_new_dump: 
                                        reason_msg = f"NQ=F 당일 전체 진폭 <code>{nq_amp_global:.2f}%</code> (2.0% 초과 확증)" if is_macro_breach else f"진입 시점 지수({nq_entry_price:.2f}) 대비 <code>{nq_diff_pct:.2f}%</code> 상승 (동적 임계치 {dynamic_threshold:.2f}% 이탈)"
                                        await notify_tg(
                                            f"🚨 <b>[aVWAP {symbol}] 대세장 이탈 손실 덤핑 격발</b>\n"
                                            f"▫️ 사유: {reason_msg}\n"
                                            f"▫️ 손익 상태: 마이너스 (계좌 붕괴 위험)\n"
                                            f"▫️ 조치: 지정가 매도 덫 원자적 파기 및 전량 시장가(LIMIT) 덤핑 퇴근"
                                        )
                                    print(f"🚨 [매크로 손실 덤핑 {symbol}] 방어 스윕 발사 완료. 사유: {reason_msg}", flush=True)
                                    
                                    idempotency_keys[symbol]["M_DUMP"] = None
                        except Exception as e:
                            err_str = str(e)
                            print(f"🚨 [매크로 덤핑 방어 {symbol}] {err_str}", flush=True)
                            if any(code in err_str for code in ["400", "422", "404", "409"]):
                                idempotency_keys[symbol]["M_DUMP"] = None
                        finally:
                            in_memory_ordering_lock[symbol] = False
                        continue

            if not is_open:
                continue
                
            current_price = await client.get_current_price(symbol)
            if current_price <= 0.0:
                continue

            # 09:30 EST 정규장 개장 시 프리장 미체결 덫/요격 전면 파기 및 신규 매수 권한 소각
            if est_time_int >= 930 and est_time_int < 1600:
                if not is_session_done:
                    if buy_order_id and holdings_qty == 0:
                        if not in_memory_ordering_lock[symbol]:
                            in_memory_ordering_lock[symbol] = True
                            try:
                                await client.cancel_order(buy_order_id)
                                await asyncio.sleep(0.5)
                                await notify_tg(f"🧹 <b>[aVWAP {symbol}] 정규장 개장 (미체결 주문 파기)</b>\n▫️ 사유: 09:30 EST 도달\n▫️ 조치: 프리장 미체결 매수 파기 및 당일 신규 매수 권한 영구 소각")
                            except Exception as e:
                                print(f"🚨 [09:30 덫 파기 방어 {symbol}] {e}", flush=True)
                            finally:
                                await AssassinLedger.save_state(symbol, buy_order_id="", entry_session="", entry_time=0.0, is_session_done=True)
                                in_memory_ordering_lock[symbol] = False
                                is_session_done = True
                                buy_order_id = ""
                    else:
                        await AssassinLedger.save_state(symbol, is_session_done=True)
                        is_session_done = True
                        if holdings_qty == 0:
                            print(f"🎯 [aVWAP {symbol}] 정규장 진입. 당일 신규 매수 권한 소각 완료.", flush=True)

            if current_session_id != last_session_id:
                if holdings_qty == 0:
                    can_reset = True
                    if buy_order_id:
                        try:
                            od = await client.get_order_detail(buy_order_id)
                            if od.get("status") in ["PENDING", "PARTIAL_FILLED"]:
                                can_reset = False
                        except Exception:
                            can_reset = False
                            
                    if can_reset:
                        await AssassinLedger.save_state(symbol, price=0.0, target_sell_price=0.0, last_session_id=current_session_id, is_session_done=False, buy_order_id="", sell_order_id="", entry_session="", entry_time=0.0, nq_entry_price=0.0, nq_entry_amp=0.0)
                        is_session_done = False
                        target_sell_price = 0.0
                        buy_order_id = ""
                        sell_order_id = ""
                else:
                    await AssassinLedger.save_state(symbol, last_session_id=current_session_id)
                last_session_id = current_session_id

            if holdings_qty == 0 and (target_sell_price > 0.0 or buy_order_id or sell_order_id):
                if not in_memory_ordering_lock[symbol]:
                    idem_buy_check = idempotency_keys[symbol]["BUY"]
                    is_rbuy_active = (idem_buy_check is not None and idem_buy_check["key"].startswith("RBUY_"))
                    
                    can_clear = True
                    if buy_order_id:
                        try:
                            od = await client.get_order_detail(buy_order_id)
                            st = od.get("status", "")
                            if st in ["PENDING", "PARTIAL_FILLED", "PENDING_CANCEL", "PENDING_REPLACE"] or is_rbuy_active:
                                can_clear = False
                        except Exception:
                            can_clear = False
                            
                    if can_clear:
                        in_memory_ordering_lock[symbol] = True
                        try:
                            exit_price, filled_qty = 0.0, 0.0
                            try:
                                orders = await client.get_orders(status="CLOSED", symbol=symbol)
                                for o in orders:
                                    if o.get("side") == "SELL" and o.get("status") in ["FILLED", "PARTIAL_FILLED"]:
                                        exec_info = o.get("execution", {})
                                        avg_p = float(exec_info.get("averageFilledPrice") or 0.0)
                                        f_qty = float(exec_info.get("filledQuantity") or 0.0)
                                        if avg_p > 0 and f_qty > 0:
                                            exit_price, filled_qty = avg_p, f_qty
                                            break
                            except Exception as e:
                                print(f"🚨 [매도 정보 추출 방어] {e}", flush=True)

                            entry_price = last_buy_price
                            pnl_str = ""
                            if entry_price > 0 and exit_price > 0 and filled_qty > 0:
                                principal = entry_price * filled_qty
                                gross = exit_price * filled_qty
                                pnl_amt = gross - principal
                                pnl_rate = (exit_price / entry_price - 1.0) * 100.0
                                sign = "+" if pnl_amt > 0 else ""
                                pnl_str = f"\n▫️ 타점: 매수 ${entry_price:.2f} ➡️ 매도 ${exit_price:.2f}\n▫️ 손익: {sign}{pnl_rate:.2f}% ({sign}${pnl_amt:.2f})"
                            else:
                                pnl_str = "\n▫️ 타점: 체결 데이터 추출 지연 (장부 참조 요망)"

                            now_est_check = datetime.now(ZoneInfo('America/New_York'))
                            is_moc_time = ((now_est_check.hour == 15 and now_est_check.minute >= 59) or (now_est_check.hour == 16 and 0 <= now_est_check.minute <= 5))
                            
                            is_trap_survived = False
                            is_take_profit_exit = False
                            if sell_order_id:
                                try:
                                    od = await client.get_order_detail(sell_order_id)
                                    st = od.get("status", "")
                                    if st == "FILLED":
                                        is_take_profit_exit = True
                                    elif st in ["PENDING", "PARTIAL_FILLED", "PENDING_CANCEL", "PENDING_REPLACE"]:
                                        is_trap_survived = True
                                        
                                    await client.cancel_order(sell_order_id)
                                    print(f"🧹 [고아 덫 파기 {symbol}] 잔고 0주 연동. 서버단 지정가 매도 주문({sell_order_id}) 파기 완료.", flush=True)
                                    await asyncio.sleep(0.5)
                                except Exception as e:
                                    print(f"🚨 [고아 덫 파기 방어 {symbol}] 404 무시(이미 취소/실행됨) 또는 통신 오류: {e}", flush=True)

                            is_trap_set = bool(target_sell_price > 0.0 or sell_order_id)
                            is_manual_exit = is_trap_set and not is_take_profit_exit and not is_moc_time and not is_trap_survived
                            is_buy_cancel_exit = not is_trap_set
                            is_moc_exit = is_moc_time

                            await AssassinLedger.save_state(symbol, price=0.0, target_sell_price=0.0, buy_order_id="", sell_order_id="", is_session_done=True, entry_session="", entry_time=0.0, nq_entry_price=0.0, nq_entry_amp=0.0)
                            target_sell_price = 0.0
                            buy_order_id = ""
                            sell_order_id = ""
                            is_session_done = True
                            
                            if is_buy_cancel_exit:
                                print(f"🧹 [매수 취소/실패 {symbol}] 덫 장전 이력 부재. 허위 익절 타전 억제 및 장부 초기화 완료.", flush=True)
                            elif is_moc_exit:
                                await notify_tg(f"🛑 <b>[aVWAP {symbol}] MOC 강제 덤핑 청산 완료</b>\n▫️ 잔고 0주 (제로-오버나이트 락온){pnl_str}")
                            elif is_take_profit_exit:
                                await notify_tg(f"🎉 <b>[aVWAP {symbol}] 거래 종료 (퇴근 락온 완료)</b>\n▫️ 잔고 0주 (지정가 매도 체결 확인){pnl_str}\n▫️ 당일 신규 진입 권한 영구 소각")
                            elif is_manual_exit:
                                await notify_tg(f"🛑 <b>[aVWAP {symbol}] 수동 매도 청산 감지 (퇴근 락온 완료)</b>\n▫️ 잔고 0주 (오프라인 등 수동 청산 식별){pnl_str}\n▫️ 당일 신규 진입 권한 영구 소각 완료")
                        finally:
                            in_memory_ordering_lock[symbol] = False

            if hardcoded_session == "dayMarket":
                vwap_price = 0.0
            else:
                candles_json = await fetch_full_session_candles(client, symbol, session_baseline_est)
                vwap_price = AVWAPEngine.calculate_vwap(candles_json, session_baseline_est)

            # 04:00~04:01 1분 틱 수집 및 다수결 판정망
            if est_time_int == 400 and vwap_price > 0.0:
                if current_price >= vwap_price:
                    pre_ticks_up += 1
                else:
                    pre_ticks_down += 1
            elif est_time_int < 400:
                pre_ticks_up = 0
                pre_ticks_down = 0
                whipsaw_bypass_active = False

            # NEW: 04:01 틱 다수결 분기망 및 휩소 바이패스 (Whipsaw Bypass) 절대 락온
            if is_active and not is_session_done and hardcoded_session == "preMarket":
                if 401 <= est_time_int <= 929 and vwap_price > 0.0:
                    if holdings_qty == 0 and not buy_order_id:
                        if not in_memory_ordering_lock[symbol]:
                            in_memory_ordering_lock[symbol] = True
                            try:
                                if nq_amp_global >= 2.0:
                                    await AssassinLedger.save_state(symbol, is_session_done=True)
                                    await notify_tg(f"🛑 <b>[aVWAP {symbol}] 대세장 이탈 감지 (매수 차단)</b>\n▫️ 사유: NQ=F 실시간 전체 진폭 <code>{nq_amp_global:.2f}%</code>\n▫️ 조치: 추세 붕괴로 돌파 요격 취소 및 관망 퇴근")
                                    continue
                                
                                my_hold_check = await client.get_symbol_holdings_detail(symbol)
                                if int(math.floor(my_hold_check.get('qty', 0.0))) == 0:
                                    trigger_fire = False
                                    target_price = 0.0
                                    tag = ""

                                    # 지각 기동으로 인한 수집 누락 시 현재가 1틱으로 즉석 다수결 세팅
                                    if pre_ticks_up == 0 and pre_ticks_down == 0:
                                        if current_price >= vwap_price:
                                            pre_ticks_up = 1
                                        else:
                                            pre_ticks_down = 1

                                    if not whipsaw_bypass_active:
                                        if pre_ticks_up > pre_ticks_down:
                                            trigger_fire = True
                                            target_price = vwap_price
                                            tag = "VWAP 지정가 덫 (상회 틱 다수결)"
                                        else:
                                            if current_price >= vwap_price:
                                                whipsaw_bypass_active = True
                                                print(f"🚨 [휩소 바이패스 {symbol}] 04:01 가격이 VWAP 상회 펌핑 감지. 타격 보류 및 대기 진입.", flush=True)
                                            else:
                                                trigger_fire = True
                                                target_price = current_price
                                                tag = "즉각 타격 (하회 틱 다수결)"
                                    else:
                                        if current_price < vwap_price:
                                            trigger_fire = True
                                            target_price = current_price
                                            tag = "휩소 바이패스 통과 즉각 타격"
                                            whipsaw_bypass_active = False

                                    if trigger_fire and target_price > 0.0:
                                        try:
                                            current_bp = await client.get_usd_buying_power()
                                            safe_bp = current_bp * 0.995
                                            actual_budget = min(budget, safe_bp)
                                        except Exception:
                                            actual_budget = budget
                                            
                                        target_qty = int(math.floor(actual_budget / target_price))
                                        
                                        if target_qty > 0:
                                            idem = idempotency_keys[symbol]["BUY"]
                                            if not idem:
                                                idem = {"key": f"BUY_{symbol}_{now_est.strftime('%H%M%S')}"[:36], "qty": target_qty, "price": target_price}
                                                idempotency_keys[symbol]["BUY"] = idem
                                            else:
                                                target_qty = idem["qty"]
                                                target_price = idem["price"]
                                                
                                            res = await client.create_order(
                                                symbol=symbol, side="BUY", order_type="LIMIT",
                                                quantity=target_qty, price=f"{target_price:.2f}",
                                                client_order_id=idem["key"]
                                            )
                                            
                                            if res and isinstance(res, dict) and res.get("result", {}).get("orderId"):
                                                await AssassinLedger.save_state(symbol, buy_order_id=str(res["result"]["orderId"]), entry_session="preMarket_Trap", entry_time=time.time(), nq_entry_price=nq_c_global, nq_entry_amp=nq_amp_global)
                                                
                                                await notify_tg(
                                                    f"🎯 <b>[aVWAP {symbol}] 분기망 {tag} 장전</b>\n"
                                                    f"▫️ 기준 VWAP: ${vwap_price:.2f} | 실시간 현재가: ${current_price:.2f}\n"
                                                    f"▫️ 팩트 타격가: ${target_price:.2f}\n"
                                                    f"▫️ 틱 다수결(1분): 상회({pre_ticks_up}) vs 하회({pre_ticks_down})\n"
                                                    f"▫️ 수량: {target_qty}주 (09:29 정각 무조건 대기 및 파기 예정)"
                                                )
                                            idempotency_keys[symbol]["BUY"] = None
                            except Exception as e:
                                err_str = str(e)
                                print(f"🚨 [분기망 장전 방어 {symbol}] {err_str}", flush=True)
                                if any(code in err_str for code in ["400", "422", "404", "409", "401", "403", "429"]):
                                    idempotency_keys[symbol]["BUY"] = None
                                    if "400" in err_str or "422" in err_str:
                                        await AssassinLedger.save_state(symbol, is_session_done=True)
                                        await notify_tg(f"🛑 <b>[aVWAP {symbol}] 매수 요격 영구 셧다운</b>\n▫️ 사유: 400/422 무한 루프 감지\n▫️ 조치: 매수 권한 100% 영구 소각")
                            finally:
                                in_memory_ordering_lock[symbol] = False

            open_orders = await client.get_orders(status="OPEN", symbol=symbol)
            has_open_sell = any(o["side"] == "SELL" for o in open_orders)
            has_open_buy = any(o["side"] == "BUY" for o in open_orders) 
            
            if not is_active:
                if sell_order_id:
                    if not in_memory_ordering_lock[symbol]:
                        in_memory_ordering_lock[symbol] = True
                        notify_msg = ""
                        try:
                            await client.cancel_order(sell_order_id)
                            notify_msg = f"🛑 <b>[aVWAP {symbol}] 수동 오버나이트(가동 OFF) 전환</b>\n▫️ 조치: 기장전된 지정가 매도 주문 안전 파기 완료"
                        except Exception as e:
                            err_str = str(e).lower()
                            if "404" in err_str or "not-found" in err_str or "already" in err_str:
                                notify_msg = f"🛑 <b>[aVWAP {symbol}] 수동 오버나이트(가동 OFF) 전환</b>\n▫️ 조치: 로컬 덫 장부 초기화 완료 (서버단 이미 증발)"
                            else:
                                notify_msg = f"🛑 <b>[aVWAP {symbol}] 수동 오버나이트(가동 OFF) 전환</b>\n▫️ 조치: 매도 주문 취소 통신 에러 자체 흡수 완료"
                            print(f"🚨 [수동 OFF 덫 파기 방어 {symbol}] {e}", flush=True)
                        finally:
                            await AssassinLedger.save_state(symbol, sell_order_id="", target_sell_price=0.0)
                            print(f"🛑 [수동 오버나이트 {symbol}] 가동 OFF 감지. 매도 덫 파기 확증 완료.", flush=True)
                            if notify_msg:
                                await notify_tg(notify_msg)
                            sell_order_id = ""
                            target_sell_price = 0.0
                            await asyncio.sleep(0.5)
                            in_memory_ordering_lock[symbol] = False
                elif just_turned_off:
                    await notify_tg(f"🛑 <b>[aVWAP {symbol}] 수동 오버나이트(가동 OFF) 전환</b>\n▫️ 조치: 파기할 매도 주문 부재 확인. 시스템 대기 모드로 안전 전환 완료")
            
            if holdings_qty > 0 and sell_order_id and is_active:
                try:
                    od = await client.get_order_detail(sell_order_id)
                    status_trap = od.get("status", "")
                    if status_trap in ["CANCELED", "REJECTED"]:
                        await notify_tg(f"🚨 <b>[aVWAP {symbol}] 유령 지정가 덫 증발 감지</b>\n▫️ 사유: 상태 변이({status_trap})\n▫️ 조치: 덫 파기 및 자동 재장전 가동")
                        await AssassinLedger.save_state(symbol, sell_order_id="")
                        sell_order_id = ""
                except Exception as e:
                    err_str = str(e).lower()
                    if "404" in err_str or "not-found" in err_str:
                        await notify_tg(f"🚨 <b>[aVWAP {symbol}] 유령 지정가 덫 증발 감지</b>\n▫️ 사유: 서버 404 (수동 취소 추정)\n▫️ 조치: 덫 파기 및 자동 재장전 가동")
                        await AssassinLedger.save_state(symbol, sell_order_id="")
                        sell_order_id = ""
                    else:
                        print(f"🚨 [지정가 덫 유령 감시 방어 {symbol}] {e}", flush=True)
            
            if holdings_qty > 0 and not has_open_sell and not has_open_buy and not sell_order_id and not in_memory_ordering_lock[symbol] and is_active:
                calculated_target = target_sell_price
                
                avg_price = float(holdings_detail.get('avg_price', 0.0))
                if avg_price <= 0.0:
                    avg_price = last_buy_price

                is_rearm = True
                trap_tag = "" 
                skip_trap = False
                
                if calculated_target <= 0.0:
                    if buy_order_id:
                        try:
                            order_detail = await client.get_order_detail(buy_order_id)
                            status = order_detail.get("status", "")
                            
                            if status in ["PENDING", "PARTIAL_FILLED", "PENDING_CANCEL", "PENDING_REPLACE"]:
                                skip_trap = True
                            elif status in ["FILLED", "CANCELED", "REJECTED"]:
                                is_rearm = False
                            else:
                                skip_trap = True
                        except Exception as e:
                            print(f"🚨 [덫 대기망 방어 {symbol}] 주문 상태 프로빙 실패. 통신 에러 자체 흡수 및 덫 장전 보류: {e}", flush=True)
                            skip_trap = True
                    else:
                        is_rearm = False

                    if skip_trap:
                        continue

                    if avg_price > 0.0:
                        calculated_target = math.ceil(avg_price * (1.0 + target_profit_rate / 100.0) * 100) / 100.0
                        trap_tag = f"+{target_profit_rate}%" if entry_session in ["preMarket_Trap"] and buy_order_id else f"수동개입(+{target_profit_rate}%)"

                trap_qty = holdings_qty

                if calculated_target > 0.0 and trap_qty > 0 and not skip_trap:
                    in_memory_ordering_lock[symbol] = True
                    try:
                        idem = idempotency_keys[symbol]["TRAP"]
                        if not idem:
                            idem = {"key": f"TRAP_{symbol}_{now_est.strftime('%Y%m%d_%H%M%S')}"[:36], "qty": trap_qty, "price": calculated_target}
                            idempotency_keys[symbol]["TRAP"] = idem
                        else:
                            trap_qty = idem["qty"]
                            calculated_target = idem["price"]

                        client_id = idem["key"]

                        res = await client.create_order(
                            symbol=symbol, side="SELL", order_type="LIMIT",
                            quantity=trap_qty, price=f"{calculated_target:.2f}",
                            client_order_id=client_id
                        )
                        
                        print(f"🟢 [익절 덫 장전 {symbol}] 당일 유효 지정가 매도(LIMIT) 위임 완료. 수량: {trap_qty}주 | 덫 단가: ${calculated_target:.2f}", flush=True)
                        
                        new_sell_id = ""
                        if res and isinstance(res, dict) and res.get("result", {}).get("orderId"):
                            new_sell_id = str(res["result"]["orderId"])
                        
                        if not is_rearm:
                            if not buy_order_id:
                                await AssassinLedger.save_state(symbol, price=avg_price, target_sell_price=calculated_target, sell_order_id=new_sell_id, is_session_done=True, entry_session="MANUAL")
                                is_session_done = True
                            else:
                                await AssassinLedger.save_state(symbol, price=avg_price, target_sell_price=calculated_target, sell_order_id=new_sell_id)
                            await notify_tg(f"🟢 <b>[aVWAP {symbol}] {trap_tag} 기계적 지정가 매도 덫 장전</b>\n▫️ 팩트 평단가: ${avg_price:.2f}\n▫️ 익절 덫: ${calculated_target:.2f}\n▫️ 수량: {trap_qty}주")
                        else:
                            await AssassinLedger.save_state(symbol, sell_order_id=new_sell_id)
                            await notify_tg(f"🟢 <b>[aVWAP {symbol}] 포지션 지정가 매도 덫 재장전</b>\n▫️ 유지 평단가: ${avg_price:.2f}\n▫️ 익절 덫: ${calculated_target:.2f}\n▫️ 수량: {trap_qty}주")
                        
                        idempotency_keys[symbol]["TRAP"] = None
                        last_trap_error_msg = ""
                    except Exception as e:
                        err_str = str(e)
                        if any(code in err_str for code in ["400", "422", "404", "409", "401", "403"]):
                            idempotency_keys[symbol]["TRAP"] = None
                        if err_str != last_trap_error_msg:
                            await notify_tg(f"🚨 <b>[TRAP 에러 {symbol}]</b> {html.escape(err_str)}\n▫️ 조치: 멱등성 데드락 해제 및 재장전 파이프라인 가동 (5초 쿨다운 락온)")
                            last_trap_error_msg = err_str
                        else:
                            print(f"🔇 [TRAP 무한 침묵 {symbol}] 동일 통신 에러 타전 영구 억제 중: {err_str}", flush=True)
                        print(f"🚨 [TRAP 방어] {err_str}", flush=True)
                        await asyncio.sleep(5.0)
                    finally:
                        in_memory_ordering_lock[symbol] = False
                continue

        except Exception as e:
            print(f"🚨 [aVWAP {symbol}] 감시망 붕괴 방어: {e}", flush=True)

async def main():
    session = AiohttpSession(timeout=10.0)
    bot = Bot(token=TELEGRAM_BOT_TOKEN, session=session)
    dp = Dispatcher()
    
    api_client = TossApiClient(client_id=TOSS_CLIENT_ID, client_secret=TOSS_CLIENT_SECRET)
    
    try:
        await api_client.fetch_account_seq()
    except Exception as e:
        print(f"🚨 [초기 기동 방어] 토스 API 서버 점검 또는 통신 장애로 계좌 연동 지연 (자동 재시도 예정): {e}", flush=True)
    
    inject_dependencies(api_client, ADMIN_CHAT_ID, wakeup_event)
    dp.include_router(router)
    
    asyncio.create_task(api_client.token_renewal_loop())
    asyncio.create_task(auto_update_loop(bot, ADMIN_CHAT_ID))
    
    # MODIFIED: SOXS 단독 운영 (배타적 단일 진입)
    asyncio.create_task(assassin_loop(api_client, bot, ADMIN_CHAT_ID, "SOXS"))
    asyncio.create_task(record_candles_loop(api_client, "SOXS"))
    
    print("시스템 코어 및 SOXS 단일 암살자 방어망 결합 완료. 폴링 개시...", flush=True)
    
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await bot.send_message(
            chat_id=ADMIN_CHAT_ID, 
            text="✅ <b>[시스템 기동 완료]</b>\n▫️ 서버 재부팅 및 SOXS 단독 통제망(조건주문 소각) 코어 결속\n▫️ 04:01 정적 VWAP 덫(영구) 및 분기 타격망 락온 완료.", 
            parse_mode="HTML"
        )
    except Exception:
        pass
        
    while True:
        try:
            await dp.start_polling(bot)
        except Exception as e:
            print(f"🚨 [통신 붕괴 방어] 5초 후 치유 재가동: {e}", flush=True)
            await asyncio.sleep(5)
        else:
            break

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
