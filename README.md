# HERON - handling your queue
## Introduction

Heron is an enterprise grade API which can quickly be deployed and allows entities to easily interact with the Cardano blockchains, without the need of learning how to work with a blockchain.

## Documentation
The API documentation can be found at [https://godspeed-exe.github.io/heron-cardano](https://godspeed-exe.github.io/heron-cardano). This will also be available after deploying Heron on your infrastructure on [http://heron_api_here:8001/docs](http://heron_api_here:8001/docs)

## Requirements
- simple virtual machine with Docker with Linux or WSL
- a Blockfrost API key (https://blockfrost.io/dashboard)
- at least 1 CIP39 mnemonic

## Functions
+ ✅ load a Cardano wallet
+ ✅ query wallet balance
    + ✅ currently only in Single Address Mode (m/1852'/1815'/0'/0/0)
+ post transactions
    + ✅ single recipient
    + ✅ multiple recipients (only ADA)
    + ✅ multiple recipients (native assets)
    + ✅ attaching metadata
    + ✅ minting assets

## Installation

Since **Heron** does not include a full node, system requirements are fairly low. **Heron** relies on [Blockfrost](https://blockfrost.io/dashboard) to query Cardano blockchain data.

Obtain a free API account from [Blockfrost](https://blockfrost.io/dashboard), select the network that you want to work with and obtain your API key. This will be needed for successfully starting the Docker containers.

### Clone the Heron code from this Github repository.
```` 
git clone https://github.com/Godspeed-exe/heron-cardano.git
```` 
### Move into the folder.
```` 
cd heron-cardano
```` 
### Run this script to initiate all required environment variables.
```` 
./make_env.sh 
```` 

### Launch the docker containers
```` 
docker-compose up --build -d
````

## Troubleshoot

### These containers should be up and running
Check their logs with 'docker logs -f xxxxx'
````
- oura_worker
- heron_worker
- oura
- heron_api
- heron_db
- redis
````



## Getting started

Before being able to process transactions Heron will need to have at least 1 wallet. To load a wallet you'll need a BIP39 mnemonic (24 word recovery phrase). Heron will safely store this and use it to sign transactions before broadcasting them to the network.

This mnemonic can also be opened in Cardano wallets like Lace, Eternl, VESPR.

You can:
- re-use an existing mnemonic
- generate a new mnemnoic through Heron's API (/wallets/generate)

