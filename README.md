# HERON - handling your queue
## Introduction

Heron is an enterprise grade API which can quickly be deployed and allows entities to easily interact with the Cardano blockchains, without the need of learning how to work with a blockchain.

## Requirements
- simple virtual machine with Docker
- a Blockfrost API key (https://blockfrost.io/dashboard)
- at least 1 CIP39 mnemonic (can also be generated using the API)

## Functions


+ ✅ load a Cardano wallet
+ ✅ query wallet balance
    + ✅ currently only in Single Address Mode (m/1852'/1815'/0'/0/0)
+ post transactions
    + ✅ single recipient
    + ✅ multiple recipients (only ADA)
    + ✅ multiple recipients (native assets)
    + ⏳ attaching metadata
    + ⏳ minting assets

## Installation

Since **Heron** does not include a full node, system requirements are fairly low. **Heron** relies on Blockfrost to query Cardano blockchain data.

Go to https://blockfrost.io/dashboard , create an account and obtain your API key. This will be needed for successfully starting the Docker containers.


```` 
git clone https://github.com/Godspeed-exe/heron.git
cd heron
chmod +x make_env.sh && ./make_env.sh 
docker-compose up --build -d
````


## Documentation

After completing installation you can access the documentation on http://localhost:8001/docs 
