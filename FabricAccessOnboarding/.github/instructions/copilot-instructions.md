---
applyTo: "**"
---

# Fabric access onboarding instructions

- Follow the stages in `prompts/fabric-access-onboarding.prompt.md` in order.
- Resolve named people to exact Entra users; never infer email addresses from names.
- Never guess tenant, catalog, group, access package, policy, workspace, or identity object IDs.
- Reuse exact-name resources when they already exist and verify persistent state after each write.
- Do not create a missing entitlement catalog directly. Prepare the approved catalog request workflow and stop until the catalog exists.
- Show the recipient and exact email body and obtain explicit confirmation before sending outbound email.
- Never reveal or persist browser, Microsoft 365, Graph, Fabric, or Power BI access tokens.
- Distinguish the Fabric workspace ID from the workspace identity ID.
- Require explicit confirmation before destructive actions or access removal.
- Report completed, blocked, and unverifiable stages separately.