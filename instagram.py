"""Official Instagram Graph API publishing (container -> poll -> publish)."""
import time

from config import env, flag


def _base():
    host = env("GRAPH_HOST", "https://graph.facebook.com").rstrip("/")
    return f"{host}/{env('GRAPH_VERSION', 'v26.0')}"


def _call(method, path, **fields):
    import requests

    kw = {"data": fields} if method == "POST" else {"params": fields}
    r = requests.request(method, f"{_base()}/{path}",
                         headers={"Authorization": f"Bearer {env('IG_ACCESS_TOKEN')}"},
                         timeout=60, **kw)
    try:
        j = r.json()
    except ValueError:
        j = {"raw": r.text[:300]}
    if r.status_code >= 400 or "error" in j:
        raise RuntimeError(f"Instagram API {r.status_code}: {j}")
    return j


def quota():
    """(used, total) for the rolling 24h publishing window, read live from Meta."""
    j = _call("GET", f"{env('IG_USER_ID')}/content_publishing_limit", fields="quota_usage,config")
    d = j["data"][0]
    return d["quota_usage"], d["config"]["quota_total"]


def publish_image(image_url, caption, alt_text=""):
    uid = env("IG_USER_ID")
    fields = {"image_url": image_url, "caption": caption[:2200]}
    if alt_text:
        fields["alt_text"] = alt_text[:1000]
    if flag("AI_DISCLOSURE", "true"):
        fields["is_ai_generated"] = "true"  # Meta's AI self-disclosure flag
    cid = _call("POST", f"{uid}/media", **fields)["id"]

    for _ in range(15):  # up to ~5 minutes
        try:
            status = _call("GET", cid, fields="status_code")["status_code"]
        except RuntimeError:
            break  # status not readable: try publishing, the publish call will report any real error
        if status == "FINISHED":
            break
        if status in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Container {cid} ended with status {status}")
        time.sleep(20)

    return _call("POST", f"{uid}/media_publish", creation_id=cid)["id"]
