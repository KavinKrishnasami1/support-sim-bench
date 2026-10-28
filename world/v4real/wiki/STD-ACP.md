---
page_id: STD-ACP
title: Access Control Standard
type: standard
revision: 2.3
effective: 2024-11-04
owner: Security team
adapted_from: "UK Ministry of Justice security guidance, access-control-policy (MIT licence, Copyright (c) 2017 Crown Copyright (Ministry of Justice)). Adapted for a fictional company."
licence_notice: "Portions Copyright (c) 2017 Crown Copyright (Ministry of Justice), used under the MIT licence; see SOURCES.md."
---

# STD-ACP: Access Control Standard

This standard sets out how access to Quillmark information and systems is controlled. Statements are numbered
POL.ACP.xxx. Where a statement here conflicts with POL-100 or a procedural guide, see POL-100 1.3.

Some statements cover technical controls that are the responsibility of System Designers rather than IT Help; they
are marked [design].

## Principles

POL.ACP.001: The company must provide a unique ID that is assigned, and in use by, only one person.

POL.ACP.002: To access company systems, users must authenticate with their unique ID and MFA.

POL.ACP.003: Specifying access rights, and the reason for access, must be part of every access request.

POL.ACP.004: Successful and unsuccessful attempts to access systems and user activities conducted while using
systems must be logged. [design]

POL.ACP.005: This access control policy must be established and maintained, and reviewed annually.

POL.ACP.006: The policy must also follow the additional principles of "need to know" and "need to use", and least
privilege.

## Information access restriction

POL.ACP.007: The company must strive to prevent unauthorised access to systems.

POL.ACP.008: Access to information and application system functions must be restricted in line with this standard.

POL.ACP.011: Multi-user (MU) accounts must be managed carefully using PAM or a bastion server. [design]

## Passwords

POL.ACP.014: Passwords must not be stored or transmitted over the network in clear text.

POL.ACP.020: Users must change a password initially received by a system or support team before carrying out
company tasks.

POL.ACP.021: Password history and blocking of commonly guessed passwords must be enabled in a system. Regular
password change is not required, as it is an outdated and ineffective practice.

## User registration and de-registration

POL.ACP.024: A formal user registration and de-registration process must be implemented to enable the assignment of
access rights, specifically:

POL.ACP.025: Multi-user or shared ID accounts must only be used directly if there is no alternative.

POL.ACP.026: The identity of the new user must be confirmed.

POL.ACP.027: The hiring manager must submit a role-based access request on behalf of the new user.

POL.ACP.030: De-registration of users must be at the request of line managers and follow the leavers process in
PG-03-23. The following controls need to be adopted for leavers:

  POL.ACP.031: Line managers must authorise account removal.

  POL.ACP.032: User accounts and their access rights must be removed once an individual has left the organisation or
  no longer requires access to the system(s).

  POL.ACP.033: Existing user accounts must be reviewed every three months by the System Administrator to confirm those
  not used in the last three months, and then with the People team to approve accounts for removal.

  POL.ACP.034: Remote access authentication token usage must be reviewed by the System Administrator every three
  months, and when a token is identified as unused in the last three months, the account disabled.

  POL.ACP.035: Assigned user roles and privileges must be reviewed every six to twelve months, and those no longer
  required removed.

## User access provisioning

POL.ACP.036: A formal user access provisioning process must be implemented to assign or revoke access rights for
all users to all systems and services.

POL.ACP.038: MFA must be used to ensure access to company information.

POL.ACP.041: System Administrators must maintain an active list of all active and suspended users.

POL.ACP.043: A user leaving must move their data to a shared folder if needed for retention.

POL.ACP.044: If anyone with a company account leaves the organisation, system administrators must retrieve the
user's equipment and suspend the account.

POL.ACP.045: If a user leaving has not returned all company assets, the line manager must initially contact IT Help
and raise a security incident.

## Privileged access

POL.ACP.046: The allocation and use of privileged access rights must be restricted and controlled.

POL.ACP.047: Users must only use their system administrator account when elevated privileges are required.

POL.ACP.048: MFA must be used with privileged accounts. See GUI-PAM.

## Secret authentication information

POL.ACP.051: The allocation of secret authentication information must be controlled through a formal management
process.

POL.ACP.053: System Administrators and systems must never send passwords by email, as it is an unsecured channel.

  POL.ACP.054: Instead, users must receive a time-limited password-reset link or code to their registered email
  address or phone number. Refer to "Send a link to trigger password reset" (external guidance, not mirrored).

## Review of user access rights

POL.ACP.055: System Administrators must review users' access rights at regular intervals. The review of user access
rights is covered in this standard under User Access Provisioning.

POL.ACP.056: All employees' and external party users' access rights to information and information processing
facilities must be removed upon termination of their employment, contract or agreement, or adjusted upon change.

POL.ACP.057: All users must follow the company's password policy.

For further information on user de-registration, refer to the Enterprise Access Control Policy (page retired; see
PG-03-23).
