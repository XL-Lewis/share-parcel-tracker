/// Represents a sell allocation that links a sell transaction to one or more buy transactions
#[derive(Debug)]
pub struct SellAllocation {
    pub id: Option<i32>,
    pub sell_transaction_id: i32,
    pub buy_transaction_id: i32,
    pub quantity: u32,
    pub allocated_buy_price: f64,
    pub allocated_buy_fees: f64,
    pub capital_gain: f64,
    pub cgt_discount_applied: bool,
}

impl SellAllocation {
    /// Create a new sell allocation
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        sell_transaction_id: i32,
        buy_transaction_id: i32,
        quantity: u32,
        allocated_buy_price: f64,
        allocated_buy_fees: f64,
        capital_gain: f64,
        cgt_discount_applied: bool,
    ) -> Self {
        Self {
            id: None,
            sell_transaction_id,
            buy_transaction_id,
            quantity,
            allocated_buy_price,
            allocated_buy_fees,
            capital_gain,
            cgt_discount_applied,
        }
    }

    /// Get the effective capital gain amount after any applicable discount
    pub fn effective_capital_gain(&self) -> f64 {
        if self.capital_gain <= 0.0 {
            // Losses are not discounted
            self.capital_gain
        } else if self.cgt_discount_applied {
            // 50% discount for assets held more than 12 months
            self.capital_gain * 0.5
        } else {
            // No discount for short-term gains
            self.capital_gain
        }
    }
}
