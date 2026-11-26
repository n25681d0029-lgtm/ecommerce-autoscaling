"""Chụp ảnh giao diện từ bản demo đang chạy ở http://127.0.0.1:8000 bằng Edge chạy ngầm.

    python nguon/shoot.py home,list,product,cart,checkout,login,admin,aprod,aform,aorders,system,live12
"""
import json, time, subprocess, urllib.request, base64, sys, os, itertools
import websocket
SP = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(os.path.dirname(SP), "anh_demo")
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
B = "http://127.0.0.1:8000"
proc = subprocess.Popen([EDGE, "--headless=new", "--remote-debugging-port=9333", "--disable-gpu", "--no-first-run",
                         "--user-data-dir=" + os.path.join(SP, "_edgeprof"), "--window-size=1366,860", "about:blank"])
for _ in range(50):
    try:
        tabs = json.load(urllib.request.urlopen("http://127.0.0.1:9333/json")); break
    except Exception: time.sleep(0.3)
page = [t for t in tabs if t["type"] == "page"][0]
ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=60, suppress_origin=True)
ids = itertools.count(1)
def cdp(method, **params):
    i = next(ids); ws.send(json.dumps({"id": i, "method": method, "params": params}))
    while True:
        m = json.loads(ws.recv())
        if m.get("id") == i:
            if "error" in m: raise RuntimeError(m["error"])
            return m.get("result", {})
def js(expr):
    r = cdp("Runtime.evaluate", expression=expr, awaitPromise=True, returnByValue=True)
    return r.get("result", {}).get("value")
def wait_ready():
    for _ in range(100):
        if js("document.readyState") == "complete": break
        time.sleep(0.1)
    time.sleep(0.6)
def go(path):
    cdp("Page.navigate", url=B + path); time.sleep(0.3); wait_ready()
def shot(name, full=False, h=860):
    cdp("Emulation.setDeviceMetricsOverride", width=1366, height=h, deviceScaleFactor=1.25, mobile=False)
    time.sleep(0.4)
    params = {"format": "png"}
    if full:
        hh = js("document.documentElement.scrollHeight")
        params["clip"] = {"x": 0, "y": 0, "width": 1366, "height": min(hh, 2600), "scale": 1}
        params["captureBeyondViewport"] = True
    d = cdp("Page.captureScreenshot", **params)
    open(os.path.join(OUT, name + ".png"), "wb").write(base64.b64decode(d["data"])); print("saved", name)
def submit(sel):
    t0 = js("performance.timeOrigin")
    js(f"document.querySelector('{sel}').requestSubmit ? document.querySelector('{sel}').requestSubmit() : document.querySelector('{sel}').submit()")
    for _ in range(100):
        time.sleep(0.1)
        try:
            if js("performance.timeOrigin") != t0 and js("document.readyState") == "complete": break
        except Exception: pass
    time.sleep(0.6)
cdp("Page.enable"); cdp("Runtime.enable")
cdp("Emulation.setDeviceMetricsOverride", width=1366, height=860, deviceScaleFactor=1.25, mobile=False)
steps = sys.argv[1].split(",")
for s in steps:
    if s == "home": go("/"); shot("01_home")
    if s == "list": go("/?cat=laptop&sort=price_asc"); js("window.scrollTo(0,0)"); shot("02_list")
    if s == "search": go("/?q=tai%20nghe"); shot("02b_search")
    if s == "product": go("/product/3"); shot("03_product")
    if s == "cart":
        for pid, q in ((3, 1), (20, 2)):
            go(f"/product/{pid}")
            print(js(f"(async()=>{{const f=document.querySelector(\"form[action*='/cart/add']\");const fd=new FormData(f);fd.set('qty','{q}');const r=await fetch(f.action,{{method:'POST',body:fd,credentials:'same-origin'}});return r.status+' '+r.url}})()"))
        go("/cart"); shot("04_cart")
    if s == "checkout":
        go("/checkout")
        js("document.querySelector('[name=name]').value='Nguyễn Văn Khách';document.querySelector('[name=phone]').value='0912345678';document.querySelector('[name=address]').value='Số 1 đường Z115, TP. Thái Nguyên';")
        shot("05_checkout")
        submit("form:has([name=address])"); shot("06_order"); print(js("location.pathname"))
    if s == "track": go("/track"); shot("07_track")
    if s == "login":
        go("/login"); js("document.querySelector('[name=email]').value='admin@shop.local';document.querySelector('[name=password]').value='Admin@123';")
        submit("form:has([name=password])"); print(js("location.pathname"))
    if s == "admin": go("/admin/"); shot("08_admin", full=True)
    if s == "aprod": go("/admin/products"); shot("09_admin_products")
    if s == "aform": go("/admin/products/3"); shot("10_admin_form", full=True)
    if s == "aorders": go("/admin/orders"); shot("11_admin_orders")
    if s == "system": go("/system"); shot("12_system")
    if s == "health": go("/health"); shot("13_health", h=300)
    if s.startswith("live"):
        go("/system/live"); time.sleep(float(s[4:] or 12)); shot("14_" + s, full=True)
    if s == "err": go("/khong-ton-tai"); shot("15_404")
ws.close(); proc.terminate()
