-- Grants an additional Entra (Azure AD) principal read/write access to the Health IQ database.
-- Run once per additional principal (e.g. a teammate, or the Container App's managed identity)
-- beyond the AAD admin configured in infra/modules/sql.bicep (the admin already has full access).
--
-- Usage: substitute {{PRINCIPAL_NAME}} with the UPN (user), display name (managed identity), or
-- group name of the principal, then execute against the target database (not master) while
-- connected with an Azure AD account that is a member of the SQL AAD admin.
--
-- Tables (Medicine, MedicinePrice, LabMetric, ShareLink) are created separately by
-- scripts/seed_sql.py per docs/implementation-plan.md Section 2/M0.

IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = N'{{PRINCIPAL_NAME}}')
BEGIN
    CREATE USER [{{PRINCIPAL_NAME}}] FROM EXTERNAL PROVIDER;
END

ALTER ROLE db_datareader ADD MEMBER [{{PRINCIPAL_NAME}}];
ALTER ROLE db_datawriter ADD MEMBER [{{PRINCIPAL_NAME}}];
