#!/usr/bin/env python3
"""Pull article click counts from PostHog and write data.json.

Counts each browsing session that landed with utm_medium=article, grouped by
utm_campaign (the article). Runs on a schedule via GitHub Actions; the
PostHog key comes from the POSTHOG_API_KEY repo secret, never the page.
"""
import json
import os
import datetime
import urllib.request

API_KEY = os.environ["POSTHOG_API_KEY"]
PROJECT_ID = os.environ.get("POSTHOG_PROJECT_ID", "46996")
HOST = os.environ.get("POSTHOG_HOST", "https://us.posthog.com")
WINDOW_DAYS = 90

HOGQL = """
SELECT campaign, count() AS clicks
FROM (
  SELECT
    properties.$session_id AS sid,
    argMinIf(properties.utm_campaign, timestamp, properties.utm_campaign != '') AS campaign,
    max(properties.utm_medium = 'article') AS is_article
  FROM events
  WHERE timestamp > now() - INTERVAL %d DAY
    AND properties.$session_id != ''
  GROUP BY sid
)
WHERE is_article = 1 AND campaign != ''
GROUP BY campaign
ORDER BY clicks DESC
LIMIT 200
""" % WINDOW_DAYS


def fetch_rows():
    url = "%s/api/projects/%s/query/" % (HOST, PROJECT_ID)
    payload = json.dumps({"query": {"kind": "HogQLQuery", "query": HOGQL}}).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={
            "Authorization": "Bearer %s" % API_KEY,
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.load(resp).get("results", [])


def main():
    rows = fetch_rows()
    articles = [{"campaign": r[0], "clicks": int(r[1])} for r in rows]
    out = {
        "updated": datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "window_days": WINDOW_DAYS,
        "articles": articles,
    }
    with open("data.json", "w") as f:
        json.dump(out, f, indent=2)
    print("Wrote %d articles" % len(articles))


if __name__ == "__main__":
    main()
