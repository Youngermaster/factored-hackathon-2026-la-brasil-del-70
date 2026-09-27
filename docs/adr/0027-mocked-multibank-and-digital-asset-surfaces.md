# 0027: Multi-bank connectors and digital-asset tabs start as mock surfaces

- Status: accepted
- Date: 2026-09-27

## Context

After the initial account-inquiry and escalation work, the app may expand beyond the organizer's single synthetic-bank dataset. Customers could bring in or export their financial information across institutions in Latin America. The product roadmap also includes a crypto tab for BTC, ETH, SOL (Solana), and XRP, and a separate “xStocks on Solana” tab.

These are exploratory product directions, not part of the Tuesday release. The hackathon should be able to demonstrate the navigation and data flows without credentials, live bank connections, wallets, custody, exchange integrations, or trading services.

## Considered options

1. **Build a connector or digital-asset service now.** Could provide real external data, but requires institution-specific integrations and raises data-access, security, and financial-action concerns beyond the current hackathon scope.
2. **Use explicit mock adapters and non-functional “coming soon” tabs.** Demonstrates the intended product surfaces and stable contracts while keeping all external data and digital-asset behavior synthetic.
3. **Omit these product areas entirely.** Lowest implementation cost, but gives no way to communicate or test the planned multi-bank and digital-asset experiences.

## Decision

Choose option 2 as a later, mock-only product increment. Neither surface is part of Tuesday's release.

### Mock Latin American bank connectors

- Define a provider-neutral connector contract for importing and exporting customer-authorized financial information. Keep connector methods and schemas explicit about supported data, provenance, currency, and source institution.
- Implement only mock adapters over team-made synthetic fixtures. The app may demonstrate reading/importing balances or transaction history and exporting a customer-approved summary or file, but it must label the source and mock status clearly.
- Prioritize a short list of representative, high-usage banks in the target Latin American markets in a later planning step. Do not claim support for a bank until its connector path is implemented; no live integration or bank credential collection is included in this mock increment.
- Imported information is available for the customer's own account questions and, only with the separate consent in ADR 0026, personalized memory. It is retrieved as user data; it is not used to train or fine-tune a model.
- Keep every import/export scoped to the authenticated customer, auditable by conversation or transfer ID, and explicit about stale, missing, or mock data. Export requires the customer's confirmation of the destination and data being shared, even when the demo uses a local fixture.

### Crypto and xStocks tabs

- Add a crypto navigation tab listing BTC, ETH, SOL, and XRP, and a separate xStocks tab labeled for the Solana ecosystem. Until a later feature decision, both are clearly marked **Coming soon** and have no functional wallet or transaction actions.
- Any hackathon visual demonstration uses labeled mock/static data. It does not show a live portfolio balance, live price, yield, or completed trade as if it were real.
- Do not collect seed phrases or private keys, connect a wallet, hold assets, route a transaction, or execute a purchase or sale in these mock surfaces.
- Treat xStocks as a separate digital-asset surface from the four named cryptocurrencies; do not imply that a stock token or its underlying share is held, available, or purchased by the demo.

## Consequences

- The connector contract can later support real provider adapters without putting bank-specific behavior in the assistant or workflow code.
- “Most important banks” needs a later, evidence-based selection by country and market; this ADR intentionally records no unsupported bank-coverage claim.
- Mock bank data must remain visibly distinct from the organizer dataset and from any future institution-sourced data.
- The digital-asset tabs communicate roadmap intent only. Any future live market data, wallet connection, or transaction capability needs a separate scope, policy, security, and evaluation decision.

## References

- [ADR 0024: Tuesday MVP is account inquiry plus simulated human escalation](0024-tuesday-account-inquiry-mvp-and-observability.md)
- [ADR 0026: Personalized financial companion features are opt-in and grounded](0026-opt-in-financial-companion-and-agent-personalization.md)
- [Data card: provenance and intended use](../data/data-card.md)
