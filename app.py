"""AURORA AI TRADER: public Kraken market data and local paper trading only."""
from __future__ import annotations
import os, sqlite3, time, math, asyncio, logging, secrets, base64, binascii
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime, timezone
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT=Path(__file__).resolve().parent
DB=Path(os.getenv('AURORA_DB', str(ROOT/'aurora.db')))
KRAKEN='https://api.kraken.com/0/public'
START=10000.0

logging.basicConfig(level=os.getenv('LOG_LEVEL','INFO'))
log=logging.getLogger('aurora')
AUTO_INTERVAL=int(os.getenv('AUTO_INTERVAL_SECONDS','60'))
MAX_TRADE_EUR=float(os.getenv('MAX_TRADE_EUR','200'))
MAX_OPEN_MARKETS=int(os.getenv('MAX_OPEN_MARKETS','10'))
AUTO_DEFAULT=os.getenv('AUTO_PAPER_DEFAULT','true').lower() == 'true'
scan_task=None
last_action={}
app=FastAPI(title='AURORA AI TRADER', version='0.3.0')

@app.middleware('http')
async def protect_app(request, call_next):
    # Health checks are intentionally public; every dashboard, static and API route requires Basic Auth.
    if request.url.path == '/healthz':
        return await call_next(request)
    username=os.getenv('AURORA_USERNAME','')
    password=os.getenv('AURORA_PASSWORD','')
    if not username or not password:
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse('AURORA ist noch nicht konfiguriert: Zugangsdaten fehlen.', status_code=503)
    auth=request.headers.get('authorization','')
    valid=False
    if auth.startswith('Basic '):
        try:
            decoded=base64.b64decode(auth[6:], validate=True).decode('utf-8')
            supplied_user, supplied_password=decoded.split(':',1)
            valid=secrets.compare_digest(supplied_user,username) and secrets.compare_digest(supplied_password,password)
        except (ValueError, UnicodeDecodeError, binascii.Error):
            valid=False
    if not valid:
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse('Anmeldung erforderlich.', status_code=401, headers={'WWW-Authenticate':'Basic realm=\"AURORA AI TRADER\", charset=\"UTF-8\"'})
    # Prevent cross-site browser form/fetch requests from changing paper-trading state.
    if request.method in ('POST','PUT','PATCH','DELETE'):
        origin=request.headers.get('origin')
        if not origin or origin.rstrip('/') != str(request.base_url).rstrip('/'):
            from fastapi.responses import PlainTextResponse
            return PlainTextResponse('Ungültiger Origin für schreibende Anfrage.', status_code=403)
    return await call_next(request)

@app.get('/healthz')
def healthz():
    return {'ok':True}

app.mount('/static', StaticFiles(directory=ROOT/'static'), name='static')

@contextmanager
def db():
    conn=sqlite3.connect(DB, timeout=10)
    conn.row_factory=sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally: conn.close()

def init_db():
    with db() as c:
        c.execute('CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        c.execute('CREATE TABLE IF NOT EXISTS trades (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, pair TEXT NOT NULL, side TEXT NOT NULL, quantity REAL NOT NULL, price REAL NOT NULL, fee REAL NOT NULL)')
        c.execute('CREATE TABLE IF NOT EXISTS positions (pair TEXT PRIMARY KEY, quantity REAL NOT NULL, cost REAL NOT NULL)')
        c.execute('CREATE TABLE IF NOT EXISTS signals (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, pair TEXT NOT NULL, action TEXT NOT NULL, score REAL NOT NULL, detail TEXT NOT NULL)')
        c.execute("INSERT OR IGNORE INTO state VALUES ('cash', ?)", (str(START),))
        c.execute("INSERT OR IGNORE INTO state VALUES ('paused', '0')")
        c.execute("INSERT OR IGNORE INTO state VALUES ('auto_enabled', ?)", ('1' if AUTO_DEFAULT else '0',))
        c.execute("INSERT OR IGNORE INTO state VALUES ('scan_count', '0')")
init_db()

async def kraken(endpoint, params=None):
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            r=await client.get(f'{KRAKEN}/{endpoint}', params=params)
            r.raise_for_status()
            data=r.json()
        if data.get('error'): raise HTTPException(502, f"Kraken: {data['error']}")
        return data['result']
    except httpx.HTTPError as e:
        raise HTTPException(503, 'Kraken-Marktdaten momentan nicht erreichbar') from e

@app.get('/')
def index(): return FileResponse(ROOT/'static'/'index.html')

@app.get('/api/status')
def status():
    with db() as c:
        s=dict((r['key'],r['value']) for r in c.execute('SELECT * FROM state'))
    return {'mode':'PAPER_ONLY','starting_capital':START,'cash':float(s['cash']),'paused':s['paused']=='1','live_trading_enabled':False,'auto_paper_enabled':s.get('auto_enabled')=='1','scan_count':int(s.get('scan_count','0')),'scan_interval_seconds':AUTO_INTERVAL,'max_markets':MAX_OPEN_MARKETS,'max_trade_eur':MAX_TRADE_EUR,'data_source':'Kraken public REST; not connected to account'}

@app.get('/api/markets')
async def markets():
    result=await kraken('AssetPairs')
    pairs=[]
    for key,v in result.items():
        if v.get('status') not in (None,'online') or v.get('wsname') is None: continue
        if v.get('quote') not in ('ZEUR','ZUSD','USD','EUR'): continue
        if v.get('wsname','').endswith(('.d','.m')): continue
        pairs.append({'id':key,'name':v['wsname'],'base':v.get('base'),'quote':v.get('quote'),'ordermin':v.get('ordermin'),'pair_decimals':v.get('pair_decimals',2)})
    pairs.sort(key=lambda x: (0 if x['name'] in ('BTC/EUR','XBT/EUR','ETH/EUR','SOL/EUR','XRP/EUR','ADA/EUR','LINK/EUR') else 1,x['name']))
    return {'pairs':pairs,'count':len(pairs)}

@app.get('/api/ticker/{pair}')
async def ticker(pair:str):
    data=await kraken('Ticker',{'pair':pair})
    if not data: raise HTTPException(404,'Markt nicht gefunden')
    x=next(iter(data.values()))
    return {'price':float(x['c'][0]),'bid':float(x['b'][0]),'ask':float(x['a'][0]),'volume_24h':float(x['v'][1]),'high_24h':float(x['h'][1]),'low_24h':float(x['l'][1]),'timestamp':datetime.now(timezone.utc).isoformat()}

@app.get('/api/candles/{pair}')
async def candles(pair:str, interval:int=15):
    if interval not in (1,5,15,30,60,240,1440): raise HTTPException(400,'Ungültiges Intervall')
    result=await kraken('OHLC',{'pair':pair,'interval':interval})
    rows=next((v for k,v in result.items() if k!='last'),[])
    return {'candles':[{'time':int(x[0]),'open':float(x[1]),'high':float(x[2]),'low':float(x[3]),'close':float(x[4]),'volume':float(x[6])} for x in rows[:-1][-240:]],'interval':interval,'note':'Unvollständige aktuelle Kerze ausgeschlossen'}

def ema(values, span):
    out=values[0]; a=2/(span+1)
    for v in values[1:]: out=a*v+(1-a)*out
    return out

def rsi(values, period=14):
    diffs=[b-a for a,b in zip(values[:-1],values[1:])][-period:]
    gains=sum(max(x,0) for x in diffs)/period
    losses=sum(max(-x,0) for x in diffs)/period
    return 100 if losses==0 else 100-100/(1+gains/losses)

@app.get('/api/signal/{pair}')
async def signal(pair:str,interval:int=15):
    result=await candles(pair,interval)
    values=[x['close'] for x in result['candles']]
    if len(values)<60: raise HTTPException(422,'Zu wenig historische Daten')
    fast=ema(values[-100:],12); slow=ema(values[-100:],26); momentum=rsi(values)
    change=(values[-1]/values[-6]-1)*100
    score=50+(18 if fast>slow else -18)+(12 if momentum>55 else -12 if momentum<45 else 0)+(10 if change>0 else -10)
    score=max(0,min(100,score))
    action='BUY' if score>=75 and momentum<75 else 'SELL' if score<=25 else 'HOLD'
    return {'pair':pair,'action':action,'score':score,'rsi':round(momentum,2),'ema12':round(fast,8),'ema26':round(slow,8),'momentum_5_candles_pct':round(change,3),'price':values[-1],'method':'Heuristischer Indikator-Score, keine trainierte KI und keine Gewinnwahrscheinlichkeit','interval':interval}

class Order(BaseModel):
    pair:str=Field(min_length=2,max_length=40)
    side:str
    amount_eur:float=Field(gt=0,le=10000)

@app.post('/api/paper/order')
async def paper_order(order:Order):
    if order.side not in ('buy','sell'): raise HTTPException(400,'side muss buy oder sell sein')
    # Only EUR-quoted spot markets are supported for paper order accounting.
    pairs=(await markets())['pairs']
    market=next((p for p in pairs if p['id']==order.pair),None)
    if not market or market['quote'] not in ('ZEUR','EUR'):
        raise HTTPException(400,'Nur EUR-Spotmärkte erlaubt')
    t=await ticker(order.pair)
    price=t['ask'] if order.side=='buy' else t['bid']
    fee_rate=.004 # deliberately conservative illustrative fee; not an actual fee quote
    slippage_rate=.001
    effective=price*(1+slippage_rate if order.side=='buy' else 1-slippage_rate)
    qty=order.amount_eur/effective
    if not math.isfinite(qty) or qty<=0: raise HTTPException(400,'Ungültige Ordergröße')
    minimum=float(market.get('ordermin') or 0)
    if qty<minimum: raise HTTPException(400,f'Mindestmenge: {minimum}')
    fee=order.amount_eur*fee_rate
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        s=dict((r['key'],r['value']) for r in c.execute('SELECT * FROM state'))
        if s['paused']=='1': raise HTTPException(409,'Paper-Trading pausiert')
        cash=float(s['cash'])
        pos=c.execute('SELECT quantity,cost FROM positions WHERE pair=?',(order.pair,)).fetchone()
        old_qty=pos['quantity'] if pos else 0
        old_cost=pos['cost'] if pos else 0
        if order.side=='buy':
            if order.amount_eur+fee>cash+1e-8: raise HTTPException(400,'Nicht genug virtuelles Guthaben')
            new_cash=cash-order.amount_eur-fee
            new_qty=old_qty+qty
            new_cost=old_cost+order.amount_eur+fee
        else:
            if qty>old_qty+1e-10: raise HTTPException(400,'Nicht genügend virtuelle Coins')
            new_cash=cash+order.amount_eur-fee
            new_qty=max(0,old_qty-qty)
            new_cost=old_cost*(new_qty/old_qty) if old_qty else 0
        c.execute("UPDATE state SET value=? WHERE key='cash'",(str(new_cash),))
        if new_qty<1e-10: c.execute('DELETE FROM positions WHERE pair=?',(order.pair,))
        else: c.execute('INSERT INTO positions VALUES (?,?,?) ON CONFLICT(pair) DO UPDATE SET quantity=excluded.quantity,cost=excluded.cost',(order.pair,new_qty,new_cost))
        c.execute('INSERT INTO trades (ts,pair,side,quantity,price,fee) VALUES (?,?,?,?,?,?)',(datetime.now(timezone.utc).isoformat(),order.pair,order.side,qty,effective,fee))
    return {'success':True,'mode':'PAPER','side':order.side,'quantity':qty,'effective_price':effective,'fee':fee,'cash':new_cash,'note':'Simulierte Ausführung; angenommene Gebühr 0,4 % und Slippage 0,1 %'}

@app.get('/api/paper/signals')
def recent_signals():
    with db() as c:
        rows=[dict(r) for r in c.execute('SELECT * FROM signals ORDER BY id DESC LIMIT 50')]
    return {'signals':rows}

class AutoSetting(BaseModel):
    enabled: bool

@app.post('/api/paper/auto')
def set_auto(setting:AutoSetting):
    with db() as c:
        c.execute("UPDATE state SET value=? WHERE key='auto_enabled'",('1' if setting.enabled else '0',))
    return {'auto_paper_enabled':setting.enabled,'live_trading_enabled':False}

@app.get('/api/paper/portfolio')
def portfolio():
    with db() as c:
        cash=float(c.execute("SELECT value FROM state WHERE key='cash'").fetchone()[0])
        positions=[dict(r) for r in c.execute('SELECT * FROM positions')]
        trades=[dict(r) for r in c.execute('SELECT * FROM trades ORDER BY id DESC LIMIT 30')]
    return {'cash':cash,'positions':positions,'trades':trades,'starting_capital':START,'note':'Positionswerte benötigen aktuelle Kurse; Cash ist kein Gesamtkontowert'}

@app.post('/api/paper/pause')
def pause():
    with db() as c:
        current=c.execute("SELECT value FROM state WHERE key='paused'").fetchone()[0]
        new='0' if current=='1' else '1'
        c.execute("UPDATE state SET value=? WHERE key='paused'",(new,))
    return {'paused':new=='1'}


async def auto_scan_loop():
    """Conservative paper-only scanner. No private Kraken endpoints or real orders."""
    while True:
        try:
            with db() as c:
                state=dict((r['key'],r['value']) for r in c.execute('SELECT * FROM state'))
            if state.get('auto_enabled') == '1' and state.get('paused') != '1':
                all_pairs=(await markets())['pairs']
                preferred=('BTC/EUR','XBT/EUR','ETH/EUR','SOL/EUR','XRP/EUR','ADA/EUR','LINK/EUR')
                eur_pairs=[x for x in all_pairs if x.get('quote') in ('ZEUR','EUR')]
                eur_pairs.sort(key=lambda x:(0 if x.get('name') in preferred else 1,x.get('name','')))
                selected=eur_pairs[:max(1,MAX_OPEN_MARKETS)]
                for market in selected:
                    pair=market['id']
                    now=time.monotonic()
                    if now-last_action.get(pair,0) < 900:
                        continue
                    try:
                        sig=await signal(pair,15)
                        with db() as c:
                            c.execute('INSERT INTO signals (ts,pair,action,score,detail) VALUES (?,?,?,?,?)',
                                      (datetime.now(timezone.utc).isoformat(),pair,sig['action'],sig['score'],
                                       f"RSI={sig['rsi']}; EMA12={sig['ema12']}; EMA26={sig['ema26']}"))
                            c.execute("UPDATE state SET value=CAST(value AS INTEGER)+1 WHERE key='scan_count'")
                            pos=c.execute('SELECT quantity FROM positions WHERE pair=?',(pair,)).fetchone()
                            cash=float(c.execute("SELECT value FROM state WHERE key='cash'").fetchone()[0])
                        if sig['action']=='BUY' and not pos and cash > 10:
                            amount=min(MAX_TRADE_EUR,cash/1.004)
                            await paper_order(Order(pair=pair,side='buy',amount_eur=amount))
                            last_action[pair]=time.monotonic()
                        elif sig['action']=='SELL' and pos:
                            t=await ticker(pair)
                            amount=min(MAX_TRADE_EUR,pos['quantity']*t['bid'])
                            if amount > 1:
                                await paper_order(Order(pair=pair,side='sell',amount_eur=amount))
                                last_action[pair]=time.monotonic()
                    except Exception as exc:
                        log.warning('Auto-Paper scan failed for %s: %s',pair,exc)
        except Exception:
            log.exception('Auto-Paper scan cycle failed')
        await asyncio.sleep(max(30,AUTO_INTERVAL))

@app.on_event('startup')
async def start_auto_scanner():
    global scan_task
    # Fail closed: do not run the background trader unless credentials are configured.
    if not os.getenv('AURORA_USERNAME') or not os.getenv('AURORA_PASSWORD'):
        log.error('AURORA_USERNAME/AURORA_PASSWORD fehlen; Auto-Paper-Scanner bleibt deaktiviert.')
        return
    scan_task=asyncio.create_task(auto_scan_loop())

@app.on_event('shutdown')
async def stop_auto_scanner():
    global scan_task
    if scan_task:
        scan_task.cancel()
        try:
            await scan_task
        except asyncio.CancelledError:
            pass
