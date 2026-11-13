-- 회원별 메뉴 권한(명세 외 요청 기능). 행이 있으면 그 메뉴는 그룹 권한 대신 이 값을 쓴다. None = 접근 불가.
CREATE TABLE TB_SYS_UserMenu (
    EmpNo TEXT NOT NULL REFERENCES users(emp_no) ON DELETE CASCADE,
    MenuId TEXT NOT NULL REFERENCES TB_SYS_MenuInfo(MenuId) ON DELETE CASCADE,
    AuthGbn TEXT NOT NULL CHECK (AuthGbn IN ('None','View','Write','Admin')),
    PRIMARY KEY (EmpNo, MenuId)
);
