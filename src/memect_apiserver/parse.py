import os.path
import json
import hashlib
from functools import wraps
from contextlib import redirect_stdout

from memect_apiserver.apiserver import Api


BASE_URL = 'http://localhost:6111/api'
CACHE_DIR = '/tmp/memect_apiserver/cache/'

def set_cache_dir(cache_dir: str):
    global CACHE_DIR
    CACHE_DIR = cache_dir

def cache_json(fn):
    @wraps(fn)
    def wrapper(byte_data, *args, **kwargs):
        md5 = hashlib.md5(byte_data).hexdigest()
        cache_dir = os.path.join(CACHE_DIR, md5)
        docjson_cache_path = os.path.join(cache_dir, 'docjson.json')
        if os.path.exists(docjson_cache_path):
            with open(docjson_cache_path, 'rb') as file:
                return json.load(file)
        else:
            docjson = fn(byte_data, *args, **kwargs)
            os.makedirs(cache_dir, exist_ok=True)
            with open(docjson_cache_path, 'w') as file:
                json.dump(docjson, file, ensure_ascii=False)
            return docjson
    return wrapper


@cache_json
def get_docjson(binary_data, base_url='http://localhost:6111/api', params=None):
    apiserver = Api(base=base_url)
    if params is None:
        params = {
            'ocr': 'auto',
            'ocr-text': 'baidu',
            'mode': '3',
            'textlines': 'true',
            'format': '4',
            'merge-table': 'true'
        }
    with redirect_stdout(open(os.devnull, 'w')):
        try:
            # 获得json结果，可以使用同步或者异步的方式
            docjson = apiserver.invoke('pdf2doc', binary_data, params=params, async_=False)
        except Exception as e:
            raise Exception('调用apiserver失败')
    return docjson

