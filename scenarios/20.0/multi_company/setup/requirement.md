# Requirement (fixture for the multi-company scenarios)

The group runs its main company and a subsidiary, "OFA Subsidiary North", in the same database. The subsidiary has
one regional office, "OFA North Branch", which is part of the same legal entity. The subsidiary keeps some products
to itself, while the group's catalog parts are shared by every company. When the main company buys catalog parts
from the subsidiary, the subsidiary must get the matching sales order automatically instead of typing it again, and
it ships from its own warehouse. People who work only for the main company must not see the subsidiary's own
contacts, products or orders; the branch office sees the subsidiary's contacts and products but not its orders.
