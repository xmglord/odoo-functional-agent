"""Follow wizard actions returned by record methods (C5)."""
from ofa.errors import OdooError

DEFAULT_WIZARDS = {"confirm.stock.sms": "dont_send_sms", "stock.backorder.confirmation": "process"}


def is_wizard_action(result):
    return isinstance(result, dict) and result.get("type") == "ir.actions.act_window" and result.get("target") == "new"


def call_following(client, model, method, ids, *, params=None, context=None, wizards=None, max_depth=3):
    mapping = DEFAULT_WIZARDS | (wizards or {})
    result = client.call(model, method, ids=ids, context=context, **(params or {}))
    depth = 0
    while is_wizard_action(result):
        res_model = result.get("res_model")
        depth += 1
        if depth > max_depth:
            raise OdooError(0, "WIZARD_DEPTH", res_model)
        if res_model not in mapping:
            raise OdooError(0, "UNHANDLED_WIZARD", res_model)
        ctx = result.get("context") or {}
        wiz_id = result.get("res_id")
        if not wiz_id:
            # Like the web client: an empty create lets Odoo apply the default_* context keys.
            wiz_id = client.call(res_model, "create", vals_list=[{}], context=ctx)[0]
        result = client.call(res_model, mapping[res_model], ids=[wiz_id], context=ctx)
    return result
