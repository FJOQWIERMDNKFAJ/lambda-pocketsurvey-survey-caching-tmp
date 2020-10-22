import json

from utils import PandasJsonEncoder
from handle_cors import get_preflight_headers, get_cors_headers

DEBUGGING = False

def respond(statusCode, body, event, isBase64Encoded=False, headers=None, multiValueHeaders=None):
    o = {
        'statusCode': statusCode,
        'body': body if isinstance(body, str) else json.dumps(body, cls=PandasJsonEncoder),
        'isBase64Encoded': isBase64Encoded,
    }
    if headers:
        o['headers'] = headers
    if multiValueHeaders:
        o['multiValueHeaders'] = multiValueHeaders
        
    cors_headers = get_preflight_headers(event)
    _headers = o.setdefault('headers', {})
    o['headers'] = {**_headers, **cors_headers}
    return o
    

def normalize_headers(event):
    normalized_header = {k.lower(): v for k, v in event['headers'].items()}
    event['headers'] = normalized_header
    return event


def lambda_handler(event, context):
    event = normalize_headers(event)
    env = event['requestContext']['stage']
    method = event['httpMethod']
    try:
        if method == 'OPTIONS':
            return respond(200, {'result': 'work hard to be lazy.'}, event=event)
        resource = event['resource']
        if resource == '/blueprints/{survey-id}/{survey-version}':
            return dispatcher(handle_blueprint_cache_reader, event=event, context=context)
        if resource == '/survey-route/{urltoken}/{weborapp}':
            return dispatcher(handle_survey_route, event=event, context=context)
        if resource == '/survey-respond':
            return dispatcher(handle_survey_respond, event=event, context=context)
        if resource == '/public-upload/{original-filename}':
            return dispatcher(handle_public_upload, event=event, context=context)
        return {
            'statusCode': 200,
            'body': json.dumps('Hello!')
        }
    except:
        if DEBUGGING:
            import traceback
            import sys
            exc_contents = '\n'.join(traceback.format_exception(*sys.exc_info()))
            return respond(200, exc_contents, event)
        else:
            return respond(502, 'server error.')
    
    
def dispatcher(func, *, event, context):
    event = normalize_headers(event)
    env = event['requestContext']['stage']
    method = event['httpMethod']
    # 인증 등 필요하면 여기에서나 각 함수에서 처리하면 되겠다.
    return func(event=event, context=context)


def __handle_blueprint_cache_reader(event, context):
    env = event['requestContext']['stage']
    if env == 'prod':
        bucket_name = 'pocketsurvey.statistics.prod'
    else:
        bucket_name = 'pocketsurvey.statistics.test'
    import boto3
    from botocore.exceptions import ClientError
    survey_id = event['pathParameters']['survey-id']
    # 일단 버전은 0으로 고정해서 사용한다(최신)
    survey_version = 0
    remote_key = f'blueprint-cache/bp_cache_{survey_id}_0.json'
    remote_object = boto3.resource('s3').Object(bucket_name, remote_key)
    import io
    buf = io.BytesIO()
    try:
        remote_object.download_fileobj(buf)
    except ClientError:
        return respond(404, 'not found', event)
    buf.seek(0)
    loaded = json.load(buf)
    return loaded

def handle_blueprint_cache_reader(event, context):
    loaded = __handle_blueprint_cache_reader(event, context)
    return respond(200, loaded, event)
    
    
def send_request_metadata(env, metadata):
    if not metadata or len(metadata) == 0:
        return None

    import http.client
    import mimetypes
    conn = http.client.HTTPSConnection(
        'api.earlysloth.com'
        if env == 'prod' else
        'pktest.earlysloth.com'
    )
    payload = json.dumps(metadata)
    headers = {
      'Content-Type': 'application/json'
    }
    conn.request("POST", "/api/v1/websurvey/metadata/", payload, headers)
    res = conn.getresponse()
    data = res.read()
    return json.loads(data.decode('utf8'))['metadata_id']
        

def send_request_archive_survey(env, survey_id, phone_number):
    import re
    pn = re.sub(r'\D+', '', str(phone_number))
    if pn == '01000000000' or pn == '00000000000':
        return None
        
    import http.client
    import mimetypes
    conn = http.client.HTTPSConnection(
        'api.earlysloth.com'
        if env == 'prod' else
        'pktest.earlysloth.com'
    )
    payload = json.dumps({
        "phone_number": pn,
        "survey_id": survey_id,
    })
    headers = {
      'Content-Type': 'application/json'
    }
    conn.request("POST", "/api/v1/websurvey/archive-survey/", payload, headers)
    res = conn.getresponse()
    data = res.read()
    return None
    
    
def handle_survey_route(event, context):
    env = event['requestContext']['stage']
    url_token = event['pathParameters']['urltoken']
    front_env = event['pathParameters']['weborapp']
    # link.pocketsurvey.co.kr 링크의 item 가져오기
    import boto3
    table_name = 'pocketsurvey-short-links'  # short link는 한 테이블에서 같이 씀.
    table = boto3.resource('dynamodb').Table(table_name)
    try:
        link_item = table.get_item(
            Key={'urlToken': url_token, 'env': 'prod' if env == 'prod' else 'test'}
        )['Item']
    except KeyError:
        return respond(404, 'not found.', event)
        
    # is_shared가 False이고, 이미 저장 카운트가 1 이상이면 관련 정보를 주지 않는다.
    if (not link_item['webSurvey'].get('is_shared')) and ((link_item['webSurvey'].get('saveCounts') or 0) > 0):
        return respond(409, 'save limit exceeded.', event)
    
    # 이 함수가 할 일
    # 프론트 환경이 웹인 경우: 설문 정보, 메타데이터 등
    # 프론트 환경이 앱인 경우: 메타데이터를 등록하고, 카카오톡 앱을 여는 링크를 만들어 반환.
    if front_env == 'platform':
        return respond(200, link_item['webSurvey']['platform'], event)
    elif front_env == 'web':
        from uuid import uuid4
        # survey_id를 강제로 넣어준다.
        event['pathParameters']['survey-id'] = link_item['webSurvey']['survey_id']
        loaded = __handle_blueprint_cache_reader(event, context)
        # 추가로 넣을 정보:
        # uuid4 하나
        # web survey info 중
        # is_shared, url token
        loaded['webSurveyInfo'] = {
            'uuid': str(uuid4()),
            'isShared': link_item['webSurvey']['is_shared'],
            'metadata': link_item['webSurvey']['metadata'],
            'urlToken': url_token,
            'phoneNumber': link_item['webSurvey']['phone_number'],
        }
        return respond(200, loaded, event)
    elif front_env == 'app':
        # 메타데이터 생성
        # None일수도 있음.
        metadata_ivc_quoted = send_request_metadata(env, link_item['webSurvey']['metadata'])
        # 톡봇 링크 생성을 위해 전화번호가 실명이면 아카이빙 요청
        send_request_archive_survey(
            env, link_item['webSurvey']['survey_id'], link_item['webSurvey']['phone_number'], 
        )  # no retval
        # 톡봇 링크를 생성한다.
        from utils.ivc import to_invisible_code
        from urllib.parse import quote
        import re
        if link_item['webSurvey']['phone_number'] in ('01000000000', '00000000000'):
            pn = '00000000000'
        else:
            pn = link_item['webSurvey']['phone_number']
        ivc = quote(
            to_invisible_code(
                re.sub(r'\D+', '', str(pn)),
                link_item['webSurvey']['survey_id']
            )
        ) + (metadata_ivc_quoted if metadata_ivc_quoted else '')
        pf_id = quote(link_item['webSurvey']['pf_id'])
        statement = quote('참여하기') + ivc
        tblink = f'http://plus.kakao.com/talk/bot/@{pf_id}/{statement}'
        return respond(200, {'redirect_to': tblink}, event)
        
    return respond(200, None, event)


def handle_survey_respond(event, context):
    # POST로 JSON을 받는다.(urlToken, uuid, responseData)
    env = event['requestContext']['stage']
    body = json.loads(event['body'])
    url_token = body['urlToken']
    uuid = body['uuid']
    survey_id = body['surveyId']
    version = body['version']
    res_data = body['responseData']
    
    # link.pocketsurvey.co.kr 링크의 item 가져오기
    import boto3
    table_name = 'pocketsurvey-short-links'  # short link는 한 테이블에서 같이 씀.
    table = boto3.resource('dynamodb').Table(table_name)
    try:
        link_item_key = {'urlToken': url_token, 'env': 'prod' if env == 'prod' else 'test'}
        link_item = table.get_item(
            Key=link_item_key,
        )['Item']
    except KeyError:
        return respond(404, 'not found.', event)
        
    web_survey_info = link_item['webSurvey']
    wsi = web_survey_info
    is_shared = wsi.get('is_shared') or False
    registered_survey_id = wsi['survey_id']
    
    if survey_id != registered_survey_id:
        return respond(400, 'survey id mismatch.', event)
    
    # 내용 업로드 준비
    if is_shared:
        remote_filename = f'response__{survey_id}__{version}__shared__{url_token}__{uuid}.json'
    else:
        remote_filename = f'response__{survey_id}__{version}__private__{url_token}__{uuid}.json'
    
    remote_path = f'websurvey-responses/{survey_id}/'
    remote_key = remote_path + remote_filename
    
    bucket_name = (
        'pocketsurvey.statistics.prod'
        if env == 'prod' else
        'pocketsurvey.statistics.test'
    )
    bucket = boto3.resource('s3').Bucket(bucket_name)
    bucket.put_object(
        ACL='private',
        Body=event['body'].encode('utf8'),  # 받은거 그대로 저장한다.
        Key=remote_key
    )
    
    # 해당 link info에 응답 저장 횟수를 기록한다.
    # webSurvey.saveCounts 키가 없으면 0으로 초기화하고, 1씩 더한다.
    # 초기화
    from boto3.dynamodb.conditions import Attr
    from botocore.exceptions import ClientError
    from decimal import Decimal
    try:
        table.update_item(
            Key=link_item_key,
            ConditionExpression=~Attr('webSurvey.saveCounts').exists(),
            UpdateExpression='SET webSurvey.saveCounts = :val',
            ExpressionAttributeValues={
                ':val': Decimal('0')
            },
        )
    except ClientError as e:
        if e.response['Error']['Code'] == "ConditionalCheckFailedException":
            pass
        else:
            raise

    table.update_item(
        Key=link_item_key,
        UpdateExpression='SET webSurvey.saveCounts = webSurvey.saveCounts + :val',
        ExpressionAttributeValues={
            ':val': Decimal('1')
        }
    )
    
    
    # 해당 설문 응답이 등록되었다는것을 기록해서 통계를 트리거한다.
    if env == 'prod':
        table_name = 'pocketsurvey-analytics-modified-survey-uids-prod'
    else:
        table_name = 'pocketsurvey-analytics-modified-survey-uids-test'
    table = boto3.resource('dynamodb').Table(table_name)
    table.put_item(
        Item={
            'surveyId': survey_id,
            'uuid': uuid,
        }
    )
    
    return respond(200, 'done.', event)
    

def handle_public_upload(event, context):
    # 이 api는 이미지/비디오를 올리는 api다.
    # 이 api는 env 영향을 받지 않는다.
    if not event['isBase64Encoded']:
        return respond(400, 'type.', event)
    from urllib.parse import unquote
    import base64
    from io import BytesIO
     
    original_filename = unquote(event['pathParameters']['original-filename'])
    original_ext = original_filename.split('.')[-1]
    body_buf = BytesIO(base64.b64decode(event['body']))
    
    # s3에 파일 전송
    # api gateway의 한계로 인해 10메가바이트 이상은 들어오지 않을테니
    # 따로 검사나 리사이즈를 하지 않는다.
    import boto3
    from uuid import uuid4
    bucket = boto3.resource('s3').Bucket('pocketsurvey.earlysloth')
    remote_path = 'images/wu/'
    remote_key = remote_path + str(uuid4()) + '.' + original_ext
    bucket.upload_fileobj(
        Fileobj=body_buf,
        Key=remote_key,
        ExtraArgs={
            'ACL': 'public-read',
            'ContentType': event['headers']['content-type'],
            'Metadata': {
                'original_fn': base64.b64encode(str(original_filename).encode('utf8')).decode('utf8')
            }
        }
    )

    return respond(200, {
        'url': f'https://s3.ap-northeast-2.amazonaws.com/pocketsurvey.earlysloth/{remote_key}'
    }, event)
