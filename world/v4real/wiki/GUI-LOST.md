---
page_id: GUI-LOST
title: Lost devices or other IT security incidents
type: guidance
revision: 1.2
effective: 2024-03-01
owner: Security team
adapted_from: "UK Ministry of Justice security guidance, lost-devices-incidents (MIT licence, Copyright (c) 2017 Crown Copyright (Ministry of Justice)). Adapted for a fictional company."
licence_notice: "Portions Copyright (c) 2017 Crown Copyright (Ministry of Justice), used under the MIT licence; see SOURCES.md."
---

# Lost devices or other IT security incidents

This guidance applies to all staff and contractors who work for Quillmark.

## What to do if your device is lost, stolen, or compromised

If company data or information is lost or compromised, you should always report it as a data incident.

You can help reduce problems by making sure that devices used for company tasks are always shut down before leaving
company premises. Locking a laptop, or 'putting it to sleep' is not completely secure.

If you think your device is lost, stolen, 'hacked', or in some way compromised, you must:
- Contact IT Help. The analyst will ask the relevant questions and note responses on the ticket.
- Tell your line manager as soon as possible.
- For a lost or stolen device, contact the Police and make sure you get the incident reference number.

"Device" includes laptops, phones and security keys.

## What IT Help does

- Revoke the lost authenticator or device (`revoke_authenticator`), so it can't be used to sign in.
- Report it to Security (`report_security_incident`, kind `lost_device`).
- If the person still needs to work, see PG-01-01 for temporary sign-in options.

If you aren't sure whether a device is lost or only misplaced, treat it as lost.
