# Agent Module: Execute

## Goal

Execute only confirmed tasks and report progress continuously.

## Get Next Confirmed Task

Endpoint: `GET /api/v1/tasks/next`

- Returns at most one task
- Queue order is FIFO
- Execute current one before fetching next

## Report Step Progress

Endpoint: `POST /api/v1/tasks/{task_id}/step-progress`

```bash
curl -X POST https://postpneumonic-ungifted-gerry.ngrok-free.dev/api/v1/tasks/TASK_ID/step-progress \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "step_number": 1,
    "status": "in_progress",
    "message": "Analyzing requirements"
  }'
```

Allowed step statuses:

- `in_progress`
- `completed`
- `skipped`

Optional general progress endpoint:

- `POST /api/v1/tasks/{task_id}/progress`
