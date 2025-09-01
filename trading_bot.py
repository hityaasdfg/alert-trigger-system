# nifty_llm_handoff.py
from __future__ import annotations
import json, math, datetime as dt
from typing import Optional, Dict, Any, List, Tuple
import numpy as np
import pandas as pd
from kiteconnect import KiteConnect

# === Constants ================================================================
INDEX_ALIAS = {
    "NIFTY": "NSE:NIFTY 50",
    "BANKNIFTY": "NSE:NIFTY BANK",
    "FINNIFTY": "NSE:NIFTY FIN SERVICE",
}
STRIKE_STEP = {"NIFTY": 50, "BANKNIFTY": 100, "FINNIFTY": 50}
VIX_ALIAS = "NSE:INDIAVIX"

GATES_DEFAULT = {
    "max_spread_pct_scalp": 1.0,      # per-leg bid-ask %
    "max_spread_pct_swing": 2.0,
    "min_credit_pct_of_width": 0.25,  # credit >= 25% of width (credit spreads)
    "min_rr_inverse": 0.33,           # credit/(width-credit) >= 0.33  ==> R:R <= 1:3
    "min_pop_credit": 0.70,           # POP >= 70% for short credit
    "require_non_negative_ev": True,  # EV >= 0 using POP est
    "time_no_trade_before": "09:20",
    "time_no_trade_after_intraday": "15:15"
}

# === Simple tech + options math ==============================================
def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()

def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    pc = df["close"].shift(1)
    tr = pd.concat([(df["high"]-df["low"]).abs(), (df["high"]-pc).abs(), (df["low"]-pc).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean()

def supertrend(df: pd.DataFrame, period=10, mult=3.0) -> pd.Series:
    _atr = atr(df, period); hl2 = (df["high"]+df["low"])/2
    ub = hl2 + mult*_atr; lb = hl2 - mult*_atr
    st = pd.Series(index=df.index, dtype=float)
    for i in range(len(df)):
        st.iloc[i] = ub.iloc[i] if i==0 else (lb.iloc[i] if df["close"].iloc[i] > st.iloc[i-1] else ub.iloc[i])
    return st

def _phi(x): return math.exp(-0.5*x*x)/math.sqrt(2*math.pi)
def _cdf(x): return 0.5*(1+math.erf(x/math.sqrt(2)))

def _bs_price(S,K,T,r,q,sig,typ):
    if T<=0 or sig<=0:
        return max(0.0,S-K) if typ=="CE" else max(0.0,K-S)
    d1=(math.log(S/K)+(r-q+0.5*sig*sig)*T)/(sig*math.sqrt(T)); d2=d1-sig*math.sqrt(T)
    if typ=="CE": return S*math.exp(-q*T)*_cdf(d1)-K*math.exp(-r*T)*_cdf(d2)
    return K*math.exp(-r*T)*_cdf(-d2)-S*math.exp(-q*T)*_cdf(-d1)

def _bs_greeks(S,K,T,r,q,sig,typ):
    if T<=0 or sig<=0: return {"delta":0,"gamma":0,"vega":0,"theta":0}
    rt=math.sqrt(T); d1=(math.log(S/K)+(r-q+0.5*sig*sig)*T)/(sig*rt); d2=d1-sig*rt
    disc_r=math.exp(-r*T); disc_q=math.exp(-q*T); pdf=_phi(d1)
    if typ=="CE":
        delta=disc_q*_cdf(d1)
        theta = (-(S*pdf*sig*disc_q)/(2*rt) - (r*K*disc_r*_cdf(d2)) + (q*S*disc_q*_cdf(d1)))
    else:
        delta=-disc_q*_cdf(-d1)
        theta = (-(S*pdf*sig*disc_q)/(2*rt) + (r*K*disc_r*_cdf(-d2)) - (q*S*disc_q*_cdf(-d1)))
    gamma=(disc_q*pdf)/(S*sig*rt); vega=S*disc_q*pdf*rt
    return {"delta":delta,"gamma":gamma,"vega":vega,"theta":theta}

def _implied_vol(S,K,T,r,q,px,typ,tol=1e-6,mi=50):
    if px<=0 or T<=0 or S<=0: return np.nan
    lo,hi=1e-6,5.0; sig=min(max(math.sqrt(max(px/S,1e-8)*2/T),0.05),1.5)
    for _ in range(mi):
        diff=_bs_price(S,K,T,r,q,sig,typ)-px
        if abs(diff)<tol: return sig
        v=_bs_greeks(S,K,T,r,q,sig,typ)["vega"]
        if v<1e-8: break
        sig-=diff/v
        if not(lo<sig<hi): break
    for _ in range(mi):
        mid=0.5*(lo+hi); price=_bs_price(S,K,T,r,q,mid,typ)
        if abs(price-px)<tol: return mid
        if price>px: hi=mid
        else: lo=mid
    return 0.5*(lo+hi)

# POP (risk-neutral lognormal)
def _prob_below(S0: float, K: float, T: float, sigma: float, r: float = 0.0, q: float = 0.0):
    if S0<=0 or K<=0 or T<=0 or sigma<=0: return None
    mu=(r-q-0.5*sigma*sigma)*T
    z=(math.log(K/S0)-mu)/(sigma*math.sqrt(T))
    return _cdf(z)

# === Context builder ==========================================================
def fetch_option_chain_context(
    kite: KiteConnect,
    index: str = "NIFTY",
    expiry: Optional[dt.date] = None,
    strikes_around: int = 12,
    risk_free_rate: float = 0.065,
    div_yield: float = 0.0,
    intraday_tf: str = "5minute",
    tz_close_hour: int = 15,
    tz_close_min: int = 30,
) -> Dict[str, Any]:
    """Return clean dict + DataFrame for the chain around ATM."""
    assert index in INDEX_ALIAS, f"Unsupported index: {index}"
    step = STRIKE_STEP[index]

    # Spot + change
    spot_q = kite.quote([INDEX_ALIAS[index]])[INDEX_ALIAS[index]]
    spot = float(spot_q["last_price"])
    prev_close = float(spot_q["ohlc"]["close"])
    pct_change = 100*(spot-prev_close)/prev_close if prev_close else np.nan

    # VIX
    try:
        vix = float(kite.quote([VIX_ALIAS])[VIX_ALIAS]["last_price"])
    except Exception:
        vix = None

    # Instruments / expiry
    ins = pd.DataFrame(kite.instruments())
    oc = ins[(ins.segment=="NFO-OPT") & (ins.name==index)]
    if expiry is None:
        future_exps = sorted(set(pd.to_datetime(oc["expiry"]).dt.date))
        today = dt.date.today()
        expiry = next((e for e in future_exps if (e-today).days>=0), future_exps[0])

    chain_all = oc[pd.to_datetime(oc["expiry"]).dt.date==expiry][
        ["instrument_token","exchange","tradingsymbol","strike","instrument_type","lot_size"]
    ].rename(columns={"instrument_type":"option_type"}).copy()
    chain_all["strike"]=chain_all["strike"].astype(float)

    # Strikes around ATM
    atm = round(spot/step)*step
    lo, hi = atm - step*strikes_around, atm + step*strikes_around
    sel = chain_all[(chain_all["strike"]>=lo)&(chain_all["strike"]<=hi)].copy()
    sel["ex_key"] = sel["exchange"] + ":" + sel["tradingsymbol"]

    # Batch quotes
    def batched(xs, n=180):
        for i in range(0,len(xs),n): yield xs[i:i+n]
    quotes: Dict[str,Any] = {}
    for chunk in batched(sel["ex_key"].tolist()):
        quotes.update(kite.quote(chunk))

    # T to expiry
    expiry_dt = dt.datetime.combine(expiry, dt.time(hour=tz_close_hour, minute=tz_close_min))
    now = dt.datetime.now()
    T = max((expiry_dt-now).total_seconds(),1)/(365*24*3600)

    # Enriched rows (only fields useful to an LLM)
    rows: List[Dict[str,Any]] = []
    for _, r in sel.iterrows():
        q = quotes.get(r["ex_key"], {})
        depth = q.get("depth") or {}
        buys = depth.get("buy") or []; sells = depth.get("sell") or []
        best_bid = buys[0]["price"] if buys else np.nan
        best_ask = sells[0]["price"] if sells else np.nan
        bid_qty = buys[0]["quantity"] if buys else 0
        ask_qty = sells[0]["quantity"] if sells else 0

        ltp = float(q.get("last_price", np.nan))
        mid = (best_bid+best_ask)/2 if (best_bid==best_bid and best_ask==best_ask and best_bid>0 and best_ask>0) else ltp
        spread_pct = (best_ask-best_bid)/mid*100 if (mid and mid>0 and best_ask==best_ask and best_bid==best_bid) else np.nan
        oi = q.get("oi", None); vol = q.get("volume", None)

        iv = _implied_vol(spot, float(r["strike"]), T, risk_free_rate, div_yield, float(mid or 0.0), r["option_type"])
        greeks = _bs_greeks(spot, float(r["strike"]), T, risk_free_rate, div_yield, iv if iv==iv else 0.0, r["option_type"])

        rows.append({
            "tradingsymbol": r["tradingsymbol"],
            "strike": float(r["strike"]),
            "type": r["option_type"],      # CE/PE
            "lot_size": int(r["lot_size"]),
            "ltp": ltp,
            "bid": best_bid, "ask": best_ask, "bid_qty": bid_qty, "ask_qty": ask_qty,
            "spread_pct": spread_pct,
            "oi": oi, "volume": vol,
            "iv": iv if iv==iv else None,
            "delta": greeks["delta"],
        })

    df = pd.DataFrame(rows).sort_values(["strike","type"]).reset_index(drop=True)

    # PCR + S/R (top OI)
    call_oi = df[df.type=="CE"].groupby("strike")["oi"].sum(min_count=1)
    put_oi  = df[df.type=="PE"].groupby("strike")["oi"].sum(min_count=1)
    per_strike_pcr = (put_oi/call_oi).replace([np.inf,-np.inf], np.nan)
    pcr_overall = (put_oi.sum()/call_oi.sum()) if call_oi.sum() else np.nan
    supp = put_oi.sort_values(ascending=False).head(5).index.tolist()
    res  = call_oi.sort_values(ascending=False).head(5).index.tolist()

    # IV snapshot ATM±2
    iv_tbl = df.pivot_table(index="strike", columns="type", values="iv", aggfunc="mean")
    band = [atm-2*step, atm-step, atm, atm+step, atm+2*step]
    iv_snapshot = {k: {
        "CE": float(iv_tbl.get("CE", {}).get(k, np.nan)),
        "PE": float(iv_tbl.get("PE", {}).get(k, np.nan))
    } for k in band}

    # Trend context + ATR
    idx_row = ins[(ins.tradingsymbol==INDEX_ALIAS[index].split(":")[1]) & (ins.segment=="INDICES")]
    ema21=ema50=st=trend_bias=atr_d=None
    if not idx_row.empty:
        idx_token = int(idx_row.iloc[0]["instrument_token"])
        end = dt.datetime.now(); start = end - dt.timedelta(days=5)
        intraday = pd.DataFrame(kite.historical_data(idx_token, start, end, intraday_tf))
        if not intraday.empty:
            intraday["date"]=pd.to_datetime(intraday["date"]); intraday.set_index("date", inplace=True)
            ema21 = float(ema(intraday["close"],21).iloc[-1])
            ema50 = float(ema(intraday["close"],50).iloc[-1])
            st_val = supertrend(intraday[["open","high","low","close"]])
            st = float(st_val.iloc[-1])
            trend_bias = "up" if intraday["close"].iloc[-1] > max(ema21, st) else "down"
        d_end=end; d_start=end-dt.timedelta(days=90)
        daily = pd.DataFrame(kite.historical_data(idx_token, d_start, d_end, "day"))
        if not daily.empty:
            daily["date"]=pd.to_datetime(daily["date"]); daily.set_index("date", inplace=True)
            atr_d = float(atr(daily[["open","high","low","close"]],14).iloc[-1])

    liq_flags = {
        "wide_spread_strikes": df[df["spread_pct"]>2.0]["strike"].unique().tolist(),
        "thin_depth": df[(df["bid_qty"]<1)&(df["ask_qty"]<1)]["strike"].unique().tolist(),
    }

    return {
        "spot": float(spot),
        "pct_change": float(pct_change) if pct_change==pct_change else None,
        "vix": float(vix) if vix is not None else None,
        "atm_strike": int(atm),
        "expiry": expiry.isoformat(),
        "pcr_overall": float(pcr_overall) if pcr_overall==pcr_overall else None,
        "per_strike_pcr": {float(k): float(v) for k,v in per_strike_pcr.dropna().items()},
        "support_levels": supp, "resistance_levels": res,
        "iv_snapshot": iv_snapshot,
        "trend_context": {
            "ema21": float(ema21) if ema21 is not None else None,
            "ema50": float(ema50) if ema50 is not None else None,
            "supertrend": float(st) if st is not None else None,
            "bias": trend_bias, "daily_ATR": float(atr_d) if atr_d is not None else None,
        },
        "liquidity_flags": liq_flags,
        "chain": df,  # keep DataFrame for packing
        "T_years": max((dt.datetime.combine(dt.date.fromisoformat(expiry.isoformat()), dt.time(15,30)) - dt.datetime.now()).total_seconds(),1)/(365*24*3600)
    }

# === Packing for LLM (compact, no nulls) =====================================
def _drop_nulls(d: Dict[str, Any]) -> Dict[str, Any]:
    return {k:v for k,v in d.items() if v is not None and not (isinstance(v,float) and (v!=v))}

def _compress_chain_for_ai(df: pd.DataFrame) -> List[Dict[str, Any]]:
    keep = ["tradingsymbol","strike","type","lot_size","ltp","bid","ask","bid_qty","ask_qty","spread_pct","oi","volume","iv","delta"]
    out = []
    for _,r in df[keep].iterrows():
        row = {k: (float(r[k]) if isinstance(r[k], (int,float,np.floating)) else r[k]) for k in keep}
        # drop NaNs/None
        out.append(_drop_nulls(row))
    return out

def build_ai_packet(
    index: str,
    ctx: Dict[str, Any],
    risk_envelope: Dict[str, Any],
    gates: Dict[str, Any] = GATES_DEFAULT,
    allow_strategies: List[str] = ("credit_spread","debit_spread","straddle","strangle","naked")
) -> Dict[str, Any]:
    trend = ctx.get("trend_context") or {}
    packet = {
        "index": index,
        "expiry": ctx["expiry"],
        "spot": ctx["spot"],
        "pct_change_today": ctx.get("pct_change"),
        "atm_strike": ctx["atm_strike"],
        "vix": ctx.get("vix"),
        "pcr_overall": ctx.get("pcr_overall"),
        "per_strike_pcr": ctx.get("per_strike_pcr"),
        "support_levels": ctx.get("support_levels", [])[:5],
        "resistance_levels": ctx.get("resistance_levels", [])[:5],
        "iv_snapshot_atm_band": ctx.get("iv_snapshot", {}),
        "trend_bias": trend.get("bias"),
        "ema21": trend.get("ema21"),
        "ema50": trend.get("ema50"),
        "supertrend": trend.get("supertrend"),
        "daily_atr": trend.get("daily_ATR"),
        "liquidity_flags": ctx.get("liquidity_flags", {}),
        "T_years": ctx["T_years"],
        "chain": _compress_chain_for_ai(ctx["chain"]),
        "risk_envelope": risk_envelope,
        "gates": gates,
        "allow_strategies": list(allow_strategies)
    }
    # strip nulls at top-level too
    return _drop_nulls(packet)

def build_llm_prompt() -> str:
    """Tight instruction for the LLM. You will send this + the JSON packet."""
    return (
        "SYSTEM: You are an index options trade approver. Decide GO/NO_GO and propose ONE trade.\n"
        "HARD GATES (must all pass for GO):\n"
        "- Time filter: no new intraday trades before 09:20 IST or after 15:15 IST.\n"
        "- Liquidity: each leg bid-ask <= 1% (scalp) or <= 2% (swing) and visible depth.\n"
        "- If credit_spread: credit >= 25% of width, R:R <= 1:3, POP >= 70%, EV >= 0.\n"
        "- Use ATM IV (avg CE/PE) and T_years from context to estimate POP via lognormal.\n"
        "SELECTION:\n"
        "- Consider strategies in allow_strategies. Prefer defined-risk if shorting premium.\n"
        "- For bearish: bear call credit or put debit; for bullish: bull put credit or call debit; for neutral: short strangle/straddle only if gates pass.\n"
        "EXITS:\n"
        "- Provide spread-level target/stop on NET premium. Include per-leg for the actively managed leg only.\n"
        "OUTPUT: Return ONLY minified JSON, NO text, matching this schema (no nulls):\n"
        "{"
        "\"decision\":\"GO|NO_GO\","
        "\"strategy\":\"credit_spread|debit_spread|straddle|strangle|naked\","
        "\"side\":\"bullish|bearish|neutral\","
        "\"breakevens\": {\"lower\":number?,\"upper\":number?},"
        "\"win_chance_pct\":int,"
        "\"win_reason\":[\"...\"],"
        "\"entry\":{\"net_premium\":number},"
        "\"exits\":{\"spread_net\":{\"target_net\":number,\"stop_net\":number},\"per_leg\":[{\"symbol\":\"string\",\"target_premium\":number,\"stop_premium\":number}]},"
        "\"risk\":{\"per_lot_margin_est\":number,\"per_lot_max_profit\":number,\"per_lot_max_loss\":number},"
        "\"position\":{\"lot_size\":int,\"lot_count\":int},"
        "\"orders\":[{\"symbol\":\"string\",\"side\":\"BUY|SELL\",\"quantity\":int,\"product\":\"MIS|NRML\",\"order_type\":\"MARKET|LIMIT\"}],"
        "\"flags\":[\"time_window|liquidity|risk_budget|volatility_low|volatility_high|trend_mismatch|overnight_risky\"],"
        "\"horizon\":{\"suggestion\":\"intraday_only|carry_ok\",\"reasons\":[\"...\"]}"
        "}"
    )

# === Finalizer (use after LLM returns JSON) ==================================
def finalize_ai_decision(ai_json: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ensures totals are correct and losses are negative.
    If totals are missing, computes them from per-lot and lot_count.
    Returns a clean dict (no nulls).
    """
    p = json.loads(json.dumps(ai_json))  # deep copy
    ls = int(p["position"]["lot_size"])
    lc = int(p["position"]["lot_count"])
    entry = float(p["entry"]["net_premium"])
    tgt = float(p["exits"]["spread_net"]["target_net"])
    stp = float(p["exits"]["spread_net"]["stop_net"])
    payoff = "credit_spread" if p["strategy"]=="credit_spread" else "debit_spread"

    if payoff=="credit_spread":
        target_per_lot = round((entry - tgt)*ls, 2)
        stop_per_lot   = round((entry - stp)*ls, 2)   # negative
    else:
        target_per_lot = round((tgt - entry)*ls, 2)
        stop_per_lot   = round((stp - entry)*ls, 2)   # negative

    totals = {
        "target_rupees_per_lot": target_per_lot,
        "stop_rupees_per_lot":   stop_per_lot,
        "target_rupees_total":   round(target_per_lot*lc, 2),
        "stop_rupees_total":     round(stop_per_lot*lc, 2),
        "max_profit_rupees_total": round(float(p["risk"]["per_lot_max_profit"])*lc, 2),
        "max_loss_rupees_total":  -round(float(p["risk"]["per_lot_max_loss"])*lc, 2)  # NEGATIVE
    }
    p["totals"] = totals
    # drop any null-like keys in per-leg
    clean_legs = []
    for leg in p["exits"].get("per_leg", []):
        clean_legs.append(_drop_nulls(leg))
    p["exits"]["per_leg"] = clean_legs
    return p

# === Demo ====================================================================
if __name__ == "__main__":
    # 1) Zerodha auth
    
    access_token_path = r"\\Velocity\c\Users\kunal\Downloads\LIVE_TICK_HIGH_LOW_FLASK\LIVE_TICK_HIGH_LOW_FLASK\zerodha_access_token.txt"
    access_token = open(access_token_path).read().strip()
    API_KEY = "zuuxkho8imp70m8c"

    kite = KiteConnect(api_key=API_KEY)
    try:
        kite.set_access_token(access_token)
    except Exception:
        kite = KiteConnect(api_key=API_KEY, access_token=access_token)

    # 2) Build context and AI packet
    ctx = fetch_option_chain_context(kite, index="NIFTY", strikes_around=12)
    risk_env = {
        "available_capital": 1_200_000,
        "pending_margin_used": 0.0,
        "max_risk_per_trade_pct": 0.02,
        "intraday": True,
        "risk_tolerance": "medium"
    }
    packet = build_ai_packet("NIFTY", ctx, risk_env, gates=GATES_DEFAULT,
                             allow_strategies=["credit_spread","debit_spread"])  # keep it tight if you want

    prompt = build_llm_prompt()

    # 3) Print what you’ll feed to the LLM
    print("=== PROMPT FOR LLM ===")
    print(prompt)
    print("\n=== JSON PACKET FOR LLM ===")
    print(json.dumps(packet, indent=2))  # truncated preview

    # 4) After you call your local LLM and get ai_json back, run:
    # ai_json = <your_ollama_response_json>
    # final = finalize_ai_decision(ai_json)
    # print(json.dumps(final, indent=2))
