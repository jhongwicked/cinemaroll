import requests, os, re, time, json
import xmlrpc.client
import google.generativeai as genai

# --- CONFIGURATION ---
TMDB_API_KEY = "13a2e3c3497a4d8b8f9a1d449a02a373"
API_BASE = "https://api.themoviedb.org/3"
POSTER_BASE = "https://image.tmdb.org/t/p/w500"
PAGES_TO_FETCH = 2

TARGETS = [
    {
        "domain": "https://iyong-pbn-site.com",  # Ilagay ang iyong custom domain pag mayroon na
        "path": ".",
        "authority_url": "https://cinemaroll.pages.dev",
    }
]

# --- AI CONTENT SPINNER SETUP ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    # Gumagamit na ito ng "latest" para maiwasan ang 404 error
    ai_model = genai.GenerativeModel("gemini-1.5-flash-latest")


def generate_unique_synopsis(title, original_overview):
    """Gumagawa ng SEO-friendly description gamit ang AI"""
    if not GEMINI_API_KEY:
        return original_overview

    prompt = f"Write a unique, engaging, and SEO-friendly 50-word movie review and synopsis for the movie '{title}'. Here is the original plot: {original_overview}. Do not use the exact phrasing. Make it sound like a movie critic recommending it for streaming."
    try:
        response = ai_model.generate_content(prompt)
        time.sleep(2)
        return response.text.strip()
    except Exception as e:
        print(f"    ⚠️ AI Rewrite failed for {title}: {e}")
        return original_overview


CURRENT_INDEX_DB = []


def slugify(text, item_id=""):
    text = str(text).lower()
    slug = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return f"{slug[:50].strip('-')}-{item_id}"


def generate_json_ld(movie, url):
    schema = {
        "@context": "https://schema.org",
        "@type": "Movie",
        "name": movie.get("title", "Untitled"),
        "description": movie.get("overview", "Watch this movie in HD."),
        "image": f"{POSTER_BASE}{movie.get('poster_path', '')}",
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
                xml_content += f"  <url>\n    <loc>{site_domain}/watch/{filename}</loc>\n  </url>\n"
    xml_content += "</urlset>"
    with open(os.path.join(target_path, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write(xml_content)


def generate_robots_txt(target_path, site_domain):
    print("    🤖 Generating robots.txt...")
    content = f"User-agent: *\nAllow: /\nSitemap: {site_domain}/sitemap.xml\n"
    with open(os.path.join(target_path, "robots.txt"), "w", encoding="utf-8") as f:
        f.write(content)


def inject_links_to_index(target_path, movies):
    print("    🔗 Injecting static links to index.html for SEO...")
    index_path = os.path.join(target_path, "index.html")
    if not os.path.exists(index_path):
        return

    with open(index_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    links_html = "\n"
    for movie in movies[:50]:
        title = movie.get("title", "Untitled")
        clean_title = (
            title.replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")
        )
        slug = slugify(title, movie.get("id"))
        links_html += f'<a href="watch/{slug}.html" style="color: #888; text-decoration: none; font-size: 12px; background: #1a1d24; padding: 5px 10px; border-radius: 3px;">Watch {clean_title}</a>\n'
    links_html += ""

    new_html = re.sub(r".*?", links_html, html_content, flags=re.DOTALL)

    with open(index_path, "w", encoding="utf-8") as f:
        f.write(new_html)


def ping_pingomatic(site_name, site_url):
    print(f"    📡 Pinging Ping-o-matic for {site_name}...")
    try:
        server = xmlrpc.client.ServerProxy("http://rpc.pingomatic.com/")
        server.weblogUpdates.ping(site_name, site_url)
        print("    ✅ Ping successful!")
    except Exception as e:
        print(f"    ❌ Ping failed: {e}")


def fetch_movies_from_tmdb():
    movies_list = []
    seen_ids = set()
    print("📡 Fetching from TMDB API...")
    for page in range(1, PAGES_TO_FETCH + 1):
        try:
            url = f"{API_BASE}/trending/movie/week?api_key={TMDB_API_KEY}&page={page}"
            response = requests.get(url).json()
            for movie in response.get("results", []):
                if movie["id"] not in seen_ids and movie.get("poster_path"):
                    seen_ids.add(movie["id"])
                    movies_list.append(movie)
        except Exception as e:
            pass
    return movies_list


def process_targets(movies):
    global CURRENT_INDEX_DB
    try:
        with open("template.html", "r", encoding="utf-8") as f:
            TEMPLATE = f.read()
    except Exception:
        print("❌ ERROR: template.html not found!")
        return

    for target in TARGETS:
        domain = target["domain"]
        root_path = target["path"]
        authority_url = target["authority_url"]
        os.makedirs(os.path.join(root_path, "watch"), exist_ok=True)
        CURRENT_INDEX_DB = []
        new_files_count = 0

        for movie in movies:
            title = movie.get("title", "Untitled")
            m_id = movie.get("id")
            slug = slugify(title, m_id)
            output_path = os.path.join(root_path, "watch", f"{slug}.html")

            raw_overview = movie.get("overview", "Stream HD movies.")
            poster_url = f"{POSTER_BASE}{movie.get('poster_path')}"

            CURRENT_INDEX_DB.append(
                {
                    "id": m_id,
                    "title": title,
                    "year": movie.get("release_date", "2025").split("-")[0],
                    "rating": round(movie.get("vote_average", 0), 1),
                    "poster": poster_url,
                    "url": f"watch/{slug}.html",
                }
            )

            if os.path.exists(output_path):
                continue

            overview = generate_unique_synopsis(title, raw_overview)
            print(f"    ✨ AI Generated content for: {title}")

            html_content = (
                TEMPLATE.replace("{{TITLE}}", title.replace('"', "&quot;"))
                .replace("{{OVERVIEW}}", overview.replace('"', "&quot;"))
                .replace("{{POSTER_URL}}", poster_url)
                .replace("{{CANONICAL}}", f"{domain}/watch/{slug}.html")
                .replace(
                    "{{EMBED_CODE}}",
                    f'<iframe src="https://vidlink.pro/movie/{m_id}" class="player-frame" allowfullscreen></iframe>',
                )
                .replace("{{AUTHORITY_URL}}", authority_url)
                .replace("{{MOVIE_ID}}", str(m_id))
                .replace("{{MEDIA_TYPE}}", "movie")
                .replace(
                    "{{SCHEMA}}", generate_json_ld(movie, f"{domain}/watch/{slug}.html")
                )
            )

            with open(output_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            new_files_count += 1

        with open(
            os.path.join(root_path, "search_index.json"), "w", encoding="utf-8"
        ) as f:
            json.dump(CURRENT_INDEX_DB, f, ensure_ascii=False, indent=4)

        # NASA LABAS NA ANG MGA ITO PARA HINDI MAGKA-INFINITE LOOP
        generate_sitemaps(root_path, domain)
        generate_robots_txt(root_path, domain)
        inject_links_to_index(root_path, movies)
        ping_pingomatic("CINEMAROLL PBN", domain)


if __name__ == "__main__":
    movies_data = fetch_movies_from_tmdb()
    if movies_data:
        process_targets(movies_data)
