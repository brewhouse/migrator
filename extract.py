import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import re
import os

def extract_main_content(html):
    soup = BeautifulSoup(html, 'html.parser')
    # Remove header, footer, nav, aside, menu, left navigation
    for tag in soup(['header', 'footer', 'nav', 'aside', 'menu']):
        tag.decompose()
    for tag in soup.find_all(['div', 'section'], class_=re.compile(r'(side|nav|menu|left)', re.I)):
        tag.decompose()
    for tag in soup.find_all(['div', 'section'], id=re.compile(r'(side|nav|menu|left)', re.I)):
        tag.decompose()

    # Extract page title from <title> or first <h1>
    page_title = None
    if soup.title and soup.title.string:
        page_title = soup.title.string.strip()
    h1 = soup.find('h1')
    if h1 and h1.get_text(strip=True):
        page_title = h1.get_text(strip=True)

    # Try to find main content
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

    # Remove class attributes from all relevant tags
    for tag in content.find_all(['p', 'span', 'ol', 'ul', 'li', 'table', 'th', 'td', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'a']):
        tag.attrs = {k: v for k, v in tag.attrs.items() if k not in ['class']}

    # Convert to WordPress core blocks
    wp_blocks = []
    for el in content.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'ul', 'ol', 'img', 'figure', 'blockquote', 'hr', 'a']):
        if el.name.startswith('h'):
            level = el.name[1]
            wp_blocks.append(f'<!-- wp:heading {{"level":{level}}} --><{el.name}>{el.get_text(strip=True)}</{el.name}><!-- /wp:heading -->')
        elif el.name == 'p':
            # Avoid <p> inside <li>
            if el.find_parent('li') is None:
                wp_blocks.append(f'<!-- wp:paragraph --><p>{el.get_text(strip=True)}</p><!-- /wp:paragraph -->')
        elif el.name in ['ul', 'ol']:
            # Remove <p> tags inside <li>
            for li in el.find_all('li'):
                for p in li.find_all('p'):
                    p.unwrap()
            wp_blocks.append(f'<!-- wp:list --><{el.name}>{el.decode_contents()}</{el.name}><!-- /wp:list -->')
        elif el.name == 'img':
            src = el.get('src', '')
            alt = el.get('alt', '')
            wp_blocks.append(f'<!-- wp:image --><figure class="wp-block-image"><img src="{src}" alt="{alt}"/></figure><!-- /wp:image -->')
        elif el.name == 'figure':
            wp_blocks.append(f'<!-- wp:image --><figure class="wp-block-image">{el.decode_contents()}</figure><!-- /wp:image -->')
        elif el.name == 'blockquote':
            wp_blocks.append(f'<!-- wp:quote --><blockquote>{el.decode_contents()}</blockquote><!-- /wp:quote -->')
        elif el.name == 'hr':
            wp_blocks.append(f'<!-- wp:spacer --><hr /><!-- /wp:spacer -->')
        elif el.name == 'a':
            # Retain <a> tags as-is (they will be handled in app.py for media links)
            wp_blocks.append(str(el))

    # TODO: Add support for media-text, columns, group, etc. if detected

    return page_title, '\n'.join(wp_blocks)

def extract_hero_image(html, base_url):
    soup = BeautifulSoup(html, 'html.parser')
    # Look for banner/hero images by class/id
    img = soup.find('img', class_=re.compile(r'(hero|banner|main|large)', re.I))
    if not img:
        img = soup.find('img', id=re.compile(r'(hero|banner|main|large)', re.I))
    if not img:
        # Fallback: first large image
        imgs = soup.find_all('img')
        def safe_int(val):
            try:
                return int(val)
            except Exception:
                try:
                    return int(str(val).replace('px','').strip())
                except Exception:
                    return 0
        if imgs:
            imgs = sorted(imgs, key=lambda i: safe_int(i.get('width', 0)) * safe_int(i.get('height', 0)), reverse=True)
            img = imgs[0]
    if img and img.get('src'):
        return urljoin(base_url, img['src'])
    return None

def extract_media_links_from_content(content, base_url):
    media = set()
    for tag in content.find_all(['img', 'a']):
        if tag.name == 'img' and tag.get('src'):
            src = urljoin(base_url, tag['src'])
            media.add(src)
        if tag.name == 'a' and tag.get('href'):
            href = urljoin(base_url, tag['href'])
            if re.search(r'\.(pdf|jpg|jpeg|png|gif|webp)$', href, re.I):
                media.add(href)
    return list(media)

def extract_forms(html):
    soup = BeautifulSoup(html, 'html.parser')
    forms = []
    for form in soup.find_all('form'):
        form_data = {'fields': []}
        for field in form.find_all(['input', 'textarea', 'select']):
            field_type = field.get('type', 'text')
            name = field.get('name')
            label = None
            if field.has_attr('id'):
                label_tag = soup.find('label', {'for': field['id']})
                if label_tag:
                    label = label_tag.get_text(strip=True)
            form_data['fields'].append({
                'type': field_type,
                'name': name,
                'label': label or name
            })
        forms.append(form_data)
    return forms
