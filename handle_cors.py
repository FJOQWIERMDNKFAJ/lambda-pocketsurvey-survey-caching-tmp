

allowed_ip = ['125.128.100.112']
_allowed_origins = [
    'localhost:43000',
    'www.pocketsurvey.co.kr',
    'test.pocketsurvey.co.kr',
    'test2.pocketsurvey.co.kr',
    'pocketsurvey.co.kr',
]
allowed_origins = [
                      f'http://{host}' for host in _allowed_origins
                  ] + [
                      f'https://{host}' for host in _allowed_origins
                  ]


def get_cors_headers(event):
    cors_headers = {
        'Access-Control-Allow-Origin': event['headers']['origin'],
        'Access-Control-Allow-Methods': 'OPTIONS,GET',
        'Access-Control-Allow-Headers': 'Authorization,X-API-Username,Origin,Cache-Control,Pragma,Expires,Content-Type',
    }
    return cors_headers


def get_preflight_headers(event):
    origin = event['headers'].get('origin')
    if origin in allowed_origins:
        return get_cors_headers(event)
    else:
        return {}
        
