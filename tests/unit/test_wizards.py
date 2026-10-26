from ofa import wizards
from ofa.errors import OdooError
from tests.unit.test_client import FakeCase

BACKORDER_ACTION = {"type": "ir.actions.act_window", "res_model": "stock.backorder.confirmation", "target": "new",
                    "views": [[1, "form"]], "context": {"default_show_transfers": False, "default_pick_ids": [[4, 7]]}}


class WizardsTest(FakeCase):
    def setUp(self):
        super().setUp()
        self.c = self.open()

    def test_plain_result_is_returned(self):
        self.fake.script("sale.order", "action_confirm", True)
        self.assertTrue(wizards.call_following(self.c, "sale.order", "action_confirm", [1]))

    def test_sms_wizard_with_res_id(self):
        self.fake.script("stock.picking", "button_validate",
                         {"type": "ir.actions.act_window", "res_model": "confirm.stock.sms", "target": "new", "res_id": 11,
                          "context": {"x": 1}})
        self.fake.script("confirm.stock.sms", "dont_send_sms", True)
        self.assertTrue(wizards.call_following(self.c, "stock.picking", "button_validate", [7]))
        req = self.fake.calls("confirm.stock.sms", "dont_send_sms")[0]
        self.assertEqual((req.ids, req.context), ([11], {"x": 1}))
        self.assertEqual(self.fake.calls("confirm.stock.sms", "create"), [])

    def test_backorder_action_without_res_id(self):
        self.fake.script("stock.picking", "button_validate", BACKORDER_ACTION)
        self.fake.script("stock.backorder.confirmation", "create", [31])
        self.fake.script("stock.backorder.confirmation", "process", True)
        self.assertTrue(wizards.call_following(self.c, "stock.picking", "button_validate", [7]))
        create = self.fake.calls("stock.backorder.confirmation", "create")[0]
        self.assertEqual(create.params, {"vals_list": [{}]})
        self.assertEqual(create.context, BACKORDER_ACTION["context"])
        self.assertIsNone(create.ids)
        process = self.fake.calls("stock.backorder.confirmation", "process")[0]
        self.assertEqual((process.ids, process.context), ([31], BACKORDER_ACTION["context"]))

    def test_current_target_is_not_followed(self):
        action = {"type": "ir.actions.act_window", "res_model": "sale.order", "target": "current", "res_id": 3}
        self.fake.script("sale.order", "action_view", action)
        self.assertEqual(wizards.call_following(self.c, "sale.order", "action_view", [3]), action)

    def test_unmapped_wizard(self):
        self.fake.script("sale.order", "action_x", {"type": "ir.actions.act_window", "res_model": "x.wizard", "target": "new"})
        with self.assertRaises(OdooError) as cm:
            wizards.call_following(self.c, "sale.order", "action_x", [1])
        self.assertEqual((cm.exception.name, cm.exception.message), ("UNHANDLED_WIZARD", "x.wizard"))

    def test_custom_mapping_and_depth(self):
        loop = {"type": "ir.actions.act_window", "res_model": "loop.wizard", "target": "new", "res_id": 1}
        self.fake.script("sale.order", "action_loop", loop)
        self.fake.script("loop.wizard", "go", loop)
        with self.assertRaises(OdooError) as cm:
            wizards.call_following(self.c, "sale.order", "action_loop", [1], wizards={"loop.wizard": "go"}, max_depth=3)
        self.assertEqual(cm.exception.name, "WIZARD_DEPTH")
        self.assertEqual(len(self.fake.calls("loop.wizard", "go")), 3)
