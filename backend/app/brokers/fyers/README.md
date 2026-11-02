# fyers individual account connection

Individual credential validation is implemented in brokers/individual/verifiers.py and exposed through POST /api/v1/brokers/{broker}/individual. Setup metadata and required fields are in brokers/individual/catalog.py. No broker password/PIN/OTP is collected. The response identity must match the entered account/client ID before encrypted storage. Full automated OAuth callbacks, trading execution and provider production approval are separate capabilities and are not claimed by this module. See INDIVIDUAL_BROKER_SETUP.md.
