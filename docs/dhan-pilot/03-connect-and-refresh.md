# Connect a Dhan account and refresh portfolio data

1. Sign in to [Dhan Web](https://web.dhan.co/) with your own account. Find your Client ID and generate an access token from **My Profile → Access DhanHQ APIs**. [Dhan authentication instructions](https://dhanhq.co/docs/v2/authentication/#access-token)
2. Sign in to GNK and open [Dhan pilot](https://gnkalgo.com/user/brokers/dhan-pilot).
3. Enter **Dhan Client ID** and **Dhan access token** in the pilot form. Confirm ownership and select **Verify and connect**. Wait for **Connected**, which requires successful broker identity validation.
4. Choose **Holdings**, **Positions**, **Funds**, **Orders**, or **Trades** and select **Refresh** for that dataset. Check the timestamp and record count. Compare against Dhan using the same account and applicable time range. An empty orders or trades result can be valid.
5. Select **Check Dhan IP whitelist** to read the comparison status. See [GNK configuration and IP](02-gnk-configuration-and-ip.md) for how to interpret the result.
6. Select **Disconnect pilot** when finished. After expiry, logout or a backend restart, reconnect using a current token. Submit the token only in the pilot form.

The pilot uses the Client ID and access token directly. OAuth application keys, secrets and callback registration are needed only for other connection flows.
