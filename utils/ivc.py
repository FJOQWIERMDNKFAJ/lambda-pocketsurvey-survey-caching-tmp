# Invisible Character 전화번호 코드 변환 함수
import re
from uuid import UUID, uuid4

# put this at the start end the end of invisible string
ZERO = '\u200b'
ONE = '\ufeff'
SEP = '\u200d'
SEP2 = '\u200c'
to_num_str_dictionary = str.maketrans(f'{ZERO}{ONE}', '01')
to_ivc_dictionary = str.maketrans('01', f'{ZERO}{ONE}')
CLEANER = re.compile(r'[^\d]+')

# 설문번호, 전화번호 패턴
# 패턴 형식:
# SEPARATOR + 패턴버전 + SEPARATOR + 전화번호 + SEPARATOR + 서베이아이디 + SEPARATOR

PATTERN_VERSION = f'{ZERO}{ZERO}{ZERO}{ONE}'
PATTERN_FINDER = re.compile(
    f'{SEP}{PATTERN_VERSION}{SEP}([{ZERO}{ONE}]+){SEP}([{ZERO}{ONE}]+){SEP}')
PATTERN_FINDER2 = re.compile(
    f'{SEP2}{PATTERN_VERSION}{SEP2}([{ZERO}{ONE}]+){SEP2}([{ZERO}{ONE}]+){SEP2}')

# 메타데이터 타입, 구분자 패턴
# SEPARATOR + 패턴버전 + SEPARATOR + 메타데이터 타입번호
# + SEPARATOR + 메타데이터 레코드 구분자 + SEPARATOR
PATTERN_VERSION_META = f'{ZERO}{ZERO}{ONE}{ZERO}'
PATTERN_FINDER_META = re.compile(
    f'{SEP2}{PATTERN_VERSION_META}{SEP2}([{ZERO}{ONE}]+){SEP2}([{ZERO}{ONE}]+){SEP2}'
)

# UUID 생성 제한
UUID_MIN = 0
UUID_MAX = int('1' * 128, 2)  # 340282366920938463463374607431768211455

# 문의하기 포스트 번호
PATTERN_VERSION_NAVER_POST = f'{ZERO}{ZERO}{ONE}{ONE}'
PATTERN_FINDER_NAVER_POST = re.compile(
    f'{SEP2}{PATTERN_VERSION_NAVER_POST}{SEP2}([{ZERO}{ONE}]+){SEP2}([{ZERO}{ONE}]+){SEP2}'
)

# 익명 설문 초대장 메시지 생성 트리거
PATTERN_VERSION_ANON_INVITATION = f'{ZERO}{ONE}{ZERO}{ZERO}'
PATTERN_FINDER_ANON_INVITATION = re.compile(
    f'{SEP2}{PATTERN_VERSION_ANON_INVITATION}{SEP2}([{ZERO}{ONE}]+){SEP2}([{ZERO}{ONE}]+){SEP2}'
)

# Single-Pattern IVC: 익명 설문 QR코드에 사용할 짧은 ivc
elements = [
    '\u200b',
    '\u200c',
    '\u200d',
    '\u200e',
    '\u200f',
    '\u202c',
    '\ufeff',
    '\u2060',
    '\u2063',
    '\u180e'
]

PATTERN_VERSION_DECIMAL = f'{ZERO}{ONE}{ZERO}{ONE}'
PATTERN_ELEMENTS = '|'.join(elements)
PATTERN_FINDER_DECIMAL = re.compile(f'{SEP2}{PATTERN_VERSION_DECIMAL}{SEP2}(?P<number>(?:{PATTERN_ELEMENTS})+){SEP2}')


def __to_ivc(num_str: str) -> str:
    cleaned = CLEANER.sub('', num_str)
    converted = ''.join((f'{int(i):04b}' for i in cleaned))
    translated = converted.translate(to_ivc_dictionary)
    return translated


def __to_zero_one(code: str) -> str:
    translated = code.translate(to_num_str_dictionary)
    points = [translated[i:i+4] for i in range(0, len(translated), 4)]
    result = ''.join((str(int(i, 2)) for i in points))
    return result


def __find_pattern(text: str):
    match = PATTERN_FINDER.search(text)
    match2 = PATTERN_FINDER2.search(text)
    if match is None and match2 is None:
        return False
    elif match is not None:
        return match.group(1), match.group(2)
    elif match2 is not None:
        return match2.group(1), match2.group(2)


def __find_pattern_meta(text: str):
    match = PATTERN_FINDER_META.search(text)
    if match is not None:
        return match.group(1), match.group(2)
    else:
        return None


def __find_pattern_naver_post(text: str):
    match = PATTERN_FINDER_NAVER_POST.search(text)
    if match is not None:
        return match.group(1), match.group(2)
    else:
        return None

def __find_pattern_anon_inv(text):
    match = PATTERN_FINDER_ANON_INVITATION.search(text)
    if match is not None:
        return match.group(1), match.group(2)
    else:
        return None

# public api
def to_invisible_code(phone_number, survey_id):
    """전화번호 문자열과 서베이 아이디 문자열을 받아서 ivc code로 바꿔준다"""
    phone_number_ivc = __to_ivc(phone_number)
    survey_id_ivc = __to_ivc(survey_id)
    return f'{SEP2}{PATTERN_VERSION}{SEP2}{phone_number_ivc}{SEP2}{survey_id_ivc}{SEP2}'


def get_phone_number_and_survey_id(text: str):
    """패턴을 찾아서 전화번호와 서베이 아이디를 튜플로 반환"""
    found = __find_pattern(text)
    if not found:
        # shorter ivc 시도
        return decode_survey_id_decimal(text)
    else:
        return __to_zero_one(found[0]), __to_zero_one(found[1])


def encode_meta(meta_type_number, meta_uid_number):
    meta_type_ivc = __to_ivc(str(meta_type_number))
    meta_uid_ivc = __to_ivc(str(meta_uid_number))
    return f'{SEP2}{PATTERN_VERSION_META}{SEP2}{meta_type_ivc}{SEP2}{meta_uid_ivc}{SEP2}'


def decode_meta(text: str):
    found = __find_pattern_meta(text)
    if not found:
        return False, False
    else:
        return __to_zero_one(found[0]), __to_zero_one(found[1])


def int_to_uuid(number: int) -> UUID:
    number = int(number)
    assert UUID_MIN <= number <= UUID_MAX
    uid = UUID(int=number)
    return uid


def uuid_to_int(uuid: UUID) -> int:
    return uuid.int


def create_uuid() -> UUID:
    return uuid4()


def create_uuid_as_int() -> int:
    return create_uuid().int


def encode_post(postnum, referrer_num):
    referrer_num_ivc = __to_ivc(str(referrer_num))
    post_ivc = __to_ivc(str(postnum))
    return f'{SEP2}{PATTERN_VERSION_NAVER_POST}{SEP2}{post_ivc}{SEP2}{referrer_num_ivc}{SEP2}'


def decode_post(text: str):
    # ContactTrackingItem.pk를 읽어낸다.
    found = __find_pattern_naver_post(text)
    if not found:
        return False, False
    else:
        return __to_zero_one(found[0]), __to_zero_one(found[1])

# 익명 설문 트리거
def encode_anon_inv(proxy_model_id):
    proxy_model_id_ivc = __to_ivc(str(proxy_model_id))
    dumb_ivc = __to_ivc('175')
    return f'{SEP2}{PATTERN_VERSION_ANON_INVITATION}{SEP2}{proxy_model_id_ivc}{SEP2}{dumb_ivc}{SEP2}'

def decode_anon_inv(text):
    found = __find_pattern_anon_inv(text)
    if not found:
        return False, False
    else:
        return __to_zero_one(found[0]), __to_zero_one(found[1])


def encode_survey_id_decimal(survey_id: str):
    element_selected = ''.join([
        elements[int(idx)] for idx in str(survey_id)
    ])
    ivc_dec = (
        f'{SEP2}{PATTERN_VERSION_DECIMAL}{SEP2}{element_selected}{SEP2}'
    )
    return ivc_dec


def decode_survey_id_decimal(pattern: str):
    m = PATTERN_FINDER_DECIMAL.search(pattern)
    if m:
        found = m.group('number')
        original = ''.join([
            str(elements.index(item)) for item in found
        ])
        return '00000000000', original
    else:
        return False, False


if __name__ == '__main__':
    phone_number = '01012345678'
    survey_id = '987654'
    coded = to_invisible_code(phone_number, survey_id)
    print(repr(coded))
    test_string = f'알림톡 테스트\n이름: 김늘보{coded}\n행사명: 테스트'
    print(test_string)
    print(repr(test_string))
    back = get_phone_number_and_survey_id(test_string)
    print(repr(back))
