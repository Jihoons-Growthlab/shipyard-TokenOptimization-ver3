CREATE TABLE TB_SYS_ChatInquiry (
    CreateUserId TEXT NOT NULL,
    RequestId TEXT NOT NULL,
    InquiryId INTEGER NOT NULL,
    Category TEXT NOT NULL,
    Content TEXT NOT NULL,
    PRIMARY KEY (CreateUserId, RequestId)
);
