"""Daily link check for Agent Tools Listing.

Reads catalog.json, requests each entry's source URL, and writes status.json
with one live/dead/unknown verdict per entry plus a checked date. Also stamps
catalog.json with the same checked date. Dead links are data, never an error:
this script always exits 0 so the scheduled workflow never fails on a dead link.

Verdicts:
  live    - HTTP 200-399
  unknown - HTTP 403/429 (bot-blocked), or DNS/connection/timeout failure
            (no response received, so the source may be fine; never "dead")
  dead    - an actual HTTP 4xx/5xx response (except 403/429)
"""
import datetime
import json
import os
import ssl
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = "AgentToolsListing-LinkCheck/1.0 (+https://agent-tools-listing.vercel.app)"
TIMEOUT = 15


def probe(url):
    """Return (http_status or None, verdict). HEAD first, GET fallback."""
    for method in ("HEAD", "GET"):
        req = urllib.request.Request(url, method=method, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT,
                                        context=ssl.create_default_context()) as resp:
                code = resp.status
                if 200 <= code < 400:
                    return code, "live"
                if code in (403, 429):
                    return code, "unknown"
                return code, "dead"
        except urllib.error.HTTPError as e:
            if e.code in (403, 429):
                return e.code, "unknown"
            if e.code in (405, 501) and method == "HEAD":
                continue  # server rejects HEAD; retry with GET
            return e.code, "dead"
        except Exception:
            if method == "HEAD":
                continue  # network-level HEAD failure; retry with GET
            return None, "unknown"
    return None, "unknown"


def main():
    with open(os.path.join(ROOT, "catalog.json")) as f:
        catalog = json.load(f)
    checked = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    entries = []
    for tool in catalog["tools"]:
        code, verdict = probe(tool["source"])
        entries.append({
            "name": tool["name"],
            "source": tool["source"],
            "status": verdict,
            "http_status": code,
        })
        print(f"{verdict:7} {code}  {tool['name']}")
    status = {
        "checked_at": checked,
        "source": "automated daily link check (HTTP status only, not a delivery test)",
        "entries": entries,
    }
    with open(os.path.join(ROOT, "status.json"), "w") as f:
        json.dump(status, f, indent=2)
        f.write("\n")
    catalog["last_checked"] = checked
    with open(os.path.join(ROOT, "catalog.json"), "w") as f:
        json.dump(catalog, f, indent=2)
        f.write("\n")
    print(f"checked {len(entries)} links, wrote status.json + catalog.json (last_checked={checked})")


if __name__ == "__main__":
    main()
