import json

def gravity_form_to_json(form_fields, version='2.7'):
    # Basic Gravity Forms JSON structure
    form = {
        'title': 'Imported Form',
        'fields': [],
        'version': version
    }
    for idx, field in enumerate(form_fields):
        gf_field = {
            'id': idx + 1,
            'label': field.get('label', f'Field {idx+1}'),
            'type': field.get('type', 'text'),
            'adminLabel': field.get('name', f'field_{idx+1}')
        }
        form['fields'].append(gf_field)
    return json.dumps(form, indent=2)
