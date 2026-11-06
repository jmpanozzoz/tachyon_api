# Production pilot record

Status: template; no production participant or result claimed.

Record the service owner, bounded use case, synthetic/test phase, real traffic
approval, data boundary, dependencies, chosen artifact/source hash, platform,
expected load, support contacts and rollback owner. Record why Tachyon was chosen
and the documented differences that matter compared with the existing framework.

Before real traffic, attach installed-package/Linux validation, representative
DB/cache load, authorization checks, observability, backup/restore and rollback
drills. Agree p95/p99, error, memory, queue and recovery budgets for this workload.
Define explicit conditions to stop/reroute traffic and the accepted data-loss
boundary. A single test server or demo is not a production pilot.

During the observation period, record deploys, incidents, unexpected errors,
latencies, resource/pool/queue trends and developer friction. Measure time to
first endpoint, first test and first deployment. Start with two weeks only if
that includes representative events; extend when it does not.

At review, report criteria met/missed, limitations, resolved/unresolved incidents,
rollback result, remaining maintenance cost and the owner's adoption decision.
Publish a sanitized case study only with participant permission. Do not publish
names, logos, credentials, personal data or invented traffic/adoption metrics.
