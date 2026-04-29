"""测试URL加载器的功能"""

import pytest
import tempfile
from pathlib import Path

from evaluator.standards.loader.url_loader import UrlStandardSetLoader
from evaluator.core.schema import Schema
from evaluator.standards.models import FullSchema, SchemaType


class TestUrlStandardSetLoader:
    """URL标准集加载器测试类"""
    
    @pytest.fixture
    def gddh_schema(self):
        """GDDH数据集的schema"""
        return FullSchema.from_dict(
            {
                "type": "object",
                "data": {
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
                }
            }
            
        )
    
    @pytest.fixture
    def temp_cache_dir(self):
        """临时缓存目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    def test_url_loader_initialization(self, gddh_schema, temp_cache_dir):
        """测试URL加载器的初始化"""
        api_base_url = "http://localhost:8007/dev-api/documents_info"
        dataset_id = "aad081f0-7c2b-4756-93df-9643b58b407c"
        
        loader = UrlStandardSetLoader(
            api_base_url=api_base_url,
            dataset_id=dataset_id,
            schema=gddh_schema,
            dataset_name="GDDH_Test",
            cache_dir=temp_cache_dir,
            max_concurrent=3,
            cache_ttl=None
        )
        
        assert loader.api_base_url == api_base_url
        assert loader.dataset_id == dataset_id
        assert loader.dataset_name == "GDDH_Test"
        assert loader.max_concurrent == 3
        assert loader.cache_ttl is None
        assert loader.cache_dir == Path(temp_cache_dir)
        
        # 检查缓存目录是否创建
        assert loader.dataset_cache_dir.exists()
        assert loader.documents_cache_dir.exists()
    
    def test_schema_from_dict(self, temp_cache_dir):
        """测试从字典创建schema"""
        schema_dict = {
            "type": "object",
            "data": {
                "field1": "str",
                "field2": "int"
            }
        }
        
        loader = UrlStandardSetLoader(
            api_base_url="http://example.com",
            dataset_id="test-id",
            schema=schema_dict,
            cache_dir=temp_cache_dir
        )
        
        assert isinstance(loader.schema, Schema)
        assert "field1" in loader.schema.fields
        assert "field2" in loader.schema.fields
    
    def test_id_to_hex_conversion(self, gddh_schema, temp_cache_dir):
        """测试ID到hex的转换"""
        loader = UrlStandardSetLoader(
            api_base_url="http://example.com",
            dataset_id="test-id",
            schema=gddh_schema,
            cache_dir=temp_cache_dir
        )
        
        # 测试有效的UUID
        uuid_str = "aad081f0-7c2b-4756-93df-9643b58b407c"
        hex_result = loader._id_to_hex(uuid_str)
        assert hex_result == "aad081f07c2b475693df9643b58b407c"
        
        # 测试无效的UUID（应该返回原字符串）
        invalid_uuid = "not-a-uuid"
        hex_result = loader._id_to_hex(invalid_uuid)
        assert hex_result == "not-a-uuid"
    
    def test_process_std_data(self, gddh_schema, temp_cache_dir):
        """测试标准数据处理"""
        loader = UrlStandardSetLoader(
            api_base_url="http://example.com",
            dataset_id="test-id",
            schema=gddh_schema,
            cache_dir=temp_cache_dir
        )
        
        # 现在_process_std_data应该直接返回原数据
        test_data = {
            "field1": "value1",
            "field2": 123,
            "timestamp": 1640995200000  # 这个时间戳现在不会被处理
        }
        
        result = loader._process_std_data(test_data)
        assert result == test_data  # 应该完全相同
    
    def test_cache_validity_with_permanent_cache(self, gddh_schema, temp_cache_dir):
        """测试永久缓存的有效性检查"""
        loader = UrlStandardSetLoader(
            api_base_url="http://example.com",
            dataset_id="test-id",
            schema=gddh_schema,
            cache_dir=temp_cache_dir,
            cache_ttl=None  # 永久缓存
        )
        
        # 创建一个测试缓存文件
        cache_file = Path(temp_cache_dir) / "test_cache.json"
        cache_file.write_text('{"test": "data"}')
        
        # 永久缓存应该总是有效的
        assert loader._is_cache_valid(cache_file) is True
        
        # 不存在的文件应该无效
        non_existent = Path(temp_cache_dir) / "non_existent.json"
        assert loader._is_cache_valid(non_existent) is False
    
    def test_cache_save_and_load(self, gddh_schema, temp_cache_dir):
        """测试缓存的保存和加载"""
        loader = UrlStandardSetLoader(
            api_base_url="http://example.com",
            dataset_id="test-id",
            schema=gddh_schema,
            cache_dir=temp_cache_dir
        )
        
        # 测试JSON数据
        test_data = {"test": "data", "number": 123}
        cache_path = Path(temp_cache_dir) / "test.json"
        
        loader._save_to_cache(test_data, cache_path)
        assert cache_path.exists()
        
        loaded_data = loader._load_from_cache(cache_path)
        assert loaded_data == test_data
        
        # 测试Markdown数据
        markdown_content = "# Test Markdown\n\nThis is a test."
        md_cache_path = Path(temp_cache_dir) / "test.md"
        
        loader._save_to_cache(markdown_content, md_cache_path)
        assert md_cache_path.exists()
        
        loaded_md = loader._load_from_cache(md_cache_path)
        assert loaded_md == markdown_content
    
    @pytest.mark.integration
    def test_load_from_real_api(self, gddh_schema):
        """集成测试：从真实API加载数据（需要网络连接）"""
        # 这个测试需要真实的网络连接，使用pytest标记标识
        api_base_url = "http://localhost:8007/dev-api/documents_info"
        dataset_id = "aad081f0-7c2b-4756-93df-9643b58b407c"
        
        with tempfile.TemporaryDirectory() as tmpdir:
            loader = UrlStandardSetLoader(
                api_base_url=api_base_url,
                dataset_id=dataset_id,
                schema=gddh_schema,
                dataset_name="GDDH_Integration_Test",
                cache_dir=tmpdir,
                max_concurrent=2,  # 降低并发数以减少服务器压力
                cache_ttl=None
            )
            
            # 加载标准集
            standard_set = loader.load()
            
            # 验证结果
            assert standard_set is not None
            assert standard_set.name == "GDDH_Integration_Test"
            assert len(standard_set.standards) > 0
            assert standard_set.schema == gddh_schema
            
            # 验证标准集内容
            first_standard = standard_set.standards[0]
            assert first_standard.id is not None
            assert first_standard.labels is not None
            
            # 检查缓存是否生成
            dataset_cache_dir = Path(tmpdir) / dataset_id
            assert dataset_cache_dir.exists()
            assert (dataset_cache_dir / "dataset_info.json").exists()
            
            print(f"✅ 成功加载了 {len(standard_set.standards)} 个标准")
            print(f"✅ 缓存目录: {dataset_cache_dir}")
            
            # 测试第二次加载（应该使用缓存）
            standard_set_cached = loader.load()
            assert len(standard_set_cached.standards) == len(standard_set.standards)
            print("✅ 缓存机制工作正常")
                


def test_url_loader_basic_functionality():
    """基础功能测试（不需要网络连接）"""
    from evaluator.core.schema import Schema
    
    schema = Schema.from_dict({"field1": "str", "field2": "int"})
    
    with tempfile.TemporaryDirectory() as tmpdir:
        loader = UrlStandardSetLoader(
            api_base_url="http://example.com/api",
            dataset_id="test-dataset",
            schema=schema,
            dataset_name="Test Dataset",
            cache_dir=tmpdir,
            max_concurrent=5,
            cache_ttl=3600
        )
        
        assert loader.dataset_name == "Test Dataset"
        assert loader.max_concurrent == 5
        assert loader.cache_ttl == 3600


if __name__ == "__main__":
    # 运行基础测试
    test_url_loader_basic_functionality()
    print("✅ 基础功能测试通过")
    
    # 如果要运行集成测试，取消下面的注释
    # pytest.main([__file__ + "::TestUrlStandardSetLoader::test_load_from_real_api", "-v", "-m", "integration"])
