# Progress Monitor — 3 Approaches

> Cron job that watches this project, detects stalls, and kicks things back into motion.
> Context: multi-agent platform in early Phase 1. Plan lives in PLAN.md.
> Choose one approach and I'll implement it.

---

## Approach 1 — "The Foreman"
### Lightweight diff-watcher + direct agent kick

**Concept:** A dead-simple cron job that checks git diff + file mtimes. If nothing
meaningful has changed in N hours, it fires a focused `agentTurn` prompt to me (Donna)
with a precise summary of what the plan says should exist vs what actually does.
No state machine, no fancy scoring — just diffs and a clear "here's the gap, continue."

**How it works:**
```
Every 2 hours:
  1. git diff --stat HEAD (what changed since last commit)
  2. compare PLAN.md Phase 1 checklist against actual files on disk
  3. run test_models.py --quick (just import check, <5s)
  4. write progress.json: {last_active, completed_files, gaps, test_status}
  5. if (now - last_active > 2h) AND gaps exist:
       → fire agentTurn to Donna: "Project stalled. Gaps: [...]. Continue Phase 1."
  6. else: HEARTBEAT_OK
```

**State file (`progress.json`):**
```json
{
  "last_commit": "bc5c36f",
  "last_change_at": "2026-03-22T18:00:00Z",
  "phase": 1,
  "completed": ["config/models.yaml", "src/agents/model_factory.py"],
  "gaps": ["src/agents/team_loader.py", "config/teams/deep-research.yaml"],
  "test_status": "pass",
  "stall_count": 0,
  "last_notified_at": null
}
```

**Stall handling:** After 3 consecutive stalls with no progress → escalates to a
longer, more detailed prompt that re-reads PLAN.md and produces a full implementation
plan for the next step, not just a nudge.

**Pros:**
- Simplest to implement and reason about
- Very low token cost (most runs are 0 tokens)
- Transparent state you can read anytime
- Stall detection is deterministic (file mtime + git log)

**Cons:**
- Doesn't understand *why* something stalled (blocked vs just not started)
- Can't distinguish "Jeremy is actively working" from "nobody is working"
- Simple gap detection — won't catch partial implementations

**Schedule:** Every 2 hours, isolated agentTurn session.
**Token cost:** ~500 tokens/check when active, ~0 when idle.
**Complexity:** Low — ~80 lines of Python for the state script.

---

## Approach 2 — "The Architect Review"
### Periodic deep-read with LLM quality assessment

**Concept:** Every 4 hours, an isolated subagent gets a *full context dump* —
PLAN.md, all source files, git log, test output — and does a real LLM-based
quality and completeness assessment. Not just "does the file exist" but
"does this file actually implement what the plan calls for?" It produces a
structured JSON report that drives the next steps.

**How it works:**
```
Every 4 hours:
  1. Collect context bundle:
     - PLAN.md (full)
     - git log --stat last 20 commits
     - all .py files in src/agents/ (when they exist)
     - last test_models.py run output
     - current progress.json

  2. Fire isolated agentTurn with full bundle:
     "You are an engineering lead reviewing this project against its plan.
      Read the PLAN.md and all source files. For each Phase 1 item, assess:
      - EXISTS: file/feature is present
      - PARTIAL: exists but incomplete
      - MISSING: not started
      Produce a JSON report. Then continue the highest-priority MISSING item."

  3. Agent writes assessment to progress_report_{date}.md
  4. Agent implements the next item
  5. If agent can't continue (needs human input/decision): 
     → message Jeremy with specific blocker question
  6. After implementation: run test_models.py, update progress.json
```

**Assessment report format:**
```json
{
  "assessed_at": "2026-03-22T20:00:00Z",
  "phase": 1,
  "phase_completion": 0.3,
  "items": [
    {"name": "config/models.yaml", "status": "EXISTS", "quality": "good", "notes": ""},
    {"name": "src/agents/model_factory.py", "status": "PARTIAL", "quality": "skeleton only",
     "notes": "Missing anthropic + openclaw providers"},
    {"name": "src/agents/team_loader.py", "status": "MISSING", "notes": ""},
    {"name": "run.sh --team flag", "status": "MISSING", "notes": ""}
  ],
  "next_action": "Implement src/agents/team_loader.py",
  "blockers": [],
  "message_jeremy": false
}
```

**Blocker escalation:** If the same item appears as PARTIAL for 3+ consecutive
reviews with no improvement → treats it as a blocker, messages Jeremy:
"team_loader.py has been partial for 3 reviews. Need decision: [specific question]."

**Pros:**
- Catches partial/broken implementations, not just missing files
- Self-directing: picks the next priority item automatically
- Produces readable progress reports you can track
- LLM can handle ambiguity (e.g. "should this use YAML or TOML?")

**Cons:**
- Higher token cost per check (~3-8k tokens)
- Longer to run (full file read + LLM review = 2-5 min)
- Occasional false positives ("this looks incomplete" when it's intentionally minimal)
- More complex state management

**Schedule:** Every 4 hours, isolated agentTurn.
**Token cost:** ~4,000–8,000 tokens/check.
**Complexity:** Medium — ~150 lines + structured prompt engineering.

---

## Approach 3 — "The Project Manager"
### Stateful task queue + multi-stage loop with human checkpoints

**Concept:** A full project management system with a *persistent task queue*
stored as a JSON file. The cron job is the heartbeat of a mini-PM that:
tracks individual tasks (not just files), assigns them priorities, manages
dependencies between tasks, and runs a multi-turn agent loop to implement
each task fully before moving to the next. Human checkpoints gate phase
transitions.

**How it works:**

**One-time setup:** Parse PLAN.md into a task queue (`tasks.json`):
```json
{
  "project": "multi-agent-platform",
  "current_phase": 1,
  "phases": {
    "1": {
      "name": "Foundation",
      "status": "in_progress",
      "gate": "human_approval",    // must message Jeremy to advance
      "tasks": [
        {
          "id": "p1-t1",
          "name": "Create config/models.yaml",
          "status": "pending",     // pending | in_progress | done | blocked
          "depends_on": [],
          "files": ["config/models.yaml"],
          "acceptance": "file exists, loads with PyYAML, all 14 models present",
          "assigned_session": null,
          "started_at": null,
          "completed_at": null,
          "attempts": 0,
          "notes": ""
        },
        {
          "id": "p1-t2",
          "name": "Create src/agents/model_factory.py",
          "status": "pending",
          "depends_on": ["p1-t1"],
          ...
        }
      ]
    }
  }
}
```

**Cron loop (every 90 minutes):**
```
1. Load tasks.json
2. Find first non-blocked "pending" or "in_progress" task in current phase
3. If in_progress: check if session is still running (sessions_list)
   - still running → HEARTBEAT_OK, check back in 90 min
   - session gone → task timed out → reset to pending, increment attempts
4. If pending (and dependencies met):
   a. Spawn isolated agentTurn with full task context
   b. Prompt: "Implement task: {name}. Acceptance criteria: {acceptance}.
      Files to create: {files}. Related PLAN.md section: {excerpt}.
      When done, write a line to tasks.json marking this task complete."
   c. Store session_id in task
5. After all phase tasks done:
   - message Jeremy: "Phase 1 complete. Ready for Phase 2? Here's what was built: [summary]"
   - wait for human approval before starting Phase 2
6. Max 3 attempts per task → mark BLOCKED, message Jeremy with specific error
```

**Task handoff:** Each completed task writes a `task_output_{id}.md` with what
was built + decisions made. Next task gets this as context. Creates an audit trail.

**Recovery:** If a task fails (syntax error, test fails), the review loop:
1. Reads the error output
2. Spawns a fix-it agent with the error + current file
3. Reruns tests
4. Max 2 fix attempts before escalating to human

**Pros:**
- Most robust — can handle multi-day projects with interruptions
- Full audit trail of what was built, why, by which session
- Phase gates mean you stay in control of major transitions
- Task dependency graph prevents out-of-order execution
- Each task is a focused, bounded prompt — better LLM output

**Cons:**
- Most complex to set up (~300 lines of orchestration code)
- Overkill if you're also actively working on the project yourself
- Phase gates require your attention to advance
- tasks.json can get stale if you manually edit files

**Schedule:** Every 90 minutes, isolated agentTurn.
**Token cost:** ~2,000–5,000 tokens/check, larger bursts on task execution.
**Complexity:** High — full mini-PM system.

---

## Summary Table

| | Approach 1: Foreman | Approach 2: Architect | Approach 3: PM |
|---|---|---|---|
| **Stall detection** | File mtimes + git | LLM code review | Task queue state |
| **Action on stall** | Nudge prompt | Full review + continue | Task execution loop |
| **Human interaction** | Notify on stall | Notify on blockers | Phase gates + blockers |
| **Token cost** | ~500/check | ~6k/check | ~3k/check |
| **Phase gates** | No | No | Yes |
| **Audit trail** | progress.json | progress_report_*.md | tasks.json + output files |
| **Handles partial code** | No | Yes (LLM review) | Yes (acceptance criteria) |
| **Can resume mid-task** | Limited | Limited | Yes (session tracking) |
| **Setup complexity** | Low | Medium | High |
| **Best if...** | You're actively involved | You want quality checks | You want full autonomy |

---

## My Recommendation

**If you're going to be around and checking in:** → Approach 1 (Foreman)
**If you want it to just keep building while you're away:** → Approach 3 (PM)
**If you want code quality assurance on top of progress:** → Approach 2 (Architect)

Pick one and I'll implement it completely — cron job, state script, prompts, the works.
