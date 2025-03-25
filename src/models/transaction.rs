use crate::date::Date;

/// Common transaction traits for buy and sell transactions
pub trait Transaction {
    fn get_id(&self) -> Option<i32>;
    fn get_stock_id(&self) -> &str;
    fn get_date(&self) -> &Date;
    fn get_quantity(&self) -> u32;
    fn get_price_per_share(&self) -> f64;
    fn get_fees(&self) -> f64;
    fn get_notes(&self) -> Option<&str>;
    fn get_transaction_value(&self) -> f64 {
        self.get_price_per_share() * self.get_quantity() as f64
    }
    fn get_total_cost(&self) -> f64 {
        self.get_transaction_value() + self.get_fees()
    }
}

/// Represents a buy transaction in the portfolio
#[derive(Debug)]
pub struct BuyTransaction {
    pub id: Option<i32>,
    pub stock_id: String,
    pub date: Date,
    pub quantity: u32,
    pub price_per_share: f64,
    pub fees: f64,
    pub notes: Option<String>,
}

impl BuyTransaction {
    /// Create a new buy transaction
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        stock_id: String,
        date: Date,
        quantity: u32,
        price_per_share: f64,
        fees: f64,
        notes: Option<String>,
    ) -> Self {
        Self {
            id: None,
            stock_id,
            date,
            quantity,
            price_per_share,
            fees,
            notes,
        }
    }
}

impl Transaction for BuyTransaction {
    fn get_id(&self) -> Option<i32> {
        self.id
    }

    fn get_stock_id(&self) -> &str {
        &self.stock_id
    }

    fn get_date(&self) -> &Date {
        &self.date
    }

    fn get_quantity(&self) -> u32 {
        self.quantity
    }

    fn get_price_per_share(&self) -> f64 {
        self.price_per_share
    }

    fn get_fees(&self) -> f64 {
        self.fees
    }

    fn get_notes(&self) -> Option<&str> {
        self.notes.as_deref()
    }
}

/// Represents a sell transaction in the portfolio
#[derive(Debug)]
pub struct SellTransaction {
    pub id: Option<i32>,
    pub stock_id: String,
    pub date: Date,
    pub quantity: u32,
    pub price_per_share: f64,
    pub fees: f64,
    pub notes: Option<String>,
}

impl SellTransaction {
    /// Create a new sell transaction
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        stock_id: String,
        date: Date,
        quantity: u32,
        price_per_share: f64,
        fees: f64,
        notes: Option<String>,
    ) -> Self {
        Self {
            id: None,
            stock_id,
            date,
            quantity,
            price_per_share,
            fees,
            notes,
        }
    }
}

impl Transaction for SellTransaction {
    fn get_id(&self) -> Option<i32> {
        self.id
    }

    fn get_stock_id(&self) -> &str {
        &self.stock_id
    }

    fn get_date(&self) -> &Date {
        &self.date
    }

    fn get_quantity(&self) -> u32 {
        self.quantity
    }

    fn get_price_per_share(&self) -> f64 {
        self.price_per_share
    }

    fn get_fees(&self) -> f64 {
        self.fees
    }

    fn get_notes(&self) -> Option<&str> {
        self.notes.as_deref()
    }
}
