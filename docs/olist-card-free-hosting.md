# Card-free account setup for the Olist portfolio demo

The selected target is Render Free web plus Neon Free PostgreSQL. Account signup is the
current owner step. Application activation follows evaluation and deployment verification.

1. [Create/sign in to Render](https://dashboard.render.com/register). Keep billing details
   empty and use the free account. Do not create a database or web service yet.
2. [Create/sign in to Neon](https://console.neon.tech/signup). Keep the account on Free.
3. Stop after account login. Never paste passwords, connection strings or model keys into
   chat. If either signup requires a card, stop without entering one or upgrading.

Once the accounts are available, the deployment work will create one dedicated free
database and a separate restricted runtime role, check schema/guard compatibility, connect
only this GitHub repository to a Free web service, and use its supplied HTTPS hostname.
Administrative credentials stay outside the web runtime. The Neon console's default roles
can inherit administrator privileges; `olist_demo_host.preflight` deliberately refuses them.

Before activating the service, complete the actual live evaluation, compose durable model
admission outside Render's filesystem, provision isolated visitor accounts, verify the
deployed memory/concurrency limits and restore the data plus accounting from an encrypted
off-host backup. A tested local database adapter is not cloud recovery evidence.

Limits: Render may sleep and cold-start; its local files are discarded on restart. Neon
Free can suspend at quota limits. No paid fallback or availability guarantee is implied.
No free Render Postgres instance is selected because it expires. The managed binary restore
helper requires the exact source build; a service upgrade can invalidate that path until
a portable logical restore is separately verified.

Primary references checked2026-11-17: [Render Free](https://render.com/docs/free),
[Render first deployment](https://render.com/docs/your-first-deploy),
[Neon pricing](https://neon.com/pricing), [Neon roles](https://neon.com/docs/manage/roles),
[Neon secure connections](https://neon.com/docs/connect/connect-securely).
