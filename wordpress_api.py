import requests
from requests.auth import HTTPBasicAuth

def create_wordpress_post(site_url, username, password, title, content, post_type='page', featured_image_id=None):
    # Ensure /wp-admin/ is not in the site_url
    clean_url = site_url.replace('/wp-admin', '').rstrip('/')
    api_url = f"{clean_url}/wp-json/wp/v2/{post_type}s"
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
    clean_url = site_url.replace('/wp-admin', '').rstrip('/')
    api_url = f"{clean_url}/wp-json/wp/v2/media"
    import requests
    from requests.exceptions import Timeout
    with open(file_path, 'rb') as f:
        filename = file_path.split('/')[-1]
        headers = {
            'Content-Disposition': f'attachment; filename={filename}',
            'Content-Type': mime_type
        }
        try:
            resp = requests.post(
                api_url,
                headers=headers,
                data=f,
                auth=HTTPBasicAuth(username, password),
                timeout=120
            )
            resp.raise_for_status()
            return resp.json()
        except Timeout:
            return {'timeout': True}
