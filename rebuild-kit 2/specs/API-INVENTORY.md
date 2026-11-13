# API 위치 색인

세부 입력/출력·권한은 해당 라우터와 서비스, 기존 명세를 확인한다.

## approvals.py

- GET /inbox → inbox (line 14)
- POST /{approval_id}/decision → decision (line 19)
- GET /history → history (line 24)

## auth.py

- POST /login → login (line 19)
- POST /otp/verify → otp_verify (line 24)
- POST /register → register (line 29)
- POST /logout → logout (line 34)
- GET /me → me (line 40)
- POST /demo-role → demo_role (line 53)

## chat.py

- POST /chat/feedback → feedback (line 37)
- POST /chat → chat (line 51)

## chat_report.py

- GET /report/options → report_options (line 24)
- POST /report → create_report (line 31)
- GET /reports/{report_id} → download_report (line 40)

## dashboard.py

- GET /summary → summary (line 11)

## drawings.py

- GET  → list_drawings (line 17)
- POST  → create (line 23)
- GET /{drawing_id} → detail (line 28)
- PATCH /{drawing_id} → update (line 33)
- DELETE /{drawing_id} → delete (line 38)
- GET /{drawing_id}/revisions → revisions (line 44)
- POST /{drawing_id}/revisions → new_revision (line 50)
- POST /{drawing_id}/revisions/{rev_no}/pdf → upload_pdf (line 55)
- GET /{drawing_id}/revisions/{rev_no}/pdf → get_pdf (line 63)
- DELETE /{drawing_id}/revisions/{rev_no}/pdf → delete_pdf (line 70)
- POST /{drawing_id}/revisions/{rev_no}/request-approval → request_approval (line 75)
- POST /{drawing_id}/revisions/{rev_no}/issue → issue (line 80)
- GET /{drawing_id}/plans → drawing_plans (line 85)
- POST /{drawing_id}/plans → link_plan (line 90)
- DELETE /{drawing_id}/plans/{plan_id} → unlink_plan (line 96)

## hulls.py

- GET /hulls → list_hulls (line 14)
- POST /hulls → create_hull (line 20)
- GET /hulls/{hull_no} → get_hull (line 25)
- PATCH /hulls/{hull_no} → update_hull (line 30)
- DELETE /hulls/{hull_no} → delete_hull (line 35)
- GET /hulls/{hull_no}/milestones → milestones (line 41)
- PUT /hulls/{hull_no}/milestones → save_milestones (line 46)
- GET /hulls/{hull_no}/blocks → blocks (line 51)
- POST /hulls/{hull_no}/blocks → create_block (line 56)
- DELETE /blocks/{block_id} → delete_block (line 61)
- GET /hulls/{hull_no}/summary → summary (line 67)

## plans.py

- GET /procs → procs (line 14)
- GET /plan-hulls → plan_hulls (line 19)
- GET /hulls/{hull_no}/plans → gantt (line 24)
- POST /hulls/{hull_no}/plans → create_plan (line 29)
- GET /plans/{plan_id} → get_plan (line 34)
- PATCH /plans/{plan_id} → update_plan (line 39)
- PATCH /plans/{plan_id}/schedule → reschedule (line 46)
- DELETE /plans/{plan_id} → delete_plan (line 51)
- PUT /plans/{plan_id}/predecessors → set_preds (line 57)
- GET /plans/{plan_id}/drawings → plan_drawings (line 62)
- POST /plans/{plan_id}/drawings → link_drawing (line 67)
- DELETE /plans/{plan_id}/drawings/{drawing_id} → unlink_drawing (line 73)

## progress.py

- GET /progress-hulls → progress_hulls (line 14)
- GET /hulls/{hull_no}/progress-targets → targets (line 19)
- GET /plans/{plan_id}/progress → plan_progress (line 24)
- PUT /plans/{plan_id}/progress/{work_dt} → save (line 29)
- DELETE /progress/{progress_id} → delete (line 34)

## shell.py

- GET /health → health (line 12)
- GET /me/menu → my_menu (line 17)
- POST /me/menu-access → menu_access (line 22)
- GET /weather → weather (line 28)
- GET /codes → codes (line 33)
- GET /users/options → user_options (line 38)

## usage.py

- GET /usage/summary → usage_summary (line 16)
- GET /inquiries → list_inquiries (line 21)
- POST /inquiries → create_inquiry (line 26)
- GET /inquiries/{inquiry_id} → get_inquiry (line 31)
- PATCH /inquiries/{inquiry_id} → update_inquiry (line 36)
- DELETE /inquiries/{inquiry_id} → delete_inquiry (line 41)

## users.py

- GET /users → list_users (line 14)
- POST /users → create_user (line 19)
- GET /users/{emp_no} → get_user (line 24)
- PATCH /users/{emp_no} → update_user (line 29)
- DELETE /users/{emp_no} → delete_user (line 34)
- GET /users/{emp_no}/menus → user_menus (line 40)
- PUT /users/{emp_no}/menus → set_user_menus (line 45)
- POST /users/{emp_no}/approve → approve (line 50)
- POST /users/{emp_no}/reject → reject (line 55)
- GET /auth-groups → auth_groups (line 60)
