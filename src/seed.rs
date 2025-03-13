use rusqlite::{params, Connection, Result};

use crate::{BuyTransaction, SellTransaction};

pub fn insert_sample_data(conn: &Connection) -> Result<()> {
    // Insert buy transactions
    let buy_transactions = vec![
        BuyTransaction {
            id: 1,
            stock_id: "AAPL".to_string(), // Apple
            date: "2023-01-15".to_string(),
            quantity: 10,
            price_per_share: 145.50,
            fees: 9.99,
            notes: Some("Initial investment".to_string()),
        },
        BuyTransaction {
            id: 2,
            stock_id: "AAPL".to_string(), // AAPL
            date: "2023-02-20".to_string(),
            quantity: 5,
            price_per_share: 150.25,
            fees: 9.99,
            notes: None,
        },
        BuyTransaction {
            id: 3,
            stock_id: "AAPL".to_string(), // MSFT
            date: "2023-01-20".to_string(),
            quantity: 8,
            price_per_share: 240.10,
            fees: 9.99,
            notes: None,
        },
    ];

    for buy in buy_transactions {
        conn.execute(
            "INSERT OR REPLACE INTO buy_transactions (id, stock_id, date, quantity, price_per_share, fees, notes)
             VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)",
            params![
                buy.id,
                buy.stock_id,
                buy.date,
                buy.quantity,
                buy.price_per_share,
                buy.fees,
                buy.notes,
            ],
        )?;
    }

    // Insert sell transactions
    let sell_transactions = vec![SellTransaction {
        id: 1,
        stock_id: "AAPL".to_string(), // AAPL
        date: "2023-03-15".to_string(),
        quantity: 3,
        price_per_share: 155.75,
        fees: 9.99,
        linked_buy_id: Some(1), // Linked to first buy transaction
        notes: Some("Partial profit taking".to_string()),
    }];

    for sell in sell_transactions {
        conn.execute(
            "INSERT OR REPLACE INTO sell_transactions (id, stock_id, date, quantity, price_per_share, fees, linked_buy_id, notes)
             VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8)",
            params![
                sell.id,
                sell.stock_id,
                sell.date,
                sell.quantity,
                sell.price_per_share,
                sell.fees,
                sell.linked_buy_id,
                sell.notes,
            ],
        )?;
    }

    Ok(())
}
