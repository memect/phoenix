#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NER API 模块

提供 NER 服务的 API 接口。
"""

import json
from typing import Any
import requests
import logging

logger = logging.getLogger(__name__)


class NerApi:
    """NER API 类"""

    default_ner_ret = [
        {
            'ner_result': [],
            'ori_text': ''
        }
    ]

    logger = logger

    def __init__(self, settings) -> None:
        self.using_ner = settings.get('is_use', False)
        self.ner_url = settings.get('url', '')
        self.timeout = settings.get('timeout', 3.5)
    
    def __call__(self, content):
        """调用 NER 服务
        
        Args:
            content: 需要进行实体识别的文本
            
        Returns:
            NER 识别结果列表
        """
        if not self.using_ner:
            return self.default_ner_ret
        if not self.ner_url:
            self.logger.warning('NER service 请求链接为空')
            return self.default_ner_ret

        content = str(content)
        self.logger.debug('get_ner: {}'.format(content))
        headers = {'Content-Type': 'application/json'}
        try:
            response = requests.get(self.ner_url, params={'data': content}).json()
        except requests.exceptions.ConnectionError as err:
            self.logger.warning('cant reach NER service: %s', err)
            response = self.default_ner_ret
        except Exception as e:
            self.logger.warning(e)
            self.logger.warning('Failed to get ner result\n'
                        'url: %s?text=%s\n', self.ner_url, content)
            response = self.default_ner_ret
        ret = []
        for item in json.loads(response['Result'])['ner_result']:
            chars = item[0]
            type_ = item[1]
            start, end = item[2]
            ret.append({
                'type': type_,
                'name': chars,
                'end': end,
                'start': start,
                'recognizer': 'MemeParser'
            })

        return ret
