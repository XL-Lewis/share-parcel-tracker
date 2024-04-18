sudo apt-get install libqslite3
cargo install diesel_cli --no-default-features --features sqlite
echo DATABASE_URL = ./share-db > .env
diesel setup
diesel migration generate --diff-schema create_transactions
