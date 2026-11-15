# Acceptance and troubleshooting

| Check | Expected result |
| --- | --- |
| Open the pilot while signed in | The pilot loads and displays the session state |
| Verify with a valid token for the entered Client ID | Connected |
| Try a mismatched Client ID in a test session | Verification fails |
| Read each dataset | Timestamp plus broker data or an appropriate empty result |
| Check IP status | Match, no match, or GNK egress IP has not been configured |
| Start a separate GNK login session | It requires its own connection |
| Disconnect or log out | Reauthentication is required on the next pilot visit |
| Let the pilot expire, or restart a test backend | Reauthentication is required |

- **Pilot redirects or is absent.** Check that the VM revision includes the pilot commit, that backend and frontend were rebuilt, and that the browser is at `/user/brokers/dhan-pilot`.
- **Verification fails.** Confirm the Client ID belongs to the same account as the current token. Check whether the integration permits individual account setup.
- **Rate limited or temporary read failure.** Wait before retrying. Check the backend logs around the failure timestamp and share only redacted error details.
- **Holdings load but IP check fails.** Review egress configuration and broker-side IP entries. Portfolio access and IP comparison are separate checks.
- **Pilot disappears after a process restart.** Sign in and reconnect. Volatile sessions are local to a single GNK backend process and will require a shared session owner architecture before use across multiple backend processes.

For sign-off, record the GNK commit, date and time, health-check result, identity verification outcome, dataset results, IP status and disconnect result. Keep tokens and client identifiers out of the record.
