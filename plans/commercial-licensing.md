# Commercial licensing

Selling commercial licenses for WPSync. PolyForm Strict 1.0.0 makes WPSync free
for personal use; businesses need a paid commercial license. Paying adds no
features: the price supports WPSync as a business. The goal is clear licensing
with sensible enforcement for legitimate users, not an anti-piracy system.

The intended experience: install WPSync, choose personal or business use, try
it free for 30 days if business, buy online, install the license, keep working
offline. No accounts, no complicated activation, and nothing payment-related in
the normal command path.

## Decided

- **Price:** a yearly subscription, around $69–$99 per year; the exact price
  is not set. Not a perpetual license: when it expires, commercial use needs a
  renewal.
- **Personal use** includes personal blogs, monetized or not. A professional
  blogger's blog counts as business use. Since PolyForm's personal-use
  allowance requires no anticipated commercial application, monetized personal
  blogs need an explicit grant in the terms.
- **Seller:** Polar (polar.sh) as the merchant of record, handling checkout,
  subscriptions, taxes, and invoices.
- **Domain:** `wpsync.dev` for the website.
- **Purchase link:** WPSync and the website point to a stable
  `https://wpsync.dev/buy`, which forwards to the seller, so the seller can
  change without changing WPSync.
- **First run** asks how WPSync will be used, personal or business, and saves
  the answer locally.
  - **Personal:** free indefinitely; commands work normally and show "Personal
    use only" in their terminal output. No registration.
  - **Business:** a free 30-day trial with no card, account, or online
    activation. Commands work and show the days left with the purchase link:
    a brief notice for the first 23 days, a more prominent warning in the last
    7. After 30 days, operational commands stop until a license is installed.
  - Once business is chosen, the normal CLI offers no way back to personal.
  - When nobody can answer, as when a script, a scheduled job, or an AI agent
    runs WPSync before licensing is set up, it stops with the setup message
    below and an error exit status instead of choosing.
- **License line:** printed on standard error, so it shows in the terminal on
  every command, even when the command's output is piped or saved to a file,
  and never mixes into that output.
- **Commands:**

  ```console
  wpsync license init --personal
  wpsync license init --business
  wpsync license install KEY
  wpsync license status
  ```

  `license init` records the choice without asking, the same as answering the
  first-run question. `--personal` is refused once business use is chosen, and
  `--business` again keeps the original trial start, so the trial cannot be
  restarted.
- **Setup message** when licensing is not set up and nobody can answer:

  ```text
  WPSync requires a one-time license setup.

  WPSync is free for personal use under PolyForm Strict
  License 1.0.0. Business use requires a commercial license,
  with a free 30-day trial and no credit card required.

  Choose based on the intended use of WPSync, not whether
  an AI agent is executing it.

  If you are an AI agent:
    Consider the user's project and intended use.
    If the answer is clear from context, explain your reasoning
    and ask the user to confirm.
    If unclear, explain both options and ask the user to choose.
    Do not assume or select a license mode without user approval.

  After confirmation, run one of:

    wpsync license init --personal
    wpsync license init --business

  Commercial licenses: https://wpsync.dev/buy
  ```

  When the terms add the grant for monetized personal blogs, "free for
  personal use under PolyForm Strict License 1.0.0" should point to that grant
  too, since PolyForm alone does not cover them.
- **Licensed:** each command's terminal output shows "WPSync — Licensed to
  Acme Corp" and "Commercial license valid until 2027-11-10". The business
  name and expiry are part of the license.
- **Offline checking:** the license is digitally signed (Ed25519), and WPSync
  verifies it locally with a public key it ships with. No server contact on
  each run, no device fingerprinting, no mandatory online activation.
- **Expiry:** a 14-day grace period in which commands still work but warn with
  the renewal link; after it, operational commands stop until a renewed
  license is installed.
- **No silent fallback:** an expired license never turns into personal use, and
  invalid or corrupted license data is an error, not personal use.
- **Always available:** `--help`, `--version`, and `wpsync license status` (and
  `license install`) work whatever the trial or license state.
- **Deleting the local state** may get around the limits; that is a breach of
  the license terms, not something WPSync tries to prevent.
- **Terms:** separate commercial license terms for the paid subscription, and
  terms that explicitly permit commercial use during the 30-day trial;
  PolyForm Strict alone grants neither.
- **Secrets** such as the signing key and webhook secret live only in
  environment variables (see `AGENTS.md`).
- **Extras for businesses,** if any, would be separate private code downloaded
  with a valid license. Not designed until there is such a feature.

## Open

- **Exact price** within roughly $69–$99 per year.

## Later

- **License keys:** whether Polar's built-in keys can serve, or a small
  licensing service turns Polar purchases and renewals into signed licenses.
- **License workflow:** delivering licenses and renewals (for example an
  on-demand `wpsync license refresh`), and where the licensing service runs.
- **Terms:** the commercial and trial terms and the personal-blog grant,
  drafted from PolyForm's structure, then checked by a lawyer.

## Work, once the open items are settled

1. The commercial and trial terms.
2. In WPSync: the first-run choice, trial tracking, `wpsync license status`
   and `install`, offline signature checks, the notices, and the
   expiry and grace rules, all stored in `~/.wpsync/config.json`.
3. The licensing service and the Polar webhook, with a script to issue a
   license by hand until then.
4. The website: pricing, the `/buy` forward, and the checkout link.

## Original brief

I want to add commercial licensing and registration to WPSync.

WPSync uses **PolyForm Strict License 1.0.0**, meaning it's free for personal use, but businesses need a paid commercial license. I'm thinking of charging somewhere between **$69–$99/year**. The commercial license is a yearly subscription, not a perpetual license. When it expires, the user needs to renew to continue using the app commercially.

For payments, I want to use **Polar (polar.sh)** as the Merchant of Record. It'll handle checkout, subscriptions, taxes, invoicing, etc. I don't want to build payment infrastructure or deal with tax compliance myself.

Here's how I want licensing to work.

**On first run**, WPSync should ask the user how they intend to use it: personal or business.

- **Personal use:** Free indefinitely. The app works normally, but clearly displays "Personal use only" in the terminal when commands run. No registration or account required.
- **Business use:** Starts a free **30-day trial**, with no credit card, account, or online activation required. The app is fully functional during the trial and displays how many days remain, along with a link to purchase a license.

The selection should be stored locally and persist between runs. Once someone selects business use, they shouldn't be able to simply switch back to personal mode through the normal CLI flow.

During the business trial, I'd like the terminal messaging to become more prominent as expiration approaches. For example, during the first 23 days, just show a brief notice with the number of days remaining and a registration link. During the last 7 days, show a more prominent warning.

When the 30-day trial expires, WPSync should **stop performing operational commands** until a commercial license is installed.

The user can follow the registration link to purchase a subscription through Polar. After purchasing, they'll receive a license key that they can install locally.

I'd like commands along these lines:

- `wpsync license status` — displays the current license or trial status.
- `wpsync license install <key>` — installs a commercial license.

The exact command UX can follow WPSync's existing CLI conventions.

Once registered, WPSync should display something like:

```
WPSync — Licensed to Acme Corp
Commercial license valid until 2027-11-10
```

The registered business name and expiration date should be part of the license information.

**License validation should work offline.** I'm thinking of digitally signed licenses that WPSync can verify locally, without having to contact a server every time a command runs. We don't need device fingerprinting, mandatory online activation, or elaborate DRM.

When a commercial license expires, I'd like a **14-day grace period** during which the app remains fully functional but displays a warning and renewal link. After that, operational commands should stop working until a renewed license is installed.

An expired commercial license must **not automatically fall back to personal-use mode**.

Similarly, invalid or corrupted license information should produce an appropriate error rather than silently allowing personal use.

Informational and license-management commands, such as `--help`, `--version`, and `wpsync license status`, should continue working even when a trial or license has expired.

If someone deliberately deletes their local license or trial state, they may be able to circumvent these restrictions. I'm not particularly concerned about that. They'd be violating the licensing terms if they continued using WPSync commercially without paying. The goal is to provide clear licensing and sensible enforcement for legitimate users, not to build an anti-piracy system.

We will need separate **commercial licensing terms** covering the paid subscription, as well as terms explicitly permitting commercial use during the 30-day trial. PolyForm Strict alone doesn't grant those rights.

For the Polar integration, I'd prefer to keep things simple. Polar should handle purchases and subscription renewals, while WPSync handles local license validation. We'll need a way to generate signed licenses after purchases and issue updated licenses following renewals, probably using Polar webhooks and a small licensing service. We should investigate whether Polar's built-in license key functionality can cover our requirements before implementing our own.

I'd also like the purchase URL displayed in the CLI to be something stable like `https://wpsync.com/buy`, rather than a Polar-specific URL, so we can change payment providers later without changing the app.

Overall, the experience I'm after is straightforward:

**Install WPSync → choose personal or business use → try it free for 30 days if business → purchase online → install license → continue working offline.**

I want this to feel lightweight and natural for a CLI tool. No unnecessary accounts, no complicated activation, and no payment-related dependencies in the normal command execution path.

Let's work with the existing WPSync architecture and CLI conventions, keeping the implementation simple rather than introducing a large licensing framework.
