-- 사용 로그(API 호출)와 건의·문의(명세 외 요청 기능).
CREATE TABLE TB_SYS_LogApi (
    LogApiId INTEGER PRIMARY KEY AUTOINCREMENT,
    EmpNo TEXT REFERENCES users(emp_no) ON DELETE SET NULL,
    Method TEXT NOT NULL,
    Path TEXT NOT NULL,
    Status INTEGER NOT NULL,
    DurationMs INTEGER NOT NULL,
    CallDt TEXT NOT NULL,
    DemoYN INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX ix_logapi_dt ON TB_SYS_LogApi(CallDt);
CREATE INDEX ix_logapi_emp ON TB_SYS_LogApi(EmpNo, CallDt);

CREATE TABLE TB_SYS_Inquiry (
    InquiryId INTEGER PRIMARY KEY AUTOINCREMENT,
    Category TEXT NOT NULL CHECK (Category IN ('BUG','FEATURE','QUESTION','ETC')),
    Title TEXT NOT NULL,
    Content TEXT NOT NULL,
    Status TEXT NOT NULL DEFAULT 'OPEN' CHECK (Status IN ('OPEN','IN_PROGRESS','DONE','REJECTED')),
    CreateUserId TEXT REFERENCES users(emp_no) ON DELETE SET NULL,
    CreateDt TEXT NOT NULL,
    ModifyDt TEXT,
    Answer TEXT,
    AnswerUserId TEXT REFERENCES users(emp_no) ON DELETE SET NULL,
    AnswerDt TEXT
);
CREATE INDEX ix_inquiry_user ON TB_SYS_Inquiry(CreateUserId);
