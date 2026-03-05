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
    # Remove left navigation by class/id
    for tag in soup.find_all(['div', 'section'], class_=re.compile(r'(side|nav|menu|left)', re.I)):
        tag.decompose()
    for tag in soup.find_all(['div', 'section'], id=re.compile(r'(side|nav|menu|left)', re.I)):
        tag.decompose()
    # Try to find main content
    main = soup.find('main')
    content = None
    if main:
        content = main
    else:
        # Fallback: largest <div> by text length
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

    # Convert paragraphs and headings to Kadence blocks
    kadence_blocks = []
    for el in content.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'ul', 'ol', 'li', 'img']):
        if el.name.startswith('h'):
            kadence_blocks.append(f'<!-- wp:kadence/advancedheading --><{el.name}>{el.get_text(strip=True)}</{el.name}><!-- /wp:kadence/advancedheading -->')
        elif el.name == 'p':
            kadence_blocks.append(f'<!-- wp:kadence/paragraph --><p>{el.get_text(strip=True)}</p><!-- /wp:kadence/paragraph -->')
        elif el.name in ['ul', 'ol']:
            kadence_blocks.append(f'<!-- wp:list --><{el.name}>{el.decode_contents()}</{el.name}><!-- /wp:list -->')
        elif el.name == 'li':
            continue  # handled by parent ul/ol
        elif el.name == 'img':
            src = el.get('src', '')
            alt = el.get('alt', '')
            kadence_blocks.append(f'<!-- wp:image --><figure class="wp-block-image"><img src="{src}" alt="{alt}"/></figure><!-- /wp:image -->')

    return '\n'.join(kadence_blocks)

def extract_hero_image(html, base_url):
    soup = BeautifulSoup(html, 'html.parser')
    # Look for banner/hero images by class/id
    img = soup.find('img', class_=re.compile(r'(hero|banner|main|large)', re.I))
    if not img:
        img = soup.find('img', id=re.compile(r'(hero|banner|main|large)', re.I))
    if not img:
        # Fallback: first large image
        imgs = soup.find_all('img')
        if imgs:
            imgs = sorted(imgs, key=lambda i: int(i.get('width', 0)) * int(i.get('height', 0)), reverse=True)
            img = imgs[0]
    if img and img.get('src'):
        return urljoin(base_url, img['src'])
    return None

def extract_media_links(html, base_url):
    soup = BeautifulSoup(html, 'html.parser')
    media = set()
    for tag in soup.find_all(['img', 'a']):
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
