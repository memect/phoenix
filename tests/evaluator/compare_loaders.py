#!/usr/bin/env python3
"""对比目录加载器和URL加载器的功能"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from evaluator.standards.loader.direcotry_loader import DirectoryStandardSetLoader
from evaluator.standards.loader.url_loader import UrlStandardSetLoader
from evaluator.core.schema import Schema


def test_directory_loader():
    """测试目录加载器"""
    print("=== 目录加载器测试 ===")
    
    # 使用GDDH数据集
    dataset_path = project_root / "resources" / "GDDH"
    
    if not dataset_path.exists():
        print(f"❌ 数据集目录不存在: {dataset_path}")
        return None
    
    try:
        # 创建目录加载器
        loader = DirectoryStandardSetLoader(
            path=dataset_path,
            dataset_name="test"  # 这里使用test.json文件
        )
        
        print(f"✅ 创建目录加载器成功")
        print(f"   数据集路径: {dataset_path}")
        
        # 加载标准集
        print("🔄 加载标准集...")
        standard_set = loader.load()
        
        print(f"✅ 加载成功！")
        print(f"   标准集名称: {standard_set.name}")
        print(f"   标准数量: {len(standard_set.standards)}")
        print(f"   Schema字段数量: {len(standard_set.schema.fields)}")
        
        # 显示schema内容
        print(f"   Schema字段: {list(standard_set.schema.fields.keys())}")
        
        # 显示前几个标准
        print(f"\n📋 前3个标准的信息:")
        for i, std in enumerate(standard_set.standards[:3]):
            print(f"\n  标准 {i+1}:")
            print(f"    ID: {std.id}")
            print(f"    标签字段数: {len(std.labels) if std.labels else 0}")
            
            if std.info and std.info.document:
                print(f"    有markdown内容: {bool(std.info.document.md)}")
                print(f"    有docjson内容: {std.info.document.docjson is not None}")
            else:
                print(f"    无文档信息")
            
            # 显示部分标签内容
            if std.labels:
                print(f"    标签示例:")
                for key, value in list(std.labels.items())[:2]:
                    print(f"      {key}: {value}")
        
        return standard_set
        
    except Exception as e:
        print(f"❌ 目录加载器失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_url_loader_structure():
    """测试URL加载器的结构（不实际调用API）"""
    print("\n=== URL加载器结构测试 ===")
    
    # 读取GDDH的schema
    schema_path = project_root / "resources" / "GDDH" / "schema.json"
    
    if not schema_path.exists():
        print(f"❌ Schema文件不存在: {schema_path}")
        return None
    
    try:
        import json
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema_data = json.load(f)
        
        # 创建schema
        if 'data' in schema_data:
            schema = Schema.from_dict(schema_data['data'])
        else:
            schema = Schema.from_dict(schema_data)
        
        # 创建URL加载器
        loader = UrlStandardSetLoader(
            api_base_url="http://localhost:8007/dev-api/documents_info",
            dataset_id="aad081f0-7c2b-4756-93df-9643b58b407c",
            schema=schema,
            dataset_name="GDDH_URL_Test",
            max_concurrent=3,
            cache_ttl=None
        )
        
        print(f"✅ 创建URL加载器成功")
        print(f"   API URL: {loader.api_base_url}")
        print(f"   数据集ID: {loader.dataset_id}")
        print(f"   Schema字段数量: {len(loader.schema.fields)}")
        print(f"   Schema字段: {list(loader.schema.fields.keys())}")
        print(f"   缓存目录: {loader.cache_dir}")
        print(f"   最大并发数: {loader.max_concurrent}")
        print(f"   缓存TTL: {loader.cache_ttl}")
        
        # 测试辅助方法
        print(f"\n🔧 测试辅助方法:")
        
        # 测试ID转换
        test_uuid = "aad081f0-7c2b-4756-93df-9643b58b407c"
        hex_result = loader._id_to_hex(test_uuid)
        print(f"   UUID转hex: {test_uuid} -> {hex_result}")
        
        # 测试数据处理
        test_data = {"field1": "value1", "timestamp": 1640995200000}
        processed_data = loader._process_std_data(test_data)
        print(f"   数据处理: {test_data} -> {processed_data}")
        
        # 测试缓存路径
        test_cache_path = loader.dataset_cache_dir / "test.json"
        is_valid = loader._is_cache_valid(test_cache_path)
        print(f"   缓存有效性检查: {test_cache_path.name} -> {is_valid}")
        
        return loader
        
    except Exception as e:
        print(f"❌ URL加载器结构测试失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def compare_schemas():
    """对比两种加载器的schema处理"""
    print("\n=== Schema对比 ===")
    
    # 从文件读取schema
    schema_path = project_root / "resources" / "GDDH" / "schema.json"
    
    if not schema_path.exists():
        print(f"❌ Schema文件不存在: {schema_path}")
        return
    
    try:
        import json
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema_data = json.load(f)
        
        print(f"📋 原始schema数据:")
        print(f"   类型: {schema_data.get('type', 'unknown')}")
        print(f"   字段数量: {len(schema_data.get('data', {}))}")
        
        # 目录加载器的schema处理方式
        dataset_path = project_root / "resources" / "GDDH"
        if dataset_path.exists():
            try:
                dir_loader = DirectoryStandardSetLoader(dataset_path, "test")
                dir_schema = dir_loader.load_schema(dataset_path)
                print(f"\n📁 目录加载器Schema:")
                print(f"   字段数量: {len(dir_schema.fields)}")
                print(f"   字段列表: {list(dir_schema.fields.keys())[:5]}...")
            except Exception as e:
                print(f"❌ 目录加载器schema加载失败: {e}")
        
        # URL加载器的schema处理方式
        try:
            if 'data' in schema_data:
                url_schema = Schema.from_dict(schema_data['data'])
            else:
                url_schema = Schema.from_dict(schema_data)
            
            print(f"\n🌐 URL加载器Schema:")
            print(f"   字段数量: {len(url_schema.fields)}")
            print(f"   字段列表: {list(url_schema.fields.keys())[:5]}...")
            
            # 检查字段是否一致
            if dataset_path.exists():
                dir_loader = DirectoryStandardSetLoader(dataset_path, "test")
                dir_schema = dir_loader.load_schema(dataset_path)
                
                dir_fields = set(dir_schema.fields.keys())
                url_fields = set(url_schema.fields.keys())
                
                if dir_fields == url_fields:
                    print(f"✅ 两种加载器的schema字段完全一致")
                else:
                    print(f"⚠️  两种加载器的schema字段不一致:")
                    print(f"     目录独有: {dir_fields - url_fields}")
                    print(f"     URL独有: {url_fields - dir_fields}")
                
        except Exception as e:
            print(f"❌ URL加载器schema处理失败: {e}")
        
    except Exception as e:
        print(f"❌ Schema对比失败: {e}")


if __name__ == "__main__":
    print("🔍 加载器对比测试")
    print("=" * 50)
    
    try:
        # 测试目录加载器
        dir_result = test_directory_loader()
        
        # 测试URL加载器结构
        url_result = test_url_loader_structure()
        
        # 对比schemas
        compare_schemas()
        
        print("\n" + "=" * 50)
        print("✅ 对比测试完成！")
        
        if dir_result:
            print(f"📁 目录加载器: 成功加载 {len(dir_result.standards)} 个标准")
        
        if url_result:
            print(f"🌐 URL加载器: 结构测试通过")
        
    except KeyboardInterrupt:
        print("\n\n⏹️  用户中断")
    except Exception as e:
        print(f"\n❌ 对比测试时出错: {e}")
        import traceback
        traceback.print_exc()
