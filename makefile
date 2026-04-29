.PHONY: evaluate

evaluate-train-YJYB:
	@uv run python -m scripts.run_evaluator examples/extract.py resources/YJYB --type train --keys '本期扣非前净利润上限（万元）'

evaluate-test-YJYB:
	@uv run python -m scripts.run_evaluator local/GDDH/YJYB_上限.py resources/YJYB --type test --keys '本期扣非前净利润上限（万元）'

evaluate-test-GDDH:
	@uv run python -m scripts.run_evaluator local/GDDH/GDDH_address.py resources/GDDH --type test --keys '会议召开地点'

evaluate-test-GDDH-A股股东资格登记日期:
	@uv run python -m scripts.run_evaluator local/GDDH/GDDH_A股股东资格登记日期.py resources/GDDH --type test --keys 'A股股东资格登记日期'

evaluate-test-GDDH-code:
	@uv run python -m scripts.run_evaluator local/GDDH/GDDH_code.py resources/GDDH --type test --keys '股东大会类别编码'

evaluate-test-GDDH-Chapter:
	@uv run python -m scripts.run_evaluator local/GDDH/GDDH_address_chapter.py resources/GDDH --type test --keys '会议召开地点'

run-batch:
	@uv run python main.py --data-path ./resources/YJYB --batch

show-graph:
	@uv run python -m extract_agent.app --show-graph
	
run-app-gddh:
	@uv run python -m extract_agent.app --data-path resources/GDDH --init-program examples/extract_raw_GDDH.py --keys 'A股股东资格登记日期' --target-accuracy 0.9999

run-app-yab:
	@uv run python -m extract_agent.app --data-path resources/YAB --init-program examples/extract_raw_GDDH.py --target-accuracy 0.9999

run-flow:
	@-pkill -f 'uv run python -m extract_agent\.app'
	@-rm local/.run-flow.pid
	@-rm local/.run-flow.log
	@nohup uv run python -m extract_agent.app --data-path ./resources/YJYB --init-program examples/extract_raw.py > local/.run-flow.log 2>&1 &
	@tail -f local/.run-flow.log


stop-flow:
	@-pkill -f 'uv run python -m extract_agent\.app'

sync-skills:
	@echo "$(BLUE)同步OpenSkills...$(NC)"
	npx openskills sync -y -o docs/project-rules.md
	@echo "$(GREEN)✓ OpenSkills已同步$(NC)"


agent-index: ## 同步项目规则到Agent上下文文件
	@echo "$(BLUE)同步项目规则到Agent上下文...$(NC)"
	@mkdir -p .agents
	@cp docs/project-rules.md .agents/project-rules.md
	@echo "$(GREEN)✓ 项目规则已同步$(NC)"
	@echo "  - .agents/project-rules.md"
