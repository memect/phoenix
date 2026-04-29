#!/usr/bin/env python
# encoding: utf-8
"""
NER 正则匹配模块

在正则匹配中结合 NER 信息。
"""

import re
import copy
from collections import defaultdict

from .string_with_ner import StringWithNER


def str_join(sep, iterable):
    return sep.join(str(item) for item in iterable)


START_TAGS = '◤◣◐↑►⇒≤ㅏ'
END_TAGS = '◥◢◑↓◄⇐≥ㅓ'


class DictRecognizer:
    """字典识别器"""
    name = 'DOCUMENT_DICT'

    def __init__(self, dicts):
        self.dicts = dicts
        self.ner_patterns = []
        for ner_type, words in dicts.items():
            if words:
                all_word = str_join('|', [re.escape(word) for word in sorted(words, reverse=True)])
                pattern = re.compile('(?P<{}>{})'.format(ner_type, all_word))
                self.ner_patterns.append(pattern)

    def recognize(self, text):
        ret = []
        for ner_pattern in self.ner_patterns:
            matches = list(ner_pattern.finditer(text))
            for match in matches:
                regs = match.regs
                group_index = match.re.groupindex
                for ner_type, index in group_index.items():
                    start, end = regs[index]
                    ret.append(StringWithNER.new_entity(text, start, end, ner_type))
        return ret

    def __copy__(self):
        return DictRecognizer(copy.deepcopy(self.dicts))

    def __str__(self):
        return str(sorted(self.dicts.items()))


class Match:
    """匹配结果类"""

    def __init__(self, re_match=None, tags=None, new2old_mapping=None):
        if re_match is None:
            return

        tag_chars = []
        for ner_type in tags:
            for char in tags[ner_type].values():
                tag_chars.append(char)
        tag_str = '[{}]'.format(str_join('', tag_chars))
        self.__tag_str = tag_str

        self.re = re_match.re
        self.regs = tuple(
            (new2old_mapping[s], new2old_mapping[e])
            for s, e in re_match.regs
        )
        self._span = tuple(new2old_mapping[i] for i in re_match.span())
        self._groupdict = {
            k: (re.sub(tag_str, '', v) if v else v)
            for k, v in re_match.groupdict().items()
        }
        self.string = re.sub(tag_str, '', re_match.string)
        self.re_match = re_match

    def groupdict(self):
        return self._groupdict
    
    def group(self, index):
        v = self.re_match.group(index)
        return re.sub(self.__tag_str, '', v) if v else v

    def span(self):
        return self._span

    @classmethod
    def to_json(cls, match):
        if match is None:
            return None
        return {
            'regs': match.regs,
            '_groupdict': match.groupdict(),
            'string': match.string,
            'groupindex': dict(match.re.groupindex.items()),
        }

    @classmethod
    def from_json(cls, json):
        if json is None:
            return None
        json = copy.deepcopy(json)
        ret = cls()
        ret.regs = json['regs']
        ret._groupdict = json['_groupdict']
        ret.string = json['string']
        ret.re = cls()
        ret.re.groupindex = json['groupindex']


class TagString:
    """标签字符串类"""

    def __init__(self, text, tags, ner_results):

        text = text.content if isinstance(text, StringWithNER) else text

        self.tags = tags

        point_tags = self._get_point_tags(ner_results)

        split_points = {0, len(text) + 1, *{point for point, _, _ in point_tags}}
        split_points = list(sorted(split_points))

        mapping = [(i, 3) for i in range(len(text) + 1)]
        for position, _, tag_type in point_tags:
            tag_sort_num = 1 if tag_type == 'end' else 2
            mapping.append((position, tag_sort_num))
        mapping = sorted(mapping)
        self.new2old_mapping = {new_idx: old_idx for new_idx, (old_idx, _) in enumerate(mapping)}
        self.new2old_mapping[-1] = -1

        text_parts = [
            [(s, e), text[s:e]]
            for s, e in zip(split_points[:-1], split_points[1:])
        ]

        for point, ner_type, tag_type in point_tags:
            sort_number = -2 if tag_type == 'end' else -1
            text_parts.append([(point, sort_number), tags[ner_type][tag_type]])

        self.text = str_join('', [item[1] for item in sorted(text_parts)])

    def _get_point_tags(self, ner_results):

        position_ner_types = defaultdict(set)
        for ner_result in ner_results:
            start = ner_result['start']
            end = ner_result['end']
            ner_type = ner_result['type']
            position_ner_types[(start, end)].add(ner_type)

        point_tags = set()

        # 处理带'&'的tag
        for target_type in self.tags:
            if '&' in target_type:
                target_types = set(target_type.split('&'))
                for (start, end), types in position_ner_types.items():
                    if target_types.issubset(types):
                        point_tags.add((start, target_type, 'start'))
                        point_tags.add((end, target_type, 'end'))

        # 处理不带'&'的tag
        for ner_result in ner_results:
            start = ner_result['start']
            end = ner_result['end']
            ner_type = ner_result['type']
            for target_type in self.tags:
                if '&' not in target_type and self._belongs(ner_type, target_type, ner_result):
                    point_tags.add((start, target_type, 'start'))
                    point_tags.add((end, target_type, 'end'))

        return point_tags

    @classmethod
    def _belongs(cls, this_type, target_type, ner_result):
        """
        判断this_type属不属于target_type
        target_type可能是带条件的ner类型, 比如：'ORG|is_holder=True'
        其中'ORG'是ner类型，'is_holder=True'是条件
        'is_holder'属性存放在ner_result['attr']中
        """
        if this_type == target_type:
            return True
        if not target_type.startswith(this_type + '|'):
            return False
        condition = target_type[len(this_type)+1:]
        return cls._eval(condition, ner_result['attr'])

    @classmethod
    def _eval(cls, condition, params):
        """
        判断params是否满足condition条件
        :param condition: 字符串，判断条件
        :param params: 属性
        """
        if not condition:
            return True

        # 设置params里的属性为局部变量
        local_values = locals()
        for k, v in params.items():
            local_values[k] = v

        continue_eval = True
        while continue_eval:
            try:
                continue_eval = False
                result = eval(condition)
            except NameError as e:
                # 可能会没有对应的属性，此时设置对应的变量为None
                pattern = re.compile("name '(?P<var_name>[a-z_A-Z]*)' is not defined")
                match = pattern.search(str(e))
                if match:
                    var_name = match.groupdict()['var_name']
                    local_values[var_name] = None
                    continue_eval = True

        return result

    def get_new_match(self, match):
        if match is None:
            return None
        return Match(match, self.tags, self.new2old_mapping)


class NERPattern:
    """NER 正则模式类"""

    parse_pattern = re.compile(r'{@<(?P<type>[^>#]*)[^>]*>(?P<type_pattern>[^@]*)@}')
    fix_ner_types = ['ORG', 'PER']
    recognizer_priority = [
        StringWithNER.name, 
        DictRecognizer.name, 
        'MemeParser', 
        'LSTM_NER', 
        'CRF_NER', 
        'DICT_NER'
    ]

    def __init__(self, pattern, flags, ner_api):

        if pattern is None:
            return

        self.pattern = pattern
        self.flags = flags
        self.dict_recognizer = None
        self.filter_rules = self._init_filter_rules()
        self.ner_api = ner_api

        matches = list(self.parse_pattern.finditer(pattern))

        split_points = {0, len(pattern)}
        ner_types = {}
        for match in matches:
            split_points = split_points.union(set(match.span()))
            ner_types[match.span()] = match.groupdict()

        split_points = sorted(split_points)
        pattern_parts = {
            (s, e): ner_types[(s, e)] if (s, e) in ner_types else pattern[s:e]
            for s, e in zip(split_points[:-1], split_points[1:])
        }
        pattern_parts = sorted(pattern_parts.items())
        self._pattern_parts = [pattern_part[1] for pattern_part in pattern_parts]
        self.__pure_regex_pattern = self._get_pure_regex_str()

    @classmethod
    def _init_filter_rules(cls):
        return {
            ner_type: [
                # 过滤掉只有单边括号的识别结果
                re.compile('^[^（(]*[)）]'),
                re.compile('[（(][^)）]*$'),
                re.compile('[，《》]'),
                re.compile(r'^[,\d]+$'),
                re.compile(r'\d,\d*$'),
                re.compile('(控股股东|出质人|质权人|截止|直接)'),
                re.compile('^股东'),
                re.compile(r'^\d{4}.\d{1,2}.\d{1,2}$'),
            ]
            for ner_type in ['ORG', 'PER']
        }

    def __copy__(self):
        ret = NERPattern(self.pattern, self.flags, self.ner_api)
        ret.dict_recognizer = copy.copy(self.dict_recognizer)
        ret.filter_rules = {ner_type: copy.copy(rules) for ner_type, rules in self.filter_rules.items()}
        return ret

    def __str__(self):
        ret = self.pattern + str(self.flags) + str(self.dict_recognizer) + str(self.filter_rules)
        return ret

    def set_dicts_and_filter_rules(self, dicts, filter_rules):
        if not dicts and not filter_rules:
            return self

        ret = NERPattern(self.pattern, self.flags, self.ner_api)
        if dicts:
            ret.dict_recognizer = DictRecognizer(dicts)

        if filter_rules:
            for ner_type, rules in filter_rules.items():
                ret.filter_rules[ner_type].extend(self._format_rules(rules))

        return ret

    @classmethod
    def _format_rules(cls, rules):

        str_rules, pattern_rules = [], []
        for rule in rules:
            if isinstance(rule, str):
                str_rules.append(rule)
            elif isinstance(rule, type(re.compile(''))):
                pattern_rules.append(rule)
            else:
                raise ValueError('only accept str or regex filter rule!')

        if str_rules:
            pattern_rules.append(
                re.compile('^({})$'.format(str_join('|', str_rules)))
            )

        return pattern_rules

    def _get_ner_result(self, text):
        """
        对NER的结果做一些修正
        如果识别出来的结果在位置上有重叠的部分，那么按照rec
        """
        def filter_result(inputs):
            outputs = []
            for input_ in inputs:
                for false_pattern in self.filter_rules.get(input_['type'], []):
                    if false_pattern.search(input_['name']):
                        break
                else:
                    outputs.append(input_)
            return outputs

        def get_priority(item_in):
            return self.recognizer_priority.index(item_in['item']['recognizer'])

        def select(before, after):

            if None in [before['item'], after['item']]:
                return [before, after]

            if before['item']['type'] not in self.fix_ner_types or after['item']['type'] not in self.fix_ner_types:
                return [before, after]

            # before和after没有重叠
            if before['end'] <= after['start']:
                return [before, after]

            # before包含after
            if before['end'] >= after['end']:
                if re.search('(公司|合伙企业)$', text[before['start']:before['end']]):
                    return [before]

            # after包含before
            if before['start'] == after['start'] and before['end'] <= after['end']:
                if re.search('(公司|合伙企业)$', text[after['start']:after['end']]):
                    return [after]

            if get_priority(before) > get_priority(after):
                return [after]
            else:
                return [before]

        ner_results = []
        if isinstance(text, StringWithNER):
            ner_results.extend(text.get_entities())
            text = text.content

        ner_results.extend(self.ner_api(text))
        if self.dict_recognizer:
            ner_results.extend(self.dict_recognizer.recognize(text))
        ner_results = filter_result(ner_results)

        start_end_items = [{
            'start': -1, 'end': -1, 'item': None,  # 用于比较
        }, {
            'start': len(text) + 1, 'end': len(text) + 1, 'item': None,  # 用于比较
        }]
        for item in ner_results:
            item['end'] = item['end'] - 1 if item['recognizer'] == 'LSTM_NER' else item['end']
            start_end_items.append({
                'start': item['start'], 'end': item['end'], 'item': item
            })

        start_end_items = sorted(start_end_items, key=lambda x: (x['start'], x['end']))

        result_indices = []
        for idx, item in enumerate(start_end_items[:-1]):
            if idx == 0:
                continue

            # 跟前后两个item做对比
            before_item = start_end_items[idx-1]
            after_item = start_end_items[idx+1]

            if item in select(before_item, item) and item in select(item, after_item):
                result_indices.append(idx)

        return [start_end_items[idx]['item'] for idx in result_indices]

    def search(self, text):
        """搜索第一个匹配"""
        if not re.search(self.__pure_regex_pattern, text):
            return None

        ner_results = self._get_ner_result(text)

        tags = self._get_tags(text)

        tag_string = TagString(text, tags, ner_results)
        pattern_str = self._get_pattern_str(tags)

        match = re.search(pattern_str, tag_string.text)
        if match:
            return tag_string.get_new_match(match)

    def finditer(self, text):
        """查找所有匹配"""
        if not list(re.finditer(self.__pure_regex_pattern, text)):
            return []

        ner_results = self._get_ner_result(text)

        tags = self._get_tags(text)

        tag_string = TagString(text, tags, ner_results)
        pattern_str = self._get_pattern_str(tags)

        matches = re.finditer(pattern_str, tag_string.text)

        ret = [tag_string.get_new_match(match) for match in matches]
        return ret

    def split(self, text):
        """分割文本"""
        ner_results = self._get_ner_result(text)

        tags = self._get_tags(text)

        tag_string = TagString(text, tags, ner_results)

        pattern_str = self._get_pattern_str(tags)

        parts = re.split(pattern_str, tag_string.text)

        return parts

    def _get_tags(self, text):
        text = text.content if isinstance(text, StringWithNER) else text

        ner_types = set(part['type'] for part in self._pattern_parts if isinstance(part, dict))
        for part in self._pattern_parts:
            if isinstance(part, dict):
                ner_types.add(part['type'])
            else:  # part is string
                bracket_str_matches = re.compile(r'\[(?P<text>[^\[\]]+)\]').finditer(part)
                for bracket_str_match in bracket_str_matches:
                    bracket_str = bracket_str_match.groupdict()['text']
                    ner_types.update(
                        match.groupdict()['ner_type']
                        for match in re.compile('@<(?P<ner_type>[^<>]+)>').finditer(bracket_str)
                    )

        tags = [
            (start, end) for start, end in zip(START_TAGS, END_TAGS)
            if start not in text and end not in text
        ]

        if len(tags) < len(ner_types):
            raise ValueError('tag的数量不够ner类型的数量：\ntag【{}】\nner类型【{}】'.format(tags, ner_types))

        ret = {}
        for ner_type, (start, end) in zip(ner_types, tags):
            ret[ner_type] = {'start': start, 'end': end}
        return ret

    def _get_pattern_str(self, tags):

        pattern_str = ''
        for part in self._pattern_parts:
            if isinstance(part, str):
                for ner_type, tag in tags.items():
                    part = part.replace('@<' + ner_type + '>', tag['start'])
                pattern_str += part
            else:
                ner_type, type_pattern = part['type'], part['type_pattern']
                start_tag = tags[ner_type]['start']
                end_tag = tags[ner_type]['end']

                # 把.*替换成[^end_tag]*, 把[^，]*替换成[^，end_tag]*
                type_pattern = re.sub(r']', '{}]'.format(end_tag), type_pattern)
                type_pattern = re.sub(r'(?<!\\)\.', '[^{}]'.format(end_tag), type_pattern)

                pattern_str += start_tag + type_pattern + end_tag

        return pattern_str
    
    def _get_pure_regex_str(self):

        pattern_str = ''
        for part in self._pattern_parts:
            if isinstance(part, str):
                part = part.replace(r'@<[^>]*>', '')
                pattern_str += part
            else:
                ner_type, type_pattern = part['type'], part['type_pattern']

                pattern_str += type_pattern

        return pattern_str
