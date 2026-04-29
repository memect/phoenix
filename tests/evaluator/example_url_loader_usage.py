#!/usr/bin/env python3
"""URL加载器使用示例"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from evaluator.standards.loader.url_loader import UrlStandardSetLoader
from evaluator.core.schema import Schema


def example_basic_usage():
    """基础使用示例"""
    print("=== URL加载器基础使用示例 ===")
    
    # 1. 准备参数
    api_base_url = "http://localhost:8007/dev-api/documents_info"
    dataset_id = "aad081f0-7c2b-4756-93df-9643b58b407c"
    
    # 2. 创建schema（基于GDDH数据集）
    schema = Schema.from_dict({
        "会议召开地点": "str",
        "会议召开时间": "str", 
        "股东大会名称": "str",
        "股东大会类别": "str",
        "参会登记起始日": "str",
        "网络投票终止日": "str",
        "网络投票起始日": "str",
        "交易系统投票日期": "str",
        "股东大会类别编码": "str",
        "A股股东资格登记日期": "str",
        "参会登记日期截止日期": "str",
        "股东大会名称（英文）": "str",
        "异地股东传真截止日": "str"
    })
    
    # 3. 创建URL加载器
    loader = UrlStandardSetLoader(
        api_base_url=api_base_url,
        dataset_id=dataset_id,
        schema=schema,
        dataset_name="GDDH_Example",
        max_concurrent=3,  # 限制并发数
        cache_ttl=None     # 永久缓存
    )
    
    print(f"✅ 创建了URL加载器")
    print(f"   API URL: {api_base_url}")
    print(f"   数据集ID: {dataset_id}")
    print(f"   缓存目录: {loader.cache_dir}")
    print(f"   数据集缓存目录: {loader.dataset_cache_dir}")
    
    try:
        # 4. 加载标准集
        print("\n🔄 开始加载标准集...")
        standard_set = loader.load()
        
        # 5. 显示结果
        print(f"✅ 加载成功！")
        print(f"   标准集名称: {standard_set.name}")
        print(f"   标准数量: {len(standard_set.standards)}")
        print(f"   Schema字段数量: {len(standard_set.schema.fields)}")
        print(f"   元数据: {standard_set.metadata.description}")
        
        # 6. 显示前几个标准的详细信息
        print(f"\n📋 前3个标准的详细信息:")
        for i, std in enumerate(standard_set.standards[:3]):
            print(f"\n  标准 {i+1}:")
            print(f"    ID: {std.id}")
            print(f"    标签字段数: {len(std.labels) if std.labels else 0}")
            
            if std.info and std.info.document:
                print(f"    有markdown内容: {bool(std.info.document.md)}")
                print(f"    有docjson内容: {std.info.document.docjson is not None}")
                if std.info.document.md:
                    md_length = len(std.info.document.md)
                    print(f"    Markdown长度: {md_length} 字符")
            else:
                print(f"    无文档信息")
            
            # 显示部分标签内容
            if std.labels:
                print(f"    标签示例:")
                for key, value in list(std.labels.items())[:3]:
                    print(f"      {key}: {value}")
        
        # 7. 测试缓存机制
        print(f"\n🔄 测试缓存机制...")
        standard_set_cached = loader.load()
        print(f"✅ 缓存加载成功，标准数量: {len(standard_set_cached.standards)}")
        
        # 8. 验证缓存文件
        cache_info_file = loader.dataset_cache_dir / "dataset_info.json"
        if cache_info_file.exists():
            print(f"✅ 缓存文件存在: {cache_info_file}")
            print(f"   文件大小: {cache_info_file.stat().st_size} 字节")
        
        docs_cache_dir = loader.documents_cache_dir
        if docs_cache_dir.exists():
            cached_files = list(docs_cache_dir.glob("*"))
            print(f"✅ 文档缓存目录存在，包含 {len(cached_files)} 个文件")
        
        return standard_set
        
    except Exception as e:
        print(f"❌ 加载失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def example_with_custom_cache():
    """自定义缓存目录的示例"""
    print("\n=== 自定义缓存目录示例 ===")
    
    import tempfile
    
    # 使用临时目录作为缓存
    with tempfile.TemporaryDirectory() as tmpdir:
        print(f"使用临时缓存目录: {tmpdir}")
        
        schema = Schema.from_dict({"field1": "str", "field2": "int"})
        
        loader = UrlStandardSetLoader(
            api_base_url="http://example.com/api",
            dataset_id="test-dataset",
            schema=schema,
            dataset_name="Test Dataset",
            cache_dir=tmpdir,
            max_concurrent=5,
            cache_ttl=3600  # 1小时缓存
        )
        
        print(f"✅ 创建了带自定义缓存的加载器")
        print(f"   缓存TTL: {loader.cache_ttl} 秒")
        print(f"   缓存目录: {loader.cache_dir}")


def example_error_handling():
    """错误处理示例"""
    print("\n=== 错误处理示例 ===")
    
    # 测试无效的API URL
    schema = Schema.from_dict({"field1": "str"})
    
    loader = UrlStandardSetLoader(
        api_base_url="http://invalid-url-12345.com",
        dataset_id="invalid-id",
        schema=schema,
        dataset_name="Invalid Test",
        max_concurrent=1
    )
    
    try:
        print("🔄 尝试连接无效URL...")
        standard_set = loader.load()
        print(f"意外成功: {len(standard_set.standards)} 个标准")
    except Exception as e:
        print(f"✅ 预期的错误处理: {type(e).__name__}: {e}")


if __name__ == "__main__":
    print("🚀 URL加载器使用示例")
    print("=" * 50)
    
    # 运行示例
    try:
        # 基础使用示例
        standard_set = example_basic_usage()
        
        # 自定义缓存示例
        example_with_custom_cache()
        
        # 错误处理示例
        example_error_handling()
        
        print("\n" + "=" * 50)
        print("✅ 所有示例运行完成！")
        
        if standard_set:
            print(f"📊 最终结果: 成功加载了 {len(standard_set.standards)} 个标准")
        
    except KeyboardInterrupt:
        print("\n\n⏹️  用户中断")
    except Exception as e:
        print(f"\n❌ 运行示例时出错: {e}")
        import traceback
        traceback.print_exc()
