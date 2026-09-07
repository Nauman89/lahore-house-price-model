# Source evaluation — stage 1 acquisition

Working document for selecting the listing source. Claude produced the candidate list and
the check list; **Nauman visits the sites and records the findings** (PLAN §11, D-17).
Claude fetches nothing from a candidate domain until a source has passed.

Outcome is transferred to `project-log/decisions/02-acquisition.md` once the checks are done.
This file is retained as the audit trail — the evaluation itself is part of the deliverable.

---

## 1. What we are looking for

Ranked by the rule agreed 4 Sep 2026: **explicit permission beats volume.** A smaller
dataset from a source that plainly allows this is worth more than a large one from a source
that does not — both ethically and as a portfolio story.

Realistic expectation, so no time is lost hunting for a unicorn: almost no commercial
property portal publishes an affirmative "you may scrape this" statement. What we are
actually looking for, in descending order of strength:

| Grade | Condition | Verdict |
|---|---|---|
| **A** | An explicit permission, published API, or open licence covering the listing data | Use it |
| **B** | `robots.txt` `User-agent: *` allows the listing and discovery paths, **and** the terms contain no clause prohibiting automated access, extraction or systematic retrieval | Use it — permitted by robots, unrestricted by terms. Record both verbatim |
| **C** | `robots.txt` allows, but the terms prohibit automated access or restrict use to "personal, non-commercial" browsing | **Reject.** Terms outrank robots.txt |
| **D** | `robots.txt` `User-agent: *` disallows the listing or search paths | **Reject.** No further reading needed |
| **E** | `robots.txt` permits the listing pages, but **no lawful discovery surface exists** — pagination sits behind a disallowed URL pattern and no sitemap is published | **Reject.** Added 4 Sep after the Graana check; the original table did not anticipate a source that is permitted to read but impossible to enumerate |

Grade B is the expected best case and is a defensible position. Grade C is a rejection even
though the scraper would technically work — that distinction is the point of the exercise
and is worth stating in the write-up.

---

## 2. How to read robots.txt

URL is always the domain root: `https://<domain>/robots.txt`. Plain text, opens in any browser.

Only the **`User-agent: *`** group governs our scraper. Read that group and record it verbatim.

Check, in this order:

1. **Is the listing-detail path disallowed?** The URL pattern of an individual property page.
2. **Are the search / pagination paths disallowed?** This is the one people miss. Several
   portals allow detail pages but disallow the filtered search URLs that lead to them. If so,
   discovery has to come from the sitemap instead — which changes the design but is not a
   rejection.
3. **`Crawl-delay:`** — if present in the `*` group and longer than our 1–2s, we honour theirs.
4. **`Sitemap:` lines** — record every one. These are the discovery route, and often the
   better one regardless.
5. **Named bot groups** (`ClaudeBot`, `GPTBot`, `CCBot`, `anthropic-ai`, `Bytespider`) —
   record them, but they do not bind our scraper, which is not any of those agents and obeys
   the `*` group. Their presence is still **a signal worth weighting**: a site that has
   enumerated AI crawler bans has demonstrably thought about automated access, which makes a
   restrictive terms clause more likely and more likely to be enforced. Read that site's
   terms with extra care rather than treating the AI-bot list as our answer either way.

---

## 3. How to read the terms

Find the terms from the site footer — "Terms of Use", "Terms & Conditions", "Legal",
sometimes a separate "Acceptable Use" or "Data Policy". Record the exact URL and the date
you read it.

`Ctrl+F` for each of these:

```
scrap        crawl        spider       robot        bot
automated    automatic    data mining  harvest      extract
systematic   aggregat     reproduce    redistribute  resell
"non-commercial"          "personal use"            database
```

Copy any matching clause **verbatim** into the table below, with its section number. The
decision record quotes it, so a paraphrase is not enough.

Two clauses matter beyond the obvious scraping ban:

- **"personal, non-commercial use only"** — a portfolio project shown to prospective clients
  is arguably commercial. Treat this as a grade C rejection.
- **Database or compilation rights** over the listing collection — separate from copyright in
  any single listing, and it restricts redistribution even where collection is permitted.
  Relevant because `data/sample/` ships ~200 rows in the public repo.

---

## 4. Observations to collect in the same visit

Normal human browsing, no automation, zero extra cost while the site is open. These are the
source-scoring criteria from PLAN §11 and they decide the shape of stages 2 and 4.

| # | Question | How to check | Why it matters |
|---|---|---|---|
| a | **Server-rendered?** | On a listing page press `Ctrl+U` (view source), then `Ctrl+F` the price as it appears on screen. Found in the source = server-rendered = `requests` + BeautifulSoup is enough. Not found = JavaScript-rendered = the locked dependency set cannot scrape it | Decides whether the source is usable at all without amending the lockfile (D-18) |
| b | **Latitude / longitude exposed?** | Does the listing page show a map pin at the property? Right-click the map → is there a Google Maps link with coordinates in the URL? | B-04. If absent, ~150–250 locality names get geocoded once into a committed lookup |
| c | **Location structured or free text?** | Is the address broken into society / phase / block fields, or is it one sentence? | Drives the whole location feature design |
| d | **Stable listing ID?** | Is there an ID in the listing URL or on the page ("Property ID", "Ref")? | D-08 dedup pass one depends on it |
| e | **Posting date?** | Does the listing show "Added 3 weeks ago" or an actual date? | B-03 recency holdout |
| f | **Pagination depth cap** | Filter to Lahore houses for sale. What total count does it claim? Then jump to the highest page number you can reach — does it cap out (e.g. page 50) well before that count? | Decides whether discovery must be partitioned by locality × price band |
| g | **Field completeness** | Open three or four listings. Do beds, baths, area and locality reliably appear, or are half of them blank? | Quality above the 3,000 floor matters more than quantity |

---

## 5. Candidates

Suggested check order. **Stop as soon as one comes back grade A or B** — no need to work the
whole list. Budget ~15–20 minutes each.

### 5.1 Graana — `https://www.graana.com` — CHECK FIRST

Imarat Group. Mid-size national portal with a real Lahore house inventory. URL patterns
(`/sale/house-sale-lahore-2/`, `/directory/all-cities/`) suggest server-rendered paginated
search, which is what we need. Large enough to clear the floor, small enough that the terms
may be less aggressively drafted than the market leader's.

- robots: `https://www.graana.com/robots.txt`
- terms: footer — likely `/terms-and-conditions` or `/terms`
- listing path pattern to check in robots: the individual property URL, plus `/sale/`

### 5.2 Ilaan — `https://www.ilaan.com` — CHECK SECOND

Clean, predictable URL structure (`/house-for-sale/lahore`) — the best-looking discovery
surface of the group. Positions on "verified listings, 0% commission", which implies a
curated and therefore cleaner inventory. Smallest of the three mid-size portals, so volume is
the open question — check (f) and (g) carefully.

- robots: `https://www.ilaan.com/robots.txt`
- terms: footer
- volume check: what does `/house-for-sale/lahore` claim as a total count?

### 5.3 Zameen — `https://www.zameen.com` — CHECK THIRD

Market leader by a wide margin (Dubizzle / EMPG). By far the largest Lahore house inventory
and the richest field set — if it permits, nothing else competes. Also the most likely to
carry a restrictive clause, an enterprise legal team and bot protection.

Worth a **two-minute glance at robots.txt at any point regardless of order** — it is one page
load and it either removes the biggest source from consideration or makes it the front-runner.

- robots: `https://www.zameen.com/robots.txt`
- terms: footer — "Terms of Use"
- note: search paths look like `/Homes/Lahore-1-1.html`; check whether `/Homes/` is disallowed

### 5.4 Aarz — `https://www.aarz.pk` · JagahOnline — `https://www.jagahonline.com`

Smaller portals. Grouped because they are one check between them: the case for looking is
that a smaller operator may have thin or absent terms, which under our grading is **not
permission** but does clear the grade B bar if robots.txt allows. Volume is the risk — likely
at or below the 3,000 floor for Lahore houses alone.

- robots: `https://www.aarz.pk/robots.txt` · `https://www.jagahonline.com/robots.txt`

### 5.5 OLX Pakistan — `https://www.olx.com.pk` — CHECK LAST

Very large classifieds inventory (`/lahore_g4060673/houses_c1721`). Ranked last on both
criteria: a multinational classifieds ToS is near-certain to prohibit automated extraction,
and classifieds data is materially messier than portal data — free-text everything, heavy
duplication, and a junk rate that would eat the cleaning stage. Volume does not rescue it.

---

## 6. Fallback if every candidate is grade C or D

Agreed 4 Sep: no pre-commitment, but the route is public datasets with the reasoning recorded,
**not** scraping a source that has said no.

Candidate fallbacks, unverified:

- **Open Data Pakistan** — `https://opendata.com.pk/dataset/property-data-for-pakistan`.
  The only candidate in this document that publishes a licensing position at all (see its
  "Making data open legally" and "User Guidelines" pages). Honest caveat: the property dataset
  there appears to be a redistributed Zameen extract, so the portal's licence covers the
  portal's redistribution, and the underlying provenance is second-hand.
- **Kaggle Zameen extracts** — several exist, dated 2019 through 2025. Per-dataset licence
  varies and must be read individually; several are uploaded without a licence, which is not
  permission. Stale prices are a real problem given Pakistani inflation over the period.

Taking this route costs the scraper deliverable (PLAN §2 item 1) and changes the project's
story from "I acquired this" to "I cleaned someone else's file". If it happens, the evaluation
in this document becomes the substitute artifact, and it is a good one — the write-up of why
each source was rejected, with clauses quoted, is a more useful thing to show a client than a
scraper pointed at a site that prohibited it.

---

## 7. Findings

Fill in as you go. One row per source checked.

### Graana

- Date checked: 4th September 2026
- robots.txt `User-agent: *` group, verbatim: 
User-agent: *
Content-Signal: search=yes,ai-train=no,use=reference
Allow: /; 

User-agent: *
Disallow: /*?
Disallow: /secret/
Disallow: /cdn-cgi/
Disallow: /area/*undefined

- Listing path allowed? / Search path allowed? / Crawl-delay? / Sitemaps:
1. **Listing detail pages: ALLOWED.** `/property/<slug>-<id>/` carries no query string, so `Disallow: /*?` does not reach it; `Allow: /` governs.
2. **Search page 1: ALLOWED** (`/sale/house-sale-lahore-2/`). **Search pagination: DISALLOWED.** Page 2 resolves to
   `/sale/house-sale-lahore-2/?pageSize=30&page=2`, which `Disallow: /*?` blocks. Checked 4 Sep 2026.
3. Crawl-delay: **absent** from the `*` group. Our own 1-2s floor applies.
4. Sitemaps: **none declared** in robots.txt, and `https://www.graana.com/sitemap.xml` returns **404**. Checked 4 Sep 2026.

- Named AI-bot groups present: Yes. Amazonbot, Applebot-Extended, Bytespider, CCBot, ClaudeBot, CloudflareBrowserRenderingCrawler, Google-Extended, GPTBot, and meta-externalagent are all blocked

- Terms URL and date: 
1. URL: https://www.graana.com/terms/

2. Date: 4th September 2026

- Relevant clauses, verbatim with section numbers:
There are no Clause numbers. The only keyword that appears in the TOS is "reproduce". Here it is verbatim:
1. You will not reproduce, display, amend, modify, republish, distribute, display, advertise or otherwise provide access to, disassemble or decompile any part of our services, except as explicitly permitted by Graana.com.

- Observations (a)–(g): These observations are taken from this URL: https://www.graana.com/property/1-kanal-house-sale-dha-phase-1-lahore-1553368/

(a) **Server-rendered?**: </script><script id="__NEXT_DATA__" type="application/json">{"props":{"pageProps":{"data":{"id":1553368,...."price":"60000000","size":1,"sizeUnit":"kanal"....

(b) **Latitude / longitude exposed?**: Yes. "lat":31.4833597,"lng":74.3968658

(c) **Location structured or free text?**: Structured. "area.id":809,"area.name":"DHA Phase 1","city.id":2,"city.name":"Lahore"

(d) **Stable listing ID?**: Yes. type="application/json">{"props":{"pageProps":{"data":{"id":1553368. The same ID also appears at the end of the URL

(e) **Posting date?**: Yes. "createdAt":"2026-09-03T16:35:03.787Z"

(f) **Pagination depth cap**: 301 pages filtered to Lahore and houses for sale. 30 entries per page

(g) **Field completeness**: Opened 5 links. 3 of them had detailed information about the house while 2 had limited information. Price, No. of beds, No. of bathrooms, size and location seem to be the necessary fields since all posts have them  

- **Grade:** **E — rejected on discovery, not on permission.**

  Access and terms both came back clean. `robots.txt` permits the listing pages, and the terms
  contain no clause prohibiting automated access — the only keyword hit, "reproduce", restricts
  redistribution rather than collection. On the access question alone this was a grade B.

  It fails because there is no lawful way to enumerate the inventory. All 301 result pages past
  the first sit behind `?pageSize=&page=`, which the `*` group disallows, and no sitemap is
  published at the conventional path. What we are permitted to fetch does not include any route
  that tells us what to fetch.

  Routes considered and rejected:

  - **Path-form pagination** (`/sale/.../page/2/`). Even if the app served it, using an alternative
    URL form to reach content the operator placed behind a disallowed pattern is evasion of the
    directive's plain intent. Compliant in letter, not in substance. Rejected on that basis, not
    on whether it would have worked.
  - **First page per locality** (~150-250 area paths x 30 listings). Would clear the volume floor,
    but truncating every locality to its first sorted page is a systematically biased sample, and
    a biased 4,500 rows is worse than no rows.

  Not yet exhausted, if we come back: the `/directory/` tree may expose path-only drill-down to
  listings, and sitemaps are sometimes published undeclared at `/sitemap_index.xml` or
  `/sitemap-index.xml`. Two checks, about five minutes.

  Recorded for the decision log: this source had the best data of any candidate inspected -
  server-rendered `__NEXT_DATA__` JSON, latitude/longitude, structured locality IDs, a stable
  listing ID and a posting timestamp. It is being rejected despite that, which is the point.

### Ilaan

- Date checked: 5th September 2026

- robots.txt `User-agent: *` group, verbatim: 

User-Agent: * group only disallows paths related to admin related things like "/forgot-password", "/verify-email" etc. Important to note that /api/ is disallowed
User-Agent: *
Allow: /
Disallow: /api/
Disallow: /admin/
Disallow: /dashboard/
Disallow: /_next/
Disallow: /api-test/
Disallow: /safepay/
Disallow: /login
Disallow: /register
Disallow: /forgot-password
Disallow: /reset-password
Disallow: /verify-email
Disallow: /favorites
Disallow: /settings
Disallow: /add-property
Disallow: /edit-property/
Disallow: /payment/

- Listing path allowed? / Search path allowed? / Crawl-delay? / Sitemaps:
1. Listing path is allowed. 

2. Search path is allowed. 

3. Crawl delay: **absent** from the `*` group. Our own 1-2s floor applies.

4. Detailed sitemap:
Host: https://www.ilaan.com
Sitemap: https://www.ilaan.com/sitemap.xml
Sitemap: https://www.ilaan.com/sitemap-properties?page=0
Sitemap: https://www.ilaan.com/sitemap-properties?page=1
Sitemap: https://www.ilaan.com/sitemap-properties?page=2
Sitemap: https://www.ilaan.com/sitemap-properties?page=3
Sitemap: https://www.ilaan.com/sitemap-properties?page=4
Sitemap: https://www.ilaan.com/sitemap-properties?page=5
Sitemap: https://www.ilaan.com/sitemap-properties?page=6
Sitemap: https://www.ilaan.com/sitemap-properties?page=7
Sitemap: https://www.ilaan.com/sitemap-properties?page=8
Sitemap: https://www.ilaan.com/sitemap-properties?page=9
Sitemap: https://www.ilaan.com/sitemap-properties?page=10
Sitemap: https://www.ilaan.com/sitemap-properties?page=11
Sitemap: https://www.ilaan.com/sitemap-properties?page=12
Sitemap: https://www.ilaan.com/sitemap-properties?page=13
Sitemap: https://www.ilaan.com/sitemap-properties?page=14
Sitemap: https://www.ilaan.com/sitemap-properties?page=15
Sitemap: https://www.ilaan.com/sitemap-properties?page=16
Sitemap: https://www.ilaan.com/sitemap-properties?page=17
Sitemap: https://www.ilaan.com/sitemap-properties?page=18
Sitemap: https://www.ilaan.com/sitemap-properties?page=19
Sitemap: https://www.ilaan.com/sitemap-properties?page=20
Sitemap: https://www.ilaan.com/sitemap-properties?page=21
Sitemap: https://www.ilaan.com/sitemap-properties?page=22
Sitemap: https://www.ilaan.com/sitemap-properties?page=23
Sitemap: https://www.ilaan.com/sitemap-properties?page=24
Sitemap: https://www.ilaan.com/sitemap-properties?page=25
Sitemap: https://www.ilaan.com/sitemap-properties?page=26
Sitemap: https://www.ilaan.com/sitemap-properties?page=27
Sitemap: https://www.ilaan.com/sitemap-properties?page=28
Sitemap: https://www.ilaan.com/sitemap-properties?page=29
Sitemap: https://www.ilaan.com/sitemap-properties?page=30
Sitemap: https://www.ilaan.com/sitemap-properties?page=31
Sitemap: https://www.ilaan.com/sitemap-properties?page=32
Sitemap: https://www.ilaan.com/sitemap-properties?page=33
Sitemap: https://www.ilaan.com/sitemap-properties?page=34
Sitemap: https://www.ilaan.com/sitemap-properties?page=35
Sitemap: https://www.ilaan.com/sitemap-properties?page=36
Sitemap: https://www.ilaan.com/sitemap-properties?page=37
Sitemap: https://www.ilaan.com/sitemap-properties?page=38
Sitemap: https://www.ilaan.com/sitemap-properties?page=39
Sitemap: https://www.ilaan.com/sitemap-properties?page=40
Sitemap: https://www.ilaan.com/sitemap-properties?page=41
Sitemap: https://www.ilaan.com/sitemap-properties?page=42
Sitemap: https://www.ilaan.com/sitemap-properties?page=43
Sitemap: https://www.ilaan.com/sitemap-properties?page=44
Sitemap: https://www.ilaan.com/sitemap-properties?page=45
Sitemap: https://www.ilaan.com/sitemap-properties?page=46
Sitemap: https://www.ilaan.com/sitemap-properties?page=47
Sitemap: https://www.ilaan.com/sitemap-properties?page=48
Sitemap: https://www.ilaan.com/sitemap-properties?page=49
Sitemap: https://www.ilaan.com/sitemap-properties?page=50
Sitemap: https://www.ilaan.com/sitemap-properties?page=51
Sitemap: https://www.ilaan.com/sitemap-properties?page=52
Sitemap: https://www.ilaan.com/sitemap-properties?page=53
Sitemap: https://www.ilaan.com/sitemap-properties?page=54
Sitemap: https://www.ilaan.com/sitemap-properties?page=55
Sitemap: https://www.ilaan.com/sitemap-properties?page=56
Sitemap: https://www.ilaan.com/sitemap-properties?page=57

- Named AI-bot groups present: Yes. Specifically for Claude:
User-Agent: ClaudeBot
Allow: /
Disallow: /api/
Disallow: /admin/
Disallow: /dashboard/

User-Agent: Anthropic-AI
Allow: /
Disallow: /api/
Disallow: /admin/
Disallow: /dashboard/

Important to note that CC Bot is disallowed:
User-Agent: CCBot
Disallow: /

- Terms URL and date: 
1. URL: https://www.ilaan.com/privacy-policy

2. Date: 5th September 2026

I did not see any TOS link on the website. I found a Privacy Policy but it is silent on crawlers and extraction. It is then safe to assume that since robots.txt is generous about allowing access to data and has a sitemap, Ilaan is open to sharing its data. **I would like Claude to crawl the webiste (since ClaudeBot and Anthropic both are allowed) to see if I missed the TOS**  

- Relevant clauses, verbatim with section numbers: Not available

- Observations (a)–(g):
URL: https://www.ilaan.com/house-for-sale/16-marla-house-for-sale-in-ravi-block-lahore-pidvipsgcok

(a) **Server-rendered?**: available in multiple places:
1. \"price\":60000000,\"priceCurrency\":\"PKR\"
2. \"price\":60000000
3. "og:price:amount\",\"content\":\"60000000\"}]
4. <meta name="og:price:amount" content="60000000"/>
5. "offers":{"@type":"Offer","price":60000000

(b) **Latitude / longitude exposed?**: Seems to be undefined. \"views\":580,\"latitude\":\"$undefined\",\"longitude\":\"$undefined\". I checked another house and had the same result. **Claude Please recheck**

(c) **Location structured or free text?**: Structured. \"address\":\"Ravi Block, Allama Iqbal Town, Lahore\",\"city\":\"Lahore\",\"locality\":\"\",\"province\":\"Punjab\

(d) **Stable listing ID?**: Two types of IDs:
Property ID: \"propertyId\":\"796003\"
There is some unique identifier in the URL as well which: "pidvipsgcok"

(e) **Posting date?**: Yes. \"createdAt\":\"$D2026-08-29T03:21:29.027Z\

(f) **Pagination depth cap**: Two different types. One problem is that there is no option to jump pages. I can not see how many pages there are. Only way to do this is to flip each page one by one. The two types are:
1. Verified owners have their own pagination. For Lahore filtered to Houses only, 10 pages with 20 listings per page.
2. All listings: For Lahore filtered to Houses only, 40+ pages with 20 listings per page

(g) **Field completeness**: Opened 5 links. 3 of them had detailed information about the house while 2 had limited information. Price, No. of beds, No. of bathrooms and size seem to be the necessary fields since all posts have them   

- **Grade:** **B — SELECTED.** Permitted by robots, unrestricted by terms (because none exist).

  Access: `robots.txt` allows the listing paths; the disallows cover admin, auth and account
  routes plus `/api/` and `/_next/`. Query strings are not blocked, unlike Graana. Crawl-delay
  absent. 58 sitemaps declared.

  Terms: **none published.** A site-restricted search found only `/privacy-policy`, `/faq` and
  `/contact-us` indexed — a site-wide-linked terms page would be indexed if it existed. The
  privacy policy is silent on crawlers and extraction. No terms means no clause prohibiting
  automated access, and equally no licence permitting redistribution (see D-23).

  Discovery — the reason this nearly failed. Pagination carries no URL state; `?page=2` changes
  nothing. `/house-for-sale/lahore` redirects to `?verified=true`, the ~200-listing verified
  subset. All four sitemaps sampled (0, 1, 29, 45) contain only `/property-for-sale/` URLs with
  neither city nor type recoverable; 52, 56 and 57 are empty. Pagination is a JavaScript call to
  `https://npi.ilaan.com/api/properties-new/v2`, whose own robots.txt imposes no restrictions.
  Resolved by D-21: that endpoint is used for discovery only.

  Data quality, from the listing pages: server-rendered payload with integer price, `propertyId`,
  ISO `createdAt`, city, province, beds, baths, size. Two known weaknesses — `locality` is an
  empty string with block and society buried in a composite `address` string, so the dominant
  price feature needs text parsing (B-04 and PLAN §12); and coordinates are **sparse**, present
  as JSON-LD `GeoCoordinates` on some listings and absent on others, so both JSON-LD and the
  React payload are parsed and the fill rate measured at cleaning.

  Routing note: the URL path prefix is not trustworthy. A hand-constructed `/house-for-sale/…`
  URL rendered a rental, because the router resolves on the `pid` suffix and the prefix only
  selects a template. Type, transaction and city are therefore taken from the payload, never
  from the URL. `pid` is confirmed as the stable identifier for D-08.

  Operational: repeated site-wide 502s during evaluation, and 3 of 58 sitemaps empty. Recorded
  as D-24.

Page 2 URL: 
1. Verified Listings: https://www.ilaan.com/property-for-sale?q=Lahore&lc=1&ptid=1&verified=true
2. All listings: https://www.ilaan.com/property-for-sale?q=Lahore&lc=1&ptid=1

### Zameen

- Date checked: 5th September 2026
- robots.txt `User-agent: *` group, verbatim:
- Listing path allowed? / Search path allowed? / Crawl-delay? / Sitemaps:
- Named AI-bot groups present:
- Terms URL and date:
Jumped straight to checking TOS since I suspected that they would be tight and detailed:
1. URL: https://www.zameen.com/terms.html

2. Date: 5th September 2026

- Relevant clauses, verbatim with section numbers:
2.General Terms and Conditions:

Clause 2.17.4: "not use any automated software to view the Service without our consent (including use of spiders, robots, crawlers, data mining tools, or the like to download or scrape data from the Service, except for internet search engines (e.g, Google) and non-commercial public archives (e.g. archive.org) that comply with our robots.txt file) and only access the Service manually;"

Clause 2.20: "The Company grants you a limited, revocable, non-exclusive license to access and use the Service for personal use. This license granted herein does not include any of the following: (a) access to or use of the Service by Posting Agents; or (b) any collection, aggregation, copying, duplication, display or derivative use of the Service nor any use of data mining, robots, spiders, or similar data gathering and extraction tools for any purpose unless expressly permitted by the Company or as otherwise set forth in these Terms."



- Observations (a)–(g):
- **Grade:** **C — rejected on terms.** Decisive, and no further checking done or needed.

  Clause 2.17.4 prohibits automated access in terms: "not use any automated software to view the
  Service without our consent (including use of spiders, robots, crawlers, data mining tools, or
  the like to download or scrape data from the Service...) and only access the Service manually".
  The carve-out is limited to internet search engines and non-commercial public archives; a
  portfolio project shown to prospective clients is neither.

  Clause 2.20 closes it independently: the licence granted is for **personal use** and expressly
  excludes "any collection, aggregation, copying, duplication, display or derivative use of the
  Service nor any use of data mining, robots, spiders, or similar data gathering and extraction
  tools for any purpose unless expressly permitted by the Company".

  robots.txt was not read. It is irrelevant here — terms outrank robots.txt under the grading in
  §1, and no robots directive could permit what clause 2.20 withholds. Skipping straight to the
  terms was the efficient call and is the reordering now recommended in §2.

  Zameen holds by far the largest Lahore house inventory of any candidate. It is rejected anyway.

### Others checked

- Date checked:
- Source:
- Findings:
- **Grade:**
