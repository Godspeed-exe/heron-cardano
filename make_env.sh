rm -f .env
touch .env

echo "Enter your Postgresql username:"
read POSTGRES_USER
echo "Enter your Postgresql password:"
read POSTGRES_PASSWORD

echo "Enter your Blockfrost API key:"
read BLOCKFROST_PROJECT_ID

echo "Enter the encryption key that will be used to encrypt your wallets:"
read WALLET_ENCRYPTION_KEY

echo "POSTGRES_USER="$POSTGRES_USER >> .env
echo "POSTGRES_PASSWORD="$POSTGRES_PASSWORD >> .env
echo "BLOCKFROST_PROJECT_ID="$BLOCKFROST_PROJECT_ID >> .env
echo "WALLET_ENCRYPTION_KEY="$WALLET_ENCRYPTION_KEY >> .env


