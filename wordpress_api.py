import requests
from requests.auth import HTTPBasicAuth

def create_wordpress_post(site_url, username, password, title, content, post_type='page', featured_image_id=None):
    api_url = f"{site_url.rstrip('/')}/wp-json/wp/v2/{post_type}s"
    data = {
        'title': title,
        'content': content,
        'status': 'publish',
    }
    if featured_image_id:
        data['featured_media'] = featured_image_id
    resp = requests.post(api_url, json=data, auth=HTTPBasicAuth(username, password))
    resp.raise_for_status()
    return resp.json()

def upload_media(site_url, username, password, file_path, mime_type):
    api_url = f"{site_url.rstrip('/')}/wp-json/wp/v2/media"
    with open(file_path, 'rb') as f:
        filename = file_path.split('/')[-1]
        headers = {
            'Content-Disposition': f'attachment; filename={filename}',
            'Content-Type': mime_type
        }
        resp = requests.post(api_url, headers=headers, data=f, auth=HTTPBasicAuth(username, password))
        resp.raise_for_status()
        return resp.json()
