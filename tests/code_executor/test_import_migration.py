"""
Property 16: Import path migration correctness

*For any* code that previously imported from `extract_agent`, `nopagent`, or other old modules,
the equivalent import from the new module structure should provide the same functionality.

**Validates: Requirements 6.1-6.21**
"""

import pytest
from hypothesis import given, settings, strategies as st


class TestImportPathMigration:
    """
    Feature: modular-refactor, Property 16: Import path migration correctness
    
    Tests that all import paths have been correctly migrated to the new module structure.
    """
    
    def test_code_executor_main_imports(self):
        """
        Test that code_executor main module exports are available.
        
        **Validates: Requirements 6.3, 6.4, 6.5, 6.6, 6.7, 6.8**
        """
        # Test main exports from code_executor
        from code_executor import (
            execute,
            do_extract,
            to_plain_article,
            Table,
            Cell,
            create_default_tool_hub,
            get_structure_code,
            eval_config,
        )
        
        # Verify they are callable or classes
        assert callable(execute)
        assert callable(do_extract)
        assert callable(to_plain_article)
        assert Table is not None
        assert Cell is not None
        assert callable(create_default_tool_hub)
        assert callable(get_structure_code)
        assert callable(eval_config)
    
    def test_code_executor_ner_imports(self):
        """
        Test that code_executor.ner module exports are available.
        
        **Validates: Requirements 6.11, 6.12**
        """
        from code_executor.ner import (
            NERPattern,
            Match,
            StringWithNER,
            NerApi,
        )
        
        # Verify they are classes
        assert NERPattern is not None
        assert Match is not None
        assert StringWithNER is not None
        assert NerApi is not None
    
    def test_code_executor_tools_imports(self):
        """
        Test that code_executor.tools module exports are available.
        
        **Validates: Requirements 6.9, 6.10**
        """
        from code_executor.tools import (
            setup_code_tools,
            Settings,
            PolicyContext,
            Policy,
            get_global_policy,
            create_default_tool_hub,
            create_tool_hub,
            tool,
        )
        
        # Verify they are callable or classes
        assert callable(setup_code_tools)
        assert Settings is not None
        assert PolicyContext is not None
        assert Policy is not None
        assert callable(get_global_policy)
        assert callable(create_default_tool_hub)
        assert callable(create_tool_hub)
        assert callable(tool)
    
    def test_evaluation_engine_imports(self):
        """
        Test that evaluation_engine module exports are available.
        
        **Validates: Requirements 6.1, 6.2**
        """
        from evaluation_engine import EvaluationEngine
        
        # Verify EvaluationEngine class
        assert EvaluationEngine is not None
        assert hasattr(EvaluationEngine, 'from_data_path')
        assert hasattr(EvaluationEngine, 'from_url')
        assert hasattr(EvaluationEngine, 'evaluate_program')
    
    def test_evaluator_imports(self):
        """
        Test that evaluator module exports are available.
        
        **Validates: Requirements 3.5, 3.6**
        """
        from evaluator import (
            Schema,
            FieldType,
            get_evaluate_parts,
        )
        from evaluator.core.models import EvaluationResult
        
        # Verify they are available
        assert Schema is not None
        assert FieldType is not None
        assert callable(get_evaluate_parts)
        assert EvaluationResult is not None
    
    def test_simple_workflow_models_imports(self):
        """
        Test that simple_workflow.models exports are available.
        
        **Validates: Requirements 6.13, 6.14, 6.15**
        """
        from simple_workflow.models import (
            Program,
            LLMS,
            ResultJson,
            load_result_json,
        )
        
        # Verify they are classes or functions
        assert Program is not None
        assert LLMS is not None
        assert ResultJson is not None
        assert callable(load_result_json)
    
    def test_simple_workflow_utils_imports(self):
        """
        Test that simple_workflow.utils exports are available.
        
        **Validates: Requirements 6.16**
        """
        from simple_workflow.utils import extract_code_from_response
        
        # Verify it's callable
        assert callable(extract_code_from_response)
    
    def test_langchain_base_chat_model_import(self):
        """
        Test that BaseChatModel can be imported from langchain_core.
        
        **Validates: Requirements 6.19**
        """
        from langchain_core.language_models import BaseChatModel
        
        # Verify it's a class
        assert BaseChatModel is not None
    
    @settings(max_examples=100)
    @given(st.text(min_size=0, max_size=100))
    def test_extract_code_from_response_property(self, text: str):
        """
        Property test: extract_code_from_response should handle any text input.
        
        **Validates: Requirements 6.16**
        """
        from simple_workflow.utils import extract_code_from_response
        
        # Should not raise exception for any input
        result = extract_code_from_response(text)
        
        # Result should be a string
        assert isinstance(result, str)
    
    @settings(max_examples=100)
    @given(st.sampled_from(['object', 'list_of_objects']))
    def test_get_evaluate_parts_property(self, eval_type: str):
        """
        Property test: get_evaluate_parts should work with valid types.
        
        **Validates: Requirements 3.5**
        """
        from evaluator import get_evaluate_parts, Schema, FieldType
        
        # Create a valid schema
        schema = Schema(fields={"test_field": FieldType.STRING})
        
        # Should return valid parts
        parts = get_evaluate_parts(eval_type, schema)
        
        assert parts is not None
        assert parts.evaluator is not None
        assert parts.data_creator is not None
    
    def test_code_executor_batch_execute_import(self):
        """
        Test that batch_execute is available from code_executor.api.
        
        **Validates: Requirements 1.2**
        """
        from code_executor.api import batch_execute
        
        assert callable(batch_execute)
    
    def test_tool_defines_imports(self):
        """
        Test that tool defines are importable.
        
        **Validates: Requirements 6.9, 6.10**
        """
        from code_executor.tools.tool_defines.extractor_tool import ExtractTool
        from code_executor.tools.tool_defines.ner_tool import NerTool
        from code_executor.tools.tool_defines.ner_regex import NerRegexTool
        
        assert ExtractTool is not None
        assert NerTool is not None
        assert NerRegexTool is not None


class TestImportPathEquivalence:
    """
    Tests that verify the new imports provide equivalent functionality.
    """
    
    def test_table_cell_functionality(self):
        """
        Test that Table and Cell classes work correctly.
        
        **Validates: Requirements 6.6**
        """
        from code_executor import Table, Cell
        
        # Create a simple cell with correct parameters
        cell = Cell(text="test", row_index=0, col_index=0, row_span=1, col_span=1)
        assert cell.text == "test"
        assert cell.row_index == 0
        assert cell.col_index == 0
        assert cell.row_span == 1
        assert cell.col_span == 1
    
    def test_policy_context_functionality(self):
        """
        Test that PolicyContext works correctly.
        
        **Validates: Requirements 6.9**
        """
        from code_executor.tools import PolicyContext, Policy, get_global_policy
        
        # Test context manager
        policy = Policy(tool_names=['test'], tool_config={'test': {}})
        
        # Before context
        default_policy = get_global_policy()
        assert default_policy.tool_names == []
        
        # Inside context
        with PolicyContext(policy):
            current = get_global_policy()
            assert current.tool_names == ['test']
        
        # After context
        restored = get_global_policy()
        assert restored.tool_names == []
    
    def test_schema_creation(self):
        """
        Test that Schema can be created correctly.
        
        **Validates: Requirements 3.5**
        """
        from evaluator import Schema, FieldType
        
        # Create schema from dict
        schema_dict = {"name": "str", "age": "int"}
        schema = Schema.from_dict(schema_dict)
        
        assert "name" in schema.fields
        assert "age" in schema.fields
        assert schema.fields["name"] == FieldType.STRING
        assert schema.fields["age"] == FieldType.INTEGER
    
    @settings(max_examples=50)
    @given(
        code_content=st.text(min_size=1, max_size=50, alphabet="abcdefghijklmnopqrstuvwxyz")
    )
    def test_extract_code_with_tags(self, code_content: str):
        """
        Property test: extract_code_from_response should extract code from tags.
        
        **Validates: Requirements 6.16**
        """
        from simple_workflow.utils import extract_code_from_response
        
        # Test with <code> tags
        response_with_code_tag = f"Some text <code>{code_content}</code> more text"
        result = extract_code_from_response(response_with_code_tag)
        assert result == code_content
        
        # Test with ```python blocks
        response_with_python_block = f"Some text\n```python\n{code_content}\n```\nmore text"
        result = extract_code_from_response(response_with_python_block)
        assert result == code_content
