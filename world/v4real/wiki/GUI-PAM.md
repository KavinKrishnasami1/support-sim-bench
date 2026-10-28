---
page_id: GUI-PAM
title: Privileged Account Management Guide
type: guidance
revision: 1.1
effective: 2024-08-20
owner: Security team
adapted_from: "UK Ministry of Justice security guidance, privileged-account-management-guide (MIT licence, Copyright (c) 2017 Crown Copyright (Ministry of Justice)). Adapted for a fictional company."
licence_notice: "Portions Copyright (c) 2017 Crown Copyright (Ministry of Justice), used under the MIT licence; see SOURCES.md."
---

# Privileged Account Management Guide

## Introduction

This guide explains how to manage privileged accounts in order to minimise the security risks associated with their
use. This is a sub-page to PG-01-07.

## How to manage privileged accounts

Holders of privileged accounts, such as system administrators, have privileges to perform most or all of the
functions within an IT operating system. Staff should have privileged accounts only when there is a business need,
in order to prevent malicious actors gaining privileged access to systems. The company requires that ownership and
use of privileged accounts must be monitored and audited on a monthly basis.

At Quillmark, a person with privileged access has a separate administrator account (`account: admin`) alongside
their standard account (`account: standard`).

Privileged accounts should be protected with the following controls.

### DO

✔ Ensure that privileged users only use their system administrator account when elevated privileges are required.
Their general user account should be used for all other work activities.

✔ Ensure that management or administrative access is limited to users who have been suitably authenticated and have
been authorised to perform the specific action.

✔ Ensure that Multi Factor Authentication (MFA) is used, and that it is phishing-resistant (a security key; see
PG-01-01 Table 2-1). Where MFA cannot be used on a system, this is considered an exception and should be logged in
the risk register by Security, not by IT Help.

✔ Ensure that MFA is mandated for a privileged user to conduct important or privileged actions such as changing
fundamental configurations including changing registered email addresses or adding another administrator.

### DON'T

✖ Allow privileged users to use their privileged accounts for high-risk functions. These include reading emails, web
browsing, or logging into a server as 'root'.

✖ Leave default or factory set passwords for any accounts.

✖ Allow a user to have a privileged account, unless they require it for that specific service.

✖ Weaken sign-in for an administrator account, for example with one-time codes or an MFA exception (POL-100 6.2).
