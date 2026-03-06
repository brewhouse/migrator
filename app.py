
import os
import requests
import re
from flask import Flask, render_template, request, redirect, url_for, send_file, session, flash

from extract import extract_main_content, extract_hero_image, extract_forms
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
        # Split URLs by line, not comma
        source_urls = [u.strip() for u in re.split(r'[\r\n]+', form['source_urls']) if u.strip()]
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
            # Get main content as soup and as blocks
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')
            # Remove header/footer/nav as in extract_main_content
            for tag in soup(['header', 'footer', 'nav', 'aside', 'menu']):
                tag.decompose()
            for tag in soup.find_all(['div', 'section'], class_=re.compile(r'(side|nav|menu|left|breadcrumb)', re.I)):
                tag.decompose()
            for tag in soup.find_all(['div', 'section'], id=re.compile(r'(side|nav|menu|left|breadcrumb)', re.I)):
                tag.decompose()
            main = soup.find('main')
            content = None
            if main:
                content = main
            else:
                divs = soup.find_all('div')
                if divs:
                    main_div = max(divs, key=lambda d: len(d.get_text(strip=True)))
                    content = main_div
                else:
                    body = soup.find('body')
                    content = body if body else soup
            # Remove all <div> tags but keep their content
            for div in content.find_all('div'):
                div.unwrap()
            # Now extract blocks and media from this content only
            from extract import extract_main_content, extract_media_links_from_content
            page_title, main_content = extract_main_content(str(content))
            log_progress('Extracted main content.')
            hero_img_url = extract_hero_image(html, url) if featured_image else None
            media_links = extract_media_links_from_content(content, url)
            log_progress(f'Found {len(media_links)} media files.')
            # Download and upload media
            media_ids = {}
            media_urls = {}  # map original media URL to new WP URL
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
                        if media.get('timeout'):
                            log_progress(f'Upload timed out for: {m_url} (skipped)')
                            continue
                        media_ids[m_url] = media['id']
                        new_url = media.get('source_url')
                        if new_url:
                            media_urls[m_url] = new_url
                        log_progress(f'Uploaded to WordPress media library: {new_url or "(unknown)"}')
            # Featured image
            featured_id = None
            if hero_img_url and hero_img_url in media_ids:
                featured_id = media_ids[hero_img_url]
                log_progress('Set featured image.')
            # Replace <a> tags for PDFs/images with new WP URLs, retain <a> for webpages
            from bs4 import BeautifulSoup
            soup_content = BeautifulSoup(main_content, 'html.parser')
            for a in soup_content.find_all('a'):
                href = a.get('href')
                if href:
                    # If this link was imported as media, replace href
                    for orig_url, new_url in media_urls.items():
                        if href == orig_url:
                            a['href'] = new_url
                            break
                    # Remove class and style from <a>
                    a.attrs = {k: v for k, v in a.attrs.items() if k not in ['class', 'style']}
            # Fix <p> and <a> structure: if a <p> only contains an <a>, keep them together
            for p in soup_content.find_all('p'):
                children = list(p.children)
                if len(children) == 1 and children[0].name == 'a':
                    continue  # already correct
                # If <a> was moved outside <p>, move it back in
                if not any(child.name == 'a' for child in children):
                    next_sibling = p.find_next_sibling('a')
                    if next_sibling and next_sibling.previous_sibling == p:
                        p.append(next_sibling.extract())
            # Remove inline styles from all tags
            for tag in soup_content.find_all(True):
                if 'style' in tag.attrs:
                    del tag.attrs['style']
                if 'class' in tag.attrs:
                    del tag.attrs['class']
            main_content_clean = str(soup_content)
            # Create post/page with extracted title
            title = page_title or (url.split('//')[-1].split('/')[1] if '/' in url.split('//')[-1] else url)
            wp_post = create_wordpress_post(wp_url, wp_user, wp_pass, title, main_content_clean, migrate_type, featured_id)
            log_progress(f'Created {migrate_type}: {wp_post.get("link") or "(no link)"}')
            # Forms
            forms = extract_forms(html)
            if forms:
                gf_json = gravity_form_to_json(forms[0]['fields'], gravity_version)
                with open('gravity_form.json', 'w') as f:
                    f.write(gf_json)
                log_progress('Gravity Forms JSON created and available for download. <a href="/download-gravity-form" target="_blank">Download here</a>')
        @app.route('/download-gravity-form')
        def download_gravity_form():
            return send_file('gravity_form.json', as_attachment=True)
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
