/// Represents a stock or share in the system
#[derive(Debug)]
pub struct Stock {
    pub id: Option<i32>,
    pub symbol: String,
}

impl Stock {
    /// Create a new stock with a given symbol
    pub fn new(symbol: String) -> Self {
        Self { id: None, symbol }
    }

    /// Create a stock with an existing ID (typically from the database)
    pub fn with_id(id: i32, symbol: String) -> Self {
        Self {
            id: Some(id),
            symbol,
        }
    }
}
