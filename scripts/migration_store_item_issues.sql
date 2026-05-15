-- ============================================================
-- Migration: Create dbo.store_item_issues + helper view
-- Target DB:  MTHAI_ppm_db1
-- Idempotent: safe to re-run (IF OBJECT_ID guards every DDL)
-- ============================================================

-- Table
IF OBJECT_ID('dbo.store_item_issues', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.store_item_issues (
        id              BIGINT IDENTITY(1,1) NOT NULL,
        month_key       CHAR(6)        NOT NULL,   -- 'YYYY-MM'  (sortable)
        month_label     VARCHAR(8)     NOT NULL,   -- "Jan'25"   (display)
        source          VARCHAR(16)    NOT NULL,   -- 'ASO2025' | 'SUM_ASSY'
        item_no         VARCHAR(64)    NOT NULL,
        description     NVARCHAR(400)  NULL,
        process         VARCHAR(64)    NOT NULL,
        machine_model   VARCHAR(128)   NULL,
        category        VARCHAR(32)    NOT NULL,
        quantity        INT            NOT NULL DEFAULT 0,
        unit_cost       DECIMAL(18,4)  NOT NULL DEFAULT 0,
        total_cost      DECIMAL(18,2)  NOT NULL DEFAULT 0,
        source_file     VARCHAR(255)   NULL,
        loaded_at       DATETIME2(0)   NOT NULL DEFAULT SYSUTCDATETIME(),
        CONSTRAINT pk_store_item_issues PRIMARY KEY (id)
    );
    PRINT 'Created table dbo.store_item_issues';
END
ELSE
    PRINT 'Table dbo.store_item_issues already exists — skipped';

-- Indexes (each guarded individually)
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID('dbo.store_item_issues') AND name = 'ix_sii_month')
    CREATE INDEX ix_sii_month      ON dbo.store_item_issues (month_key);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID('dbo.store_item_issues') AND name = 'ix_sii_process')
    CREATE INDEX ix_sii_process    ON dbo.store_item_issues (process)       INCLUDE (total_cost, quantity);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID('dbo.store_item_issues') AND name = 'ix_sii_category')
    CREATE INDEX ix_sii_category   ON dbo.store_item_issues (category)      INCLUDE (total_cost);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID('dbo.store_item_issues') AND name = 'ix_sii_item')
    CREATE INDEX ix_sii_item       ON dbo.store_item_issues (item_no)       INCLUDE (total_cost, quantity);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID('dbo.store_item_issues') AND name = 'ix_sii_machine')
    CREATE INDEX ix_sii_machine    ON dbo.store_item_issues (machine_model) INCLUDE (total_cost);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID('dbo.store_item_issues') AND name = 'ix_sii_month_proc')
    CREATE INDEX ix_sii_month_proc ON dbo.store_item_issues (month_key, process) INCLUDE (total_cost);

PRINT 'Indexes OK';

-- Helper view
GO
CREATE OR ALTER VIEW dbo.vw_store_item_monthly AS
SELECT
    month_key,
    month_label,
    process,
    category,
    machine_model,
    SUM(total_cost)         AS total_cost,
    SUM(quantity)           AS total_qty,
    COUNT(DISTINCT item_no) AS unique_items
FROM dbo.store_item_issues
GROUP BY month_key, month_label, process, category, machine_model;
GO
PRINT 'View dbo.vw_store_item_monthly OK';
