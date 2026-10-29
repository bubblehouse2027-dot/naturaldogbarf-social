#!/usr/bin/env python3
"""Natural Dog BARF - automatic publisher for Instagram + Facebook Page (Meta Graph API).

Reads calendar.json, publishes every post whose scheduled time (Europe/Lisbon) has passed
and that is not yet recorded in state/published.json. Media is fetched by Meta from the
public GitHub Pages URL in MEDIA_BASE_URL.

Usage:
  python publisher/publish.py               # publish everything that is due
  python publisher/publish.py --dry-run     # show what would be published, call nothing
  python publisher/publish.py --check       # verify token, Page and Instagram account
  python publisher/publish.py --only 7      # publish post #07 now (ignores the date)
  python publisher/publish.py --only 7 --platform instagram
"""
import argparse, datetime as dt, json, os, sys, time
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parent.parent
CAL = ROOT / "calendar.json"
STATE = ROOT / "state" / "published.json"
TZ = ZoneInfo("Europe/Lisbon")

VERSION = os.environ.get("GRAPH_API_VERSION", "v26.0")
GRAPH = f"https://graph.facebook.com/{VERSION}"
RUPLOAD = f"https://rupload.facebook.com/video-upload/{VERSION}"
TOKEN = os.environ.get("META_PAGE_TOKEN", "")
PAGE_ID = os.environ.get("FB_PAGE_ID", "")
IG_ID = os.environ.get("IG_USER_ID", "")
BASE = os.environ.get("MEDIA_BASE_URL", "").rstrip("/")
MAX_LATE_HOURS = float(os.environ.get("MAX_LATE_HOURS", "36"))


class GraphError(RuntimeError):
    pass


def api(method, url, **kw):
    params = kw.pop("params", {}) or {}
    params.setdefault("access_token", TOKEN)
    for attempt in range(4):
        r = requests.request(method, url, params=params, timeout=120, **kw)
        try:
            data = r.json()
        except ValueError:
            data = {"raw": r.text}
        if r.ok and "error" not in data:
            return data
        err = data.get("error", data)
        transient = r.status_code >= 500 or (isinstance(err, dict) and err.get("is_transient"))
        if transient and attempt < 3:
            time.sleep(10 * (attempt + 1)); continue
        raise GraphError(f"{method} {url.split('?')[0]} -> {r.status_code}: {json.dumps(err)[:600]}")


def url(rel):
    return f"{BASE}/{rel.lstrip('/')}"


# ---------------- Instagram ----------------
def ig_wait(container, minutes=12):
    deadline = time.time() + minutes * 60
    while time.time() < deadline:
        st = api("GET", f"{GRAPH}/{container}", params={"fields": "status_code,status"})
        code = st.get("status_code")
        if code == "FINISHED": return
        if code in ("ERROR", "EXPIRED"): raise GraphError(f"Instagram container {container}: {st}")
        time.sleep(15)
    raise GraphError(f"Instagram container {container} not ready after {minutes} min")


def ig_publish(post):
    cap = post["caption"]
    if post["kind"] == "reel":
        params = {"media_type": "REELS", "video_url": url(post["media"][0]), "caption": cap, "share_to_feed": "true"}
        if post.get("cover"): params["cover_url"] = url(post["cover"])
        c = api("POST", f"{GRAPH}/{IG_ID}/media", params=params)["id"]
        ig_wait(c)
    elif post["kind"] == "carousel":
        kids = []
        for m in post["media"][:20]:
            kids.append(api("POST", f"{GRAPH}/{IG_ID}/media", params={"image_url": url(m), "is_carousel_item": "true"})["id"])
        for k in kids: ig_wait(k, 5)
        c = api("POST", f"{GRAPH}/{IG_ID}/media", params={"media_type": "CAROUSEL", "children": ",".join(kids), "caption": cap})["id"]
        ig_wait(c, 5)
    else:
        params = {"image_url": url(post["media"][0]), "caption": cap}
        if post.get("alt"): params["alt_text"] = post["alt"]
        c = api("POST", f"{GRAPH}/{IG_ID}/media", params=params)["id"]
        ig_wait(c, 5)
    return api("POST", f"{GRAPH}/{IG_ID}/media_publish", params={"creation_id": c})["id"]


# ---------------- Facebook Page ----------------
def fb_publish(post):
    cap = post["caption"]
    if post["kind"] == "reel":
        start = api("POST", f"{GRAPH}/{PAGE_ID}/video_reels", params={"upload_phase": "start"})
        vid = start["video_id"]
        r = requests.post(f"{RUPLOAD}/{vid}", headers={"Authorization": f"OAuth {TOKEN}", "file_url": url(post["media"][0])}, timeout=300)
        if not r.ok: raise GraphError(f"Facebook reel upload -> {r.status_code}: {r.text[:400]}")
        for _ in range(40):  # wait for upload processing
            st = api("GET", f"{GRAPH}/{vid}", params={"fields": "status"}).get("status", {})
            if st.get("uploading_phase", {}).get("status") == "complete" or st.get("video_status") in ("ready", "upload_complete"):
                break
            if st.get("video_status") == "error": raise GraphError(f"Facebook reel {vid}: {st}")
            time.sleep(10)
        api("POST", f"{GRAPH}/{PAGE_ID}/video_reels", params={"video_id": vid, "upload_phase": "finish", "video_state": "PUBLISHED", "description": cap})
        return vid
    if post["kind"] == "carousel":
        ids = [api("POST", f"{GRAPH}/{PAGE_ID}/photos", params={"url": url(m), "published": "false"})["id"] for m in post["media"]]
        params = {"message": cap}
        for i, pid in enumerate(ids): params[f"attached_media[{i}]"] = json.dumps({"media_fbid": pid})
        return api("POST", f"{GRAPH}/{PAGE_ID}/feed", params=params)["id"]
    return api("POST", f"{GRAPH}/{PAGE_ID}/photos", params={"url": url(post["media"][0]), "caption": cap})["post_id"]


PUBLISHERS = {"instagram": ig_publish, "facebook": fb_publish}


# ---------------- state & scheduling ----------------
def load_state():
    return json.loads(STATE.read_text()) if STATE.exists() else {}


def save_state(s):
    STATE.parent.mkdir(exist_ok=True); STATE.write_text(json.dumps(s, indent=2, ensure_ascii=False) + "\n")


def when(post):
    return dt.datetime.fromisoformat(f"{post['date']}T{post['time']}").replace(tzinfo=TZ)


def check():
    ok = True
    for name, fn in [("Token / Page", lambda: api("GET", f"{GRAPH}/{PAGE_ID}", params={"fields": "id,name"})),
                     ("Instagram account", lambda: api("GET", f"{GRAPH}/{IG_ID}", params={"fields": "id,username"})),
                     ("Instagram publishing quota", lambda: api("GET", f"{GRAPH}/{IG_ID}/content_publishing_limit", params={"fields": "quota_usage,config"})),
                     ("Media hosting", lambda: {"status": requests.head(url(json.loads(CAL.read_text())["posts"][0]["media"][0]), timeout=30).status_code})]:
        try: print(f"OK   {name}: {fn()}")
        except Exception as e: ok = False; print(f"FAIL {name}: {e}")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true"); ap.add_argument("--check", action="store_true")
    ap.add_argument("--only", type=int); ap.add_argument("--platform", choices=list(PUBLISHERS))
    a = ap.parse_args()
    missing = [k for k, v in {"META_PAGE_TOKEN": TOKEN, "FB_PAGE_ID": PAGE_ID, "IG_USER_ID": IG_ID, "MEDIA_BASE_URL": BASE}.items() if not v]
    if missing and not a.dry_run:
        sys.exit(f"Missing settings: {', '.join(missing)} (see README, step 6)")
    if a.check: sys.exit(0 if check() else 1)

    cal = json.loads(CAL.read_text())["posts"]; state = load_state(); now = dt.datetime.now(TZ); failures = 0
    for post in sorted(cal, key=when):
        key = f"{post['n']:02d}"
        if a.only is not None and post["n"] != a.only: continue
        if a.only is None:
            if when(post) > now: continue
            if (now - when(post)).total_seconds() > MAX_LATE_HOURS * 3600 and not state.get(key):
                print(f"skip #{key}: more than {MAX_LATE_HOURS:.0f} h late, publish it manually with --only {post['n']}"); continue
        if post.get("hold"):
            print(f"hold #{key}: {post.get('hold_reason', 'waiting for confirmation')} (set \"hold\": false in calendar.json)"); continue
        for plat in post.get("platforms", ["instagram", "facebook"]):
            if a.platform and plat != a.platform: continue
            if state.get(key, {}).get(plat): continue
            if a.dry_run:
                print(f"would publish #{key} {post['kind']} to {plat}: {[url(m) for m in post['media']][:2]}"); continue
            try:
                pid = PUBLISHERS[plat](post)
                state.setdefault(key, {})[plat] = {"id": pid, "at": dt.datetime.now(TZ).isoformat(timespec="seconds")}
                save_state(state); print(f"published #{key} to {plat}: {pid}")
            except Exception as e:
                failures += 1; print(f"ERROR #{key} {plat}: {e}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
