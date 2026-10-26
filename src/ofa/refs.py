"""Value references in plans and scenarios, and the `__ofa__` xmlid store (C4)."""
from ofa.errors import UsageError, ValidationError

OFA_MODULE = "__ofa__"
_REF_KEYS = ("$ref", "$var", "$search", "$set", "$add", "$create")


def _ref_key(value):
    if isinstance(value, dict) and len(value) == 1:
        (k,) = value
        if k in _REF_KEYS:
            return k
    return None


def _xmlid(client, module, name):
    rows = client.call("ir.model.data", "search_read",
                       domain=[["module", "=", module], ["name", "=", name]], fields=["model", "res_id"])
    return (rows[0]["model"], rows[0]["res_id"]) if rows else None


def _resolve_id(client, value, vars):
    resolved = resolve(client, value, vars)
    if isinstance(resolved, bool) or not isinstance(resolved, int):
        raise ValidationError("BAD_REF", f"expected a record id, got {resolved!r}")
    return resolved


def resolve(client, value, vars):
    key = _ref_key(value)
    if key == "$ref":
        ref = value[key]
        module, sep, name = str(ref).partition(".")
        if not sep or not module or not name:
            raise ValidationError("BAD_REF", f"$ref must be module.name, got {ref!r}")
        found = lookup_ofa(client, name) if module == OFA_MODULE else _xmlid(client, module, name)
        if found is None:
            raise ValidationError("UNRESOLVED_REF", f"{ref} does not exist")
        return found[1]
    if key == "$var":
        try:
            return vars[value[key]]
        except KeyError:
            raise ValidationError("UNRESOLVED_VAR", f"variable {value[key]!r} is not set") from None
    if key == "$search":
        spec = value[key]
        ids = client.call(spec["model"], "search", domain=resolve(client, spec["domain"], vars))
        if len(ids) != 1:
            raise ValidationError("SEARCH_NOT_UNIQUE", f"{spec['model']} search matched {len(ids)} records")
        return ids[0]
    if key == "$set":
        return [[6, 0, [_resolve_id(client, r, vars) for r in value[key]]]]
    if key == "$add":
        return [[4, _resolve_id(client, r, vars)] for r in value[key]]
    if key == "$create":
        return [[0, 0, resolve(client, vals, vars)] for vals in value[key]]
    if isinstance(value, dict):
        return {k: resolve(client, v, vars) for k, v in value.items()}
    if isinstance(value, list):
        return [resolve(client, v, vars) for v in value]
    return value


def _backend(client):
    backend = getattr(client, "xmlid_store", None)
    if backend is None:
        raise UsageError("client has no xmlid_store; set it from server.xmlid_store")
    if backend != "ir_model_data":
        raise UsageError(f"xmlid store {backend!r} is not implemented (spike S8 selected ir_model_data)")
    return backend


def lookup_ofa(client, key):
    _backend(client)
    return _xmlid(client, OFA_MODULE, key)


def store_ofa(client, key, model, res_id):
    _backend(client)
    rows = client.call("ir.model.data", "search_read",
                       domain=[["module", "=", OFA_MODULE], ["name", "=", key]], fields=["model", "res_id"])
    if rows:
        row = rows[0]
        if (row["model"], row["res_id"]) != (model, res_id):
            client.call("ir.model.data", "write", ids=[row["id"]], vals={"model": model, "res_id": res_id})
        return
    client.call("ir.model.data", "create", vals_list=[{"module": OFA_MODULE, "name": key, "model": model, "res_id": res_id}])


def normalize_read(value):
    """Many2one as [id, name] or id -> id; x2many id lists -> sorted. Other values pass through."""
    if isinstance(value, list):
        if len(value) == 2 and isinstance(value[0], int) and not isinstance(value[0], bool) and isinstance(value[1], str):
            return value[0]
        if all(isinstance(v, int) and not isinstance(v, bool) for v in value):
            return sorted(value)
    return value
