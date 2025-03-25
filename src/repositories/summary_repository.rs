use anyhow::Result;
use rusqlite::{params, Connection};

use crate::models::CapitalGainsSummary;

/// Repository for capital gains summary operations in the database
pub struct CapitalGainsSummaryRepository<'a> {
    conn: &'a Connection,
}

impl<'a> CapitalGainsSummaryRepository<'a> {
    /// Create a new CapitalGainsSummaryRepository with a connection
    pub fn new(conn: &'a Connection) -> Self {
        Self { conn }
    }

    /// Generate capital gains summary for a specific financial year
    pub fn generate_summary(&self, fy: &str) -> Result<CapitalGainsSummary> {
        // Financial years in Australia are formatted as "2023-2024" for FY starting July 1, 2023
        let parts: Vec<&str> = fy.split('-').collect();
        let start_year: u32 = parts[0].parse()?;
        let end_year: u32 = parts[1].parse()?;

        let mut stmt = self.conn.prepare(
            "SELECT sa.capital_gain, sa.cgt_discount_applied
             FROM sell_allocations sa
             JOIN sell_transactions st ON sa.sell_transaction_id = st.id
             WHERE
                (strftime('%Y', st.date) = ?1 AND strftime('%m', st.date) >= '07') OR
                (strftime('%Y', st.date) = ?2 AND strftime('%m', st.date) <= '06')",
        )?;

        let rows = stmt.query_map(
            params![start_year.to_string(), end_year.to_string()],
            |row| {
                let capital_gain: f64 = row.get(0)?;
                let cgt_discount_applied: bool = row.get::<_, i32>(1)? != 0;

                Ok((capital_gain, cgt_discount_applied))
            },
        )?;

        let mut short_term_gains = 0.0;
        let mut long_term_gains = 0.0;
        let mut capital_losses = 0.0;

        // Calculate gains and losses
        for row_result in rows {
            let (gain, discount_eligible) = row_result?;

            if gain > 0.0 {
                if discount_eligible {
                    long_term_gains += gain;
                } else {
                    short_term_gains += gain;
                }
            } else if gain < 0.0 {
                capital_losses += -gain; // Convert to positive for reporting
            }
        }

        Ok(CapitalGainsSummary::new(
            fy.to_string(),
            short_term_gains,
            long_term_gains,
            capital_losses,
        ))
    }
}
