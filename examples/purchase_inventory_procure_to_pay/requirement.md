# Requirement

Harbor Fresh Distribution buys packaged food and cleaning supplies from about 30 vendors and stores them in one warehouse before delivering to restaurants and hotels. Purchasing and the warehouse work on paper and spreadsheets today, and we often run out of fast-moving products or receive things we never ordered. We want purchasing and inventory in Odoo, from the purchase order to the vendor bill:

1. Purchase approval. Any buyer can create purchase orders, but an order of 50,000 or more (before tax) must be approved by the purchasing manager before it is sent to the vendor.

2. Vendor prices. Each product has one or more vendors with their own price, minimum quantity and delivery lead time. When a buyer orders a product, the cheapest vendor that can deliver that quantity should be proposed.

3. Replenishment. For our fast-moving products we keep a minimum and a maximum stock level. When stock falls below the minimum, a purchase order to the proposed vendor should be prepared automatically for the quantity needed to reach the maximum, so the buyer only has to review and confirm it.

4. Receiving. Goods are received in two steps: first unloaded at the receiving dock and counted, then moved to their shelf. If a vendor delivers only part of an order, we receive what came and keep the rest open as pending, without creating a new order.

5. Lots and expiry. Food products are tracked by lot with an expiry date recorded at receipt. When we pick for delivery, the lots that expire first must go out first.

6. Vendor bills. A vendor bill can only be paid for the quantities we actually received, not for what we ordered. If the vendor bills more than we received or at a different price, Accounts Payable must see the difference before validating the bill.

## Clarifications (2026-10-27)

- Approval threshold: the user accepted 50,000 compared with the order total including tax (Odoo has no before-tax option), which is stricter than asked.
- Vendor choice: the user accepted Odoo's native vendor-selection rule, documented and tested, including the case where it does not pick the cheapest vendor.
