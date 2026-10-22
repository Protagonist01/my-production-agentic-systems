# production-agent-supply-chain

Import package: `supply_chain`. S1 prepares pinned original DataCo shipping observations and a separate official NWS alert snapshot. Public views exclude delivery outcomes and customer identifiers, enforce actual observation/capture clocks and require an explicit weather freshness allowance. Historical shipping timezones remain unverified; contemporary US alerts are not joined causally to historical international shipments.

See [source commands/provenance](../../docs/supply-chain-source.md) and the [source walkthrough](../../docs/code-study-supply-source.md). Original files and per-record stores remain outside Git. Simulator, interventions, model quality and release acceptance remain later work.
