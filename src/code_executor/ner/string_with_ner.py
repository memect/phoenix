#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
带 NER 信息的字符串类

提供 StringWithNER 类用于处理带有命名实体识别信息的字符串。
"""

import copy
from typing import Union, Dict, List


class StringWithNER:
    """带 NER 信息的字符串类"""

    name = 'BORN_NER'

    def __init__(self, content, position_entities: Union[Dict, List]):
        self.content = content

        entities_items = None
        if isinstance(position_entities, dict):
            entities_items = [
                self.new_entity(content, start, end, ner_type)
                for (start, end), ner_type in position_entities.items()
            ]
        elif isinstance(position_entities, list):
            entities_items = position_entities

        entity_dict: Dict = {}
        for idx, item in enumerate(entities_items):
            key = '{type}_{start}_{end}'.format(**item)

            if key in entity_dict:
                entity_dict[key]['attr'].update(item['attr'])
                entity_dict[key]['match_patterns'] = list(set(entity_dict[key]['match_patterns'] + item['match_patterns']))
            else:
                entity_dict[key] = item

        self.entities_items = list(sorted(entity_dict.values(), key=lambda x: (x['start'], x['end'])))

        self._records = {
            '{type}_{start}_{end}'.format(**item): index
            for index, item in enumerate(self.entities_items)
        }

    def __repr__(self): 
        return str(self.content)

    def __len__(self): 
        return len(self.content)

    def __contains__(self, s): 
        return str(s) in str(self.content)

    def __getitem__(self, i): 
        return self.content.__getitem__(i)

    def count(self, x, __start=None, __end=None): 
        return self.content.count(x, __start, __end)

    @classmethod
    def new_entity(cls, text, start, end, ner_type, rec_name=None, match_pattern=None):
        """创建新的实体"""
        rec_name = rec_name if rec_name else cls.name
        match_patterns = [match_pattern] if match_pattern else []
        return {
            'name': text[start:end],
            'start': start,
            'recognizer': rec_name,
            'normalized': text[start:end],
            'type': ner_type,
            'end': end,
            'probabilities`': {
                'pro': 1
            },
            'attr': {},
            'match_patterns': match_patterns,
        }

    def get_entities(self): 
        return copy.copy(self.entities_items)

    def get_entity_types(self):
        return set(item['type'] for item in self.entities_items)

    @classmethod
    def merge(cls, ner_strings):
        """合并多个 NER 字符串"""
        if len(ner_strings) == 1:
            return ner_strings[0]

        content = ner_strings[0].content
        entities_items = ner_strings[0].entities_items[:]
        for ner_string in ner_strings[1:]:
            if ner_string.content != content:
                raise ValueError('{}merge的只能是content相同的string: {} / {}'.format(cls, content, ner_string.content))

            entities_items.extend(ner_string.entities_items)

        # 过滤重复的实体
        entities_items = list({id(item): item for item in entities_items}.values())

        return cls(content, entities_items)

    def _get_index(self, target_item):
        return self._records[target_item.key()]

    def change_ner_type(self, items, suffix):
        """更改 NER 类型"""
        for item in items:
            index = self._get_index(item)
            self.entities_items[index]['type'] = self.entities_items[index]['type'] + suffix

    def recover_ner_type(self, items, suffix):
        """恢复 NER 类型"""
        for item in items:
            index = self._get_index(item)
            self.entities_items[index]['type'] = self.entities_items[index]['type'][:-len(suffix)]

    @classmethod
    def merge_entities(cls, entities, new_entities):
        """合并实体列表"""
        entity_indices = {}
        for idx, item in enumerate(entities):
            key = '{type}_{start}_{end}'.format(**item)
            entity_indices[key] = idx

        for new_entity in new_entities:
            this_key = '{type}_{start}_{end}'.format(**new_entity)
            if this_key in entity_indices:
                idx = entity_indices[this_key]
                entities[idx]['match_patterns'] = entities[idx]['match_patterns'] + new_entity['match_patterns']
            else:
                entities.append(new_entity)
                entity_indices[this_key] = len(entities)

    def jsonify(self, **kwargs): 
        return self.content
