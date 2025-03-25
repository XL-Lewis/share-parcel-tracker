use anyhow::Result;
use rusqlite::Connection;

use crate::models::CapitalGainsSummary;
use crate::repositories::CapitalGainsSummaryRepository;
use crate::services::AllocationService;

/// Service for generating reports
pub struct ReportingService<'a> {
    conn: &'a Connection,
}

impl<'a> ReportingService<'a> {
    /// Create a new ReportingService with a database connection
    pub fn new(conn: &'a Connection) -> Self {
        Self { conn }
    }

    /// Generate capital gains summary for a specific financial year
    pub fn generate_capital_gains_summary(&self, fy: &str) -> Result<CapitalGainsSummary> {
        let repo = CapitalGainsSummaryRepository::new(self.conn);
        repo.generate_summary(fy)
    }

    /// Generate per-stock capital gains breakdown for a financial year
    pub fn generate_capital_gains_by_stock(
        &self,
        fy: &str,
    ) -> Result<Vec<(String, f64, f64, f64, f64)>> {
        let allocation_service = AllocationService::new(self.conn);
        let stock_gains = allocation_service.get_capital_gains_by_stock(fy)?;

        // Calculate net gains and include in the result
        let results = stock_gains
            .into_iter()
            .map(|(stock_id, short_term, long_term, losses)| {
                // Calculate discounted and net gains for this stock
                let discounted = long_term * 0.5;
                let total = short_term + discounted;
                let net = if total > losses { total - losses } else { 0.0 };

                (stock_id, short_term, long_term, losses, net)
            })
            .collect();

        Ok(results)
    }

    /// Format a financial year string from a year (e.g., 2023 -> "2023-2024")
    pub fn format_financial_year(year: i32) -> String {
        format!("{}-{}", year, year + 1)
    }

    /// Parse a financial year string into start_year and end_year
    pub fn parse_financial_year(fy: &str) -> Result<(i32, i32)> {
        let parts: Vec<&str> = fy.split('-').collect();
        if parts.len() != 2 {
            return Err(anyhow::anyhow!("Invalid financial year format: {}", fy));
        }

        let start_year: i32 = parts[0].parse()?;
        let end_year: i32 = parts[1].parse()?;

        Ok((start_year, end_year))
    }
}
