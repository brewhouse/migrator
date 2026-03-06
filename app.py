
import os
import requests
from flask import Flask, render_template, request, redirect, url_for, send_file, session, flash

from extract import extract_main_content, extract_hero_image, extract_media_links, extract_forms
from wordpress_api import create_wordpress_post, upload_media
from gravity_form import gravity_form_to_json
import tempfile
import mimetypes
import threading
import time

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'changeme')

# In-memory progress log (per session)
progress_log = []

def log_progress(msg):
    progress_log.append(msg)
    if len(progress_log) > 50:
        progress_log.pop(0)

def migrate_content(form):
    try:
        log_progress('Starting migration...')
        source_urls = [u.strip() for u in form['source_urls'].split(',') if u.strip()]
        wp_url = form['wp_url']
        wp_user = form['wp_user']
        wp_pass = form['wp_pass']
        migrate_type = form['migrate_type']
        featured_image = 'featured_image' in form
        gravity_version = form.get('gravity_version', '2.7')
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        for url in source_urls:
            log_progress(f'Fetching {url}...')
            resp = requests.get(url, headers=headers)
            resp.raise_for_status()
            html = resp.text
            page_title, main_content = extract_main_content(html)
            log_progress('Extracted main content.')
            hero_img_url = extract_hero_image(html, url) if featured_image else None
            media_links = extract_media_links(html, url)
            log_progress(f'Found {len(media_links)} media files.')
            # Download and upload media
            media_ids = {}
            for m_url in media_links:
                log_progress(f'Downloading media: {m_url}')
                m_resp = requests.get(m_url, headers=headers)
                if m_resp.status_code == 200:
                    ext = os.path.splitext(m_url)[-1]
                    mime = mimetypes.guess_type(m_url)[0] or 'application/octet-stream'
                    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                        tmp.write(m_resp.content)
                        tmp.flush()
                        media = upload_media(wp_url, wp_user, wp_pass, tmp.name, mime)
                        media_ids[m_url] = media['id']
                        log_progress(f'Uploaded to WordPress media library: {media.get("source_url") or "(unknown)"}')
            # Featured image
            featured_id = None
            if hero_img_url and hero_img_url in media_ids:
                featured_id = media_ids[hero_img_url]
                log_progress('Set featured image.')
            # Create post/page with extracted title
            title = page_title or (url.split('//')[-1].split('/')[1] if '/' in url.split('//')[-1] else url)
            wp_post = create_wordpress_post(wp_url, wp_user, wp_pass, title, main_content, migrate_type, featured_id)
            log_progress(f'Created {migrate_type}: {wp_post.get("link") or "(no link)"}')
            # Forms
            forms = extract_forms(html)
            if forms:
                gf_json = gravity_form_to_json(forms[0]['fields'], gravity_version)
                with open('gravity_form.json', 'w') as f:
                    f.write(gf_json)
                log_progress('Gravity Forms JSON created and available for download.')
        log_progress('Migration complete!')
    except Exception as e:
        log_progress(f'Error: {str(e)}')

@app.route('/', methods=['GET', 'POST'])
def index():
    global progress_log
    if request.method == 'POST':
        progress_log = []
        form = request.form.to_dict(flat=True)
        thread = threading.Thread(target=migrate_content, args=(form,))
        thread.start()
        time.sleep(1)  # Let the thread start
    return render_template('index.html', progress_log=progress_log)

@app.route('/progress')
def progress():
    return {'log': progress_log}

if __name__ == '__main__':
    app.run(debug=True)
