"""Agent orchestrator - main agent loop."""

import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.agent_runtime.state import AgentStage, RunState
from backend.agent_runtime.events import (
    emit_stage_started,
    emit_stage_completed,
    emit_tool_called,
    emit_tool_completed,
    emit_policy_rejected,
    emit_plan_created,
    emit_action_executed,
    emit_replan_started,
)
from backend.agent_runtime.provider import LLMProvider, MockLLMProvider
from backend.agents.diagnosis import diagnose_failure
from backend.agents.candidate_generator import generate_candidates
from backend.agents.planner import create_recovery_plan
from backend.agents.replanner import replan
from backend.tools.registry import tool_registry
from backend.policy.validator import validate_plan
from backend.executor.executor import execute_recovery_action
from backend.db.models import AgentRun


class AgentOrchestrator:
    """Main agent orchestration loop."""
    
    def __init__(self, llm_provider: Optional[LLMProvider] = None):
        self.llm = llm_provider or MockLLMProvider()
    
    async def run(
        self,
        session: AsyncSession,
        order_id: str,
        trigger_event_id: Optional[str] = None,
    ) -> RunState:
        """Run the agent for an order."""
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        state = RunState(run_id=run_id, order_id=order_id)
        
        # Create agent_run record
        agent_run = AgentRun(
            run_id=run_id,
            order_id=order_id,
            status="running",
            current_stage=AgentStage.RECEIVED.value,
        )
        session.add(agent_run)
        await session.flush()
        
        try:
            # Stage 1: Context Loading
            state = await self._run_context_loading(session, state)
            
            # Stage 2: Diagnosis
            state = await self._run_diagnosis(session, state)
            
            # Stage 3: Candidate Generation
            state = await self._run_candidate_generation(session, state)
            
            # Stage 4: Counterfactual Evaluation
            state = await self._run_counterfactual_evaluation(session, state)
            
            # Stage 5: Planning
            state = await self._run_planning(session, state)
            
            # Stage 6: Safety Check
            state = await self._run_safety_check(session, state)
            
            if not state.safety_result or not state.safety_result.get("approved", False):
                # Replanning loop
                max_replans = 3
                while state.replan_count < max_replans:
                    state = await self._run_replanning(session, state)
                    state = await self._run_safety_check(session, state)
                    if state.safety_result and state.safety_result.get("approved", False):
                        break
                
                if not (state.safety_result and state.safety_result.get("approved", False)):
                    state.status = "failed"
                    state.final_reason = "Max replan attempts exceeded"
                    await self._complete_run(session, agent_run, state)
                    return state
            
            # Stage 7: Execution
            state = await self._run_execution(session, state)
            
            # Stage 8: Waiting for Outcome (simplified - completes immediately)
            state.current_stage = AgentStage.WAITING_FOR_OUTCOME
            state.status = "completed"
            state.completed_at = datetime.now(timezone.utc)
            
            await self._complete_run(session, agent_run, state)
            return state
            
        except Exception as e:
            state.status = "failed"
            state.error = str(e)
            state.final_reason = f"Agent error: {e}"
            await self._complete_run(session, agent_run, state)
            raise
    
    async def _run_context_loading(self, session: AsyncSession, state: RunState) -> RunState:
        start = time.time()
        state.current_stage = AgentStage.CONTEXT_LOADING
        await emit_stage_started(session, state.run_id, state.order_id, AgentStage.CONTEXT_LOADING, {})
        
        # Call get_order_context tool
        await emit_tool_called(session, state.run_id, state.order_id, AgentStage.CONTEXT_LOADING, "get_order_context", {"order_id": state.order_id})
        context = await tool_registry.call("get_order_context", order_id=state.order_id)
        await emit_tool_completed(session, state.run_id, state.order_id, AgentStage.CONTEXT_LOADING, "get_order_context", context, int((time.time() - start) * 1000))
        
        state.context = context
        await emit_stage_completed(session, state.run_id, state.order_id, AgentStage.CONTEXT_LOADING, {"context_loaded": True}, int((time.time() - start) * 1000))
        return state
    
    async def _run_diagnosis(self, session: AsyncSession, state: RunState) -> RunState:
        start = time.time()
        state.current_stage = AgentStage.DIAGNOSING
        await emit_stage_started(session, state.run_id, state.order_id, AgentStage.DIAGNOSING, {"context": state.context})
        
        diagnosis = await diagnose_failure(self.llm, state.context)
        state.diagnosis = diagnosis
        
        await emit_stage_completed(session, state.run_id, state.order_id, AgentStage.DIAGNOSING, diagnosis, int((time.time() - start) * 1000))
        return state
    
    async def _run_candidate_generation(self, session: AsyncSession, state: RunState) -> RunState:
        start = time.time()
        state.current_stage = AgentStage.GENERATING_CANDIDATES
        await emit_stage_started(session, state.run_id, state.order_id, AgentStage.GENERATING_CANDIDATES, {"diagnosis": state.diagnosis})
        
        # Get allowed actions from policy
        await emit_tool_called(session, state.run_id, state.order_id, AgentStage.GENERATING_CANDIDATES, "get_allowed_actions", {"order_id": state.order_id})
        allowed = await tool_registry.call("get_allowed_actions", order_id=state.order_id)
        await emit_tool_completed(session, state.run_id, state.order_id, AgentStage.GENERATING_CANDIDATES, "get_allowed_actions", {"allowed_actions": allowed}, int((time.time() - start) * 1000))
        
        candidates = await generate_candidates(self.llm, state.diagnosis, allowed)
        state.candidates = candidates
        
        await emit_stage_completed(session, state.run_id, state.order_id, AgentStage.GENERATING_CANDIDATES, {"candidates": candidates}, int((time.time() - start) * 1000))
        return state
    
    async def _run_counterfactual_evaluation(self, session: AsyncSession, state: RunState) -> RunState:
        start = time.time()
        state.current_stage = AgentStage.EVALUATING_COUNTERFACTUALS
        await emit_stage_started(session, state.run_id, state.order_id, AgentStage.EVALUATING_COUNTERFACTUALS, {"candidates": state.candidates})
        
        counterfactuals = []
        for candidate in state.candidates:
            action = candidate["action"]
            await emit_tool_called(session, state.run_id, state.order_id, AgentStage.EVALUATING_COUNTERFACTUALS, "estimate_recovery", {"order_id": state.order_id, "action": action})
            result = await tool_registry.call("estimate_recovery", order_id=state.order_id, action=action)
            await emit_tool_completed(session, state.run_id, state.order_id, AgentStage.EVALUATING_COUNTERFACTUALS, "estimate_recovery", result, int((time.time() - start) * 1000))
            counterfactuals.append({"action": action, **result})
        
        state.counterfactuals = counterfactuals
        await emit_stage_completed(session, state.run_id, state.order_id, AgentStage.EVALUATING_COUNTERFACTUALS, {"counterfactuals": counterfactuals}, int((time.time() - start) * 1000))
        return state
    
    async def _run_planning(self, session: AsyncSession, state: RunState) -> RunState:
        start = time.time()
        state.current_stage = AgentStage.PLANNING
        await emit_stage_started(session, state.run_id, state.order_id, AgentStage.PLANNING, {"diagnosis": state.diagnosis, "counterfactuals": state.counterfactuals})
        
        plan = await create_recovery_plan(self.llm, state.diagnosis, state.counterfactuals)
        state.plan = plan
        
        await emit_plan_created(session, state.run_id, state.order_id, plan)
        await emit_stage_completed(session, state.run_id, state.order_id, AgentStage.PLANNING, plan, int((time.time() - start) * 1000))
        return state
    
    async def _run_safety_check(self, session: AsyncSession, state: RunState) -> RunState:
        start = time.time()
        state.current_stage = AgentStage.SAFETY_CHECK
        await emit_stage_started(session, state.run_id, state.order_id, AgentStage.SAFETY_CHECK, {"plan": state.plan})
        
        if not state.plan:
            state.safety_result = {"approved": False, "reason": "No plan generated"}
            await emit_policy_rejected(session, state.run_id, state.order_id, "none", "No plan generated")
            return state
        
        validation = await validate_plan(session, state.plan, state.order_id)
        state.safety_result = {
            "approved": validation.approved,
            "reason": validation.reason,
            "filtered_steps": validation.filtered_steps,
        }
        
        if not validation.approved:
            await emit_policy_rejected(session, state.run_id, state.order_id, state.plan.get("steps", [{}])[0].get("action", "unknown"), validation.reason or "Unknown")
        else:
            await emit_stage_completed(session, state.run_id, state.order_id, AgentStage.SAFETY_CHECK, state.safety_result, int((time.time() - start) * 1000))
        
        return state
    
    async def _run_execution(self, session: AsyncSession, state: RunState) -> RunState:
        start = time.time()
        state.current_stage = AgentStage.EXECUTING
        await emit_stage_started(session, state.run_id, state.order_id, AgentStage.EXECUTING, {"plan": state.plan})
        
        if not state.plan or not state.plan.get("steps"):
            state.execution_result = {"success": False, "reason": "No steps in plan"}
            return state
        
        # Execute first step (simplified - real impl would handle multi-step)
        first_step = state.plan["steps"][0]
        action = first_step.get("action")
        
        if action:
            result = await execute_recovery_action(session, state.order_id, action)
            state.execution_result = {
                "success": result.success,
                "action_id": result.action_id,
                "reason": result.reason,
            }
            state.final_action = action
            state.final_reason = result.reason or "Executed"
            
            await emit_action_executed(session, state.run_id, state.order_id, action, state.execution_result)
        
        await emit_stage_completed(session, state.run_id, state.order_id, AgentStage.EXECUTING, state.execution_result, int((time.time() - start) * 1000))
        return state
    
    async def _run_replanning(self, session: AsyncSession, state: RunState) -> RunState:
        start = time.time()
        state.replan_count += 1
        state.current_stage = AgentStage.REPLANNING
        
        rejection_reason = state.safety_result.get("reason") if state.safety_result else "Unknown rejection"
        await emit_replan_started(session, state.run_id, state.order_id, rejection_reason)
        
        new_plan = await replan(self.llm, state.diagnosis, state.counterfactuals, rejection_reason)
        state.plan = new_plan
        
        await emit_stage_completed(session, state.run_id, state.order_id, AgentStage.REPLANNING, new_plan, int((time.time() - start) * 1000))
        return state
    
    async def _complete_run(self, session: AsyncSession, agent_run: AgentRun, state: RunState):
        agent_run.status = state.status
        agent_run.current_stage = state.current_stage.value
        agent_run.completed_at = state.completed_at or datetime.now(timezone.utc)
        agent_run.final_action = state.final_action
        agent_run.final_reason = state.final_reason
        await session.flush()


async def run_agent(
    session: AsyncSession,
    order_id: str,
    llm_provider: Optional[LLMProvider] = None,
) -> RunState:
    """Convenience function to run agent."""
    orchestrator = AgentOrchestrator(llm_provider)
    return await orchestrator.run(session, order_id)