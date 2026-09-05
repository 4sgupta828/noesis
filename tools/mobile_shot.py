"""Phone-viewport screenshot + layout measurement via the Chrome DevTools protocol.

Plain `chrome --headless --window-size=390,...` does NOT emulate a phone: the viewport meta is
ignored on desktop, so a card that fits a real phone can look clipped (and vice versa). This
drives real device emulation (390px, DPR 2, mobile UA) and reports innerWidth / scrollWidth /
the gate card rect, then saves a screenshot.

  .venv/bin/python tools/mobile_shot.py https://noesis-api-production.up.railway.app/ out.png [390]
Env: NOESIS_SHOT_USER (JSON for localStorage `noesis_user`, e.g. a test token) boots signed in;
     NOESIS_SHOT_JS runs a snippet before the screenshot (e.g. "openAccount()").
"""
import asyncio, base64, json, subprocess, sys, time, urllib.request
import websockets
URL=sys.argv[1]; OUT=sys.argv[2]; W=int(sys.argv[3]) if len(sys.argv)>3 else 390
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
proc=subprocess.Popen([CHROME,"--headless=new","--disable-gpu","--remote-debugging-port=9333","--user-data-dir=/tmp/claude-cdp-profile","about:blank"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
    for _ in range(50):
        try:
            tabs=json.load(urllib.request.urlopen("http://127.0.0.1:9333/json")); break
        except Exception: time.sleep(0.2)
    ws_url=[t for t in tabs if t["type"]=="page"][0]["webSocketDebuggerUrl"]
    async def main():
        async with websockets.connect(ws_url, max_size=50_000_000) as ws:
            i=0
            async def call(method, **params):
                nonlocal i; i+=1
                await ws.send(json.dumps({"id":i,"method":method,"params":params}))
                while True:
                    m=json.loads(await ws.recv())
                    if m.get("id")==i: return m.get("result",{})
            await call("Emulation.setDeviceMetricsOverride", width=W, height=844, deviceScaleFactor=2, mobile=True)
            await call("Emulation.setUserAgentOverride", userAgent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
            await call("Page.enable"); await call("Runtime.enable")
            await call("Page.navigate", url=URL)
            await asyncio.sleep(4)
            # optional signed-in state: NOESIS_SHOT_USER='{"name":..,"email":..,"token":..}' is written to
            # localStorage on the origin, then the page is reloaded so the app boots signed in
            import os
            if os.environ.get("NOESIS_SHOT_USER"):
                await call("Runtime.evaluate", expression="localStorage.setItem('noesis_user', %s)" % json.dumps(os.environ["NOESIS_SHOT_USER"]))
                await call("Page.reload"); await asyncio.sleep(5)
            if os.environ.get("NOESIS_SHOT_JS"):
                res = await call("Runtime.evaluate", expression="(async()=>{"+os.environ["NOESIS_SHOT_JS"].replace("\n"," ")+"})()" if "await " in os.environ["NOESIS_SHOT_JS"] else os.environ["NOESIS_SHOT_JS"], awaitPromise=True, returnByValue=True)
                print("JS:", (res.get("result") or {}).get("value"))
                await asyncio.sleep(2)
            r=await call("Runtime.evaluate", expression="""(()=>{const c=document.querySelector('.idcard');const r=c&&c.getBoundingClientRect();return JSON.stringify({innerWidth, docScrollW:document.documentElement.scrollWidth, card:r&&{left:r.left,right:r.right,width:r.width}, modalHidden: document.querySelector('#idmodal').hidden})})()""", returnByValue=True)
            print(r["result"]["value"])
            shot=await call("Page.captureScreenshot", format="png")
            open(OUT,"wb").write(base64.b64decode(shot["data"]))
    asyncio.run(main())
finally:
    proc.terminate()
