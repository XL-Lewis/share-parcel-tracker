mod schema;
#[cfg(test)]
mod test;
mod transaction;

use diesel::{Connection, SqliteConnection};
use dotenv::dotenv;
use std::env;
use transaction::Transaction;
fn main() {}

pub fn establish_conection() -> SqliteConnection {
    dotenv().ok();
    let db_url = env::var("DATABASE_URL").expect("db url must be set");
    SqliteConnection::establish(&db_url).expect("Db not found, have you run the migration?")
}
