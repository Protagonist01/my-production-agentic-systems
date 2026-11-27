# Azure database and operating plan for the five agent demos

## Approved deployment default

Reuse the existing private Canada Central Azure PostgreSQL Flexible Server and Container Apps environment for the five **SIM portfolio demos**. Give each agent a separate logical database, database owner or migration role, least-privilege runtime login, and Container App. Use these boundaries in every deployment session. Keep connection strings in that app's secret configuration. Run migrations through a separate, temporary job or administrator connection. Use verified TLS and private database networking.

| Agent | Database | Rollout state |
|---|---|---|
| Olist Support | `olist_demo` | Existing deployment |
| Revenue Integrity | `revenue_demo_recording` | First new database on the shared server |
| CFPB Triage | `cfpb_demo` | Name reserved in this plan |
| Prior Auth | `prior_auth_demo` | Name reserved in this plan |
| Supply Chain Disruption | `supply_demo` | Name reserved in this plan |

Separate logical databases let us provision, migrate and restore one agent at a time. One shared server buys one baseline of compute and storage for the demos. It also makes database maintenance, storage exhaustion and server failure shared events. Keep evaluation corpora, bulk experiments and telemetry off the serving server. The shared provider-attempt ledger, if hosted there, uses its own database and operator credentials. Treat real customer, patient, complaint and billing workloads as separate release decisions that need their own access, recovery and data-handling requirements. [Azure PostgreSQL pricing](https://azure.microsoft.com/en-us/pricing/details/postgresql/flexible-server/)

## Before each agent goes live

1. Review the Azure preview for the exact existing server and network, the new app or revision, and any cost changes. Use the existing Burstable capacity while the measured workload fits. Run one deployment or schema migration at a time during the initial rollout.
2. Revoke database `CONNECT` and `TEMPORARY` from `PUBLIC` on the new database. Grant access to the named migration and runtime principals only as needed. Before opening another demo, inspect existing portfolio database grants and scope any change to named databases and roles. Test from the app network that the new runtime can connect to its own database, cannot connect to a peer's database, and cannot perform schema changes or erase its ledger. Also check the reverse peer-to-new boundary. Azure server administrators remain trusted. [PostgreSQL privileges](https://www.postgresql.org/docs/current/ddl-priv.html)
3. Keep the initial replica count at one or less. Set an explicit connection budget per runtime login and a per-request or pool admission limit, counting background workers and simultaneous old/new revisions. Start with a ceiling of eight concurrent database sessions for Revenue and reserve headroom for administration, rollbacks and peer apps. Measure before raising it. As a planning budget, cap aggregate app allocations at 70% of the measured usable server connection ceiling. CPU, memory and I/O can saturate earlier. [Azure PostgreSQL connection limits](https://learn.microsoft.com/en-us/azure/postgresql/configure-maintain/concepts-limits)
4. Use separate liveness and database readiness probes. A database outage should make a revision unready. Keep HTTP errors bounded and avoid retries that amplify the incident. Check one known-good request, anonymous denial and a replayed operation after each deployment. Record the app revision, digest, access test and actual result.

## Incident playbook and rehearsal

Thresholds below are starting alert settings for the SIM fleet. Recalibrate from observed baseline and load tests. Record UTC incident timestamps, the affected agents and the recovered data point.

| Scenario | Response | Recovery evidence |
|---|---|---|
| One agent gets a traffic spike | Compare per-agent request rate, p95 latency, error rate and DB sessions with shared CPU, credits, memory and disk. Sample every minute. Investigate sustained 70% connection use or steadily declining CPU credits over 15 minutes. Limit admission for the busy app and pause its background work. Preserve peer access before scaling replicas. | On an isolated copy, drive one agent's load to its cap while making steady requests to two peers. Record admission failures, peer latency and ledger duplicates. Tune queries or pooling first. Resize the shared server if normal fleet load is the cause. Move the hot agent to a dedicated server if it repeatedly degrades peers after tuning. |
| Database timeout or server outage | Stop launching mutations when persistence is unavailable. Return a retryable unavailable response, preserve any known operation ID and reconcile its receipt when service returns. Cap read retries with jitter. An interrupted write remains ambiguous until readback. | Interrupt a disposable PostgreSQL server before and after commit. Verify failed readiness, bounded responses, recovered readiness, and one approval/effect/receipt after replay. For loss of the server, restore to a new Azure server and reconnect apps only after checking isolated grants and each ledger. |
| One database is corrupted or a migration fails | Stop writes for that agent and record the last known good point. Recover its database from a verified logical backup, or export it from a point-in-time restored server into a separate target. Leave peers on their existing databases. Roll code back only to a schema-compatible revision. | Verify schema version, principal boundaries and record/receipt counts before changing the affected app's DSN. Run its known approval/replay journey. Measure actual elapsed restore time and data loss. |
| Bad application revision | Hold the readiness gate or shift back to the previous ready image digest. Avoid coupling the code rollback to an unrelated database restore. | Verify the active digest and run an authenticated read plus receipt replay. Retain the failed revision's timing and diagnosis without raw customer data. |

Use Azure metrics for server saturation. Attribute demand using per-app request metrics and database/user session counts. For a connection-heavy app, consider pooling after testing session/transaction behavior and measuring the gain. The shared server's Azure point-in-time restore creates a new server. Keep a per-agent logical restore playbook and rehearse both recovery paths before promising recovery times. [Azure metrics](https://learn.microsoft.com/en-us/azure/postgresql/monitor/concepts-monitoring) · [Azure backup and restore](https://learn.microsoft.com/en-us/azure/postgresql/backup-restore/concepts-backup-restore) · [Container Apps revisions](https://learn.microsoft.com/en-us/azure/container-apps/revisions)
