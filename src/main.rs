mod schema;
#[cfg(test)]
mod test;
mod transaction;
use diesel::{prelude::*, result};
use diesel::{Connection, SelectableHelper, SqliteConnection};
use dotenv::dotenv;
use schema::transactions::num_sold;
use std::env;
use transaction::Transaction;
fn main() {
    use self::schema::transactions::dsl::*;
    let conn = &mut establish_conection();
    new_transaction(conn, "zip", 5, 502.0, 9919, Some("Abcd".to_string()));
    new_transaction(conn, "abc", 2, 520.0, 9929, Some("Abcd".to_string()));
    new_transaction(conn, "def", 35, 530.0, 9939, Some("Abcd".to_string()));
    new_transaction(conn, "ghi", 15, 520.0, 9499, Some("Abcd".to_string()));
    new_transaction(conn, "jkl", 53, 501.0, 999, Some("Abcd".to_string()));
    new_transaction(conn, "sad", 5, 503.0, 999, Some("Abcd".to_string()));

    let res = transactions
        .limit(5)
        .select(Transaction::as_select())
        .load(conn)
        .expect("Failed to get transactions!");
    println!("{:?}", res);
}

pub fn establish_conection() -> SqliteConnection {
    dotenv().ok();
    let db_url = env::var("DATABASE_URL").expect("db url must be set");
    SqliteConnection::establish(&db_url).expect("Db not found, have you run the migration?")
}

pub fn new_transaction(
    conn: &mut SqliteConnection,
    ticker: &str,
    numsold: i32,
    price: f32,
    date: i32,
    desc: Option<String>,
) {
    use crate::schema::transactions;
    let txn = Transaction::new(ticker.to_owned(), numsold, price, date, desc);
    diesel::insert_into(transactions::table)
        .values(&txn)
        .execute(conn)
        .expect("Failed to insert into db");
}
