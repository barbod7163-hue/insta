"""Instagram posting agent: generate -> QC -> (review) -> schedule -> publish.

Usage:  python agent.py {status|generate|review|approve|reject|tick|publish-now}
Cron:   */10 * * * * cd /path/to/ig-agent && python agent.py tick >> data/agent.log 2>&1
"""
import argparse
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import content
import db
import instagram
import media
from config import DATA, HASHTAGS, QUALITY, ROOT, SCHEDULE, flag

TZ = ZoneInfo(SCHEDULE["timezone"])


def log(msg):
    print(f"[{datetime.now(TZ):%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


# ---------- scheduling ----------

def posts_per_day():
    """Posts/day for today, following the ramp in persona.json (days since first run)."""
    start = db.get_meta("start_date")
    if not start:
        start = date.today().isoformat()
        db.set_meta("start_date", start)
    days = (date.today() - date.fromisoformat(start)).days
    n = 1
    for step in sorted(SCHEDULE["ramp"], key=lambda s: s["from_day"]):
        if days >= step["from_day"]:
            n = step["posts_per_day"]
    return n


def due():
    """True if a post should go out now: inside active hours, under today's target, spacing respected."""
    lo, hi = SCHEDULE["active_hours"]
    now = datetime.now(TZ)
    if not (lo <= now.hour < hi):
        return False
    ppd = posts_per_day()
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    since = day_start.astimezone(timezone.utc).isoformat(timespec="seconds")
    if db.published_since(since) >= ppd:
        return False
    last = db.last_published()
    gap = timedelta(minutes=(hi - lo) * 60 / ppd)
    return last is None or datetime.now(timezone.utc) - last >= gap


# ---------- generation ----------

def _caption(idea):
    tags = [t if t.startswith("#") else f"#{t}" for t in idea.get("hashtags", [])]
    tags = (tags[: HASHTAGS["count"]] + HASHTAGS.get("always", []))
    return idea["caption"].strip() + ("\n\n" + " ".join(tags) if tags else "")


def generate_one():
    """Create one post. Returns post id, or None if every attempt failed QC."""
    idea = content.new_idea(db.recent(), HASHTAGS["count"])
    pid = db.add_post(status="draft", topic=idea["topic"], image_prompt=idea["image_prompt"],
                      caption=_caption(idea), alt_text=idea.get("alt_text", ""))
    path = DATA / "images" / f"{pid}.jpg"
    for attempt in range(1, QUALITY["max_attempts"] + 1):
        media.generate_image(idea["image_prompt"], path, bool(idea.get("persona_in_frame")))
        qc = content.review(path, idea)
        db.update(pid, image_path=path.relative_to(ROOT).as_posix(), qc_score=qc["score"],
                  qc_notes="; ".join(qc.get("issues", [])))
        log(f"post {pid} attempt {attempt}: score={qc['score']} safe={qc['safe']}")
        if qc["safe"] and qc["score"] >= QUALITY["min_score"]:
            break
    else:
        db.update(pid, status="rejected")
        return None
    db.update(pid, status="pending_review" if flag("REQUIRE_APPROVAL", "true") else "ready")
    return pid


def top_up():
    """Keep a buffer of finished posts; capped per run to control API cost."""
    waiting = db.count("ready") + db.count("pending_review")
    to_make = min(SCHEDULE["buffer_posts"] - waiting, SCHEDULE["max_generate_per_tick"])
    for _ in range(max(0, to_make)):
        try:
            generate_one()
        except Exception as e:  # keep the loop alive; the next tick retries
            log(f"generation failed: {e}")
            break


# ---------- publishing ----------

def publish_next(force=False):
    if not force and not due():
        return log("not due")
    post = db.next_ready()
    if not post:
        return log("no approved post in the queue")
    dry = flag("DRY_RUN")
    try:
        if not dry:
            used, total = instagram.quota()
            if used >= total - 2:
                return log(f"publishing quota nearly full ({used}/{total})")
            url = media.upload(ROOT / post["image_path"], f"posts/{post['id']}.jpg")
            db.update(post["id"], image_url=url)
            media_id = instagram.publish_image(url, post["caption"], post["alt_text"])
        else:
            media_id = "dry-run"
            log(f"DRY_RUN would publish post {post['id']}: {post['caption'][:60]!r}")
        db.update(post["id"], status="published", ig_media_id=media_id, published_at=db.now_iso())
        log(f"published post {post['id']} -> {media_id}")
    except Exception as e:
        attempts = (post["attempts"] or 0) + 1
        db.update(post["id"], attempts=attempts, error=str(e)[:500],
                  status="failed" if attempts >= 3 else "ready")
        log(f"publish failed (attempt {attempts}): {e}")


# ---------- review page ----------

def write_review_md():
    """REVIEW.md shows every post waiting for approval (image + caption) right in the GitHub UI."""
    lines = ["# Posts waiting for approval", "",
             "Approve: Actions > instagram-agent > Run workflow > `approve --all` (or `approve 3 4`). "
             "Reject: `reject 5`.", ""]
    rows = db.list_status("pending_review")
    if not rows:
        lines.append("_Nothing waiting._")
    for p in rows:
        lines += [f"## #{p['id']} - {p['topic']} (QC {p['qc_score']})",
                  f"![post {p['id']}]({p['image_path']})", "", p["caption"], ""]
    (ROOT / "REVIEW.md").write_text("\n".join(lines), encoding="utf-8")


# ---------- CLI ----------

def cmd_status(_):
    for s in ("pending_review", "ready", "published", "failed", "rejected"):
        print(f"{s:15} {db.count(s)}")
    print(f"target today    {posts_per_day()} posts/day")
    try:
        used, total = instagram.quota()
        print(f"IG quota (24h)  {used}/{total}")
    except Exception as e:
        print(f"IG quota        unavailable ({str(e)[:80]})")


def cmd_review(_):
    for p in db.list_status("pending_review"):
        print(f"#{p['id']}  score={p['qc_score']}  topic={p['topic']}\n  image: {p['image_path']}\n"
              f"  notes: {p['qc_notes'] or '-'}\n  caption: {p['caption']}\n")


def cmd_approve(a):
    ids = [p["id"] for p in db.list_status("pending_review")] if a.all else a.ids
    for i in ids:
        db.update(i, status="ready")
    print(f"approved {len(ids)}")


def cmd_reject(a):
    for i in a.ids:
        db.update(i, status="rejected")
    print(f"rejected {len(a.ids)}")


def cmd_generate(a):
    for _ in range(a.n):
        log(f"generated post id: {generate_one()}")


def cmd_tick(_):
    publish_next()
    top_up()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status").set_defaults(fn=cmd_status)
    sub.add_parser("review").set_defaults(fn=cmd_review)
    g = sub.add_parser("generate"); g.add_argument("-n", type=int, default=1); g.set_defaults(fn=cmd_generate)
    p = sub.add_parser("approve"); p.add_argument("ids", nargs="*", type=int)
    p.add_argument("--all", action="store_true"); p.set_defaults(fn=cmd_approve)
    r = sub.add_parser("reject"); r.add_argument("ids", nargs="+", type=int); r.set_defaults(fn=cmd_reject)
    sub.add_parser("tick").set_defaults(fn=cmd_tick)
    sub.add_parser("publish-now").set_defaults(fn=lambda _: publish_next(force=True))
    a = ap.parse_args()
    a.fn(a)
    write_review_md()


if __name__ == "__main__":
    main()
