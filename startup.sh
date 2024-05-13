sudo apt-get install libqslite3-dev
cargo install diesel_cli --no-default-features --features sqlite
echo DATABASE_URL = ./share-db > .env
diesel setup
diesel migration generate --diff-schema create_transactions
diesel migration run
