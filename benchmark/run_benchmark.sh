#!/usr/bin/env bash
# Benchmark: FastAPI vs Tachyon API
# Run with: bash benchmark/run_benchmark.sh
# Requires: wrk  (brew install wrk)

set -u

DURATION=10
CONNECTIONS=100
THREADS=4
WARMUP=3
PORT_FA=8001
PORT_TA=8002

cd "$(dirname "$0")/.."

FA_VER=$(python -c "import fastapi; print(fastapi.__version__)" 2>/dev/null || echo "?")
TA_VER=$(python -c "import tachyon_api; print(tachyon_api.__version__)" 2>/dev/null || echo "dev")

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  FastAPI v${FA_VER} (Pydantic v2) vs Tachyon API v${TA_VER}"
echo "  ${DURATION}s · ${CONNECTIONS} connections · ${THREADS} threads · 1 worker"
echo "  uvicorn + uvloop + httptools"
echo "═══════════════════════════════════════════════════════════"
echo ""

cleanup() { kill "$FA_PID" "$TA_PID" 2>/dev/null || true; }
trap cleanup EXIT

uvicorn benchmark.app_fastapi:app --port $PORT_FA --workers 1 \
    --loop uvloop --http httptools --log-level error --no-access-log &
FA_PID=$!

uvicorn benchmark.app_tachyon:app --port $PORT_TA --workers 1 \
    --loop uvloop --http httptools --log-level error --no-access-log &
TA_PID=$!

sleep 2

RESULTS_FILE="/tmp/bench_results_$$.txt"

# ── Lua scripts ──────────────────────────────────────────────────────────
SCRIPT_POST_ITEM="/tmp/bench_post_item_$$.lua"
SCRIPT_POST_ORDER="/tmp/bench_post_order_$$.lua"
SCRIPT_AUTH="/tmp/bench_auth_$$.lua"

cat > "$SCRIPT_POST_ITEM" << 'LUA'
wrk.method = "POST"
wrk.headers["Content-Type"] = "application/json"
wrk.body = '{"name":"Widget","price":9.99,"in_stock":true}'
LUA

cat > "$SCRIPT_POST_ORDER" << 'LUA'
wrk.method = "POST"
wrk.headers["Content-Type"] = "application/json"
wrk.body = '{"customer":"Alice","lines":[{"item_id":1,"qty":2},{"item_id":2,"qty":1}]}'
LUA

cat > "$SCRIPT_AUTH" << 'LUA'
wrk.headers["x-api-key"] = "secret"
LUA

# ── scenario runner ───────────────────────────────────────────────────────
run_scenario() {
    local name="$1"
    local fa_path="$2"
    local ta_path="$3"
    local extra="${4:-}"

    echo "▶ ${name}"

    wrk -t2 -c10 -d"${WARMUP}s" ${extra} "http://localhost:${PORT_FA}${fa_path}" >/dev/null 2>&1 || true
    wrk -t2 -c10 -d"${WARMUP}s" ${extra} "http://localhost:${PORT_TA}${ta_path}" >/dev/null 2>&1 || true

    FA_OUT=$(wrk -t"$THREADS" -c"$CONNECTIONS" -d"${DURATION}s" ${extra} "http://localhost:${PORT_FA}${fa_path}" 2>/dev/null)
    TA_OUT=$(wrk -t"$THREADS" -c"$CONNECTIONS" -d"${DURATION}s" ${extra} "http://localhost:${PORT_TA}${ta_path}" 2>/dev/null)

    FA_RPS=$(echo "$FA_OUT" | awk '/Requests\/sec/{print $2}')
    TA_RPS=$(echo "$TA_OUT" | awk '/Requests\/sec/{print $2}')
    FA_LAT=$(echo "$FA_OUT" | awk '/Latency/{print $2}')
    TA_LAT=$(echo "$TA_OUT" | awk '/Latency/{print $2}')

    python3 -c "
fa=float('${FA_RPS:-0}'); ta=float('${TA_RPS:-0}')
delta = (ta/fa - 1)*100 if fa>0 else 0
sign  = '+' if delta>=0 else ''
color = '\033[0;32m' if delta>=0 else '\033[0;31m'
reset = '\033[0m'
print(f'  FastAPI  — {fa:>10,.0f} req/s  latency ${FA_LAT:-?}')
print(f'  Tachyon  — {ta:>10,.0f} req/s  latency ${TA_LAT:-?}')
print(f'  Speedup  — {color}{ta/fa:.2f}x  ({sign}{delta:.1f}%){reset}')
print()
with open('$RESULTS_FILE', 'a') as f:
    f.write('${name}|{:.0f}|{:.0f}\n'.format(fa, ta))
"
}

# ── scenarios ────────────────────────────────────────────────────────────
run_scenario "1. Hello World" \
    "/hello" "/hello"

run_scenario "2. Path + query params" \
    "/items/42?q=test&limit=5" "/items/42?q=test&limit=5"

run_scenario "3. Body — simple Struct/Model" \
    "/items" "/items" "-s $SCRIPT_POST_ITEM"

run_scenario "4. Body — nested Struct/Model" \
    "/orders" "/orders" "-s $SCRIPT_POST_ORDER"

run_scenario "5. Response model serialization" \
    "/users/1" "/users/1"

run_scenario "6. Header param + auth" \
    "/auth" "/auth" "-s $SCRIPT_AUTH"

run_scenario "7. Dependency injection" \
    "/users/1/profile" "/users/1/profile"

run_scenario "8. Multiple query params" \
    "/search?q=foo&page=1&size=20&active=true" \
    "/search?q=foo&page=1&size=20&active=true"

# ── summary ───────────────────────────────────────────────────────────────
echo "═══════════════════════════════════════════════════════════"
echo "  SUMMARY — req/s  (higher is better)"
echo "═══════════════════════════════════════════════════════════"
python3 << PYEOF
lines = open("$RESULTS_FILE").read().strip().split('\n')
rows = []
for line in lines:
    name, fa, ta = line.split('|')
    rows.append((name, float(fa), float(ta)))

print(f"  {'Scenario':<42} {'FastAPI':>10} {'Tachyon':>10} {'Δ':>10}")
print(f"  {'─'*42} {'─'*10} {'─'*10} {'─'*10}")

total_fa = 0; total_ta = 0
for name, fa, ta in rows:
    delta = (ta/fa - 1)*100 if fa > 0 else 0
    sign  = "+" if delta >= 0 else ""
    color = "\033[0;32m" if delta >= 0 else "\033[0;31m"
    reset = "\033[0m"
    print(f"  {name:<42} {fa:>10,.0f} {ta:>10,.0f} {color}{sign}{delta:>9.1f}%{reset}")
    total_fa += fa; total_ta += ta

print(f"  {'─'*42} {'─'*10} {'─'*10} {'─'*10}")
ratio   = total_ta / total_fa if total_fa > 0 else 0
overall = (ratio - 1) * 100
sign    = "+" if overall >= 0 else ""
color   = "\033[0;32m" if overall >= 0 else "\033[0;31m"
reset   = "\033[0m"
print(f"  {'TOTAL (sum of req/s)':<42} {total_fa:>10,.0f} {total_ta:>10,.0f} {color}{sign}{overall:.1f}% ({ratio:.2f}x){reset}")
PYEOF
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "  Apple Silicon · Python 3.10 · uvicorn + uvloop + httptools · 1 worker"
echo ""

rm -f "$SCRIPT_POST_ITEM" "$SCRIPT_POST_ORDER" "$SCRIPT_AUTH" "$RESULTS_FILE"
