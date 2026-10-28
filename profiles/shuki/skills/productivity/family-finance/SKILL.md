---
name: family-finance
description: Use when managing family brokerage accounts or trades.
version: 1.0.0
author: Eluzix, Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [family, finance, portfolio, brokerage, tracker]
    category: productivity
    related_skills: []
---

# Family finance

Manage the family's brokerage accounts through the local portfolio-tracker MCP. The server name is `family_finance`. Do not query the database, print credentials, or shell into `tracker` for account data when these tools are available.

## When to Use

- Holdings, balances, performance, dividends, account lists, tags, or owners.
- Buy/sell history, recording a trade, or deleting a recorded trade.
- Questions about family investment accounts in USD or ILS.

Do not use this for bank cash, bills, credit cards, or market-data refresh unless the user explicitly asks to update prices.

## Tools

Call the registered tools directly:

- `mcp__family_finance__portfolio` — optional `tag` (`All` when omitted) and `currency` (`USD` or `ILS`, default `USD`). Returns every matching account plus a total. This is the account directory.
- `mcp__family_finance__account` — required `account_id`; optional `currency`. Metadata, metrics, and holdings. No transaction list.
- `mcp__family_finance__account_transactions` — required `account_id`; optional `show_dividends` (default true). History is always USD cents.
- `mcp__family_finance__add_transaction` — record a Buy or Sell.
- `mcp__family_finance__delete_transaction` — delete one recorded Buy or Sell.

If those tools are absent, say this session has not loaded the MCP server. Do not invent holdings or bypass the server. A new session or `/reload-mcp` loads it. New Hermes profiles get the server from `~/.hermes/bin/install-family-finance`.

## Reading results

- Money fields are integer cents. Show them in the returned currency with two decimals. Never send a dollar amount to a cents field.
- `gain_ratio`, `annualized_yield_ratio`, and `modified_dietz_yield_ratio` are fractions, not percents. Display a defined ratio as a percent. A null yield is undefined; do not render it as zero.
- Holdings are `symbol`, whole-share `quantity`, and `value_cents`.
- Account identity is `id`, `name`, `owner`, `institution`, `tags`, and `status`. Resolve a name, owner, or tag from `portfolio` before any id-scoped call. If more than one account matches, ask which one.
- Transaction rows are `recorded` (Buy/Sell, deletable) or `derived` (Dividend/Split, not deletable). For a split, `split_ratio` is the share multiplier; it is not a price, and price/total are null.
- `dividend_tax_rate` defaults to 0.25 unless `TRACKER_DIVIDEND_TAX_RATE` is set. `dividends_after_tax_cents` already applies that rate.

## Writes

Writes go to the shared remote-backed database and are visible to every profile. Never add or delete unless the user explicitly asked for that change.

Before `add_transaction`, restate and wait for confirmation: account name and id, date (`YYYY-MM-DD`), type (`Buy` or `Sell`), symbol, whole-share quantity, USD price per share, and total (quantity times price). Send `price_per_share_cents` as a positive integer. Quantity must be a positive integer. Type is only `Buy` or `Sell`.

Before `delete_transaction`, restate account id, transaction id, date, type, symbol, quantity, and total, and wait for confirmation. Only a recorded Buy or Sell belonging to that account can be deleted. A missing id is a failure, not a success.

After either write, report the tool result, including the generated id for an add. Do not claim the change landed if the tool returned an error.

## Limits

This MCP cannot create or edit accounts, record cash deposits or withdrawals, or refresh prices. Price refresh is `tracker update` via `~/.hermes/scripts/tracker_update.py`, which loads `TRACKER_DATABASE_URL`, `TRACKER_AUTH_TOKEN`, `MARKETSTACK_API_KEY`, and `EXCHANGE_RATES_API_KEY` from the environment or shell rc files. A nightly cron, `30 23 * * *` America/New_York, runs that script with no agent and no success delivery. Run it only when asked outside that schedule. ILS conversion uses the stored `ILS` rate and fails if that rate is missing. Never print `TRACKER_DATABASE_URL`, `TRACKER_AUTH_TOKEN`, or other credentials.
