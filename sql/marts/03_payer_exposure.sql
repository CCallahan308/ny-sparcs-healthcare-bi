-- Payer exposure.
-- Grain: discharge_year x facility x county x payer class.
-- Exposure only: share of discharges and share of estimated cost. Not
-- reimbursement, net revenue, or margin (no payment data exists in the source).

CREATE OR REPLACE TABLE mart_payer_exposure AS
SELECT
    discharge_year,
    facility_id,
    facility_name,
    county,
    payer_class,
    COUNT(*) AS discharges,
    SUM(total_costs) AS estimated_cost
FROM stg_normalized
GROUP BY
    discharge_year,
    facility_id,
    facility_name,
    county,
    payer_class;
