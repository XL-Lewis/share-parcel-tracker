/// Represents a capital gains tax summary for a specific financial year
#[derive(Debug)]
pub struct CapitalGainsSummary {
    pub financial_year: String,
    pub short_term_gains: f64, // Held < 1 year
    pub long_term_gains: f64,  // Held > 1 year (before discount)
    pub discounted_gains: f64, // After 50% discount
    pub capital_losses: f64,
    pub net_capital_gains: f64, // Total taxable
}

impl CapitalGainsSummary {
    /// Create a new capital gains summary
    pub fn new(
        financial_year: String,
        short_term_gains: f64,
        long_term_gains: f64,
        capital_losses: f64,
    ) -> Self {
        // Apply 50% discount to long-term gains
        let discounted_gains = long_term_gains * 0.5;

        // Calculate net capital gains (losses can offset gains)
        let total_gains = short_term_gains + discounted_gains;
        let net_capital_gains = if total_gains > capital_losses {
            total_gains - capital_losses
        } else {
            0.0 // Capital losses can only offset gains, excess is carried forward
        };

        Self {
            financial_year,
            short_term_gains,
            long_term_gains,
            discounted_gains,
            capital_losses,
            net_capital_gains,
        }
    }

    /// Calculate the excess losses that can be carried forward to future tax years
    pub fn excess_losses(&self) -> f64 {
        let total_gains = self.short_term_gains + self.discounted_gains;
        if self.capital_losses > total_gains {
            self.capital_losses - total_gains
        } else {
            0.0
        }
    }
}
