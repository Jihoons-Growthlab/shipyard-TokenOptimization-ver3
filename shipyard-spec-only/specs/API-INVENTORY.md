# API 계약 색인

경로·입력 스키마는 각 JSON에서 확인한다. 응답 세부와 업무 규칙은 F01~F10 및 DELTA.md가 기준이다. 빈 응답 스키마는 구현 완료를 뜻하지 않는다.

## shell

계약 파일 api/shell.json

- GET /api/health
- GET /api/me/menu
- POST /api/me/menu-access
- GET /api/weather
- GET /api/codes
- GET /api/users/options

## auth

계약 파일 api/auth.json

- POST /api/auth/login
- POST /api/auth/otp/verify
- POST /api/auth/register
- POST /api/auth/logout
- GET /api/auth/me
- POST /api/auth/demo-role

## hulls

계약 파일 api/hulls.json

- GET /api/hulls
- POST /api/hulls
- GET /api/hulls/{hull_no}
- PATCH /api/hulls/{hull_no}
- DELETE /api/hulls/{hull_no}
- GET /api/hulls/{hull_no}/milestones
- PUT /api/hulls/{hull_no}/milestones
- GET /api/hulls/{hull_no}/blocks
- POST /api/hulls/{hull_no}/blocks
- DELETE /api/blocks/{block_id}
- GET /api/hulls/{hull_no}/summary

## plans

계약 파일 api/plans.json

- GET /api/procs
- GET /api/plan-hulls
- GET /api/hulls/{hull_no}/plans
- POST /api/hulls/{hull_no}/plans
- GET /api/plans/{plan_id}
- PATCH /api/plans/{plan_id}
- DELETE /api/plans/{plan_id}
- PATCH /api/plans/{plan_id}/schedule
- PUT /api/plans/{plan_id}/predecessors
- GET /api/plans/{plan_id}/drawings
- POST /api/plans/{plan_id}/drawings
- DELETE /api/plans/{plan_id}/drawings/{drawing_id}

## progress

계약 파일 api/progress.json

- GET /api/progress-hulls
- GET /api/hulls/{hull_no}/progress-targets
- GET /api/plans/{plan_id}/progress
- PUT /api/plans/{plan_id}/progress/{work_dt}
- DELETE /api/progress/{progress_id}

## drawings

계약 파일 api/drawings.json

- GET /api/drawings
- POST /api/drawings
- GET /api/drawings/{drawing_id}
- PATCH /api/drawings/{drawing_id}
- DELETE /api/drawings/{drawing_id}
- GET /api/drawings/{drawing_id}/revisions
- POST /api/drawings/{drawing_id}/revisions
- POST /api/drawings/{drawing_id}/revisions/{rev_no}/pdf
- GET /api/drawings/{drawing_id}/revisions/{rev_no}/pdf
- DELETE /api/drawings/{drawing_id}/revisions/{rev_no}/pdf
- POST /api/drawings/{drawing_id}/revisions/{rev_no}/request-approval
- POST /api/drawings/{drawing_id}/revisions/{rev_no}/issue
- GET /api/drawings/{drawing_id}/plans
- POST /api/drawings/{drawing_id}/plans
- DELETE /api/drawings/{drawing_id}/plans/{plan_id}

## approvals

계약 파일 api/approvals.json

- GET /api/approvals/inbox
- POST /api/approvals/{approval_id}/decision
- GET /api/approvals/history

## users

계약 파일 api/users.json

- GET /api/users
- POST /api/users
- GET /api/users/{emp_no}
- PATCH /api/users/{emp_no}
- DELETE /api/users/{emp_no}
- GET /api/users/{emp_no}/menus
- PUT /api/users/{emp_no}/menus
- POST /api/users/{emp_no}/approve
- POST /api/users/{emp_no}/reject
- GET /api/auth-groups

## dashboard

계약 파일 api/dashboard.json

- GET /api/dashboard/summary

## chat

계약 파일 api/chat.json

- POST /api/chat/feedback
- POST /api/chat
- GET /api/chat/report/options
- POST /api/chat/report
- GET /api/chat/reports/{report_id}

## usage

계약 파일 api/usage.json

- GET /api/usage/summary
- GET /api/inquiries
- POST /api/inquiries
- GET /api/inquiries/{inquiry_id}
- PATCH /api/inquiries/{inquiry_id}
- DELETE /api/inquiries/{inquiry_id}
