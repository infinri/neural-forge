# /persistent-generate
1. If no DAG tasks, derive tasks from PLAN.md using enqueue_task.
2. Loop:
   - get_next_task → search_memory (scoped context)
   - Implement code; run tests
   - On failure: log_error and fix; repeat
   - save_diff; update_task_status=Done
