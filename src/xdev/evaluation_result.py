"""
xdev 评估结果封装
"""

import json
import math
from pathlib import Path
from typing import Any, Optional

from evaluator.evaluators.object.models import ObjectEvaluationResult, RecordDetail as ObjectRecordDetail, FieldDetail
from evaluator.evaluators.list_of_objects.models import ListOfObjectsEvaluationResult, RecordDetail as ListRecordDetail, MatchedObjectDetail
from evaluator.core.evaluation_models import FullExtractedResult, FullStandard, RuntimeInfo, ExceptionInfo
from evaluator.core.schema import Schema, FieldType


class SafeJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if obj is ...:
            return {'__special__': 'ellipsis'}
        if isinstance(obj, set):
            return {'__special__': 'set', 'value': list(obj)}
        if isinstance(obj, bytes):
            import base64
            return {'__special__': 'bytes', 'value': base64.b64encode(obj).decode('ascii')}
        if isinstance(obj, Path):
            return str(obj)
        return super().default(obj)

    def encode(self, obj):
        return super().encode(self._convert_floats(obj))

    def _convert_floats(self, obj):
        if isinstance(obj, float):
            if math.isinf(obj):
                return {'__special__': 'inf' if obj > 0 else '-inf'}
            if math.isnan(obj):
                return {'__special__': 'nan'}
            return obj
        if isinstance(obj, dict):
            return {k: self._convert_floats(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [self._convert_floats(i) for i in obj]
        return obj


def _restore(obj: Any) -> Any:
    if isinstance(obj, dict):
        if '__special__' in obj:
            t = obj['__special__']
            if t == 'ellipsis': return ...
            if t == 'set': return set(obj['value'])
            if t == 'bytes':
                import base64
                return base64.b64decode(obj['value'])
            if t == 'inf': return float('inf')
            if t == '-inf': return float('-inf')
            if t == 'nan': return float('nan')
        return {k: _restore(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_restore(i) for i in obj]
    return obj


class EvaluationResult:
    """带元数据的 xdev 评估结果"""

    def __init__(
        self,
        result: ObjectEvaluationResult | ListOfObjectsEvaluationResult,
        *,
        set_id: str | None = None,
        base_url: str | None = None,
    ):
        self.result = result
        self.set_id = set_id
        self.base_url = base_url

    def __getattr__(self, name: str) -> Any:
        """透传底层评估结果属性，兼容旧调用方式。"""
        return getattr(self.result, name)

    def save(self, path: str | Path, indent: int = 2) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = _result_to_dict(self.result, metadata={'set_id': self.set_id, 'base_url': self.base_url})
        path.write_text(json.dumps(data, cls=SafeJSONEncoder, ensure_ascii=False, indent=indent), encoding='utf-8')

    def save_html(self, path: str | Path, base_url: str | None = None) -> None:
        from .html_report import save_html_report
        save_html_report(self, path, base_url=base_url)

    @classmethod
    def load(cls, path: str | Path) -> 'EvaluationResult':
        data = _restore(json.loads(Path(path).read_text(encoding='utf-8')))
        return _dict_to_evaluation_result(data)


# ---------- serialization ----------

def _schema_to_dict(schema: Schema) -> dict:
    return {'fields': {k: v.value if hasattr(v, 'value') else v for k, v in schema.fields.items()}}


def _dict_to_schema(data: dict) -> Schema:
    return Schema(fields={k: FieldType(v) for k, v in data['fields'].items()})


def _runtime_to_dict(ri: RuntimeInfo | None) -> dict | None:
    if ri is None:
        return None
    ei = None
    if ri.exception_info:
        ei = {'error_message': ri.exception_info.error_message,
              'error_traceback': ri.exception_info.error_traceback,
              'exception_type': ri.exception_info.exception_type}
    return {'exception_info': ei, 'stdout': ri.stdout, 'stderr': ri.stderr}


def _dict_to_runtime(data: dict | None) -> RuntimeInfo | None:
    if not data:
        return None
    ei = None
    if data.get('exception_info'):
        ei = ExceptionInfo(**data['exception_info'])
    return RuntimeInfo(exception_info=ei, stdout=data.get('stdout', ''), stderr=data.get('stderr', ''))


def _object_detail_to_dict(d: ObjectRecordDetail) -> dict:
    return {
        'type': d.type.value,
        'standared_info': {'id': d.standared_info.id, 'labels': d.standared_info.labels},
        'extracted_info': {
            'id': d.extracted_info.id,
            'labels': d.extracted_info.labels,
            'success': d.extracted_info.success,
            'runtime_info': _runtime_to_dict(d.extracted_info.runtime_info),
            'raw_data': d.extracted_info.raw_data,
        },
        'related_field_details': [
            {'name': f.name, 'type': f.type.value,
             'standard_value': f.standard_value, 'extracted_value': f.extracted_value}
            for f in d.related_field_details
        ],
    }


def _dict_to_object_detail(data: dict) -> ObjectRecordDetail:
    from evaluator.core.models import RecordDetailType, FieldDetailType
    std = FullStandard(id=data['standared_info']['id'], labels=data['standared_info']['labels'])
    ext = FullExtractedResult(
        id=data['extracted_info']['id'],
        labels=data['extracted_info']['labels'],
        success=data['extracted_info'].get('success', True),
        runtime_info=_dict_to_runtime(data['extracted_info'].get('runtime_info')),
        raw_data=data['extracted_info'].get('raw_data'),
    )
    fields = [FieldDetail(name=f['name'], type=FieldDetailType(f['type']),
                          standard_value=f['standard_value'], extracted_value=f['extracted_value'])
              for f in data['related_field_details']]
    return ObjectRecordDetail(type=RecordDetailType(data['type']),
                              standared_info=std, extracted_info=ext, related_field_details=fields)


def _list_detail_to_dict(d: ListRecordDetail) -> dict:
    def match_to_dict(m: MatchedObjectDetail) -> dict:
        return {
            'std_list_idx': m.std_list_idx, 'ext_list_idx': m.ext_list_idx,
            'similarity_score': m.similarity_score,
            'correct_fields': m.correct_fields, 'incorrect_fields': m.incorrect_fields,
            'missing_fields': m.missing_fields, 'extra_fields': m.extra_fields,
            'standard_value': m.standard_value, 'extracted_value': m.extracted_value,
        }
    return {
        'type': d.type.value,
        'standared_info': {'id': d.standared_info.id, 'labels': d.standared_info.labels},
        'extracted_info': {
            'id': d.extracted_info.id,
            'labels': d.extracted_info.labels,
            'success': d.extracted_info.success,
            'runtime_info': _runtime_to_dict(d.extracted_info.runtime_info),
            'raw_data': d.extracted_info.raw_data,
        },
        'matched': [match_to_dict(m) for m in d.matched],
        'missing': d.missing,
        'extra': d.extra,
    }


def _dict_to_list_detail(data: dict) -> ListRecordDetail:
    from evaluator.core.models import RecordDetailType
    std = FullStandard(id=data['standared_info']['id'], labels=data['standared_info']['labels'])
    ext = FullExtractedResult(
        id=data['extracted_info']['id'],
        labels=data['extracted_info']['labels'],
        success=data['extracted_info'].get('success', True),
        runtime_info=_dict_to_runtime(data['extracted_info'].get('runtime_info')),
        raw_data=data['extracted_info'].get('raw_data'),
    )
    matched = [MatchedObjectDetail(**m) for m in data.get('matched', [])]
    return ListRecordDetail(type=RecordDetailType(data['type']),
                            standared_info=std, extracted_info=ext,
                            matched=matched, missing=data.get('missing', []), extra=data.get('extra', []))


def _result_to_dict(result, metadata: dict | None = None) -> dict:
    if isinstance(result, ObjectEvaluationResult):
        result_type = 'object'
        details = [_object_detail_to_dict(d) for d in result.details]
    elif isinstance(result, ListOfObjectsEvaluationResult):
        result_type = 'list_of_objects'
        details = [_list_detail_to_dict(d) for d in result.details]
    else:
        raise ValueError(f"不支持的评估结果类型: {type(result)}")
    data: dict = {'__type__': result_type, 'schema_': _schema_to_dict(result.schema_), 'details': details}
    if metadata:
        data['metadata'] = metadata
    return data


def _dict_to_evaluation_result(data: dict) -> EvaluationResult:
    result_type = data['__type__']
    schema = _dict_to_schema(data['schema_'])
    if result_type == 'object':
        result = ObjectEvaluationResult(schema_=schema, details=[_dict_to_object_detail(d) for d in data['details']])
    elif result_type == 'list_of_objects':
        result = ListOfObjectsEvaluationResult(schema_=schema, details=[_dict_to_list_detail(d) for d in data['details']])
    else:
        raise ValueError(f"不支持的评估结果类型: {result_type}")
    metadata = data.get('metadata', {})
    return EvaluationResult(result=result, set_id=metadata.get('set_id'), base_url=metadata.get('base_url'))
