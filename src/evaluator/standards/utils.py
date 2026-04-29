from .models import StandardSet, StandardSetMetadata, FullSchema
from evaluator.core.evaluation_models import FullStandard



def filter_standard_set(dataset: StandardSet, keys: list[str]) -> StandardSet:
    """创建一个预过滤的数据集副本，只包含指定字段"""
    
    # 验证字段存在性
    invalid_keys = [k for k in keys if k not in dataset.schema.fields]
    if invalid_keys:
        raise ValueError(f"字段 {invalid_keys} 在 schema 中不存在")
    
    # 过滤schema
    filtered_schema = FullSchema(type=dataset.schema.type, fields={
        k: v for k, v in dataset.schema.fields.items() if k in keys
    })
    
    # 过滤所有标准答案的labels
    filtered_standards = []
    for std in dataset.standards:
        filtered_labels = {k: v for k, v in std.labels.items() if k in keys}
        filtered_std = FullStandard(
            id=std.id,
            labels=filtered_labels,
            info=std.info,
            metadata=std.metadata,
            created_at=std.created_at,
            updated_at=std.updated_at
        )
        filtered_standards.append(filtered_std)
    
    # 创建过滤后的数据集
    filtered_metadata = StandardSetMetadata(
        name=f"{dataset.metadata.name}_filtered_{len(keys)}fields",
        description=f"过滤版本，包含字段: {', '.join(keys)}",
        schema_type=dataset.metadata.schema_type,
        version=dataset.metadata.version,
        created_at=dataset.metadata.created_at,
        total_standards=len(filtered_standards),
        train_count=len(filtered_standards),  # 简化处理，假设都是训练数据
        test_count=0
    )
    
    return StandardSet(
        name=filtered_metadata.name,
        schema=filtered_schema,
        standards=filtered_standards,
        metadata=filtered_metadata
    )