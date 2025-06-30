rm -f .env
touch .env

echo "Enter your Postgresql username:"
read POSTGRES_USER
echo "Enter your Postgresql password:"
read POSTGRES_PASSWORD

echo "Enter your Blockfrost API key:"
read BLOCKFROST_PROJECT_ID

FERNET_KEY=$(openssl rand -base64 32)

echo "Generated Fernet encryption key:"
echo "$FERNET_KEY"

echo "POSTGRES_USER="$POSTGRES_USER >> .env
echo "POSTGRES_PASSWORD="$POSTGRES_PASSWORD >> .env
echo "BLOCKFROST_PROJECT_ID="$BLOCKFROST_PROJECT_ID >> .env
echo "WALLET_ENCRYPTION_KEY="$FERNET_KEY >> .env


