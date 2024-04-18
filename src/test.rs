// use crate::transaction::Transaction;
// use rusqlite::{Connection, Result};

// #[test]
// fn test_create_new_transaction() {
//     Transaction::new("ABC".to_string(), 50, 100.0, 111, None);
// }

// #[test]
// fn test_init_db_and_add_transaction() -> Result<()> {
//     let conn = Connection::open_in_memory().unwrap();

//     conn.execute(
//         "CREATE TABLE txn (
//                 id          TEXT PRIMARY KEY,
//                 ticker      TEXT NOT NULL,
//                 num_sold    INTEGER NOT NULL,
//                 price       REAL NOT NULL,
//                 date        INTEGER NOT NULL,
//                 description BLOB
//             )",
//         (),
//     )
//     .unwrap();

//     let txn = Transaction::new("ZIP".to_string(), 5, 5.0, 22, None);
//     conn.execute(
//         "INSERT INTO txn (id, ticker, num_sold, price, date, description) VALUES (?1, ?2, ?3, ?4, ?5, ?6)",
//         (
//             txn.id.to_string(),
//             &txn.ticker,
//             txn.num_sold,
//             txn.price,
//             txn.date,
//             txn.description,
//         ),
//     ).unwrap();

//     let mut stmt = conn
//         .prepare("SELECT id, ticker, num_sold FROM txn")
//         .unwrap();
//     let mut rows = stmt.query([]).unwrap();
//     while let Some(row) = rows.next().unwrap() {
//         assert_eq!(row.get::<&str, String>("id").unwrap(), txn.id.to_string());
//         assert_eq!(row.get::<&str, String>("ticker").unwrap(), txn.ticker);
//         assert_eq!(row.get::<&str, u32>("num_sold").unwrap(), txn.num_sold);
//         assert_eq!(row.get::<&str, f32>("price").unwrap(), txn.price);
//         assert_eq!(row.get::<&str, u32>("date").unwrap(), txn.date);
//         assert_eq!(
//             row.get::<&str, String>("description").unwrap(),
//             txn.id.to_string()
//         );
//     }
//     Ok(())
// }
