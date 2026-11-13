"""회원별 메뉴 권한(명세 외 요청 기능): 그룹 권한 위에 메뉴 단위로 우선한다."""


def _levels(r):
    return {m["menu_id"]: (m["group_level"], m["user_level"], m["level"]) for m in r["menus"]}


def test_user_menus_override_group(client, auth):
    a = auth("admin")
    r = client.get("/api/users/choi.qa/menus", headers=a).json()
    lv = _levels(r)
    assert lv["M21"] == (1, None, 1) and lv["M91"] == (0, None, 0) and lv["M22"] == (1, None, 1)
    body = {"menus": [{"menu_id": "M21", "level": 2}, {"menu_id": "M22", "level": 0},
                      {"menu_id": "M11", "level": 1}, {"menu_id": "M31", "level": None}]}
    lv = _levels(client.put("/api/users/choi.qa/menus", json=body, headers=a).json())
    # 그룹과 같은 값(M11 읽기)은 저장하지 않고 그룹을 따른다.
    assert lv["M21"] == (1, 2, 2) and lv["M22"] == (1, 0, 0) and lv["M11"] == (1, None, 1) and lv["M31"] == (1, None, 1)
    q = auth("choi.qa")
    menu = {m["menu_id"]: m for m in client.get("/api/me/menu", headers=q).json()}
    assert menu["M21"]["can_write"] is True and "M22" not in menu and menu["M11"]["can_write"] is False
    assert client.get("/api/hulls/8001/plans", headers=q).status_code == 200
    assert client.post("/api/me/menu-access", json={"menu_id": "M22"}, headers=q).status_code == 403
    r = client.patch("/api/plans/1", json={"remark": "권한 테스트"}, headers=q)
    assert r.status_code == 200, r.text
    # 전체 교체: 빈 목록이면 그룹 권한으로 돌아간다.
    lv = _levels(client.put("/api/users/choi.qa/menus", json={"menus": []}, headers=a).json())
    assert lv["M21"] == (1, None, 1)
    assert client.patch("/api/plans/1", json={"remark": "x"}, headers=q).status_code == 403


def test_user_menus_admin_menu_and_validation(client, auth):
    a = auth("admin")
    lv = _levels(client.put("/api/users/park.pm/menus", json={"menus": [{"menu_id": "M90", "level": 1},
                                                                       {"menu_id": "M91", "level": 2}]}, headers=a).json())
    assert lv["M91"] == (0, 2, 2)
    p = auth("park.pm")
    assert client.get("/api/users", headers=p).status_code == 200
    r = client.put("/api/users/park.pm/menus", json={"menus": [{"menu_id": "NOPE", "level": 1}]}, headers=a)
    assert (r.status_code, r.json()["message"]) == (400, "존재하지 않는 메뉴입니다.")
    r = client.put("/api/users/park.pm/menus", json={"menus": [{"menu_id": "M21", "level": 5}]}, headers=a)
    assert (r.status_code, r.json()["message"]) == (400, "허용되지 않는 권한입니다.")
    r = client.put("/api/users/admin/menus", json={"menus": [{"menu_id": "M91", "level": 1}]}, headers=a)
    assert (r.status_code, r.json()["code"]) == (409, "SELF_LOCKOUT")
    assert client.get("/api/users/ghost/menus", headers=a).status_code == 404
    assert client.get("/api/users/park.pm/menus", headers=auth("choi.qa")).status_code == 403
