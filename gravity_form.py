import json

def gravity_form_to_json(form_fields, version='2.7'):
    # Build a Gravity Forms export JSON matching the example structure
    # Only one form per export, with the form as the value of key '0'
    form = {
        "title": "Planeteria Support",
        "description": "",
        "labelPlacement": "top_label",
        "descriptionPlacement": "below",
        "button": {
            "type": "text",
            "text": "Submit",
            "imageUrl": "",
            "width": "auto",
            "location": "bottom",
            "layoutGridColumnSpan": 12
        },
        "fields": [],
        "version": version,
        "id": 1,
        "markupVersion": 2,
        "nextFieldId": 11,
        "useCurrentUserAsAuthor": True,
        "postContentTemplateEnabled": False,
        "postTitleTemplateEnabled": False,
        "postTitleTemplate": "",
        "postContentTemplate": "",
        "lastPageButton": None,
        "pagination": None,
        "firstPageCssClass": None,
        "confirmations": [
            {
                "id": "62c3bbbf061c5",
                "name": "Default Confirmation",
                "isDefault": True,
                "type": "message",
                "message": "Thanks for contacting us! We will get in touch with you shortly.",
                "url": "",
                "pageId": "",
                "queryString": ""
            }
        ],
        "notifications": [
            {
                "id": "62c3bbbf04038",
                "isActive": True,
                "to": "keegan@planeteria.com",
                "name": "Admin Notification",
                "event": "form_submission",
                "toType": "email",
                "subject": "New submission from {form_title} | {site_name}",
                "message": "{all_fields}",
                "service": "wordpress",
                "toEmail": "keegan@planeteria.com",
                "toField": "",
                "routing": None,
                "fromName": "Dev Seed Site 2024",
                "from": "noreply@planeteria.com",
                "replyTo": "",
                "bcc": "",
                "disableAutoformat": False,
                "notification_conditional_logic_object": "",
                "notification_conditional_logic": "0",
                "conditionalLogic": None,
                "cc": "",
                "enableAttachments": False
            }
        ]
    }
    # Map fields
    for idx, field in enumerate(form_fields[0]['fields'] if form_fields and 'fields' in form_fields[0] else []):
        gf_field = {
            'id': idx + 1,
            'label': field.get('label', f'Field {idx+1}'),
            'type': field.get('type', 'text'),
            'adminLabel': field.get('name', f'field_{idx+1}')
        }
        form['fields'].append(gf_field)
    # The export must be a dict with key '0' and the form as value
    export = {'0': form, 'version': version}
    return json.dumps(export, indent=2)
