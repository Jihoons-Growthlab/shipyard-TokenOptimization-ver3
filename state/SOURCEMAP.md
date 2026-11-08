<!-- srcmap:e1a90e3ab5b4 -->
# SOURCEMAP (scripts/wf.py srcmap가 생성. 직접 고치지 않는다)
## API (openapi)
GET /api/health
GET /api/me/menu
POST /api/me/menu-access body=MenuAccessIn
GET /api/weather ?region
GET /api/codes
GET /api/users/options
POST /api/auth/login body=LoginIn
POST /api/auth/otp/verify body=OtpIn
POST /api/auth/register body=MemberIn
POST /api/auth/logout
GET /api/auth/me
GET /api/hulls ?status,ship_type,q
POST /api/hulls body=HullIn
GET /api/hulls/{hull_no}
PATCH /api/hulls/{hull_no} body=HullIn
DELETE /api/hulls/{hull_no}
GET /api/hulls/{hull_no}/milestones
PUT /api/hulls/{hull_no}/milestones body=MilestonesIn
GET /api/hulls/{hull_no}/blocks
POST /api/hulls/{hull_no}/blocks body=BlockIn
DELETE /api/blocks/{block_id}
GET /api/hulls/{hull_no}/summary
GET /api/procs
GET /api/plan-hulls
GET /api/hulls/{hull_no}/plans ?block_id
POST /api/hulls/{hull_no}/plans body=PlanIn
GET /api/plans/{plan_id}
PATCH /api/plans/{plan_id} body=PlanIn
DELETE /api/plans/{plan_id}
PUT /api/plans/{plan_id}/predecessors body=PredsIn
GET /api/plans/{plan_id}/drawings
POST /api/plans/{plan_id}/drawings body=LinkDrawingIn
DELETE /api/plans/{plan_id}/drawings/{drawing_id}
GET /api/progress-hulls
GET /api/hulls/{hull_no}/progress-targets ?include_done
GET /api/plans/{plan_id}/progress
PUT /api/plans/{plan_id}/progress/{work_dt} body=ProgressIn
DELETE /api/progress/{progress_id}
GET /api/drawings ?hull_no,discipline,status,q
POST /api/drawings body=DrawingIn
GET /api/drawings/{drawing_id}
PATCH /api/drawings/{drawing_id} body=DrawingIn
DELETE /api/drawings/{drawing_id}
GET /api/drawings/{drawing_id}/revisions
POST /api/drawings/{drawing_id}/revisions body=RevisionIn
POST /api/drawings/{drawing_id}/revisions/{rev_no}/pdf ?filename
GET /api/drawings/{drawing_id}/revisions/{rev_no}/pdf
DELETE /api/drawings/{drawing_id}/revisions/{rev_no}/pdf
POST /api/drawings/{drawing_id}/revisions/{rev_no}/request-approval body=ApprovalRequestIn
POST /api/drawings/{drawing_id}/revisions/{rev_no}/issue
GET /api/drawings/{drawing_id}/plans
POST /api/drawings/{drawing_id}/plans body=LinkPlanIn
DELETE /api/drawings/{drawing_id}/plans/{plan_id}
GET /api/approvals/inbox
POST /api/approvals/{approval_id}/decision body=DecisionIn
GET /api/approvals/history
GET /api/users ?status,q
POST /api/users body=UserIn
GET /api/users/{emp_no}
PATCH /api/users/{emp_no} body=UserIn
DELETE /api/users/{emp_no}
POST /api/users/{emp_no}/approve body=ApproveIn
POST /api/users/{emp_no}/reject
GET /api/auth-groups
GET /api/dashboard/summary
## Python
backend/app/config.py: today, db_path, file_dir, app_secret, token_ttl, otp_token_ttl, weather_provider
backend/app/db.py: connect, tx, migrate, get_db, rows, one, scalar
backend/app/deps.py: token_payload, current_user, require
backend/app/errors.py: ApiError, bad, not_found, conflict, duplicate, forbidden, unauthorized, install
backend/app/routers/approvals.py: inbox, decision, history
backend/app/routers/auth.py: login, otp_verify, register, logout, me
backend/app/routers/dashboard.py: summary
backend/app/routers/drawings.py: list_drawings, create, detail, update, delete, revisions, new_revision, upload_pdf, get_pdf, delete_pdf, request_approval, issue, drawing_plans, link_plan, unlink_plan
backend/app/routers/hulls.py: list_hulls, create_hull, get_hull, update_hull, delete_hull, milestones, save_milestones, blocks, create_block, delete_block, summary
backend/app/routers/plans.py: procs, plan_hulls, gantt, create_plan, get_plan, update_plan, delete_plan, set_preds, plan_drawings, link_drawing, unlink_drawing
backend/app/routers/progress.py: progress_hulls, targets, plan_progress, save, delete
backend/app/routers/shell.py: health, my_menu, menu_access, weather, codes, user_options
backend/app/routers/users.py: list_users, create_user, get_user, update_user, delete_user, approve, reject, auth_groups
backend/app/schemas.py: Str, In, LoginIn, OtpIn, MemberIn, UserIn, ApproveIn, MenuAccessIn, HullIn, MilestoneItem, MilestonesIn, BlockIn, PlanIn, PredsIn, LinkDrawingIn, LinkPlanIn, ProgressIn, DrawingIn, RevisionIn, ApprovalRequestIn, DecisionIn
backend/app/security.py: hash_password, verify_password, make_token, decode_token, totp, current_step, otp_locked, check_otp, reset_state
backend/app/seed.py: load_seed, main
backend/app/services/approvals.py: waiting, ready, inbox, decide, history
backend/app/services/auth.py: me, login, verify_otp, logout, register
backend/app/services/common.py: is_date, now_utc, act_dt, blank, clean, codes, code_map, check_code, user_name, check_approved, user_options, menu_level, hull_exists
backend/app/services/dashboard.py: summary
backend/app/services/drawings.py: item_out, list_drawings, revisions, detail, create, update, delete, new_revision, request_approval, issue, sanitize_filename, upload_pdf, pdf_path, delete_pdf, drawing_plans
backend/app/services/hulls.py: get_hull_row, hull_out, list_hulls, get_hull, create_hull, update_hull, delete_hull, milestones, save_milestones, blocks, create_block, delete_block, summary
backend/app/services/members.py: normalize_phone, validate_member, groups_of, user_out
backend/app/services/plans.py: sort_key, plan_out, hull_plans, get_plan_row, get_plan, procs, plan_hulls, gantt, create_plan, update_plan, set_predecessors, delete_plan, get_drawing_row, add_link, remove_link, plan_drawings, default_new_plan
backend/app/services/progress.py: progress_hulls, targets, plan_progress, save, delete
backend/app/services/rules.py: period_days, weighted_progress, plan_label, blockers_by_plan, preds_by_plan, plan_status, recalc_hull, recalc_hulls, impacts, file_path, remove_files
backend/app/services/shell.py: my_menu, log_menu_access, weather
backend/app/services/users.py: get_user, list_users, auth_groups, create_user, update_user, approve, reject, delete_user
## Vue (props/emits/scoped css)
frontend/src/App.vue: props[] emits[]
frontend/src/components/AppModal.vue: props[title,size] emits[close]
frontend/src/components/DrawingFields.vue: props[model,hulls,users,edit,readonly,current] emits[]
frontend/src/components/PageHead.vue: props[title,desc,readonly] emits[]
frontend/src/components/ProgressBar.vue: props[value] emits[]
frontend/src/components/ShipViewer3D.vue: props[options] emits[] css[card fail guide model ovl pbar side ucanvas v3d viewer views why]
frontend/src/components/StatusBadge.vue: props[group,code] emits[]
frontend/src/components/ToastHost.vue: props[] emits[]
frontend/src/components/WeatherWidget.vue: props[] emits[] css[live sample src temp wx]
frontend/src/screens/ApprovalScreen.vue: props[token,param,ctx,canWrite,title] emits[] css[acts btn cmt]
frontend/src/screens/DashboardScreen.vue: props[token,param,ctx,canWrite,title] emits[] css[card disc donut ds dt ell err grid3 hbar hp kpi kpis legend li ml mon months muted mv none row stack warn]
frontend/src/screens/DrawingDetail.vue: props[drawingId,canWrite] emits[close,changed] css[act cnt dd ell fixed fn grow imp meta psel rsel rv sample side t vbody vfile viewer vtool]
frontend/src/screens/DrawingListScreen.vue: props[token,param,ctx,canWrite,title] emits[] css[dsel fq hsel mdesc total]
frontend/src/screens/HullDetail.vue: props[hullNo,canWrite] emits[close,changed] css[addrow card fs mdesc pcell sum]
frontend/src/screens/HullListScreen.vue: props[token,param,ctx,canWrite,title] emits[] css[fq fsel pcell total]
frontend/src/screens/PlaceholderScreen.vue: props[token,param,ctx,canWrite,title] emits[]
frontend/src/screens/PlanGanttScreen.vue: props[token,param,ctx,canWrite,title] emits[] css[bc bsel dw gbar gbody gcorner gdeps gempty ghead ginner glabel glayer gm gml gmonths grow gsel gtoday gtrack gwrap h66 hp hsel legend links lrow ltitle on panel pbody pf pg phd pmeta prow ssel toolbar w2 w3]
frontend/src/screens/ProgressScreen.vue: props[token,param,ctx,canWrite,title] emits[] css[del detail hsel pcell]
frontend/src/screens/UserMgmtScreen.vue: props[token,param,ctx,canWrite,title] emits[] css[bottom cnt fq ssel top um]
frontend/src/views/LoginView.vue: props[] emits[] css[acard af auth dim err eyebrow foot glow go grid2 headline intro logo otp scene sub wide]
frontend/src/views/ShellView.vue: props[] emits[] css[body brand closeall grow grp hbtn hdr main menu mi mtitle on screen shell sub tab tabbar who work x]
## JS exports
frontend/src/api/client.js: TOKEN_KEY, ApiError, tokenStore, onUnauthorized, request, api
frontend/src/router.js: router
frontend/src/screens/index.js: screens
frontend/src/stores/session.js: session, loadSession, clearSession, menuByToken, codeList, codeName, userLabel, toasts, toast, fail
frontend/src/stores/tabs.js: TABS_KEY, MAX_TABS, LIMIT_MSG, DENY_MSG, tabKey, createTabs
frontend/src/utils/date.js: parseD, fmtD, addDays, diffDays, dash, numOrNull, blankNull
frontend/src/utils/drawing.js: PDF_MAX, PDF_TYPE_MSG, PDF_SIZE_MSG, checkPdf, uploadPdf, loadHullOptions, loadBlocks, STEP_NM, RESULT_BADGE, revText, fileLine
frontend/src/utils/gantt.js: LEFT, ROW, HEAD, SCALES, ganttLayout, depPaths
frontend/src/utils/unityViewer.js: BUILD_BASE, NOT_FOUND_MSG, TIMEOUT_MSG, LOADER_MSG, READY_EVENT, VIEWS, firstLine, fetchConfig, loadLoader, loseContext, startViewer, __resetForTest
## CSS classes
frontend/src/styles.css: b b-APPROVED b-DELAY b-DONE b-DRAFT b-ISSUED b-OBSOLETE b-PLAN b-READY b-REVIEW b-WORK b-bad b-info b-ok b-warn bar-row btn c2 c4 c6 card chk click danger empty error f fg grow large lnk mbg mbody mclose modal muted note num ok on pbar ph pri r3 ro s2 s3 sall sm subtabs success t toast toasts toolbar tw warn wrap xl
## Unity
unity/ShipyardViewer/Assets/Editor/ViewerBuild.cs: ViewerBuild, Build
unity/ShipyardViewer/Assets/Plugins/WebGL/ShipViewer.jslib: 
unity/ShipyardViewer/Assets/Scripts/ShipModel.cs: ShipModel, HalfWidth, Builder, Add, Tri, Quad, HullMesh, Build
unity/ShipyardViewer/Assets/Scripts/ShipViewer.cs: ShipViewer, SetView
## Tests (count)
backend/tests/conftest.py (0)
backend/tests/helpers.py (0)
backend/tests/test_t01_foundation.py (6)
backend/tests/test_t02_auth.py (10)
backend/tests/test_t03_shell.py (8)
backend/tests/test_t04_hulls.py (11)
backend/tests/test_t05_plans.py (10)
backend/tests/test_t06_progress.py (6)
backend/tests/test_t07_drawings.py (10)
backend/tests/test_t08_approvals.py (8)
backend/tests/test_t09_users.py (9)
backend/tests/test_t10_dashboard.py (8)
