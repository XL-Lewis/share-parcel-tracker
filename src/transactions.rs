struct Transaction {
    ticker: String,
    shares_sold: u32,
    price: f32,
    date: u32,
    description: Option<String>,
}
