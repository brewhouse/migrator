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
    if main:
        return str(main)
    # Fallback: largest <div> by text length
    divs = soup.find_all('div')
    if divs:
        main_div = max(divs, key=lambda d: len(d.get_text(strip=True)))
        return str(main_div)
    # Fallback: body
    body = soup.find('body')
    return str(body) if body else html

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
