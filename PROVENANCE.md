# Provenance

Every task is derived from one conversation in the **Action-Based Conversations Dataset (ABCD)** by ASAPP Research ([repository](https://github.com/asappresearch/abcd), commit `6b8700ce67c6b37b062dd7a60abc76d7ef832a97`, MIT license, Copyright (c) 2021 ASAPP Research). ABCD has about 10,000 human-to-human customer-service chats for a clothing retailer, each labelled with a policy-constrained flow such as refunds, order status, address changes and billing disputes.

**What we took from the source conversations:** the shape of the customer's behaviour (vague openings, details given one at a time, corrections, impatience with verification, third parties, pushback). **What we did not take:** any text, names, addresses, order numbers or the agents' actions. The ABCD agents sometimes break their own policy (for example crediting money back without checks), so the source chats are not used as labels. Every task was rewritten for food delivery with invented people, restaurants, orders and amounts.

The raw ABCD files are not in this repository. `scripts/download_abcd.sh` fetches the pinned version (SHA-256 checked), and `python scripts/show_source.py T05` prints the source chat for a task.

| Task | Title | ABCD convo | Flow / subflow | License | What we took |
|---|---|---|---|---|---|
| T01 | Late delivery: credit, not a card refund | 912 | order_issue / status_delivery_time | MIT | Customer opens vaguely about delivery timing and gives her name before any detail; agent must collect identifiers before acting. |
| T02 | Missing item: refund just that item | 9888 | shipping_issue / missing | MIT | Customer opens with a general 'question about my order', explains only when asked, and sends identifiers one message at a time. |
| T03 | Two missing items, customer prefers credit, mentions the second late | 6313 | product_defect / refund_initiate | MIT | Customer asks for the value as account credit for future purchases instead of a refund. |
| T04 | Wrong item: customer demands a full refund | 7239 | product_defect / return_color | MIT | Customer received the wrong variant of an item, and complains about how much information verification takes ('that's a lot of info'). |
| T05 | Whole order never arrived, over the refund limit | 1006 | shipping_issue / status | MIT | Customer chasing an order that should have arrived long ago, and mentioning a delivery detail (the address) that is wrong. |
| T06 | Address change while preparing, with a corrected detail | 2029 | manage_account / manage_change_address | MIT | Customer gives an address, then corrects one digit of it ('it should be 1908'). |
| T07 | Address change after pickup: refuse, no cancel, no goodwill | 3079 | shipping_issue / manage | MIT | Customer wants to change the address on an order whose shipping status is already past the point where it can change. |
| T08 | Very late order: customer demands $40, policy caps at $15 | 8598 | purchase_dispute / bad_price_competitor | MIT | Customer cites a competitor's better deal, presses the agent ('there's nothing you can do for your customers?'), and asks for more than the agent can give. |
| T09 | Unrecognized charge: escalate, don't refund | 3348 | purchase_dispute / mistimed_billing_never_bought | MIT | Customer charged for an order they say they never made; in the source the agent simply credits the money back, which our policy forbids. |
| T10 | Wrong item, allergic reaction revealed late | 3770 | product_defect / refund_update | MIT | Customer comes back to an in-progress refund with an extra detail that changes what needs to happen. |
| T11 | Small missing item, but 4 refunds in 30 days | 1044 | product_defect / return_stain | MIT | Routine-sounding refund request where the customer expects money back on the card quickly. |
| T12 | Caller is not the account holder and can't verify | 6007 | order_issue / status_quantity | MIT | Customer can't provide the email needed for verification and the agent can't confirm identity. |
| T13 | Late and still preparing: status check turns into a cancellation | 1361 | order_issue / manage_cancel | MIT | Customer wants to change an order that may already be on its way; the agent checks the status before deciding what's possible. |

The world data (`world/base.json`) and policy (`world/policy.md`) were written for this benchmark. All people, contact details and addresses in them are invented.
