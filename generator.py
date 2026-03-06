import requests, os, re, time, json

# --- GLOBAL CONFIGURATION ---
TMDB_API_KEY = "13a2e3c3497a4d8b8f9a1d449a02a373"
API_BASE = "https://api.themoviedb.org/3"
POSTER_BASE = "https://image.tmdb.org/t/p/w500"

# Ilang pahina ng Trending Movies ang kukunin (20 movies per page)
PAGES_TO_FETCH = 2

# [MULTI-CLUSTER PBN CONFIGURATION]
TARGETS = [
    {
        "domain": "https://iyong-pbn-site.com",  # Palitan ng domain ng PBN mo
        "path": ".",  # Folder kung saan mase-save ang files (ginawa kong "." para sa root folder mo muna, o palitan ng "./pbn_output")
        "authority_url": "https://cinemaroll.pages.dev",  # Iyong Money Site
    }
]

# Database buffer para sa search index
CURRENT_INDEX_DB = []


# --- HELPER FUNCTIONS ---
def slugify(text, item_id=""):
    text = str(text).lower()
    slug = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    slug = slug[:50].strip("-")
    if not slug:
        slug = "movie"
    return f"{slug}-{item_id}"


def generate_json_ld(movie, url):
    """Schema.org para sa Movie SEO"""
    schema = {
        "@context": "https://schema.org",
        "@type": "Movie",
        "name": movie.get("title", "Untitled"),
        "description": movie.get("overview", "Watch this movie in HD."),
        "image": f"{POSTER_BASE}{movie.get('poster_path', '')}",
        "dateCreated": movie.get("release_date", ""),
        "url": url,
    }
    return json.dumps(schema)


def generate_sitemaps(target_path, site_domain):
    print(f"    🗺️  Generating sitemap.xml...")
    xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'

    videos_path = os.path.join(target_path, "watch")
    if os.path.exists(videos_path):
        for filename in os.listdir(videos_path):
            if filename.endswith(".html"):
                file_path = os.path.join(videos_path, filename)
                mod_time = time.strftime(
                    "%Y-%m-%d", time.gmtime(os.path.getmtime(file_path))
                )
                xml_content += f"  <url>\n    <loc>{site_domain}/watch/{filename}</loc>\n    <lastmod>{mod_time}</lastmod>\n    <priority>0.80</priority>\n  </url>\n"

    xml_content += "</urlset>"
    with open(os.path.join(target_path, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write(xml_content)


def generate_robots_txt(target_path, site_domain):
    print("    🤖 Generating robots.txt...")
    content = f"User-agent: *\nAllow: /\nUser-agent: AhrefsBot\nDisallow: /\nUser-agent: SemrushBot\nDisallow: /\nSitemap: {site_domain}/sitemap.xml\n"
    with open(os.path.join(target_path, "robots.txt"), "w", encoding="utf-8") as f:
        f.write(content)


# --- CORE LOGIC ---
def fetch_movies_from_tmdb():
    movies_list = []
    seen_ids = set()
    print("📡 Kumokonekta sa TMDB API...")

    for page in range(1, PAGES_TO_FETCH + 1):
        try:
            url = f"{API_BASE}/trending/movie/week?api_key={TMDB_API_KEY}&page={page}"
            response = requests.get(url).json()
            for movie in response.get("results", []):
                if movie["id"] not in seen_ids and movie.get("poster_path"):
                    seen_ids.add(movie["id"])
                    movies_list.append(movie)
        except Exception as e:
            print(f"  ❌ Error fetching TMDB page {page}: {e}")

    print(f"✅ Nakakuha ng {len(movies_list)} unique movies.")
    return movies_list


def process_targets(movies):
    global CURRENT_INDEX_DB
    try:
        with open("template.html", "r", encoding="utf-8") as f:
            TEMPLATE = f.read()
    except FileNotFoundError:
        print("❌ CRITICAL ERROR: Wala ang template.html sa folder na ito!")
        return

    for target in TARGETS:
        domain = target["domain"]
        root_path = target["path"]
        authority_url = target["authority_url"]

        print(f"\n🚀 Processing Target PBN: {domain}")
        os.makedirs(os.path.join(root_path, "watch"), exist_ok=True)

        new_files_count = 0
        CURRENT_INDEX_DB = []  # I-reset per target

        for movie in movies:
            title = movie.get("title", "Untitled")
            m_id = movie.get("id")
            slug = slugify(title, m_id)

            output_filename = f"{slug}.html"
            output_path = os.path.join(root_path, "watch", output_filename)

            page_url = f"{domain}/watch/{slug}.html"
            canonical_url = f"{domain}/watch/{slug}.html"

            try:
                # Prepare data
                overview = movie.get(
                    "overview", "Stream this premium movie in HD quality online."
                )
                rating = round(movie.get("vote_average", 0), 1)
                year = movie.get("release_date", "2025").split("-")[0]
                poster_url = f"{POSTER_BASE}{movie.get('poster_path')}"

                embed_code = f'<iframe src="https://vidlink.pro/movie/{m_id}" class="player-frame" allowfullscreen referrerpolicy="origin" scrolling="no" frameborder="0"></iframe>'
                seo_desc = f"Watch {title} ({year}) full movie in HD. High-quality streaming review and details."

                # --- 1. IDAGDAG SA SEARCH INDEX ---
                CURRENT_INDEX_DB.append(
                    {
                        "id": m_id,
                        "title": title,
                        "year": year,
                        "rating": rating,
                        "poster": poster_url,
                        "url": f"watch/{output_filename}",  # Static link
                    }
                )

                if os.path.exists(output_path):
                    continue

                # --- 2. GUMAWA NG HTML FILE ---
                html_content = (
                    TEMPLATE.replace("{{TITLE}}", title.replace('"', "&quot;"))
                    .replace("{{SEO_DESCRIPTION}}", seo_desc.replace('"', "&quot;"))
                    .replace("{{CANONICAL}}", canonical_url)
                    .replace("{{EMBED_CODE}}", embed_code)
                    .replace("{{POSTER_URL}}", poster_url)
                    .replace("{{RATING}}", str(rating))
                    .replace("{{YEAR}}", str(year))
                    .replace("{{OVERVIEW}}", overview.replace('"', "&quot;"))
                    .replace("{{AUTHORITY_URL}}", authority_url)
                    .replace("{{MOVIE_ID}}", str(m_id))
                    .replace("{{MEDIA_TYPE}}", "movie")
                    .replace("{{SCHEMA}}", generate_json_ld(movie, page_url))
                )

                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(html_content)
                new_files_count += 1

            except Exception as e:
                print(f"    ❌ Error sa movie {m_id}: {e}")

        print(f"   ✅ Finished. New files generated: {new_files_count}")
        generate_sitemaps(root_path, domain)
        generate_robots_txt(root_path, domain)

        # --- 3. I-SAVE ANG SEARCH INDEX JSON ---
        search_index_path = os.path.join(root_path, "search_index.json")
        with open(search_index_path, "w", encoding="utf-8") as f:
            json.dump(CURRENT_INDEX_DB, f, ensure_ascii=False, indent=4)
        print(
            f"   🔍 Generated search_index.json with {len(CURRENT_INDEX_DB)} entries."
        )


if __name__ == "__main__":
    print("🎬 Starting CINEMAROLL PBN Generator...")
    start_time = time.time()
    movies_data = fetch_movies_from_tmdb()
    if movies_data:
        process_targets(movies_data)
    else:
        print("❌ Walang nakuha sa API. Aborting.")
    print(f"\n🎉 All tasks completed in {round(time.time() - start_time, 2)} seconds.")
