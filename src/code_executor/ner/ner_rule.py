#!/usr/bin/env python
# encoding: utf-8
"""
NER 规则模块

提供 NER 规则处理功能。
"""

import re

from .string_with_ner import StringWithNER


class NERRule:
    """
    设置实体属性，或新建实体
    """

    suffix = '_this'

    def __init__(self, rule_pattern, name=''):

        self._target_ner_type = None
        self._action = None
        self._rule_pattern = None
        self._name = name

        self._set_fields(rule_pattern)

    def __repr__(self):
        return self._name

    @classmethod
    def convert_pattern(cls, match, org_pattern):
        """
        给org_pattern中的ner_type添加cls.suffix
        还原org_pattern（'→' --> '{@', '←' --> '@}'）
        """
        group_idx = match.re.groupindex['ner_name']
        _, end = match.regs[group_idx]
        ret = org_pattern[:end] + cls.suffix + org_pattern[end:]
        return ret.replace('️→', '{@').replace('←', '@}')

    def _set_fields(self, rule_pattern):

        if re.compile(r'\(\?P<.*\(\?P<').search(rule_pattern):
            self._action = 'new_ner'  # 将命名组提取为新的实体，返回的action为'new_ner'
            self._rule_pattern = re.compile(rule_pattern)
            return

        # 在re_manager中会对有ner的正则做处理，这里要防止这种处理
        rule_pattern = rule_pattern.replace('{@', '️→').replace('@}', '←')

        # match '(?P<name>→<ner_name>.*←)'
        target_ner_pattern = re.compile(r'\(\?P<[^>]*>[^→←]*→<(?P<ner_name>[^→←|]*)[^→←]*>[^→←]*←[^→←]*\)')
        match = target_ner_pattern.search(rule_pattern)
        if match:
            self._target_ner_type = match.groupdict()['ner_name']
            self._action = 'new_ner'  # 将命名组提取为新的实体，返回的action为'new_ner'
            self._rule_pattern = re.compile(self.convert_pattern(match, rule_pattern))
            return

        # match '(?P<name>.*)'
        if re.compile(r'\(\?P<.*?>.*\)').search(rule_pattern):
            rule_pattern = rule_pattern.replace('️→', '{@').replace('←', '@}')
            self._action = 'new_ner'  # 将命名组提取为新的实体，返回的action为'new_ner'
            self._rule_pattern = re.compile(rule_pattern)
            return

        # match '(→<ner_name|attr1==True#attr2=False>.*←)' or '(→<ner_name|#attr=False>.*←)'
        # 设置实体属性, 返回的action为'#'后面的字符串，如'attr=False'
        target_ner_pattern = re.compile(r'→<(?P<ner_name>[^→←|]*)\|[^→←|#]*#(?P<action>[^→←|#]+)>.*←')
        matches = list(target_ner_pattern.finditer(rule_pattern))
        assert matches, 'not found target ner type'
        assert len(matches) <= 1, 'not support more than one named group'

        match = matches[0]
        groupdict = match.groupdict()
        self._target_ner_type = groupdict['ner_name']
        self._action = groupdict['action']  # 将命名组提取为新的实体，返回的action为'new_ner'
        self._rule_pattern = re.compile(self.convert_pattern(match, rule_pattern))

    def exec(self):
        """
        执行设置属性的动作，将设置的属性返回
        """
        exec(self._action)
        return locals()

    def _new_entities_from_match(self, text, match):

        ret = []
        for group_name in match.groupdict().keys():
            group_idx = match.re.groupindex[group_name]
            start, end = match.regs[group_idx]
            new_entity = StringWithNER.new_entity(text, start, end, group_name, match_pattern=self._name)
            ret.append(new_entity)

        return ret

    def extract_entity(self, ner_string):
        """
        为ner_string添加新的实体，或设置实体属性
        """

        text = ner_string.content
        entities = ner_string.get_entities()

        # 不涉及实体的正则
        if self._target_ner_type is None:
            matches = self._rule_pattern.finditer(ner_string)
            if not matches:
                return ner_string

            for match in matches:
                new_entities = self._new_entities_from_match(text, match)
                StringWithNER.merge_entities(entities, new_entities)

            return StringWithNER(text, entities)

        update_attrs = {}
        entities = sorted(entities, key=lambda x: x['start'])
        for idx, entity in enumerate(entities[:]):
            # 对每一个实体进行规则匹配，为了保证是对当前实体进行匹配
            # 会将实体类型加上self.suffix后缀
            # 对应的规则正则也会加上self.suffix后缀

            if entity['type'] != self._target_ner_type:
                continue

            entity['type'] = entity['type'] + self.suffix  # 暂时更改实体类型，后面会恢复

            new_string = StringWithNER(text, entities)
            match = self._rule_pattern.search(new_string)
            if match:
                if self._action == 'new_ner':  # 通过正则的命名组添加新的实体
                    new_entities = self._new_entities_from_match(text, match)
                    StringWithNER.merge_entities(entities, new_entities)
                else:  # 为已有的实体添加属性
                    update_attrs[idx] = self.exec()

            entity['type'] = entity['type'][:-len(self.suffix)]  # 恢复实体类型

        # 设置属性
        for idx, attrs in update_attrs.items():
            attrs.pop('self')
            entities[idx]['attr'].update(attrs)
            entities[idx]['match_patterns'].append(self._name)

        return StringWithNER(text, entities)
