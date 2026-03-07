

import os
import requests
import re
from flask import Flask, render_template, request, redirect, url_for, send_file, session, flash
from werkzeug.utils import secure_filename
from docx_extract import extract_docx_content
from pdf_extract import extract_pdf_content

from extract import extract_main_content, extract_hero_image, extract_forms, extract_media_links_from_content
from wordpress_api import create_wordpress_post, upload_media
from gravity_form import gravity_form_to_json
import tempfile
import mimetypes
import threading
import time

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'changeme')

# Route to download Gravity Forms JSON export
from flask import abort
@app.route('/download-form-json')
def download_form_json():
    path = request.args.get('path')
    if not path or not os.path.isfile(path):
        return abort(404)
    return send_file(path, as_attachment=True, download_name=os.path.basename(path), mimetype='application/json')

# In-memory progress log (per session)
progress_log = []

def log_progress(msg):
    progress_log.append(msg)
    if len(progress_log) > 50:
        progress_log.pop(0)

@app.route('/', methods=['GET', 'POST'])
def index():
    global progress_log
    if request.method == 'POST':
        form = request.form.to_dict()
        if 'upload_file' in request.files:
            form['upload_file'] = request.files['upload_file']
        thread = threading.Thread(target=migrate_content, args=(form,))
        thread.start()
        time.sleep(1)
        return redirect(url_for('index'))
    log = progress_log.copy()
    progress_log = []
    return render_template('index.html', progress_log=log)

def migrate_content(form):
    try:
        log_progress('Starting migration...')
        source_urls = [u.strip() for u in re.split(r'[\r\n]+', form.get('source_urls', '')) if u.strip()]
        upload_file = form.get('upload_file')
        wp_url = form['wp_url']
        wp_user = form['wp_user']
        wp_pass = form['wp_pass']
        migrate_type = form['migrate_type']
        featured_image = 'featured_image' in form
        gravity_version = form.get('gravity_version', '2.7')
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}

        # --- Handle file upload (Word/PDF) first ---
        if upload_file:
            try:
                log_progress('Starting migration...')
                source_urls = [u.strip() for u in re.split(r'[\r\n]+', form.get('source_urls', '')) if u.strip()]
                upload_file = form.get('upload_file')
                wp_url = form['wp_url']
                wp_user = form['wp_user']
                wp_pass = form['wp_pass']
                migrate_type = form['migrate_type']
                featured_image = 'featured_image' in form
                gravity_version = form.get('gravity_version', '2.7')
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}

                # --- Handle file upload (Word/PDF) first ---
                if upload_file:
                    filename = secure_filename(upload_file.filename)
                    temp_path = os.path.join(tempfile.gettempdir(), filename)
                    upload_file.save(temp_path)
                    if filename.lower().endswith('.docx'):
                        html = extract_docx_content(temp_path)
                        filetype = 'Word document'
                    elif filename.lower().endswith('.pdf'):
                        html = extract_pdf_content(temp_path)
                        filetype = 'PDF document'
                    else:
                        log_progress('Unsupported file type uploaded.')
                        return
                    page_title, main_content = extract_main_content(html)
                    main_content_clean = main_content
                    title = page_title or filename
                    wp_post = create_wordpress_post(wp_url, wp_user, wp_pass, title, main_content_clean, migrate_type, None)
                    log_progress(f'Created {migrate_type} from {filetype}: {wp_post.get("link") or "(no link)"}')

            except Exception as e:
                log_progress(f'Error processing uploaded file: {str(e)}')

        # --- Handle URL migration ---
        for url in source_urls:
            log_progress(f'Fetching {url}...')
            try:
                resp = requests.get(url, headers=headers, timeout=30)
                resp.raise_for_status()
            except Exception as e:
                log_progress(f'Error fetching {url}: {str(e)}')
                continue
            html = resp.text
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')
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
            for div in content.find_all('div'):
                div.unwrap()
            page_title, main_content = extract_main_content(str(content))
            log_progress('Extracted main content.')
            # Gravity Forms export
            forms = extract_forms(str(content))
            if forms and len(forms) > 0:
                gf_json = gravity_form_to_json(forms, gravity_version)
                temp_json_path = os.path.join(tempfile.gettempdir(), f'gravity_form_{int(time.time())}.json')
                with open(temp_json_path, 'w') as f:
                    f.write(gf_json)
                log_progress(f'Gravity Form detected and exported. <a href=\"/download-form-json?path={temp_json_path}\" target=\"_blank\">Download JSON</a>')
            hero_img_url = extract_hero_image(html, url) if featured_image else None
            media_links = extract_media_links_from_content(content, url)
            log_progress(f'Found {len(media_links)} media files.')
            media_ids = {}
            media_urls = {}
            for m_url in media_links:
                log_progress(f'Downloading media: {m_url}')
                try:
                    m_resp = requests.get(m_url, headers=headers, timeout=30)
                    if m_resp.status_code != 200:
                        log_progress(f'Failed to download media: {m_url} (status {m_resp.status_code})')
                        continue
                except Exception as e:
                    log_progress(f'Error downloading media: {m_url} ({str(e)})')
                    continue
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
            featured_id = None
            if hero_img_url and hero_img_url in media_ids:
                featured_id = media_ids[hero_img_url]
                log_progress('Set featured image.')
            soup_content = BeautifulSoup(main_content, 'html.parser')
            for a in soup_content.find_all('a'):
                href = a.get('href')
                if href:
                    for orig_url, new_url in media_urls.items():
                        if href == orig_url:
                            a['href'] = new_url
                            break
                    a.attrs = {k: v for k, v in a.attrs.items() if k not in ['class', 'style']}
            for p in soup_content.find_all('p'):
                children = list(p.children)
                if len(children) == 1 and children[0].name == 'a':
                    continue
                if not any(child.name == 'a' for child in children):
                    next_sibling = p.find_next_sibling('a')
                    if next_sibling and next_sibling.previous_sibling == p:
                        p.append(next_sibling.extract())
            for tag in soup_content.find_all(True):
                if 'style' in tag.attrs:
                    del tag.attrs['style']
                if 'class' in tag.attrs:
                    del tag.attrs['class']
            main_content_clean = str(soup_content)
            title = page_title or (url.split('//')[-1].split('/')[1] if '/' in url.split('//')[-1] else url)
            wp_post = create_wordpress_post(wp_url, wp_user, wp_pass, title, main_content_clean, migrate_type, featured_id)
            log_progress(f'Created {migrate_type}: {wp_post.get("link") or "(no link)"}')
            log_progress('Migration complete!')

    except Exception as e:
        log_progress(f'Error: {str(e)}')

# End of migrate_content
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5001)), debug=True)
