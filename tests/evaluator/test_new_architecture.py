#!/usr/bin/env python3
"""测试新架构的功能"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

def test_basic_imports():
    """测试基本导入"""
    print("测试基本导入...")
    try:
        from evaluator import (
            Schema, FieldType,
            StandardSetManager,
            get_evaluate_parts
        )
        print("✅ 基本导入成功")
        return True
    except ImportError as e:
        print(f"❌ 导入失败: {e}")
        return False

def test_create_schema():
    """测试创建Schema"""
    print("测试创建Schema...")
    try:
        from evaluator import Schema, FieldType
        
        schema = Schema(fields={
            "name": FieldType.STRING,
            "age": FieldType.INTEGER,
            "score": FieldType.FLOAT
        })
        
        print(f"✅ Schema创建成功: {schema.fields}")
        return True
    except Exception as e:
        print(f"❌ Schema创建失败: {e}")
        return False

def test_load_standard_set():
    """测试加载标准集"""
    print("测试加载标准集...")
    from evaluator import StandardSetManager
    manager = StandardSetManager()
    standard_set = manager.load_from_directory(Path("resources/GDDH"), 'train')
    print(f"✅ 标准集加载成功: {standard_set.name}, 标准数量: {len(standard_set)}")

def test_create_standard_set():
    """测试创建标准集"""
    print("测试创建标准集...")
    try:
        from evaluator import Schema, FieldType, StandardSetManager, Standard
        
        # 创建schema
        schema = Schema(fields={
            "name": FieldType.STRING,
            "age": FieldType.INTEGER
        })
        
        # 创建管理器
        manager = StandardSetManager()
        
        # 创建标准集
        standard_set = manager.create_standard_set(
            name="test_set",
            schema=schema,
            description="测试标准集"
        )
        
        # 添加标准
        test_standard = Standard[dict](
            id="test_1",
            labels={"name": "Alice", "age": 25}
        )
        
        standard_set.add_standard(test_standard)
        
        print(f"✅ 标准集创建成功: {standard_set.name}, 标准数量: {len(standard_set)}")
        return True
    except Exception as e:
        print(f"❌ 标准集创建失败: {e}")
        return False

def test_get_evaluate_parts():
    """测试获取评估组件"""
    print("测试获取评估组件...")
    try:
        from evaluator import get_evaluate_parts, Schema, FieldType
        
        schema = Schema(fields={
            "name": FieldType.STRING,
            "age": FieldType.INTEGER
        })
        
        parts = get_evaluate_parts('object', schema)
        
        print(f"✅ 评估组件获取成功: evaluator={type(parts.evaluator).__name__}, data_creator={type(parts.data_creator).__name__}")
        return True
    except Exception as e:
        print(f"❌ 评估组件获取失败: {e}")
        return False

def test_document_index():
    """测试文档索引功能（内联到 StandardSetManager）"""
    print("测试文档索引功能...")
    try:
        from evaluator import StandardSetManager
        
        # 创建标准集管理器
        manager = StandardSetManager()
        
        # 测试文档索引方法存在
        assert hasattr(manager, 'get_document')
        assert hasattr(manager, 'get_documents')
        assert hasattr(manager, 'has_document')
        
        # 测试空索引
        assert manager.get_document("non_existent") is None
        assert manager.has_document("non_existent") is False
        
        print(f"✅ 文档索引功能正常")
        return True
    except Exception as e:
        print(f"❌ 文档索引功能测试失败: {e}")
        return False

def test_evaluate_standard_set():
    """测试评估标准集"""
    print("测试评估标准集...")
    from evaluator import StandardSetManager
    manager = StandardSetManager()
    standard_set = manager.load_from_directory(Path("resources/GDDH"), 'train')
    evaluator = standard_set.get_evaluator()
    print(f"✅ 评估器创建成功: {evaluator}")
    return True

def main():
    """运行所有测试"""
    print("🚀 开始测试新架构...")
    print("=" * 50)
    
    tests = [
        test_basic_imports,
        test_create_schema,
        test_create_standard_set,
        test_get_evaluate_parts,
        test_document_index
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ 测试 {test.__name__} 出现异常: {e}")
            results.append(False)
        print()
    
    print("=" * 50)
    success_count = sum(results)
    total_count = len(results)
    
    if success_count == total_count:
        print(f"🎉 所有测试通过! ({success_count}/{total_count})")
        print("新架构基本功能正常！")
    else:
        print(f"⚠️  部分测试失败: {success_count}/{total_count}")
        print("需要检查失败的部分")
    
    return success_count == total_count

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
