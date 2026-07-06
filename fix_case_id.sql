CREATE SEQUENCE IF NOT EXISTS cases_case_id_seq START 1;
ALTER TABLE cases ALTER COLUMN case_id SET DEFAULT nextval('cases_case_id_seq');