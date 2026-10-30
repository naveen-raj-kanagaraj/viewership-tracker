"""/privacy and /terms: plain pages the YouTube API Services policies ask for (the site uses YouTube API Services,
links to YouTube's Terms of Service and Google's Privacy Policy, and says what is collected about visitors).
Contact: CONTACT_EMAIL in .env (shown on both pages); without it, the site's social accounts."""
import html
import os

from tracker import eventpage

UPDATED = "30 October 2026"
YT_TOS = "https://www.youtube.com/t/terms"
G_PRIV = "https://policies.google.com/privacy"
G_SEC = "https://myaccount.google.com/permissions"


def _contact() -> str:
    e = os.getenv("CONTACT_EMAIL", "").strip()
    if e:
        return f'email <a href="mailto:{html.escape(e)}">{html.escape(e)}</a>'
    return ('message us on X <a href="https://x.com/letsgrowesports">@letsgrowesports</a> or Instagram '
            '<a href="https://www.instagram.com/letsgrowesports.igc/">@letsgrowesports.igc</a>')


def _page(title: str, body: str) -> str:
    b = html.escape(eventpage.BRAND)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} | {b}</title><meta name="theme-color" content="#07051a">
<style>:root{{color-scheme:dark}}body{{margin:0;background:#0b0b12;color:#e6e6ef;font:16px/1.65 system-ui,-apple-system,"Segoe UI",sans-serif}}
.top{{border-bottom:1px solid #262636;background:#0b0b12}}.top .in{{max-width:820px;margin:0 auto;padding:12px 16px;display:flex;gap:14px;align-items:center}}
.brand{{color:#b6f23a;font-weight:800;text-decoration:none;letter-spacing:.04em;text-transform:uppercase}}main{{max-width:820px;margin:0 auto;padding:20px 16px 48px}}
h1{{font-size:30px;margin:8px 0 2px}}h2{{font-size:19px;margin:28px 0 6px}}.up{{color:#8d8ca3;font-size:14px}}a{{color:#b6f23a}}li{{margin:4px 0}}</style></head>
<body><div class="top"><div class="in"><a class="brand" href="/">{b}</a></div></div><main><h1>{title}</h1><div class="up">Last updated {UPDATED}</div>{body}</main></body></html>"""


def privacy_html() -> str:
    site = html.escape(eventpage.SITE_URL)
    return _page("Privacy Policy", f"""
<p>This policy covers <a href="{site}">{site.split('//')[-1]}</a> (the "site"), a free analytics website run by letsgrowesports
that shows public statistics about YouTube, Twitch and Kick channels and live streams.</p>
<h2>YouTube API Services</h2>
<p>The site uses YouTube API Services to read public information about YouTube channels and videos (such as channel names,
subscriber and view counts, video titles, views, likes and comments, and live viewer counts). By using the site you are also
bound by the <a href="{YT_TOS}">YouTube Terms of Service</a>. Google's handling of data is described in the
<a href="{G_PRIV}">Google Privacy Policy</a>.</p>
<p>The site does not ask you to sign in with Google or YouTube and never accesses your YouTube account or any private data.
If you have ever granted access to any app through your Google account, you can review or revoke it on the
<a href="{G_SEC}">Google security settings page</a>.</p>
<h2>What we collect about visitors</h2>
<ul>
<li><b>No accounts and no tracking cookies.</b> You can use the whole site without giving us any personal information.</li>
<li><b>Anonymous visit counts.</b> While a page is open it tells our server it is still being viewed, using a random
number that lives only in that browser tab. With it we count visitors, the country and city they are in (from our hosting
provider, Cloudflare), the website they came from, the page and the screen size. The IP address of a visit is kept in
memory for up to 2 days to spot abuse and bots; it is not written to our database.</li>
<li><b>Your region choice.</b> If you pick Global or India, the choice is saved in your own browser (local storage), not on our server.</li>
<li><b>Server logs.</b> Cloudflare and our server keep standard technical logs for security and to keep the site running.</li>
<li><b>Predict &amp; Win.</b> If you take part in a Predict &amp; Win game we keep your Instagram ID, display name, picks,
feedback and the IP address you joined and submitted from. The IP address is used only to stop duplicate and fake accounts.
These details are used only to run the game and contact winners, are never sold or shared, and can be deleted on request.</li>
</ul>
<h2>Embedded YouTube videos</h2>
<p>Some pages play short highlights with the official YouTube embedded player. When you play one, YouTube and Google may set
cookies and collect data as described in the <a href="{G_PRIV}">Google Privacy Policy</a>.</p>
<h2>Data about channels</h2>
<p>We store public statistics about channels (such as daily subscriber and view counts and video statistics) to show how
channels grow over time, and we refresh them regularly from the platforms. Channel owners can ask us to remove their channel
from the site at any time; {_contact()}.</p>
<h2>Sharing</h2>
<p>We do not sell or rent any data. We share data only with the services that run the site (Cloudflare and our hosting
provider) or when the law requires it.</p>
<h2>Children</h2>
<p>The site is not directed at children under 13 and does not knowingly collect personal information from them.</p>
<h2>Changes and contact</h2>
<p>We may update this policy; the date above shows the latest version. Questions or removal requests: {_contact()}.</p>
<p><a href="/terms">Terms of Use</a></p>""")


def terms_html() -> str:
    return _page("Terms of Use", f"""
<p>By using this site you agree to these terms and to the <a href="{YT_TOS}">YouTube Terms of Service</a>.
Our <a href="/privacy">Privacy Policy</a> explains what we collect.</p>
<h2>What the site is</h2>
<p>An unofficial, free analytics website by letsgrowesports. It is not affiliated with or endorsed by YouTube, Google, Twitch,
Kick or any game publisher. Channel and video information comes from those platforms' public data, including YouTube API Services.</p>
<h2>Accuracy</h2>
<p>Numbers are collected automatically and may be incomplete, delayed or estimated (for example, totals only cover the streams
we find). Everything is provided "as is", without warranties, and should not be relied on as the official figure.</p>
<h2>Fair use</h2>
<p>Do not overload, scrape at scale or attempt to break the site. You may share screenshots and the share cards with credit to the site.</p>
<h2>Content and removal</h2>
<p>Videos, names and logos belong to their owners. Channel owners can ask for their channel to be removed; {_contact()}.</p>
<p>These terms may change; the date above shows the latest version.</p>""")
