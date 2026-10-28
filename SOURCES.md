# Sources for the v4real suite

v4real tests whether real, messy source material makes frontier models fail where designed tasks didn't (see
[V4_DESIGN.md](V4_DESIGN.md)). This file records every outside source, its terms, and exactly what we took from it.
Sources for v1 and v2 (ABCD) are in [PROVENANCE.md](PROVENANCE.md). v3 used no outside sources.

**Ground rules**
- The company, people, systems and records are all fictional (Quillmark Labs, as in v3).
- Nothing here comes from, or refers to, any real company's internal product, data or processes. The policy
  sources are documents that public agencies published for anyone to read.
- No raw source files are stored in this repo. `scripts/fetch_v4_sources.sh` downloads the
  pinned versions below and checks their SHA-256.

## 1. IT policies (adapted into the Quillmark policy wiki)

We were looking for long, cross-referenced policies with exceptions and ambiguity, on terms that allow adapting
them. University IT policies were checked first. The ones we found are all-rights-reserved, so none are used. US
federal works are public domain, and the UK Ministry of Justice publishes its security guidance under the MIT
licence. Those are what we used.

| ID | Document | Publisher | Version | Terms | SHA-256 |
|---|---|---|---|---|---|
| P1 | [IT Security Procedural Guide: Access Control (AC), CIO-IT Security-01-07](https://origin-www.gsa.gov/system/files/Access-Control-%28AC%29-%5BCIO-IT-Security-01-07-Rev-8%5D.pdf) | US General Services Administration (GSA) | Revision 8, 2026-02-05 | US government work, public domain (17 U.S.C. §105). Not endorsed by GSA. | `e41234d552fb48a50ceaafc810e7624f420f50079e3cc3f884ddf9abea631b26` |
| P2 | [IT Security Procedural Guide: Identification and Authentication (IA), CIO-IT Security-01-01](https://www.gsa.gov/system/files/Identification-and-Authentication-%28IA%29-%5BCIO-IT-Security-01-01-Rev-8%5D.pdf) | GSA | Revision 8 | Public domain, as P1 | `e1c717090459ad111fa37c271ed36b19928259eccf962c58b57d27ce51d7e6c3` |
| P3 | [IT Security Procedural Guide: Termination and Transfer, CIO-IT Security-03-23](https://www.gsa.gov/system/files/Termination-and-Transfer-%5BCIO-IT-Security-03-23-Rev-6%5D-04-19-2022docx.pdf) | GSA | The file name says Revision 6 (2022-04-19), but the cover says Revision 7. We kept this mismatch. | Public domain, as P1 | `0254469ab08df160540b84f7a6c65230818fd7d002d4a81841fbfb14931b9916` |
| P4 | [MoJ Security Guidance](https://github.com/ministryofjustice/security-guidance) (DITA sources): `access-control-policy`, `long-term-leave`, `accessing-moj-it-systems-from-overseas`, `acceptable-use-policy`, `lost-devices-incidents`, `privileged-account-management-guide` | UK Ministry of Justice | commit `15c1c838835ee52185fe22134889780b3d7d241a` | MIT licence, "Copyright (c) 2017 Crown Copyright (Ministry of Justice)". Its notice is reproduced in each adapted wiki page and below. The repo's OGL-licensed content comes from GDS's "The GDS Way", and the pages we used contain none of it. | per file, in `scripts/fetch_v4_sources.sh` |

**How the policies were adapted**
- **Kept:**
  - section structure and numbering style (control IDs with bracketed parameters, `POL.ACP.0xx` statements);
  - cross-references between documents;
  - "Appendix: policy statements" sections that quote the top-level policy, together with their supersession note
    ("When [the top policy] is updated, the statements within it will supersede the policy statements below").
  - the sources' overlapping timelines (14 / 30 / 90 days, 24 hours, "immediately"), exceptions and exemptions,
    "may" against "must", "line managers are empowered to determine", and "if you are unsure, go to Part Two";
  - internal contradictions. For example, P2's body allows password-reset verification by questions "only expected
    to be known by the user", while also saying knowledge-based questions are discouraged.
- **Changed:**
  - agency-specific terms were replaced with generic ones: PIV card → security key, ISSO → system security owner,
    COR → contract sponsor, OHRM → People team, ServiceNow catalog paths → generic desk request types;
  - real intranet URLs, phone numbers and personnel names were removed;
  - dead links to pages that no task needs were kept as dead links, because real wikis have them;
  - P4 states its modal verbs through DITA conrefs (for example `policymust` → "must"); these were restored.
- **Added, and marked as Quillmark-specific in V4_DESIGN.md:**
  - a current version of the top-level policy (POL-100), whose wording has drifted from the old version quoted in
    the guides' appendices;
  - a page that defines the travel regions. The source names regions but doesn't define them.

MIT notice for content adapted from P4:

> Copyright (c) 2017 Crown Copyright (Ministry of Justice). Permission is hereby granted, free of charge, to any
> person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the
> Software without restriction, including without limitation the rights to use, copy, modify, merge, publish,
> distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is
> furnished to do so, subject to the following conditions: The above copyright notice and this permission notice
> shall be included in all copies or substantial portions of the Software. THE SOFTWARE IS PROVIDED "AS IS",
> WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED. (Full text: the repository's `LICENCE` file.)

## 2. Support threads (the shape of requests only)

We took **the shape of each conversation only**: how vague the first message was, wrong assumptions, missing
details, the order of the back-and-forth, and changes mid-thread. No text, usernames, names, emails, hostnames,
group names or other identifiers were copied. Each thread was read through a summarising step that was told to
drop all personal details. Every person and identifier in the tasks is invented.

| ID | Thread | Site and terms | Shape we took |
|---|---|---|---|
| S1 | [Phabricator T305634](https://phabricator.wikimedia.org/T305634) | Wikimedia Phabricator, CC BY-SA 4.0 (site footer) | Asks for a restricted data group after a dashboard permission error, believing it only grants dashboard viewing, though it grants the raw data. Approval goes manager first, then data owner. The task is later renamed to the narrower scope. |
| S2 | [Phabricator T433258](https://phabricator.wikimedia.org/T433258) | as S1 | A request template with blank fields. Desk asks "is this only for dashboards?" The requester joins the lower tier, the charts time out, and they then ask for a higher tier. The access tiers confuse everyone. |
| S3 | [Phabricator T319014](https://phabricator.wikimedia.org/T319014) | as S1 | A precise request with a wrong assumption: one part of the provisioning would happen automatically. It didn't, and the access half-worked until an admin noticed. |
| S4 | [Phabricator T331170](https://phabricator.wikimedia.org/T331170) | as S1 | Lost phone with 2FA, emergency codes partly used. The requester assumes in-person verification is needed, asks for same-day help, then argues "a colleague says staff status alone should be enough". The desk asks for verification through a second channel. |
| S5 | [Phabricator T222028](https://phabricator.wikimedia.org/T222028) | as S1 | A 2FA reset request vague about which system. The desk asks which one, and asks for confirmation from the registered address. |
| S6 | [Phabricator T371644](https://phabricator.wikimedia.org/T371644) | as S1 | A departing person wants to keep some access and move ownership of something they maintain to a personal account, because they'll be back as a contractor in about two months. On the return date their access briefly breaks. |
| S7 | [Phabricator T383056](https://phabricator.wikimedia.org/T383056) | as S1 | A manager asks to remove a leaver's access with an incomplete list and unclear dates and scope, expecting more to be disabled than standard practice does. Mid-thread they remember a documented procedure. |
| S8 | [Server Fault Q190994](https://serverfault.com/questions/190994) | Stack Exchange, CC BY-SA 2.5 (posted 2010) | A user is locked out repeatedly, minutes after connecting, and blames the platform ("a friend said it's a known Windows issue"). The real cause is a second client retrying old credentials. |
| S9 | [Server Fault Q809295](https://serverfault.com/questions/809295) | Stack Exchange, CC BY-SA 3.0 (posted 2016) | An "unknown" mobile device keeps locking an account out. The likely answer is a device the user forgot they still had signed in. Could also be an attack, so the device list decides. |

Stack Exchange was also searched for end-user IT requests (MFA, leave, travel, transfers). Most results were
admin-to-admin troubleshooting, so only S8 and S9 were used. Public forums of commercial IT vendors were skipped:
their terms don't clearly allow reuse.
