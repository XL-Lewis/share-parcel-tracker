use anyhow::Result;
use rusqlite::Connection;
use std::path::Path;

/// Creates a connection to an SQLite database file
pub fn create_connection(db_path: &Path) -> Result<Connection> {
    let conn = Connection::open(db_path)?;

    // Enable foreign keys
    conn.execute("PRAGMA foreign_keys = ON", [])?;

    Ok(conn)
}
