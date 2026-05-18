-- vw_job_setup: same as vw_job_nokey but includes ALL machines (no flag_key filter)
-- Used by the Setup section of downtime.py to capture non-key WB machines
-- (CHANGE CAP, CONVERT on non-key WB are technician setup jobs)
CREATE OR ALTER VIEW [dbo].[vw_job_setup] AS
SELECT
      jl.[id_job]
    , jl.[code_machine]
    , jl.[group_machine]
    , jl.[job_type]
    , jl.[des_job]
    , jl.[req]
    , jl.[supv]
    , jl.[datex]
    , jl.[by_ack]
    , jl.[date_ack]
    , YEAR(jl.[date_ack])  AS Year_X
    , MONTH(jl.[date_ack]) AS Month_X
    , jl.[cause]
    , jl.[by_perform]
    , jl.[date_close]
    , jl.[remark]
    , jl.[action]
    , jl.[num_task]
    , jl.[lot_no]
    , jl.[shift]
    , jl.[ww]
    , jl.[id_area]
    , jl.[Die Size]
    , jl.[Leadframe Type]
    , jl.[Package Type]
    , jl.[Supervisor]
    , jl.[Thikness]
    , jl.[Wire Type]
    , jl.[Side]
    , jl.[Press]
    , jl.[PM]
    , jl.[Automotive]
    , jl.[id_operation]
    , jl.[fy_ww]
    , jl.[fy_quarter]
    , jl.[fy_month]
    , jl.[mpc]
    , jl.[Cure type]
    , jl.[Process Type]
    , jl.[ENGINEERING DOWN]
    , jl.[Package]
    , DATEDIFF(MINUTE, jl.[datex],    jl.[date_ack])   AS Waiting_time
    , DATEDIFF(MINUTE, jl.[date_ack], jl.[date_close]) AS Repair_time
    , m.[flag_key]
    , m.[ods_name]
FROM [dbo].[job_listx] jl
LEFT JOIN [dbo].[machine] m ON jl.[code_machine] = m.[code_machine];
GO
