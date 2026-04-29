"""
Property 15: Database backward compatibility

*For any* historical workflow data stored in the database, the refactored 
`simple_workflow` module should be able to read and parse it correctly 
without data loss.

**Validates: Requirements 10.1, 10.2, 10.3**
"""

import uuid
from contextlib import contextmanager
from datetime import datetime
from typing import Dict, Any, Optional

import pytest
from hypothesis import given, settings, strategies as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from simple_workflow.database.base import Base
from simple_workflow.database.program import Program
from simple_workflow.database.evaluation_result import EvaluationResult
from simple_workflow.database.runs import Runs
from simple_workflow.database.workflow.models import Workflow, WorkflowStep


# ===== Context manager for database session =====

@contextmanager
def create_test_session():
    """Create an in-memory SQLite database session for testing"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


# ===== Strategies for generating test data =====

@st.composite
def evaluation_result_data(draw) -> Dict[str, Any]:
    """Generate valid evaluation result data structure"""
    field_count = draw(st.integers(min_value=1, max_value=10))
    field_stats = {}
    for i in range(field_count):
        field_name = f"field_{i}"
        field_stats[field_name] = {
            "accuracy": draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False)),
            "recall": draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False)),
            "precision": draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False)),
            "f1": draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False)),
        }
    
    return {
        "version": "1.0",
        "data": {
            "overall_accuracy": draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False)),
            "total_records": draw(st.integers(min_value=0, max_value=1000)),
            "total_correct": draw(st.integers(min_value=0, max_value=1000)),
            "field_stats": field_stats,
        }
    }


@st.composite
def workflow_info_data(draw) -> Dict[str, Any]:
    """Generate valid workflow info data structure"""
    return {
        "run_type": draw(st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('L', 'N')))),
        "keys": draw(st.lists(st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('L', 'N'))), min_size=0, max_size=5)),
        "target_accuracy": draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False)),
        "max_iterations": draw(st.integers(min_value=1, max_value=100)),
    }


@st.composite
def program_code(draw) -> str:
    """Generate valid Python program code"""
    field_num = draw(st.integers(min_value=0, max_value=100))
    field_value = draw(st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N"))))
    return f"""def extract(article):
    # Generated test program
    result = {{}}
    result['field_{field_num}'] = '{field_value}'
    return result
"""


# ===== Property Tests =====

class TestDatabaseBackwardCompatibility:
    """
    Feature: simple_workflow, Property 15: Database backward compatibility
    
    Tests that historical workflow data can be read and parsed correctly.
    """
    
    @settings(max_examples=100)
    @given(
        code=program_code(),
        eval_data=evaluation_result_data(),
    )
    def test_program_and_evaluation_round_trip(
        self, 
        code: str, 
        eval_data: Dict[str, Any]
    ):
        """
        Property: For any valid program and evaluation result data,
        storing and retrieving should preserve all data.
        
        **Validates: Requirements 10.1, 10.2**
        """
        with create_test_session() as session:
            # Create and store program
            program_id = uuid.uuid4()
            program = Program(id=program_id, code=code)
            session.add(program)
            session.flush()
            
            # Create and store evaluation result
            eval_id = uuid.uuid4()
            eval_result = EvaluationResult(
                id=eval_id,
                program_id=program_id,
                result=eval_data,
            )
            session.add(eval_result)
            session.commit()
            
            # Retrieve and verify
            retrieved_program = session.query(Program).filter_by(id=program_id).first()
            retrieved_eval = session.query(EvaluationResult).filter_by(id=eval_id).first()
            
            assert retrieved_program is not None
            assert retrieved_program.code == code
            assert retrieved_program.id == program_id
            
            assert retrieved_eval is not None
            assert retrieved_eval.result == eval_data
            assert retrieved_eval.program_id == program_id
            
            # Verify relationship
            assert len(retrieved_program.evaluation_results) == 1
            assert retrieved_program.evaluation_results[0].id == eval_id
    
    @settings(max_examples=100)
    @given(
        workflow_info=workflow_info_data(),
        step_types=st.lists(
            st.sampled_from(["init", "reflect", "optimize", "terminate"]),
            min_size=1,
            max_size=10,
        ),
    )
    def test_workflow_and_steps_round_trip(
        self,
        workflow_info: Dict[str, Any],
        step_types: list,
    ):
        """
        Property: For any valid workflow and steps data,
        storing and retrieving should preserve all data.
        
        **Validates: Requirements 10.1, 10.2, 10.3**
        """
        with create_test_session() as session:
            # Create run
            run_id = uuid.uuid4()
            run = Runs(
                id=run_id,
                type="workflow",
                info={"keys": workflow_info.get("keys", [])},
                status="running",
            )
            session.add(run)
            session.flush()
            
            # Create workflow
            workflow_id = uuid.uuid4()
            workflow = Workflow(
                id=workflow_id,
                run_id=run_id,
                status="running",
                workflow_info=workflow_info,
                start_time=datetime.now(),
            )
            session.add(workflow)
            session.flush()
            
            # Create steps
            created_steps = []
            for i, step_type in enumerate(step_types):
                step_info = {
                    "version": str(uuid.uuid4()),
                    "data": {"step_index": i, "type": step_type},
                }
                step = WorkflowStep(
                    workflow_id=workflow_id,
                    round=i + 1,
                    step_type=step_type,
                    step_info=step_info,
                    start_time=datetime.now(),
                )
                session.add(step)
                created_steps.append((step_type, step_info))
            
            session.commit()
            
            # Retrieve and verify
            retrieved_workflow = session.query(Workflow).filter_by(id=workflow_id).first()
            
            assert retrieved_workflow is not None
            assert retrieved_workflow.workflow_info == workflow_info
            assert retrieved_workflow.run_id == run_id
            assert len(retrieved_workflow.steps) == len(step_types)
            
            # Verify steps
            for i, step in enumerate(sorted(retrieved_workflow.steps, key=lambda s: s.round)):
                expected_type, expected_info = created_steps[i]
                assert step.step_type == expected_type
                assert step.step_info == expected_info
                assert step.round == i + 1
            
            # Verify run relationship
            retrieved_run = session.query(Runs).filter_by(id=run_id).first()
            assert retrieved_run is not None
            assert len(retrieved_run.workflows) == 1
            assert retrieved_run.workflows[0].id == workflow_id
    
    @settings(max_examples=50)
    @given(
        run_type=st.sampled_from(["workflow", "agent"]),
        status=st.sampled_from(["running", "success", "failed", None]),
        info=st.dictionaries(
            keys=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('L',))),
            values=st.text(min_size=0, max_size=50),
            min_size=0,
            max_size=5,
        ),
    )
    def test_runs_data_preservation(
        self,
        run_type: str,
        status: Optional[str],
        info: Dict[str, Any],
    ):
        """
        Property: For any valid runs data,
        storing and retrieving should preserve all fields.
        
        **Validates: Requirements 10.1, 10.2**
        """
        with create_test_session() as session:
            run_id = uuid.uuid4()
            run = Runs(
                id=run_id,
                type=run_type,
                info=info,
                status=status,
            )
            session.add(run)
            session.commit()
            
            # Retrieve and verify
            retrieved_run = session.query(Runs).filter_by(id=run_id).first()
            
            assert retrieved_run is not None
            assert retrieved_run.type == run_type
            assert retrieved_run.info == info
            assert retrieved_run.status == status
