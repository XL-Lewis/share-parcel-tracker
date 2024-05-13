use diesel::{deserialize::Queryable, prelude::Insertable, Selectable};
use uuid::Uuid;
#[derive(Debug, Queryable, Selectable, Insertable)]
#[diesel(check_for_backend(diesel::sqlite::Sqlite))]
#[diesel(table_name = crate::schema::transactions)]
pub struct Transaction {
    pub id: String,

    pub ticker: String,
    pub num_sold: i32,
    pub price: f32,
    pub date: i32,
    pub description: Option<String>,
}

impl Transaction {
    pub fn new(
        ticker: String,
        num_sold: i32,
        price: f32,
        date: i32,
        description: Option<String>,
    ) -> Transaction {
        return Transaction {
            id: Uuid::new_v4().to_string(),
            ticker,
            num_sold,
            price,
            date,
            description,
        };
    }
}
