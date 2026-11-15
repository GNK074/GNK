# Configure GNK and verify the Dhan IP match

1. Check the existing operator setting in `/opt/gnk/.env`. Individual broker setup must be available (`INDIVIDUAL_BROKER_SETUP_ENABLED=true`, the application default). If a Dhan integration record exists, the existing registry must allow individual setup and have authentication marked verified. Review the integration settings in GNK before changing them.
2. For the whitelist check, use `BROKER_EGRESS_IP` with the verified public outbound address used by GNK to reach Dhan. A browser's public IP, an ingress address, and a GNK IP registration entry can each differ from backend egress. Confirm the egress address through the VM's network configuration.
3. If an operator setting changed, validate the environment, then recreate the backend and Nginx so the containers pick up the value and routing. Use [the deployment guide](01-production-deployment.md).
4. After connecting in the Dhan pilot, select **Check Dhan IP whitelist**. GNK compares its configured egress value against the primary and secondary entries returned by Dhan. A match confirms the configured value appears in Dhan's list. Verification of the VM's actual outbound address is a separate network check.
5. If the comparison reports a mismatch, review the configured egress and the entries in Dhan's official IP settings. Record any GNK IP change using the existing IP management workflow when applicable, then verify broker-side status separately. [Dhan IP documentation](https://dhanhq.co/docs/v2/authentication/#setup-static-ip)

The read-only pilot has no dependency on the live-placement reference, tick multiplier or trading switches. The IP comparison is a separate action from portfolio reads.
