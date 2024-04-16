use uuid::Uuid;
#[derive(Debug)]
pub struct Transaction {
    pub id: Uuid,

    pub ticker: String,
    pub num_sold: u32,
    pub price: f32,
    pub date: u32,
    pub description: Option<String>,
}

impl Transaction {
    pub fn new(
        ticker: String,
        num_sold: u32,
        price: f32,
        date: u32,
        description: Option<String>,
    ) -> Transaction {
        return Transaction {
            id: Uuid::new_v4(),
            ticker,
            num_sold,
            price,
            date,
            description,
        };
    }
}
