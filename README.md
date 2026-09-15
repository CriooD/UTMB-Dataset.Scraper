<h1>Dataset Scraper - UTMB Puerto Vallarta 2024</h1>

<h2>Description</h2>
This script gets the public results for "Puerto Vallarta México by UTMB 2024" from the UTMB Index pages on utmb.world.
<br />

<h2>Languages Used</h2>

- <b>Python</b> 

<h2>Environments Used </h2>

- <b>Google Collab</b> 

<h2>Script walk-through:</h2>

  - <b>The data sources</b>
    
The event's live results page, `https://live.utmb.world/puertovallarta/2024`, turned out to be a JavaScript single-page app: the raw HTML only contains a loading placeholder, since the actual results are injected later by client-side JavaScript calling an internal API that isn't publicly documented.
Instead, this scraper pulls data from **utmb.world**'s UTMB Index race pages, which ARE server-rendered (the full results table is already present in the initial HTML) and paginated 25 runners per page:

<br />

| Distance | Race        | URL                                                                                                  |
|----------|-------------|-------------------------------------------------------------------------------------------------------|
| 100M     | Wixárika    | https://utmb.world/utmb-index/races/32454.puertovallartamexicobyutmbwixarika-100m.2024               |
| 100K     | Hikuri      | https://utmb.world/utmb-index/races/32456.puertovallartamexicobyutmbhikuri100k.2024                  |
| 50K      | Nakawé      | https://utmb.world/utmb-index/races/32458.puertovallartamexicobyutmbnakawe50k.2024                   |
| 33K      | Haramara    | https://utmb.world/utmb-index/races/39600.puertovallartamexicobyutmbharamara33k.2024                 |
| 20K      | Ereno       | https://utmb.world/utmb-index/races/32460.puertovallartamexicobyutmbereno20k.2024                    |
| 10K      | Pata Salada | https://utmb.world/utmb-index/races/39602.puertovallartamexicobyutmbpatasalada10k.2024                |

<br />

- <b>No `<table>` tag to rely on</b>

utmb.world is a Next.js site, and its results grid isn't built with semantic `<table>`/`<tr>`/`<td>` tags — it's plain `<div>`s styled as a grid. That means a normal `soup.find("table")` approach returns nothing. Instead, the script reads the page's *visible text* in order (`soup.get_text(separator="\n")`) and reconstructs each row by recognizing the *shape* the data takes on the page, rather than relying on any specific tag or CSS class.

<br />

- <b>Anchoring each row on gender</b>

Every runner row includes either `Men` or `Women` — the one value that's always present, whether the runner finished or not. The script scans the page's text lines and uses that as an anchor point: once a `Men`/`Women` line is found, it looks one line before it for nationality, two lines before for the runner's name, and one line after for the age category.

<br />

- <b>Pagination</b>

Each race's results are paginated 25 runners per page. Before scraping a race, the script reads the pagination links at the bottom of page 1 (`?page=2`, `?page=3`, ...) to figure out how many pages exist, then requests each one in turn with a short delay between requests.

<br />

- <b>Handling DNF runners</b>

Finishers have a rank number and a time (`HH:MM:SS`) right before their name. Runners who did not finish (DNF) don't get a rank number at all on the page — their row is one field shorter. The script checks the line where a time *should* be: if it's a real time, it also grabs the rank right before it; if it's `DNF` (or `-`, `DNS`, `DSQ`) instead, it skips looking for a rank altogether and records that runner with `time = 00:00:00` and `status = DNF`, so finishers and non-finishers end up in the same table but stay clearly distinguishable.

<br />

- <b>Output</b>

Every parsed row is tagged with its race category, distance, elevation gain and year, then all six distances are combined into a single `pandas` DataFrame and exported to `utmb_puerto_vallarta_2024.csv`.
